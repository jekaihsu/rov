"""N3: turn CC0 Sketchfab / Smithsonian specimen scans into game-ready reef GLBs.

Blender 4.x (must be run inside Blender):

  blender -b -P cad/build_reef_life.py -- \\
      --source /tmp/reef_sources [--only urchin] [--skip-render]

Scratch layout (never committed):
  <source>/ffish/<id>/src/scene.gltf     Sketchfab glTF downloads
  <source>/smithsonian/<id>_raw.glb      Smithsonian meshes (meshopt decoded)

For each asset the script: drops the 10 mm colour-chart cube, scales to metres,
orients fish nose to glTF +Z with the back up, decimates, unwraps, bakes colour
+ tangent normals to 512 px maps, recolours dry Smithsonian coral with procedural
living pigments (no photographs), writes near/far GLBs and a 1600×900 studio JPEG,
then packs with glTF-Transform (meshopt + WebP).

Triangle budgets (near / far): small life 1500/300, fish 2500/700, coral 4000/800.
Each packed GLB ≤ 400 KB.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'simulator/viewer/models/reef'
DOC = ROOT / 'docs/design/reef-life'
TEX = 512
MAX_GLB = 400 * 1024
GLTF_TRANSFORM = ['npx', '--yes', '@gltf-transform/cli@4.5.1']
CHART_EDGE_M = 0.01  # ffishAsia colour chart is a 10 mm cube

# Living coral pigments from public underwater descriptions (not from photos).
CORAL_PIGMENT = {
    # (body, tip, shade) — saturated living colours from public underwater descriptions.
    'acropora_palmata': ((0.55, 0.32, 0.10), (0.78, 0.58, 0.18), (0.22, 0.14, 0.06)),
    'acropora_hyacinthus': ((0.36, 0.40, 0.12), (0.70, 0.62, 0.18), (0.16, 0.22, 0.08)),
    'diploria': ((0.50, 0.40, 0.12), (0.30, 0.48, 0.22), (0.18, 0.14, 0.06)),
    'pocillopora': ((0.72, 0.32, 0.34), (0.88, 0.55, 0.50), (0.38, 0.16, 0.18)),
    'porites': ((0.62, 0.50, 0.14), (0.40, 0.52, 0.22), (0.24, 0.20, 0.08)),
}

ASSETS = {
    'urchin': {
        'kind': 'small', 'tris': (1500, 300), 'length_m': 0.07,
        'src': 'ffish/urchin/src/scene.gltf',
        'page': 'https://sketchfab.com/models/4cbc27daa0404b628e3b2f05b59d4f49',
        'author': 'ffish.asia / floraZia.com',
        'title': '紫海膽 Heliocidaris crassispina',
    },
    'starfish': {
        'kind': 'small', 'tris': (1500, 300), 'length_m': 0.12,
        'src': 'ffish/starfish/src/scene.gltf',
        'page': 'https://sketchfab.com/models/14319712a5f445fe8a1eb461eadf6527',
        'author': 'ffish.asia / floraZia.com',
        'title': '藍蝙蝠海星 Patiria pectinifera',
    },
    'crab': {
        'kind': 'small', 'tris': (1500, 300), 'length_m': 0.14,
        'src': 'ffish/crab/src/scene.gltf',
        'page': 'https://sketchfab.com/models/4915ee5a2d9f46af9a24d3b8da505d00',
        'author': 'ffish.asia / floraZia.com',
        'title': '石蟳 Charybdis japonica',
    },
    'cucumber': {
        'kind': 'small', 'tris': (1500, 300), 'length_m': 0.25,
        'src': 'ffish/cucumber/src/scene.gltf',
        'page': 'https://sketchfab.com/models/c8fcb7b084df432c9d5765eee264ee02',
        'author': 'ffish.asia / floraZia.com',
        'title': '刺參 Apostichopus japonicus',
    },
    'mussel': {
        'kind': 'small', 'tris': (1500, 300), 'length_m': 0.07,
        'src': 'ffish/mussel/src/scene.gltf',
        'page': 'https://sketchfab.com/models/0920004b72a54a099155abbad85de99d',
        'author': 'ffish.asia / floraZia.com',
        'title': '紫贻貝 Mytilus galloprovincialis',
    },
    'barnacle': {
        'kind': 'small', 'tris': (1500, 300), 'length_m': 0.045,
        'src': 'ffish/barnacle/src/scene.gltf',
        'page': 'https://sketchfab.com/models/7e2bbead73344312aad9ba99240be7ab',
        'author': 'ffish.asia / floraZia.com',
        'title': '日本藤壺 Tetraclita japonica',
    },
    'butterflyfish': {
        'kind': 'fish', 'tris': (2500, 700), 'length_m': 0.16,
        'src': 'ffish/butterflyfish/src/scene.gltf',
        'page': 'https://sketchfab.com/models/27f435f82a0443ef8980b42e4bd9105e',
        'author': 'ffish.asia / floraZia.com',
        'title': '關公魚 Heniochus acuminatus',
    },
    'angelfish': {
        'kind': 'fish', 'tris': (2500, 700), 'length_m': 0.18,
        'src': 'ffish/angelfish/src/scene.gltf',
        'page': 'https://sketchfab.com/models/a5c0bb6877184e698c1992e5ce1a69d0',
        'author': 'ffish.asia / floraZia.com',
        'title': '藍紋神仙魚 Chaetodontoplus septentrionalis',
    },
    'stripey': {
        'kind': 'fish', 'tris': (2500, 700), 'length_m': 0.15,
        'src': 'ffish/stripey/src/scene.gltf',
        'page': 'https://sketchfab.com/models/32e3ef9d5ea24bd3a05a282416f9baac',
        'author': 'ffish.asia / floraZia.com',
        'title': '條紋魚 Microcanthus strigatus',
    },
    'wrasse': {
        'kind': 'fish', 'tris': (2500, 700), 'length_m': 0.32,
        'src': 'ffish/wrasse/src/scene.gltf',
        'page': 'https://sketchfab.com/models/a1fa2be4f363454baadf35fafa403e6b',
        'author': 'ffish.asia / floraZia.com',
        'title': '狐狸鯛 Bodianus oxycephalus',
    },
    'acropora_palmata': {
        'kind': 'coral', 'tris': (4000, 800), 'length_m': 0.45,
        'src': 'smithsonian/acropora_palmata_raw.glb',
        'page': 'https://sketchfab.com/models/8cb986313c824ac38c373c0fabd0805f',
        'author': 'Smithsonian Institution',
        'title': '鹿角珊瑚 Acropora palmata',
        'si': 'https://ids.si.edu/ids/media_view?id=3d_package:6fd30c79-3345-4d06-b27c-99d5b320ce5f',
    },
    'acropora_hyacinthus': {
        'kind': 'coral', 'tris': (4000, 800), 'length_m': 0.35,
        'src': 'smithsonian/acropora_hyacinthus_raw.glb',
        'page': 'https://sketchfab.com/models/5e8f3939400d4753bcb8e4a43819473c',
        'author': 'Smithsonian Institution',
        'title': '桌形珊瑚 Acropora hyacinthus',
        'si': 'https://ids.si.edu/ids/media_view?id=3d_package:1a0a3b2d-5ef6-4bc0-af39-0a35d95f1f01',
    },
    'diploria': {
        'kind': 'coral', 'tris': (4000, 800), 'length_m': 0.30,
        'src': 'smithsonian/diploria_raw.glb',
        'page': 'https://sketchfab.com/models/cbbf64f211f84a7cb62887fec11f54fe',
        'author': 'Smithsonian Institution',
        'title': '腦珊瑚 Diploria labyrinthiformis',
        'si': 'https://ids.si.edu/ids/media_view?id=3d_package:87738412-3acd-45d1-bff4-3ab67093470e',
    },
    'pocillopora': {
        'kind': 'coral', 'tris': (4000, 800), 'length_m': 0.22,
        'src': 'smithsonian/pocillopora_raw.glb',
        'page': 'https://sketchfab.com/models/925b1db06f1d407f8bbca23d91031049',
        'author': 'Smithsonian Institution',
        'title': 'Pocillopora damicornis',
        'si': 'https://ids.si.edu/ids/media_view?id=3d_package:1951c814-3758-4b7f-b0ba-8f996534ff2b',
    },
    'porites': {
        'kind': 'coral', 'tris': (4000, 800), 'length_m': 0.25,
        'src': 'smithsonian/porites_raw.glb',
        'page': 'https://sketchfab.com/models/68c44f2315374bb0a4f088c9a1ab174e',
        'author': 'Smithsonian Institution',
        'title': '塊狀珊瑚 Porites monticulosa',
        'si': 'https://ids.si.edu/ids/media_view?id=3d_package:32cb1ed0-3d3d-40d7-856f-8d3c599ca0fc',
    },
}


def argv_after_double_dash():
    if '--' in sys.argv:
        return sys.argv[sys.argv.index('--') + 1:]
    return sys.argv[1:]


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']


def triangle_count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def world_bounds(objects):
    points = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    low = Vector((min(p[i] for p in points) for i in range(3)))
    high = Vector((max(p[i] for p in points) for i in range(3)))
    return low, high


def apply_transforms(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.select_set(False)


def bake_world_transforms(objects):
    """Clear parents while keeping world geometry, then bake loc/rot/scale into the mesh.

    Sketchfab glTF imports often leave the mesh under a transformed empty. world_bounds() is
    in world space, but obj.location is parent-relative — centering must run on unparented meshes.
    """
    for obj in objects:
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
    apply_transforms(objects)


def join_meshes(objects, name):
    bake_world_transforms(objects)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    active = bpy.context.view_layer.objects.active
    active.name = name
    return active


def delete_object(obj):
    bpy.data.objects.remove(obj, do_unlink=True)


def import_source(path: Path):
    clear_scene()
    path = path.resolve()
    bpy.ops.import_scene.gltf(filepath=str(path))
    return mesh_objects()


def drop_colour_chart(objects):
    """Remove the 10 mm colour-chart cube (Material.001) used by ffishAsia scans."""
    kept, charts, chart_edge = [], [], None
    for obj in objects:
        names = [slot.name if slot else '' for slot in obj.data.materials]
        only_chart = names and all(name.startswith('Material.001') or name == 'Material.001' for name in names)
        tiny = triangle_count(obj) <= 24
        if only_chart and tiny:
            low, high = world_bounds([obj])
            chart_edge = max(high - low)
            charts.append(obj)
        else:
            kept.append(obj)
    for obj in charts:
        delete_object(obj)
    return kept, chart_edge


def calibrate_and_scale(objects, length_m, chart_edge):
    """Scale so the longest AABB edge becomes length_m; prefer the 10 mm chart when present."""
    if chart_edge and chart_edge > 1e-6:
        factor = CHART_EDGE_M / chart_edge
        for obj in objects:
            obj.scale *= factor
        apply_transforms(objects)
    low, high = world_bounds(objects)
    size = high - low
    longest = max(size)
    if longest < 1e-6:
        raise RuntimeError('empty bounds')
    factor = length_m / longest
    for obj in objects:
        obj.scale *= factor
    apply_transforms(objects)


def center_on_origin(objects):
    bake_world_transforms(objects)
    low, high = world_bounds(objects)
    center = (low + high) * 0.5
    # Sit invertebrates / coral on the ground plane (Z = 0 in Blender before export).
    for obj in objects:
        obj.location -= center
    apply_transforms(objects)
    low, high = world_bounds(objects)
    shift_z = -low.z
    for obj in objects:
        obj.location.z += shift_z
    apply_transforms(objects)


def orient_fish(obj):
    """Nose → Blender −Y (glTF +Z), back → Blender +Z (glTF +Y)."""
    apply_transforms([obj])
    low, high = world_bounds([obj])
    size = high - low
    order = sorted(range(3), key=lambda i: size[i], reverse=True)
    mesh = obj.data
    # Longest → Y, next → Z (height), remaining → X.
    for vert in mesh.vertices:
        co = vert.co.copy()
        vert.co = Vector((co[order[2]], co[order[0]], co[order[1]]))
    mesh.update()
    low, high = world_bounds([obj])
    mid_y = 0.5 * (low.y + high.y)

    def rms_xz(points):
        if not points:
            return 0.0
        cx = sum(p.x for p in points) / len(points)
        cz = sum(p.z for p in points) / len(points)
        return math.sqrt(sum((p.x - cx) ** 2 + (p.z - cz) ** 2 for p in points) / len(points))

    pos = [vert.co for vert in mesh.vertices if vert.co.y >= mid_y]
    neg = [vert.co for vert in mesh.vertices if vert.co.y < mid_y]
    # Thinner end is the snout and must face −Y.
    if rms_xz(pos) < rms_xz(neg):
        for vert in mesh.vertices:
            vert.co.y *= -1
        mesh.update()
    # If the mesh is upside down (more mass above mid-Z), flip.
    mid_z = 0.5 * (min(v.co.z for v in mesh.vertices) + max(v.co.z for v in mesh.vertices))
    above = sum(1 for v in mesh.vertices if v.co.z >= mid_z)
    below = len(mesh.vertices) - above
    if above > below * 1.15:
        for vert in mesh.vertices:
            vert.co.z *= -1
        mesh.update()
    center = sum((v.co for v in mesh.vertices), Vector((0, 0, 0))) / len(mesh.vertices)
    for vert in mesh.vertices:
        vert.co -= center
    mesh.update()


def orient_static(obj, kind):
    """Invertebrates and coral: largest footprint on XY, sit on Z = 0."""
    mesh = obj.data
    low, high = world_bounds([obj])
    size = high - low
    order = sorted(range(3), key=lambda i: size[i], reverse=True)
    # Put the two largest extents on X/Y, the smallest as height Z for flat animals;
    # for branching coral keep original up if already tallest.
    if kind == 'coral' and size.z >= size.x * 0.55 and size.z >= size.y * 0.55:
        pass
    else:
        for vert in mesh.vertices:
            co = vert.co.copy()
            vert.co = Vector((co[order[0]], co[order[1]], co[order[2]]))
        mesh.update()
    apply_transforms([obj])
    center_on_origin([obj])


def living_coral_material(name):
    base, tip, shade = CORAL_PIGMENT[name]
    mat = bpy.data.materials.new(f'{name}_live')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    tex = nodes.new('ShaderNodeTexCoord')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 12.0
    noise.inputs['Detail'].default_value = 8.0
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*shade, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (*tip, 1)
    mid = ramp.color_ramp.elements.new(0.45)
    mid.color = (*base, 1)
    sep = nodes.new('ShaderNodeSeparateXYZ')
    zmap = nodes.new('ShaderNodeMapRange')
    zmap.inputs['From Min'].default_value = 0.0
    zmap.inputs['From Max'].default_value = 0.35
    zmap.inputs['To Min'].default_value = 0.0
    zmap.inputs['To Max'].default_value = 0.55
    mix = nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MIX'
    links.new(tex.outputs['Object'], noise.inputs['Vector'])
    links.new(tex.outputs['Object'], sep.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], mix.inputs['Color1'])
    # Higher object Z leans toward tip colour (Z is metres; remap into 0–1).
    links.new(sep.outputs['Z'], zmap.inputs['Value'])
    links.new(zmap.outputs['Result'], mix.inputs['Fac'])
    tip_rgb = nodes.new('ShaderNodeRGB')
    tip_rgb.outputs[0].default_value = (*tip, 1)
    links.new(tip_rgb.outputs[0], mix.inputs['Color2'])
    links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.55
    bsdf.inputs['Specular IOR Level'].default_value = 0.2
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def apply_coral_recolour(obj, name):
    mat = living_coral_material(name)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def duplicate_mesh(obj, name):
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name
    copy.hide_set(False)
    copy.hide_render = False
    copy.hide_viewport = False
    bpy.context.scene.collection.objects.link(copy)
    return copy


def merge_by_distance(obj, distance):
    obj.hide_set(False)
    obj.hide_viewport = False
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=distance)
    bpy.ops.object.mode_set(mode='OBJECT')


def decimate(obj, target_tris):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    low, high = world_bounds([obj])
    merge_by_distance(obj, max(max(high - low) * 1e-4, 1e-5))
    for _ in range(8):
        count = max(triangle_count(obj), 1)
        if count <= target_tris:
            break
        mod = obj.modifiers.new('decimate', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(1e-4, min(1.0, target_tris / count))
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        new_count = triangle_count(obj)
        if new_count >= count * 0.98:
            # Collapse stalled (many shells); voxel remesh then retry.
            rem = obj.modifiers.new('remesh', 'REMESH')
            rem.mode = 'VOXEL'
            rem.voxel_size = max(max(high - low) / 48.0, 1e-4)
            bpy.ops.object.modifier_apply(modifier=rem.name)
    count = triangle_count(obj)
    if count > target_tris * 1.2:
        mod = obj.modifiers.new('decimate_final', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(1e-4, min(1.0, target_tris / max(count, 1)))
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return triangle_count(obj)


def smart_uv(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')


def make_image(name, size=TEX, *, color=False):
    image = bpy.data.images.new(name, width=size, height=size, alpha=False, float_buffer=False)
    image.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return image


def bake_target_material(obj, image):
    """Material with a single unconnected image node (avoids circular bake deps)."""
    mat = bpy.data.materials.new(obj.name + '_bake_target')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1)
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = image
    nodes.active = tex
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat, tex


def final_baked_material(obj, color_image, normal_image):
    color_image.colorspace_settings.name = 'sRGB'
    normal_image.colorspace_settings.name = 'Non-Color'
    mat = bpy.data.materials.new(obj.name + '_baked')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    tex_c = nodes.new('ShaderNodeTexImage')
    tex_c.image = color_image
    tex_c.label = 'BaseColor'
    tex_n = nodes.new('ShaderNodeTexImage')
    tex_n.image = normal_image
    tex_n.label = 'Normal'
    nmap = nodes.new('ShaderNodeNormalMap')
    links.new(tex_c.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(tex_n.outputs['Color'], nmap.inputs['Color'])
    links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.6
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def force_emission_from_base_color(obj):
    """Replace surface shaders with Emission(base colour) so colour bakes are lit-independent."""
    for slot in obj.data.materials:
        if slot is None or not slot.use_nodes:
            continue
        nodes = slot.node_tree.nodes
        links = slot.node_tree.links
        out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if out is None or bsdf is None:
            continue
        emit = nodes.new('ShaderNodeEmission')
        emit.inputs['Strength'].default_value = 1.0
        base = bsdf.inputs['Base Color']
        if base.is_linked:
            links.new(base.links[0].from_socket, emit.inputs['Color'])
        else:
            emit.inputs['Color'].default_value = base.default_value
        for link in list(out.inputs['Surface'].links):
            links.remove(link)
        links.new(emit.outputs['Emission'], out.inputs['Surface'])


def bake_maps(high, low, color_image, normal_image, samples=4):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.cycles.bake_type = 'EMIT'
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.use_cage = False
    extent = max(world_bounds([high])[1] - world_bounds([high])[0])
    scene.render.bake.cage_extrusion = max(0.01, 0.15 * extent)
    scene.render.bake.max_ray_distance = 0.0
    scene.render.bake.margin = 16
    bpy.context.view_layer.update()

    def select_pair():
        bpy.ops.object.select_all(action='DESELECT')
        for obj in (high, low):
            obj.hide_render = False
            obj.hide_viewport = False
            obj.hide_set(False)
        high.select_set(True)
        low.select_set(True)
        bpy.context.view_layer.objects.active = low
        bpy.context.view_layer.update()

    scratch = Path(tempfile.mkdtemp(prefix='reef_bake_'))

    # Normals first, while the high mesh still has its original surface shaders.
    bake_target_material(low, normal_image)
    select_pair()
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', use_clear=True,
                        use_selected_to_active=True)
    normal_path = scratch / f'{low.name}_normal.png'
    normal_image.filepath_raw = str(normal_path)
    normal_image.file_format = 'PNG'
    normal_image.save()

    # Colour via emission so lighting does not tint the albedo.
    force_emission_from_base_color(high)
    bake_target_material(low, color_image)
    select_pair()
    bpy.ops.object.bake(type='EMIT', use_clear=True, use_selected_to_active=True)
    color_pixels = [0.0] * (color_image.size[0] * color_image.size[1] * 4)
    color_image.pixels.foreach_get(color_pixels)
    mean = sum(color_pixels[0::4]) / max(len(color_pixels) // 4, 1)
    color_path = scratch / f'{low.name}_color.png'
    color_image.filepath_raw = str(color_path)
    color_image.file_format = 'PNG'
    color_image.save()
    print(f'  bake color_mean={mean:.4f} color_png={color_path.stat().st_size} '
          f'normal_png={normal_path.stat().st_size}')
    if mean < 0.02 or color_path.stat().st_size < 8_000:
        raise RuntimeError(f'colour bake failed (mean={mean:.5f}, bytes={color_path.stat().st_size})')

    for image, path, space in (
        (color_image, color_path, 'sRGB'),
        (normal_image, normal_path, 'Non-Color'),
    ):
        image.source = 'FILE'
        image.filepath = str(path)
        image.reload()
        image.colorspace_settings.name = space
        image.pack()
    return final_baked_material(low, color_image, normal_image)


def export_glb(obj, path: Path):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
        export_image_format='AUTO',
    )


def pack_glb(raw: Path, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = GLTF_TRANSFORM + [
        'optimize', str(raw), str(out),
        '--compress', 'meshopt',
        '--texture-compress', 'webp',
        '--texture-size', str(TEX),
    ]
    subprocess.run(cmd, check=True)


def glb_stats(path: Path):
    data = path.read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    gltf = json.loads(data[20:20 + length])
    accessors = gltf.get('accessors', [])
    tris = 0
    for mesh in gltf.get('meshes', []):
        for prim in mesh['primitives']:
            if 'indices' in prim:
                tris += accessors[prim['indices']]['count'] // 3
            else:
                tris += accessors[prim['attributes']['POSITION']]['count'] // 3
    return {'bytes': path.stat().st_size, 'tris': tris}


def studio_render(obj, path: Path):
    """Render ``obj`` in-place (already textured); hide every other mesh."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.render.film_transparent = False
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 84
    world = bpy.data.worlds.new('studio')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.62, 0.66, 0.70, 1)
    bg.inputs[1].default_value = 0.8
    for other in list(bpy.context.scene.objects):
        if other.type == 'MESH':
            other.hide_render = other != obj
            other.hide_viewport = other != obj
        elif other.type in {'LIGHT', 'CAMERA'}:
            bpy.data.objects.remove(other, do_unlink=True)
    low, high = world_bounds([obj])
    center = (low + high) * 0.5
    size = high - low
    radius = max(max(size) * 0.5, 1e-3)
    cam_data = bpy.data.cameras.new('studio_cam')
    cam = bpy.data.objects.new('studio_cam', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # Three-quarter view; raise the camera so flat seabed props are not edge-on.
    cam.location = center + Vector((radius * 1.8, -radius * 2.1, radius * 1.7))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = 60
    # Fit the subject: approximate vertical FOV coverage.
    span = max(size.x, size.y, size.z)
    distance = (cam.location - center).length
    cam_data.lens = max(24, min(80, 50 * (distance / max(span * 2.2, 1e-3))))
    key = bpy.data.lights.new('key', 'AREA')
    key.energy = 40
    key.size = max(radius * 5, 0.4)
    key_obj = bpy.data.objects.new('key', key)
    scene.collection.objects.link(key_obj)
    key_obj.location = center + Vector((radius * 1.2, -radius * 0.8, radius * 2.4))
    fill = bpy.data.lights.new('fill', 'AREA')
    fill.energy = 18
    fill.size = max(radius * 6, 0.4)
    fill_obj = bpy.data.objects.new('fill', fill)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = center + Vector((-radius * 1.8, radius * 1.2, radius * 1.2))
    rim = bpy.data.lights.new('rim', 'AREA')
    rim.energy = 12
    rim.size = max(radius * 4, 0.4)
    rim_obj = bpy.data.objects.new('rim', rim)
    scene.collection.objects.link(rim_obj)
    rim_obj.location = center + Vector((0.0, radius * 2.0, radius * 1.0))
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.exposure = 0.0
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    if path.exists() and path.stat().st_size > 300 * 1024:
        try:
            from PIL import Image
            Image.open(path).save(path, 'JPEG', quality=72, optimize=True)
        except Exception:
            pass


def process_asset(name, spec, source_root: Path, work: Path, skip_render: bool):
    src = source_root / spec['src']
    if not src.exists():
        raise FileNotFoundError(src)
    print(f'=== {name}: import {src}')
    objects = import_source(src)
    objects, chart_edge = drop_colour_chart(objects)
    if not objects:
        raise RuntimeError(f'{name}: no meshes after dropping colour chart')
    # Bake parented Sketchfab nodes into object space before any world-space math.
    bake_world_transforms(objects)
    calibrate_and_scale(objects, spec['length_m'], chart_edge)
    high = join_meshes(objects, f'{name}_high')
    if spec['kind'] == 'coral':
        apply_coral_recolour(high, name)
        orient_static(high, 'coral')
    elif spec['kind'] == 'fish':
        orient_fish(high)
    else:
        orient_static(high, 'small')

    near_tris, far_tris = spec['tris']
    results = {}
    for label, budget in (('near', near_tris), ('far', far_tris)):
        high.hide_set(False)
        high.hide_viewport = False
        high.hide_render = False
        low = duplicate_mesh(high, f'{name}_{label}')
        count = decimate(low, budget)
        smart_uv(low)
        color = make_image(f'{name}_{label}_color', color=True)
        normal = make_image(f'{name}_{label}_normal', color=False)
        # Hide siblings during bake.
        for obj in mesh_objects():
            obj.hide_set(obj not in (high, low))
        bake_maps(high, low, color, normal, samples=2 if label == 'far' else 4)
        # Disconnect high so export is clean.
        high.hide_set(True)
        raw = work / f'{name}_{label}_raw.glb'
        # Save images into the blend memory for export.
        # Images are already packed inside bake_maps; export embeds them.
        export_glb(low, raw)
        out_name = f'{name}.glb' if label == 'near' else f'{name}_lo.glb'
        packed = OUT / out_name
        pack_glb(raw, packed)
        stats = glb_stats(packed)
        stats['decimated_tris'] = count
        results[label] = stats
        print(f'  {out_name}: tris={stats["tris"]} bytes={stats["bytes"]}')
        if stats['bytes'] > MAX_GLB:
            tmp = work / f'{name}_{label}_tight.glb'
            subprocess.run(
                GLTF_TRANSFORM + [
                    'optimize', str(raw), str(tmp),
                    '--compress', 'meshopt',
                    '--texture-compress', 'webp',
                    '--texture-size', '256',
                    '--simplify', 'true',
                    '--simplify-error', '0.01',
                ],
                check=True,
            )
            shutil.copy2(tmp, packed)
            stats = glb_stats(packed)
            results[label] = stats
            print(f'  retightened {out_name}: tris={stats["tris"]} bytes={stats["bytes"]}')
        if label == 'near' and not skip_render:
            high.hide_render = True
            high.hide_set(True)
            studio_render(low, DOC / f'{name}.jpg')
        delete_object(low)
    return results


def write_readme(report):
    DOC.mkdir(parents=True, exist_ok=True)
    lines = [
        '# 礁區生物與珊瑚模型（N3）',
        '',
        '由 CC0 真實標本掃描減面、烘焙後輸出。重建：',
        '',
        '```bash',
        'python cad/download_reef_sources.py --out /tmp/reef_sources',
        'blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources',
        '```',
        '',
        '下載腳本會寫入 `ffish/<id>/src/scene.gltf` 與 `smithsonian/<id>_raw.glb`，',
        '與本建置腳本的 `ASSETS` 路徑一致。來源與授權見 `simulator/viewer/models/CREDITS.md`。',
        '珊瑚為史密森尼乾燥標本，已用程序色改成活珊瑚色調（未使用任何照片貼圖）。',
        '',
        '| 模型 | 近景三角形 | 近景大小 | 遠景三角形 | 遠景大小 | 授權 |',
        '|---|---:|---:|---:|---:|---|',
    ]
    for name, info in report.items():
        near = info['near']
        far = info['far']
        lines.append(
            f'| `{name}` | {near["tris"]} | {near["bytes"] / 1024:.1f} KB | '
            f'{far["tris"]} | {far["bytes"] / 1024:.1f} KB | CC0 |'
        )
    lines.append('')
    (DOC / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (DOC / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Build N3 reef-life GLBs')
    parser.add_argument('--source', required=True, type=Path, help='scratch folder with ffish/ and smithsonian/')
    parser.add_argument('--only', nargs='*', help='subset of asset ids')
    parser.add_argument('--skip-render', action='store_true')
    args = parser.parse_args(argv_after_double_dash())
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    names = args.only or list(ASSETS)
    report = {}
    with tempfile.TemporaryDirectory(prefix='reef_life_') as tmp:
        work = Path(tmp)
        for name in names:
            if name not in ASSETS:
                raise SystemExit(f'unknown asset {name}')
            report[name] = process_asset(name, ASSETS[name], args.source, work, args.skip_render)
    write_readme(report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
