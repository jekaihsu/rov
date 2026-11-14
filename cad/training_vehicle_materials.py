"""Apply deterministic 1K PBR surfaces to the existing training sources, without rebuilding geometry.

Run inside Blender 4.5.9 (also callable through Blender MCP):
    import runpy
    runpy.run_path('/path/to/rov/cad/training_vehicle_materials.py', run_name='__main__')
The source geometry, modifiers, transforms, hierarchy and object extras are checked before saving.
Textures are original procedural work; no downloaded textures, markings, or manufacturer artwork.
"""
from pathlib import Path
import hashlib
import json

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.runtime' / 'a3'
SIZE = 1024


def geometry_signature():
    """Exclude only surface data (material slots, UVs, and shading attributes)."""
    records = []
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        geometry = []
        if obj.type == 'MESH':
            geometry = ([tuple(v.co) for v in obj.data.vertices],
                        [tuple(p.vertices) for p in obj.data.polygons])
        elif obj.type == 'CURVE':
            geometry = [(s.type, [tuple(p.co) for p in s.points],
                         [(tuple(p.co), tuple(p.handle_left), tuple(p.handle_right))
                          for p in s.bezier_points]) for s in obj.data.splines]
        records.append((obj.name, obj.type, obj.parent.name if obj.parent else None,
                        [list(row) for row in obj.matrix_basis],
                        [list(row) for row in obj.matrix_parent_inverse],
                        obj.id_properties_ensure().to_dict(), geometry,
                        [(mod.name, mod.type) for mod in obj.modifiers]))
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def smooth(field, passes):
    for _ in range(passes):
        field = (field * 4 + np.roll(field, 1, 0) + np.roll(field, -1, 0)
                 + np.roll(field, 1, 1) + np.roll(field, -1, 1)) / 8
    return field


def image_from_array(name, rgb, color_space, folder, jpeg=False):
    image = bpy.data.images.new(name, width=SIZE, height=SIZE, alpha=False)
    image.colorspace_settings.name = color_space
    pixels = np.ones((SIZE, SIZE, 4), dtype=np.float32)
    pixels[:, :, :3] = np.clip(rgb, 0, 1)
    image.pixels.foreach_set(pixels.ravel())
    image.file_format = 'JPEG' if jpeg else 'PNG'
    image.filepath_raw = str(folder / (name + ('.jpg' if jpeg else '.png')))
    image.save()
    image.pack()
    return image


def make_surfaces():
    """Subtle pores, mould grain, directional machining and irregular rubbed edges."""
    folder = WORK / 'textures'
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(32019)
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32) / (SIZE - 1)
    edge_distance = np.minimum.reduce([x, y, 1 - x, 1 - y])
    textures = {}
    for family in ('polymer', 'foam', 'metal'):
        grain = smooth(rng.random((SIZE, SIZE)).astype(np.float32), 2)
        broad = smooth(rng.random((64, 64)).astype(np.float32), 5)
        broad = np.repeat(np.repeat(broad, 16, axis=0), 16, axis=1)
        wear = np.clip((.018 - edge_distance) / .018, 0, 1)
        wear *= np.clip((grain - .36) * 5, 0, 1)
        scratches = np.zeros_like(grain)
        for _ in range(90):
            row = rng.integers(4, SIZE - 4)
            col = rng.integers(4, SIZE - 100)
            length = rng.integers(6, 95)
            scratches[row:row + 1, col:col + length] = rng.uniform(.15, .55)
        scratches = smooth(scratches, 1)
        if family == 'foam':
            pores = smooth((rng.random((SIZE, SIZE)) > .97).astype(np.float32), 3)
            height = grain * .15 - pores * 1.6
            tone = .89 + (grain - .5) * .20 - pores * .28 + wear * .10
            roughness = .73 + (grain - .5) * .30 + pores * .35 - wear * .12
            strength = .85
        elif family == 'metal':
            brushing = smooth(rng.random((SIZE, SIZE)).astype(np.float32), 1)
            for _ in range(12):
                brushing = (brushing + np.roll(brushing, 2, 1) + np.roll(brushing, -2, 1)) / 3
            height = (brushing - .5) * .25 - scratches * .3
            tone = .88 + (brushing - .5) * .32 + scratches * .10 + wear * .10
            roughness = .37 + (brushing - .5) * .7 + scratches * .18 - wear * .12
            strength = 2.0
        else:
            height = (grain - .5) * .12 - scratches * .20
            tone = .88 + (grain - .5) * .12 + scratches * .13 + wear * .10
            roughness = .56 + (grain - .5) * .28 + scratches * .18 - wear * .10
            strength = 1.8
        tone += (broad - .5) * .24
        dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * strength
        dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * strength
        normal = np.stack([-dx, -dy, np.ones_like(dx)], axis=2)
        normal /= np.linalg.norm(normal, axis=2, keepdims=True)
        normal = normal * .5 + .5
        # Quantize map values slightly to keep lossless PNGs comfortably within the GLB budget.
        normal = np.round(normal * 31) / 31
        roughness = np.round(np.clip(roughness, 0, 1) * 15) / 15
        textures[family] = (
            image_from_array('surface_' + family + '_color', np.repeat(tone[:, :, None], 3, 2),
                             'sRGB', folder, jpeg=True),
            image_from_array('surface_' + family + '_roughness', np.repeat(roughness[:, :, None], 3, 2),
                             'Non-Color', folder),
            image_from_array('surface_' + family + '_normal', normal, 'Non-Color', folder),
        )
    return textures


def surface_material(name, color, metal, family, textures):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Metallic'].default_value = metal
    # Bake the color factor into a small family-specific image so glTF and Blender match exactly.
    source, roughness, normal = textures[family]
    pixels = np.array(source.pixels[:], dtype=np.float32).reshape(SIZE, SIZE, 4)
    # Blender generated image buffers and material factors are both scene-linear.
    factor = np.array(color)
    image = image_from_array(name.replace(' ', '_') + '_color', pixels[:, :, :3] * factor,
                             'sRGB', WORK / 'textures', jpeg=True)
    for label, source_image, input_name in [('Color', image, 'Base Color'),
                                           ('Roughness', roughness, 'Roughness'),
                                           ('Normal', normal, None)]:
        tex = nodes.new('ShaderNodeTexImage')
        tex.label = label
        tex.image = source_image
        if input_name:
            links.new(tex.outputs['Color'], shader.inputs[input_name])
        else:
            normal_node = nodes.new('ShaderNodeNormalMap')
            normal_node.inputs['Strength'].default_value = .55 if family == 'foam' else .35
            links.new(tex.outputs['Color'], normal_node.inputs['Color'])
            links.new(normal_node.outputs['Normal'], shader.inputs['Normal'])
    return mat


def classify(obj, original):
    name = obj.name.lower()
    mat = original.name.lower()
    if any(word in mat for word in ('glass', 'optical', 'emitters', 'diffuser')):
        return None
    if any(word in name for word in ('pressure housing', 'junction housing', 'pressure tube',
                                      'battery housing', 'hydraulic actuator', 'hydraulic barrel',
                                      'manifold enclosure', 'power unit', 'wrist valve')):
        return 'Anodized enclosure', (.055, .065, .075), .82, 'metal'
    if any(word in name for word in ('channel', 'outrigger', 'cross member', 'aluminium bezel')):
        return 'Satin aluminium', (.42, .46, .49), .9, 'metal'
    if any(word in mat for word in ('stainless', 'machined')):
        return 'Machined steel', (.43, .48, .51), .95, 'metal'
    if 'buoyancy' in mat and 'neck' not in name:
        return 'Blue closed-cell foam' if 'blue' in mat else 'Yellow foam skin', (
            (.025, .22, .65) if 'blue' in mat else (.68, .48, .0005)), 0, 'foam'
    if any(word in name for word in ('cable', 'hose', 'harness', 'strain', 'spring', 'feedthrough')):
        color = tuple(original.diffuse_color[:3])
        return 'Cable jacket ' + ('orange' if max(color) > .2 else 'black'), color, 0, 'polymer'
    shader = original.node_tree.nodes.get('Principled BSDF')
    color = tuple(shader.inputs['Base Color'].default_value[:3])
    return 'Worn ' + original.name, color, 0, 'polymer'


def planar_uv(obj):
    """Add surface coordinates only; do not change meshes or evaluate/apply modifiers."""
    if obj.type != 'MESH':
        return
    mesh = obj.data
    uv = mesh.uv_layers.active or mesh.uv_layers.new(name='SurfaceUV')
    coords = np.array([v.co[:] for v in mesh.vertices])
    lower = coords.min(axis=0)
    extent = np.maximum(coords.max(axis=0) - lower, 1e-8)
    for polygon in mesh.polygons:
        axis = max(range(3), key=lambda i: abs(polygon.normal[i]))
        axes = [i for i in range(3) if i != axis]
        for loop_index in polygon.loop_indices:
            point = coords[mesh.loops[loop_index].vertex_index]
            uv.data[loop_index].uv = tuple((point[i] - lower[i]) / extent[i] for i in axes)


def apply(model):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'cad' / (model + '.blend')))
    if any(mat.name.startswith('Worn ') for mat in bpy.data.materials):
        raise ValueError('Restore the pristine source .blend before generating this material pass again')
    bpy.context.preferences.filepaths.save_version = 0
    before = geometry_signature()
    textures = make_surfaces()
    materials = {}
    for obj in bpy.context.scene.objects:
        if not hasattr(obj.data, 'materials'):
            continue
        touched = False
        for index, original in enumerate(obj.data.materials):
            spec = classify(obj, original)
            if not spec:
                continue
            name, color, metal, family = spec
            if name not in materials:
                materials[name] = surface_material(name, color, metal, family, textures)
            obj.data.materials[index] = materials[name]
            touched = True
        if touched:
            planar_uv(obj)
    assert before == geometry_signature(), 'Geometry or object contract changed'
    # Remove unused original materials and generated source images, retaining every object/datablock used by geometry.
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)
    for image in list(bpy.data.images):
        if image.users == 0:
            bpy.data.images.remove(image)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'cad' / (model + '.blend')), compress=True)
    bpy.ops.export_scene.gltf(
        filepath=str(WORK / (model + '-materials.glb')), export_format='GLB',
        export_extras=True, export_apply=True, export_yup=True,
        export_cameras=False, export_lights=False, export_image_format='AUTO',
    )
    print(json.dumps({'model': model, 'geometry_signature': before, 'materials': list(materials),
                      'objects': len(bpy.context.scene.objects)}))


if __name__ == '__main__':
    WORK.mkdir(parents=True, exist_ok=True)
    for model_id in ('falcon', 'bluerov2_heavy'):
        apply(model_id)
