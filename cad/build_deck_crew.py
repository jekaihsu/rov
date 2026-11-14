"""Dress the CC0 rigged worker (Quaternius "Animated Men") as ROV deck crew and export it as a GLB.

    python cad/build_deck_crew.py OUT.glb [--source worker_source.glb] [--textures DIR]   # needs `import bpy`

The rig, skin weights and the 12 animation clips stay exactly as in the source, so simulator/viewer/humanoid.js
keeps its bone names and IK. Changes, all skinned to the same armature:
  * proportions: head scaled to 90 % about the neck (the source head is about 1/6.4 of body height);
  * work clothes: one-piece coverall split into "Shirt" (top) and "Pants" materials so the viewer can still tint
    them, woven fabric normal map, reflective tape bands on arms and legs, rubber boots, work gloves;
  * PPE as separate skinned meshes: a foam work vest ("LifeVest", materials "Vest" + "VestTape") and a hard hat
    with ridge and brim ("HardHat", material "Helmet"). humanoid.js hides them for the pilot and tints them.
Without --source the original model is read from git history (commit 380b340), so no copy is kept in cad/.
"""
import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy  # noqa: I001  (bpy must be imported before bmesh/mathutils)
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import support_assets_lib as kit  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REV = '380b340'
SOURCE_PATH = 'simulator/viewer/models/worker.glb'
HEAD_SCALE = 0.9
FABRIC_TILE = 0.7          # model units (1 unit = 0.36 m at the default 1.75 m height)
HAND_BONES = ('Palm', 'MiddleHand', 'Fingers', 'Thumb1', 'Thumb2')


def source_glb(path):
    if path is not None:
        return Path(path)
    data = subprocess.run(['git', 'show', f'{SOURCE_REV}:{SOURCE_PATH}'], cwd=ROOT, check=True,
                          capture_output=True).stdout
    tmp = Path(tempfile.mkdtemp()) / 'worker_source.glb'
    tmp.write_bytes(data)
    return tmp


def weight_of(vert, deform, groups, names):
    """Summed skin weight of ``vert`` for the vertex groups in ``names``."""
    total = 0.0
    for index, w in vert[deform].items():
        if groups.get(index) in names:
            total += w
    return total


def side_names(bases):
    return {f'{b}.{s}' for b in bases for s in ('L', 'R')}


def material_index(mesh, material):
    for i, m in enumerate(mesh.materials):
        if m == material:
            return i
    mesh.materials.append(material)
    return len(mesh.materials) - 1


def push(verts, distance):
    """Move vertices outward along normals averaged per position, so split (flat/UV-seam) vertices that share a
    position move together and the surface stays closed."""
    buckets = {}
    for v in verts:
        key = (round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4))
        buckets.setdefault(key, []).append(v)
    for group in buckets.values():
        normal = Vector()
        for v in group:
            for f in v.link_faces:
                normal += f.normal * f.calc_area()
        if normal.length < 1e-9:
            continue
        normal.normalize()
        for v in group:
            v.co += normal * distance


def cut(bm, axis, values):
    """Bisect the mesh at planes normal to ``axis`` so tape bands get exact, straight edges."""
    normal = [0.0, 0.0, 0.0]
    normal[axis] = 1.0
    for value in values:
        co = [0.0, 0.0, 0.0]
        co[axis] = value
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=normal)


LEG_TAPE = ((0.88, 0.98), (1.62, 1.72))
ARM_TAPE = (1.72, 1.82)
VEST_TAPE = ((3.0, 3.09), (3.38, 3.47))


def in_bands(value, bands):
    return any(lo < value < hi for lo, hi in bands)


def dress_body(body, mats):
    """Proportions, boots, gloves and tape bands on the base body mesh (rest pose, model units)."""
    mesh = body.data
    groups = {vg.index: vg.name for vg in body.vertex_groups}
    bm = bmesh.new()
    bm.from_mesh(mesh)
    deform = bm.verts.layers.deform.active
    cut(bm, 2, [z for band in LEG_TAPE for z in band])
    cut(bm, 0, [ARM_TAPE[0], ARM_TAPE[1], -ARM_TAPE[0], -ARM_TAPE[1]])
    bm.normal_update()
    # head to 90 % about the neck joint
    head_verts = [(v, weight_of(v, deform, groups, {'Head'})) for v in bm.verts]
    pivot = Vector((0.0, 0.08, 4.12))
    for v, w in head_verts:
        if w > 0:
            k = 1.0 - (1.0 - HEAD_SCALE) * w
            v.co = pivot + (v.co - pivot) * k
    hands = side_names(HAND_BONES)
    idx = {key: material_index(mesh, m) for key, m in mats.items()}
    shirt = mesh.materials.find('Shirt')
    pants = mesh.materials.find('Pants')
    boot_verts = set()
    glove_verts = set()
    for f in bm.faces:
        c = f.calc_center_median()
        hand_w = sum(weight_of(v, deform, groups, hands) for v in f.verts) / len(f.verts)
        if c.z < 0.62 and f.material_index in (pants, mesh.materials.find('Skin')):
            f.material_index = idx['Boots']
            boot_verts.update(f.verts)
        elif hand_w > 0.5:
            f.material_index = idx['Gloves']
            glove_verts.update(f.verts)
        elif f.material_index == pants and in_bands(c.z, LEG_TAPE):
            f.material_index = idx['Tape']
        elif f.material_index == shirt and in_bands(abs(c.x), (ARM_TAPE,)):
            f.material_index = idx['Tape']
    bm.normal_update()
    push(boot_verts, 0.035)
    push(glove_verts, 0.012)
    sole = [v for v in boot_verts if v.co.z < 0.06]
    for v in sole:
        v.co.z = min(v.co.z, 0.0)
    bm.to_mesh(mesh)
    bm.free()


def make_vest(body, armature, mats):
    """Copy the torso faces, inflate them outward and give them thickness: a foam work vest."""
    vest = body.copy()
    vest.data = body.data.copy()
    vest.name = 'LifeVest'
    vest.data.name = 'LifeVest'
    bpy.context.scene.collection.objects.link(vest)
    mesh = vest.data
    shirt = mesh.materials.find('Shirt')
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    keep = []
    for f in bm.faces:
        c = f.calc_center_median()
        if f.material_index == shirt and 2.62 < c.z < 3.9 and abs(c.x) < 0.55 - 0.25 * max(0.0, c.z - 3.6):
            keep.append(f)
    keep = set(keep)
    drop = [f for f in bm.faces if f not in keep]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)      # one closed shell, so it thickens as one piece
    edge = list({v for e in bm.edges if e.is_boundary for v in e.verts})
    for _ in range(6):                                            # soften the jagged arm and neck openings
        bmesh.ops.smooth_vert(bm, verts=edge, factor=0.6, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()
    push(bm.verts, 0.07)
    cut(bm, 2, [z for band in VEST_TAPE for z in band])
    for f in bm.faces:
        f.material_index = 1 if in_bands(f.calc_center_median().z, VEST_TAPE) else 0
    mesh.materials.clear()
    mesh.materials.append(mats['Vest'])
    mesh.materials.append(mats['VestTape'])
    bm.to_mesh(mesh)
    bm.free()
    solid = vest.modifiers.new('Thickness', 'SOLIDIFY')
    solid.thickness = 0.11
    solid.offset = 1.0
    solid.use_rim = True
    with bpy.context.temp_override(object=vest, active_object=vest):
        bpy.ops.object.modifier_move_to_index(modifier='Thickness', index=0)
        bpy.ops.object.modifier_apply(modifier='Thickness')
    for poly in mesh.polygons:
        poly.use_smooth = True
    return vest


def make_hard_hat(armature, head_center, radius, mats):
    """Hard hat shell with a centre ridge and a short peaked brim, rigidly skinned to the Head bone.

    Built at a nominal 0.41 shell radius and scaled to ``radius`` (model units).
    """
    part = kit.Part('HardHat', mats['Helmet'], uv_tile=0.5, smooth_angle=50)
    shell = kit.lathe([(0.41, 0.0), (0.41, 0.05), (0.39, 0.16), (0.33, 0.27), (0.22, 0.35), (0.1, 0.39),
                       (0.0, 0.4)], seg=32, caps=False)
    part.add_bmesh(shell)
    brim = kit.lathe([(0.4, 0.0), (0.41, -0.006), (0.415, 0.003), (0.402, 0.02)], seg=40, caps=False)
    for v in brim.verts:
        if v.co.y < 0:
            v.co.y *= 1.0 + 0.5 * (-v.co.y / 0.415) ** 4      # cap-style peak at the front only
    part.add_bmesh(brim)
    ridge = kit.sweep([(0.0, -0.36 + 0.72 * k / 10, 0.0) for k in range(11)], radius=0.03, seg=8)
    for v in ridge.verts:
        y = v.co.y
        v.co.z += math.sqrt(max(0.0, 0.4 ** 2 - y * y)) * 0.98
    part.add_bmesh(ridge)
    band = kit.lathe([(0.395, 0.06), (0.395, 0.1)], seg=32, caps=False)
    hat = part.obj(bpy.context.scene.collection)
    band_part = kit.Part('HardHatBand', mats['HatBand'])
    band_part.add_bmesh(band)
    band_obj = band_part.obj(bpy.context.scene.collection)
    for ob in (hat, band_obj):
        ob.location = head_center
        ob.scale = (radius / 0.41, radius / 0.41, radius / 0.41)
    with bpy.context.temp_override(selected_editable_objects=[hat, band_obj], active_object=hat,
                                   selected_objects=[hat, band_obj]):
        bpy.ops.object.join()
    with bpy.context.temp_override(selected_editable_objects=[hat], object=hat, active_object=hat):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    group = hat.vertex_groups.new(name='Head')
    group.add(list(range(len(hat.data.vertices))), 1.0, 'REPLACE')
    hat.parent = armature
    mod = hat.modifiers.new('Armature', 'ARMATURE')
    mod.object = armature
    return hat


def box_project(ob, tile):
    """Replace the UVs with a world-scale box projection (fabric weave scale)."""
    mesh = ob.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        kit.box_uv_face(f, layer, tile)
    bm.to_mesh(mesh)
    bm.free()


def head_centre(body):
    groups = {vg.index: vg.name for vg in body.vertex_groups}
    pts = []
    for v in body.data.vertices:
        for g in v.groups:
            if groups[g.group] == 'Head' and g.weight > 0.9:
                pts.append(v.co.copy())
    lo = min(p.z for p in pts)
    hi = max(p.z for p in pts)
    cy = sum(p.y for p in pts) / len(pts)
    crown = [p for p in pts if p.z > hi - 0.35]
    radius = max(math.hypot(p.x, p.y - cy) for p in crown)
    return Vector((0.0, cy, lo + (hi - lo) * 0.68)), hi, radius


def build_materials(texture_dir):
    fabric = kit.fabric_set(texture_dir, 'coverall', size=512, seed=71, weave=72)
    rubber = kit.worn_paint_set(texture_dir, 'boot', size=256, seed=72, chips=0.9, streaks=0.1, base_rough=0.6)
    plastic = kit.worn_paint_set(texture_dir, 'helmet', size=256, seed=73, chips=0.8, streaks=0.15, base_rough=0.3)
    return {
        'Boots': kit.make_material('Boots', (0.05, 0.05, 0.055), textures=rubber),
        'Gloves': kit.make_material('Gloves', (0.55, 0.42, 0.2), rough=0.85, textures=fabric),
        'Tape': kit.make_material('Tape', (0.8, 0.82, 0.84), rough=0.35, metal=0.2),
        'Vest': kit.make_material('Vest', (1.0, 0.42, 0.07), textures=fabric),
        'VestTape': kit.make_material('VestTape', (0.84, 0.85, 0.86), rough=0.32, metal=0.25),
        'Helmet': kit.make_material('Helmet', (0.95, 0.95, 0.93), textures=plastic),
        'HatBand': kit.make_material('HatBand', (0.08, 0.08, 0.09), rough=0.7),
        'fabric': fabric,
    }


def build(out_glb, source, texture_dir):
    kit.reset_scene()
    texture_dir = Path(texture_dir)
    texture_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.import_scene.gltf(filepath=str(source_glb(source)))
    for ob in list(bpy.data.objects):
        if ob.type == 'MESH' and ob.name.startswith('Icosphere'):
            bpy.data.objects.remove(ob)
    body = bpy.data.objects['BaseHuman']
    armature = bpy.data.objects['HumanArmature']
    mats = build_materials(texture_dir)
    fabric = mats.pop('fabric')
    for name in ('Shirt', 'Pants'):
        bpy.data.materials[name].name = name + '_source'
        new = kit.make_material(name, (1.0, 1.0, 1.0), textures=fabric)
        body.data.materials[body.data.materials.find(name + '_source')] = new
    dress_body(body, mats)
    box_project(body, FABRIC_TILE)
    centre, top, head_radius = head_centre(body)
    vest = make_vest(body, armature, mats)
    box_project(vest, FABRIC_TILE)
    hat_base = Vector((centre.x, centre.y - 0.02, top - 0.33))
    hat = make_hard_hat(armature, hat_base, head_radius * 1.02 + 0.03, mats)
    for ob in (body, vest, hat):
        ob.data.calc_loop_triangles()
    tris = kit.triangle_count([body, vest, hat])
    path = Path(out_glb)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_yup=True, export_apply=False,
                              export_animations=True, export_skins=True, export_cameras=False,
                              export_lights=False, export_image_format='AUTO')
    kit.patch_material_factors(path, list(bpy.data.materials))
    print(f'deck crew: {tris} triangles -> {path}')
    return tris


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('out', type=Path)
    parser.add_argument('--source', type=Path, default=None)
    parser.add_argument('--textures', type=Path, default=Path('build/crew_textures'))
    args = parser.parse_args()
    build(args.out, args.source, args.textures)


if __name__ == '__main__':
    main()
