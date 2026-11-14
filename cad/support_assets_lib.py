"""Shared helpers for the deck support asset generators (work boat, deck crew).

Runs inside Blender's Python (`pip install bpy` or `blender --background --python`). Provides:
  * tileable spectral noise and normal-from-height for procedural PBR textures (numpy + Pillow),
  * a small mesh kit (boxes, beams, lathes, swept tubes, tori, extrusions) that builds bmesh geometry in metres,
  * material creation with image textures, and joining parts per material,
  * post-export patching of GLB material factors (the Blender exporter writes factor 1 when a texture is used).
All geometry and textures are original, procedurally generated work.
"""
import json
import math
import struct
from pathlib import Path

import bpy  # noqa: I001  (bpy must be imported before bmesh/mathutils)
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image

# ───────────────────────────── textures ─────────────────────────────


def spectral_noise(shape, beta=2.0, seed=0, fmin=1.0, fmax=None, fy_max=None):
    """Tileable fractal noise in [-1, 1]: white noise filtered with a 1/f^beta amplitude spectrum.

    ``fy_max`` limits vertical frequencies, which turns the noise into vertical streaks.
    """
    rng = np.random.default_rng(seed)
    h, w = shape
    white = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.fftfreq(w)[None, :] * w
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta / 2.0)
    amp[f < fmin] = 0.0
    if fmax is not None:
        amp[f > fmax] = 0.0
    if fy_max is not None:
        amp[np.abs(fy) > fy_max + np.zeros_like(fx)] = 0.0
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * amp))
    out -= out.mean()
    peak = np.abs(out).max()
    return out / peak if peak > 0 else out


def smoothstep(e0, e1, x):
    """Hermite step between e0 and e1 (works for arrays)."""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def normal_from_height(height, strength):
    """Tangent-space normal map (OpenGL / glTF convention, rows top-down) from a height field."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, 1, axis=0) - np.roll(height, -1, axis=0)) * 0.5
    n = np.dstack([-dx * strength, -dy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def save_image(path, array):
    """Save a float array (H, W, 3) in [0, 1] as an 8-bit PNG."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (np.clip(array, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(data).save(path)
    return path


def save_rgba(path, array):
    """Save a float array (H, W, 4) in [0, 1] as an 8-bit RGBA PNG."""
    path = Path(path)
    data = (np.clip(array, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(data, 'RGBA').save(path)
    return path


def orm(rough, metal, occlusion=None):
    """Pack occlusion (R), roughness (G), metalness (B) into one image as glTF expects."""
    occ = np.ones_like(rough) if occlusion is None else occlusion
    return np.dstack([occ, rough, metal])


def worn_paint_set(out, name, size=1024, seed=1, chips=0.55, streaks=0.35, base_rough=0.45):
    """Near-white worn paint (tinted per material through baseColorFactor): grime, chips, streaks."""
    shape = (size, size)
    grime = spectral_noise(shape, 2.2, seed, fmin=2)
    fine = spectral_noise(shape, 1.0, seed + 1, fmin=24)
    chip_field = spectral_noise(shape, 2.6, seed + 2, fmin=6)
    chip = smoothstep(chips, chips + 0.04, chip_field)
    streak = spectral_noise(shape, 1.4, seed + 3, fmin=3, fy_max=2)
    streak = smoothstep(0.2, 0.9, streak) * streaks
    tone = 0.93 + 0.05 * grime - 0.03 * fine - streak * 0.18
    tone = tone * (1.0 - chip * 0.55)
    base = np.dstack([tone, tone * 0.995, tone * 0.985])
    rough = np.clip(base_rough + 0.12 * grime + 0.05 * fine + chip * 0.3 + streak * 0.2, 0.05, 1.0)
    height = -chip * 0.6 + fine * 0.05
    normal = normal_from_height(height, 2.5)
    return {
        'base': save_image(Path(out) / f'{name}_base.png', base),
        'normal': save_image(Path(out) / f'{name}_normal.png', normal),
        'orm': save_image(Path(out) / f'{name}_orm.png', orm(rough, np.zeros_like(rough))),
    }


def brushed_metal_set(out, name, size=1024, seed=5, rough=0.32, metalness=0.35):
    """Brushed aluminium / stainless: directional streaks in roughness and a faint normal.

    Metalness stays partial because the viewer scenes have no environment map; fully metallic surfaces would
    render almost black there.
    """
    shape = (size, size)
    lines = spectral_noise(shape, 1.2, seed, fmin=8, fy_max=1).T
    smear = spectral_noise(shape, 2.0, seed + 1, fmin=2)
    tone = 0.86 + 0.04 * lines + 0.04 * smear
    base = np.dstack([tone, tone, tone * 1.01])
    r = np.clip(rough + 0.06 * lines + 0.12 * smear, 0.08, 0.9)
    normal = normal_from_height(lines * 0.2, 0.6)
    return {
        'base': save_image(Path(out) / f'{name}_base.png', base),
        'normal': save_image(Path(out) / f'{name}_normal.png', normal),
        'orm': save_image(Path(out) / f'{name}_orm.png', orm(r, np.full_like(r, metalness))),
    }


def fabric_set(out, name, size=512, seed=9, weave=96):
    """Woven synthetic fabric (canopy, coveralls): tileable weave normal plus soft dirt."""
    y, x = np.mgrid[0:size, 0:size] / size
    warp = np.sin(2 * np.pi * weave * x) * (np.sin(2 * np.pi * weave * y) > 0)
    weft = np.sin(2 * np.pi * weave * y) * (np.sin(2 * np.pi * weave * x) <= 0)
    height = warp * 0.5 + weft * 0.5
    dirt = spectral_noise((size, size), 2.2, seed, fmin=2)
    tone = 0.9 + 0.06 * dirt - 0.04 * height
    base = np.dstack([tone, tone, tone])
    rough = np.clip(0.82 + 0.08 * dirt, 0, 1)
    return {
        'base': save_image(Path(out) / f'{name}_base.png', base),
        'normal': save_image(Path(out) / f'{name}_normal.png', normal_from_height(height, 0.9)),
        'orm': save_image(Path(out) / f'{name}_orm.png', orm(rough, np.zeros_like(rough))),
    }


# ───────────────────────────── materials ─────────────────────────────


def _image(path, non_color):
    img = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def make_material(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, textures=None, emission=None,
                  emission_strength=1.0, alpha_clip=False, emissive_map=False, double_sided=False):
    """Principled material. ``textures``: dict with optional base/normal/orm image paths.

    ``emissive_map`` drives the emission colour from the base colour image (screens, lamps).
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = not double_sided
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    textures = textures or {}
    if 'base' in textures:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = _image(textures['base'], False)
        links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if emissive_map:
            links.new(tex.outputs['Color'], bsdf.inputs['Emission Color'])
        if alpha_clip:
            links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    if 'orm' in textures:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = _image(textures['orm'], True)
        sep = nodes.new('ShaderNodeSeparateColor')
        links.new(tex.outputs['Color'], sep.inputs['Color'])
        links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
        links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
    if 'normal' in textures:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = _image(textures['normal'], True)
        nmap = nodes.new('ShaderNodeNormalMap')
        links.new(tex.outputs['Color'], nmap.inputs['Color'])
        links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    if emission is not None and not emissive_map:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1.0)
    if emission is not None or emissive_map:
        bsdf.inputs['Emission Strength'].default_value = emission_strength
    mat['factor'] = list(color)
    mat['tinted'] = bool(textures.get('base'))
    mat['alpha_clip'] = alpha_clip
    return mat


# ───────────────────────────── mesh kit ─────────────────────────────


class Part:
    """Accumulates bmesh geometry for one material; ``obj()`` turns it into a Blender object."""

    def __init__(self, name, material, uv_tile=1.0, smooth_angle=35.0):
        self.name = name
        self.material = material
        self.uv_tile = uv_tile
        self.smooth_angle = smooth_angle
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')

    def add_bmesh(self, other, matrix=None, uvs=None):
        """Append another bmesh (optionally transformed). ``uvs``: per-loop UV list in face order."""
        if matrix is not None:
            other.transform(matrix)
        mapping = {}
        for v in other.verts:
            mapping[v] = self.bm.verts.new(v.co)
        other_uv = other.loops.layers.uv.active
        for f in other.faces:
            try:
                nf = self.bm.faces.new([mapping[v] for v in f.verts])
            except ValueError:
                continue
            nf.smooth = f.smooth
            if other_uv is not None:
                for la, lb in zip(f.loops, nf.loops):
                    lb[self.uv].uv = la[other_uv].uv
                nf.tag = True
        other.free()

    def obj(self, collection, parent=None):
        """Create the object: box-projected UVs for faces without explicit UVs, smooth by angle."""
        bm = self.bm
        for f in bm.faces:
            if f.tag:
                continue
            box_uv_face(f, self.uv, self.uv_tile)
        mesh = bpy.data.meshes.new(self.name)
        bm.normal_update()
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(self.material)
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.set_sharp_from_angle(angle=math.radians(self.smooth_angle))
        ob = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(ob)
        if parent is not None:
            ob.parent = parent
        return ob


def box_uv_face(face, layer, tile):
    """World-scale box projection: UV in metres / tile along the face's dominant axes."""
    n = face.normal
    ax = max(range(3), key=lambda i: abs(n[i]))
    a, b = [(1, 2), (0, 2), (0, 1)][ax]
    for loop in face.loops:
        co = loop.vert.co
        loop[layer].uv = (co[a] / tile, co[b] / tile)


def _new_bm():
    return bmesh.new()


def box(size, center=(0, 0, 0), bevel=0.0, segments=2, rot=None):
    """Axis box (size x, y, z) with optional bevelled edges; returns a bmesh."""
    bm = _new_bm()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segments, affect='EDGES', profile=0.5)
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ rot
    bm.transform(m)
    return bm


def _frame(direction):
    """Rotation matrix whose local Z points along ``direction``."""
    d = Vector(direction).normalized()
    return d.to_track_quat('Z', 'Y').to_matrix().to_4x4()


def beam(p0, p1, w, h, bevel=0.0):
    """Rectangular section beam from p0 to p1 (w across, h in the 'up' plane)."""
    p0 = Vector(p0)
    p1 = Vector(p1)
    length = (p1 - p0).length
    bm = box((w, h, length), bevel=bevel)
    bm.transform(Matrix.Translation((p0 + p1) / 2) @ _frame(p1 - p0))
    return bm


def cylinder(p0, p1, r, seg=16, r1=None, caps=True):
    """Cylinder / cone frustum between two points."""
    p0 = Vector(p0)
    p1 = Vector(p1)
    r1 = r if r1 is None else r1
    profile = [(r, 0.0), (r1, 1.0)]
    bm = lathe(profile, seg=seg, caps=caps, scale_z=(p1 - p0).length)
    bm.transform(Matrix.Translation(p0) @ _frame(p1 - p0))
    return bm


def lathe(profile, seg=24, caps=True, scale_z=1.0, center=(0, 0, 0), axis=(0, 0, 1)):
    """Surface of revolution around local Z from (radius, z) pairs; optional end caps."""
    bm = _new_bm()
    rings = []
    for r, z in profile:
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z * scale_z)))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    if caps:
        if profile[0][0] > 1e-5:
            bm.faces.new(list(reversed(rings[0])))
        if profile[-1][0] > 1e-5:
            bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.transform(Matrix.Translation(Vector(center)) @ _frame(axis))
    return bm


def sweep(points, radius=0.02, seg=10, closed=False, profile=None, caps=True, up_hint=(0, 0, 1)):
    """Tube along a polyline. ``profile``: optional list of (x, y) section points (default circle)."""
    pts = [Vector(p) for p in points]
    if profile is None:
        profile = [(radius * math.cos(2 * math.pi * i / seg), radius * math.sin(2 * math.pi * i / seg))
                   for i in range(seg)]
    n = len(pts)
    bm = _new_bm()
    rings = []
    normal = None
    for i, p in enumerate(pts):
        if closed:
            t = (pts[(i + 1) % n] - pts[i - 1])
        elif i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        t.normalize()
        if normal is None:
            normal = Vector(up_hint).cross(t)
            if normal.length < 1e-4:
                normal = Vector((1, 0, 0)).cross(t)
        normal = (normal - t * normal.dot(t)).normalized()
        binormal = t.cross(normal)
        ring = [bm.verts.new(p + normal * x + binormal * y) for x, y in profile]
        rings.append(ring)
    m = len(profile)
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for ra, rb in pairs:
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return bm


def torus(major, minor, seg=32, ring_seg=12, center=(0, 0, 0), axis=(0, 0, 1), arc=2 * math.pi):
    """Torus (or partial arc) around ``axis``."""
    pts = [(major * math.cos(arc * i / seg), major * math.sin(arc * i / seg), 0.0) for i in range(seg + 1)]
    closed = arc >= 2 * math.pi - 1e-6
    if closed:
        pts = pts[:-1]
    bm = sweep(pts, minor, ring_seg, closed=closed)
    bm.transform(Matrix.Translation(Vector(center)) @ _frame(axis))
    return bm


def extrude(outline, depth, center=(0, 0, 0), rot=None):
    """Prism from a 2D outline [(x, y)] in local XY, extruded along local Z, centred on depth."""
    bm = _new_bm()
    bottom = [bm.verts.new((x, y, -depth / 2)) for x, y in outline]
    top = [bm.verts.new((x, y, depth / 2)) for x, y in outline]
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    k = len(outline)
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ rot
    bm.transform(m)
    return bm


def plate_yz(outline, thickness, x=0.0):
    """Prism whose outline [(y, z)] lies in the YZ plane, thickness along X centred on ``x``."""
    bm = _new_bm()
    left = [bm.verts.new((x - thickness / 2, y, z)) for y, z in outline]
    right = [bm.verts.new((x + thickness / 2, y, z)) for y, z in outline]
    bm.faces.new(left)
    bm.faces.new(list(reversed(right)))
    k = len(outline)
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((left[j], left[i], right[i], right[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def grid_surface(points, uvs=None, flip=False):
    """Quad surface from a 2D list of points [row][col]; optional matching UVs."""
    bm = _new_bm()
    layer = bm.loops.layers.uv.new('UVMap') if uvs is not None else None
    verts = [[bm.verts.new(p) for p in row] for row in points]
    for i in range(len(points) - 1):
        for j in range(len(points[0]) - 1):
            quad = [(i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)]
            if flip:
                quad.reverse()
            try:
                f = bm.faces.new([verts[a][b] for a, b in quad])
            except ValueError:
                continue
            f.smooth = True
            if uvs is not None:
                for loop, (a, b) in zip(f.loops, quad):
                    loop[layer].uv = uvs[a][b]
    return bm


def rot_x(angle):
    return Matrix.Rotation(angle, 4, 'X')


def rot_y(angle):
    return Matrix.Rotation(angle, 4, 'Y')


def rot_z(angle):
    return Matrix.Rotation(angle, 4, 'Z')


# ───────────────────────────── scene + export ─────────────────────────────


def reset_scene():
    """Empty factory scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene.collection


def triangle_count(objects):
    total = 0
    for ob in objects:
        if ob.type != 'MESH':
            continue
        ob.data.calc_loop_triangles()
        total += len(ob.data.loop_triangles)
    return total


def export_glb(path, extras=True):
    """Export the whole scene as GLB (Y up, modifiers applied, custom properties as extras)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_yup=True, export_apply=True,
                              export_extras=extras, export_cameras=False, export_lights=False,
                              export_animations=False, export_image_format='AUTO')
    return path


def read_glb(path):
    data = Path(path).read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + length])
    rest = data[20 + length:]
    return doc, rest


def write_glb(path, doc, rest):
    raw = json.dumps(doc, separators=(',', ':')).encode()
    raw += b' ' * ((4 - len(raw) % 4) % 4)
    total = 12 + 8 + len(raw) + len(rest)
    head = struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(raw), 0x4E4F534A)
    Path(path).write_bytes(head + raw + rest)


def patch_material_factors(path, materials):
    """Write baseColorFactor for textured materials (Blender exports 1.0) and alpha masks."""
    doc, rest = read_glb(path)
    by_name = {m.name: m for m in materials}
    for entry in doc.get('materials', []):
        mat = by_name.get(entry.get('name'))
        if mat is None:
            continue
        pbr = entry.setdefault('pbrMetallicRoughness', {})
        if mat.get('tinted'):
            pbr['baseColorFactor'] = [*mat['factor'], 1.0]
        if mat.get('alpha_clip'):
            entry['alphaMode'] = 'MASK'
            entry['alphaCutoff'] = 0.5
    write_glb(path, doc, rest)
