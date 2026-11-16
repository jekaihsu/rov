"""Original N1 fish: deterministic geometry, pigment/ORM atlases, GLBs and studio evidence.

Blender 4.x: blender -b -P cad/build_fish_models.py
No downloads, add-ons, photographs or non-Blender Python dependencies.
The small glTF writer preserves +Z forward and both UV sets without exporter remapping.
"""
import json
import math
import struct
import zlib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'simulator/viewer/models/fish'
DOC = ROOT / 'docs/design/fish-models'
SPECS = {
    'salmon': (.60, .115, .065),
    'saithe': (.45, .105, .055),
    'fusilier': (.25, .125, .045),
    'damselfish': (.09, .215, .070),
    'butterflyfish': (.13, .285, .045),
    'surgeonfish': (.20, .225, .050),
}


def png(rgb):
    """Lossless RGB PNG, top row first."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + row.tobytes() for row in rgb.astype(np.uint8))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', 512, 256, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def textures(name):
    y, x = np.mgrid[0:256, 0:512]
    u = x / 511
    v = 1 - y / 255
    height = np.cos(v / .8 * 2 * np.pi)
    back = np.clip((height - .12) / .8, 0, 1)[..., None]
    belly = np.clip((-height - .2) / .8, 0, 1)[..., None]
    palettes = {
        'salmon': ([173, 187, 192], [30, 49, 63], [217, 219, 211]),
        'saithe': ([139, 155, 150], [42, 54, 36], [205, 210, 197]),
        'fusilier': ([69, 143, 193], [20, 64, 136], [183, 207, 212]),
        'damselfish': ([13, 94, 218], [16, 46, 153], [238, 192, 24]),
        'butterflyfish': ([237, 197, 37], [199, 156, 20], [245, 218, 88]),
        'surgeonfish': ([47, 66, 94], [29, 38, 60], [84, 95, 112]),
    }
    side, dorsal, ventral = map(np.array, palettes[name])
    color = side * (1 - back) + dorsal * back
    color = color * (1 - belly) + ventral * belly
    # Fine staggered scale margins: pigment variation only, no painted lighting.
    sx = (u * 87 + (np.floor(v * 50) % 2) * .5) % 1
    sy = (v * 50) % 1
    scale = np.exp(-((sx - .5) ** 2 + (sy - .52) ** 2) * 9)
    color = color + (scale[..., None] - .5) * 7
    if name == 'salmon':
        rng = np.random.default_rng(71)
        for a, b, r in zip(rng.uniform(.12, .79, 74), rng.uniform(0, .8, 74), rng.uniform(.002, .006, 74)):
            spot = ((u - a) ** 2 + ((v - b) * .55) ** 2 < r ** 2) & (height > -.05)
            color[spot] = [28, 38, 43]
    if name == 'saithe':
        color[np.abs(height - (.08 + .16 * np.exp(-((u - .25) / .15) ** 2))) < .032] = [215, 220, 193]
    if name == 'fusilier':
        color[(height > .32) & (height < .53)] = [242, 199, 31]
    if name == 'butterflyfish':
        color[u < .23] = [230, 232, 215]
        color[(u > .115) & (u < .165)] = [23, 29, 32]
        color[((u - .68) / .095) ** 2 + ((height - .25) / .5) ** 2 < 1] = [37, 34, 29]
        color += (np.sin((u * 44 + height * 3) * np.pi)[..., None] ** 14) * -13
    if name == 'surgeonfish':
        color[(u > .73) & (u < .85) & (abs(height) < .7)] = [233, 185, 32]
    # Opercular edge and small terminal mouth, symmetrical on both sides.
    gill = abs(u - (.235 + .035 * height ** 2)) < .003
    color[gill & (abs(height) < .85)] *= .55
    color[(u < .08) & (abs(height + .15) < .045)] *= .35
    fin = v > .8
    fin_color = [212, 173, 34] if name in ('fusilier', 'damselfish', 'butterflyfish') else dorsal * 1.45
    color[fin] = np.array(fin_color) + (np.sin(u[fin] * 240) * 5)[:, None]
    if name in ('fusilier', 'damselfish'):
        color[(v > .8) & (v < .87)] = dorsal
    eye = v > .95
    color[eye] = [157, 151, 100]
    color[eye & (u < .5)] = [5, 9, 12]
    orm = np.zeros((256, 512, 3))
    orm[..., 0] = 255  # Neutral AO; do not bake studio illumination.
    orm[..., 1] = (76 if name in ('salmon', 'saithe') else 170) + (scale - .5) * 24
    orm[..., 2] = 128 if name in ('salmon', 'saithe') else 0
    orm[fin, 1] = 160
    orm[fin, 2] = 0
    orm[eye, 1] = 65
    return [png(np.clip(a, 0, 255)) for a in (color, orm)]


def geometry(name, lod):
    length, depth, width = SPECS[name]
    rings, sides = [(36, 28), (20, 14), (10, 8)][lod]
    verts, uv, faces = [], [], []

    def vertex(x, y, t, tex):
        verts.append((x * length, y * length, (.5 - t) * length))
        uv.append(tex)
        return len(verts) - 1

    def profile(t):
        # Rounded shoulder, tapered peduncle, terminal mouth; all species have distinct depth/width.
        return max(.018, math.sin(math.pi * min(t / .9, 1)) ** .75 * (1 - .60 * t))

    for i in range(rings + 1):
        t = .86 * i / rings
        p = profile(t)
        if i == 0:
            p = .045
        for j in range(sides + 1):
            a = j / sides * math.tau
            vertex(width * p * math.sin(a), depth * p * math.cos(a), t, (t, j / sides * .8))
    for i in range(rings):
        for j in range(sides):
            a = i * (sides + 1) + j
            b = a + sides + 1
            faces.extend([(a, a + 1, b), (a + 1, b + 1, b)])
    # Close both axial ends with fans.
    for i, t in [(0, 0), (rings, .86)]:
        c = vertex(0, 0, t, (t, .4))
        for j in range(sides):
            a = i * (sides + 1) + j
            faces.append((c, a + 1, a) if i == 0 else (c, a, a + 1))

    def fin(points):
        # Thin, double-sided membrane; fan topology follows concave fork via separate lobes.
        for _ in range(0 if any(t == 1 for x, y, t in points) else 2 if lod == 0 else 1 if lod == 1 else 0):
            softened = []
            for k, point in enumerate(points):
                following = points[(k + 1) % len(points)]
                softened.append(tuple(.85 * a + .15 * b for a, b in zip(point, following)))
                softened.append(tuple(.15 * a + .85 * b for a, b in zip(point, following)))
            points = softened
        is_tail = any(t == 1 for x, y, t in points)
        dorsal = all(y > 0 for x, y, t in points)
        band = .83 if dorsal and not is_tail else .91
        ids = [vertex(x, y, t, (t, band + .02 * y)) for x, y, t in points]
        for k in range(1, len(ids) - 1):
            faces.append((ids[0], ids[k], ids[k + 1]))

    tail = .15 if name in ('salmon', 'saithe', 'fusilier', 'damselfish') else .19
    notch = {'salmon': .94, 'saithe': .94, 'fusilier': .91,
             'damselfish': .97, 'butterflyfish': .98, 'surgeonfish': .96}[name]
    for sign in [-1, 1]:
        fin([(0, 0, .83), (0, sign * .035, .86), (0, sign * tail * .65, .94),
             (0, sign * tail * .94, .998), (0, sign * tail * .90, 1),
             (0, sign * tail * .57, .98), (0, 0, notch)])
    if name == 'saithe':
        dorsal_ranges = [(.25, .44, .10), (.49, .73, .08)]
    elif name == 'salmon':
        dorsal_ranges = [(.35, .57, .10), (.72, .80, .035)]
    elif name == 'fusilier':
        dorsal_ranges = [(.28, .72, .085)]
    else:
        dorsal_ranges = [(.22, .77, .09)]
    for start, end, rise in dorsal_ranges:
        fin([(0, depth * profile(start), start), (0, depth * profile(start + .06) + rise, start + .06),
             (0, depth * profile((start + end) / 2) + rise * .65, (start + end) / 2),
             (0, depth * profile(end) + rise * .12, end), (0, depth * profile(end), end)])
    fin([(0, -depth * profile(.51), .51), (0, -depth * profile(.56) - .07, .56),
         (0, -depth * profile(.73) - .03, .73), (0, -depth * profile(.74), .74)])
    for sign in [-1, 1]:
        fin([(sign * width * .8, -.015, .27), (sign * width * 1.9, -.08, .43),
             (sign * width * 1.3, -.07, .49), (sign * width * .7, -.03, .33)])
        fin([(sign * width * .35, -depth * profile(.43), .43),
             (sign * width * .8, -depth * profile(.43) - .055, .54),
             (sign * width * .35, -depth * profile(.54), .54)])
        # Modest raised eye, iris ring and pupil dome, all in the same mesh/material.
        n = [16, 10, 6][lod]
        t = .135
        cy = depth * .28
        cx = sign * width * profile(t) * .96
        radius = .012 if name in ('salmon', 'saithe') else .018
        c = vertex(cx + sign * radius * .35, cy, t, (.15, .98))
        inner, outer = [], []
        for j in range(n):
            a = j / n * math.tau
            inner.append(vertex(cx + sign * radius * .28, cy + radius * .63 * math.sin(a),
                                t + radius * .63 * math.cos(a), (.15, .98)))
            outer.append(vertex(cx, cy + radius * math.sin(a), t + radius * math.cos(a), (.75, .98)))
        for j in range(n):
            k = (j + 1) % n
            faces.extend([(c, inner[j], inner[k]), (inner[j], outer[j], outer[k]),
                          (inner[j], outer[k], inner[k])])
    return verts, uv, faces


def mesh_object(name, data, material):
    verts, uv, faces = data
    mesh = bpy.data.meshes.new(name)
    # Author in the glTF coordinate system, render in Blender Z-up.
    mesh.from_pydata([(x, -z, y) for x, y, z in verts], [], faces)
    mesh.update()
    layer = mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        poly.use_smooth = True
        for loop in poly.loop_indices:
            layer.data[loop].uv = uv[mesh.loops[loop].vertex_index]
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def material(name, images):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    for index, data in enumerate(images):
        path = OUT / f'{name}_{"basecolor" if index == 0 else "orm"}.png'
        path.write_bytes(data)
        image = bpy.data.images.load(str(path), check_existing=False)
        image.colorspace_settings.name = 'sRGB' if index == 0 else 'Non-Color'
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = image
        if index == 0:
            links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        else:
            sep = nodes.new('ShaderNodeSeparateColor')
            links.new(tex.outputs['Color'], sep.inputs[0])
            links.new(sep.outputs['Green'], shader.inputs['Roughness'])
            links.new(sep.outputs['Blue'], shader.inputs['Metallic'])
    return mat


def export_glb(name, datasets, objects, images):
    binary = bytearray()
    views, accessors = [], []

    def view(data):
        while len(binary) % 4:
            binary.append(0)
        views.append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)})
        binary.extend(data)
        return len(views) - 1

    def accessor(values, kind, dtype='<f4'):
        array = np.array(values, dtype=dtype)
        item = {'bufferView': view(array.tobytes()), 'componentType': 5126 if dtype == '<f4' else 5123,
                'count': len(array), 'type': kind}
        if kind == 'VEC3':
            item['min'] = array.min(axis=0).tolist()
            item['max'] = array.max(axis=0).tolist()
        accessors.append(item)
        return len(accessors) - 1

    meshes = []
    for lod, ((verts, uv, faces), obj) in enumerate(zip(datasets, objects)):
        normals = [(v.normal.x, v.normal.z, -v.normal.y) for v in obj.data.vertices]
        attrs = {'POSITION': accessor(verts, 'VEC3'), 'NORMAL': accessor(normals, 'VEC3'),
                 'TEXCOORD_0': accessor([(u, 1 - v) for u, v in uv], 'VEC2'),
                 'TEXCOORD_1': accessor([(.5 - z / SPECS[name][0], 0) for x, y, z in verts], 'VEC2')}
        indices = accessor([i for face in faces for i in face], 'SCALAR', '<u2')
        meshes.append({'name': f'{name}_lod{lod}', 'primitives': [{'attributes': attrs,
                       'indices': indices, 'material': 0}]})
    img = [{'bufferView': view(data), 'mimeType': 'image/png'} for data in images]
    doc = {'asset': {'version': '2.0', 'generator': 'ROV N1 original procedural fish'},
           'scene': 0, 'scenes': [{'nodes': [0, 1, 2]}],
           'nodes': [{'name': m['name'], 'mesh': i} for i, m in enumerate(meshes)],
           'meshes': meshes, 'buffers': [{'byteLength': len(binary)}], 'bufferViews': views,
           'accessors': accessors, 'images': img, 'textures': [{'source': 0}, {'source': 1}],
           'materials': [{'name': name, 'doubleSided': True, 'pbrMetallicRoughness': {
               'baseColorTexture': {'index': 0}, 'metallicRoughnessTexture': {'index': 1},
               'metallicFactor': 1, 'roughnessFactor': 1}, 'occlusionTexture': {'index': 1}}]}
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    assert total <= 300000, (name, total)
    result = struct.pack('<3I', 0x46546C67, 2, total)
    result += struct.pack('<2I', len(encoded), 0x4E4F534A) + encoded
    result += struct.pack('<2I', len(binary), 0x004E4942) + binary
    (OUT / f'{name}.glb').write_bytes(result)
    return total


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def studio():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 8
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 85
    scene.world.color = (.18, .18, .18)
    scene.view_settings.view_transform = 'AgX'
    bpy.ops.object.camera_add(location=(1, 0, 0))
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    scene.camera = camera
    for location, power, size in [((1, -1, 2), 150, 2), ((-1, 0, 1), 100, 2), ((0, 1, .5), 80, 1)]:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = power
        light.data.shape = 'DISK'
        light.data.size = size
        aim(light, (0, 0, 0))
    return camera


def render(camera, path, location, scale, target=(0, 0, 0)):
    camera.location = location
    camera.data.ortho_scale = scale
    aim(camera, target)
    if location == (0, 0, 1):
        camera.rotation_euler.rotate_axis('Z', math.pi / 2)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    assert path.stat().st_size <= 300000, path


def overview(camera, heroes):
    """Render an orthographic comparison with unchanged metre-scale geometry."""
    for i, obj in enumerate(heroes):
        obj.hide_render = False
        column = i % 3
        row = i // 3
        obj.location = (0, (column - 1) * .70, (.5 - row) * .36)
        label = bpy.data.curves.new('species_label', 'FONT')
        label.body = f'{list(SPECS)[i]}  /  {SPECS[list(SPECS)[i]][0]:.2f} m'
        label.size = .024
        label.align_x = 'CENTER'
        text = bpy.data.objects.new('label', label)
        bpy.context.collection.objects.link(text)
        text.rotation_euler = (math.pi / 2, 0, math.pi / 2)
        text.location = (.03, obj.location.y, obj.location.z - .14)
    render(camera, DOC / 'overview.jpg', (2, 0, 0), 2.2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    camera = studio()
    rows = []
    heroes = []
    for name, (length, depth, width) in SPECS.items():
        images = textures(name)
        mat = material(name, images)
        datasets = [geometry(name, lod) for lod in range(3)]
        counts = [len(data[2]) for data in datasets]
        assert all(n <= cap for n, cap in zip(counts, [2500, 800, 250])), counts
        objects = [mesh_object(f'{name}_lod{lod}', data, mat) for lod, data in enumerate(datasets)]
        size = export_glb(name, datasets, objects, images)
        for obj in objects[1:]:
            obj.hide_render = True
        for view, location in [('side', (1, 0, 0)), ('top', (0, 0, 1)), ('front34', (1, -.8, .35))]:
            scale = length * (1.65 if view == 'front34' else 1.3)
            render(camera, DOC / f'{name}_{view}.jpg', location, scale)
        objects[0].hide_render = True
        heroes.append(objects[0])
        rows.append({'id': name, 'length_m': length, 'triangles': counts, 'glb_bytes': size,
                     'basecolor': [512, 256], 'orm': [512, 256]})
        print('N1_VALIDATED', rows[-1], flush=True)
    overview(camera, heroes)
    (DOC / 'validation.json').write_text(json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
