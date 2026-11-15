"""Headless original CC0 cable asset and mission build; no blend or reference photos saved."""
import json
import math
import subprocess
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.cable_route import layout, SEED
OUT = ROOT / 'simulator/viewer/models/cable_route'
TEMP = ROOT / 'simulator/output'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    rng = np.random.default_rng(SEED)
    size = 256
    y, x = np.mgrid[:size, :size]
    grime = np.full((size, size), .56)
    for cells, weight in ((4, .16), (16, .12), (64, .09), (256, .08)):
        noise = rng.random((cells, cells))
        gx, gy = x * cells / size, y * cells / size
        ix, iy = gx.astype(int), gy.astype(int)
        ax, ay = gx - ix, gy - iy
        ax, ay = ax * ax * (3 - 2 * ax), ay * ay * (3 - 2 * ay)
        field = ((1 - ax) * (1 - ay) * noise[iy, ix] + ax * (1 - ay) * noise[iy, (ix + 1) % cells]
                 + (1 - ax) * ay * noise[(iy + 1) % cells, ix]
                 + ax * ay * noise[(iy + 1) % cells, (ix + 1) % cells])
        grime += weight * (field * 2 - 1)
    grime -= .15 * (rng.random((size, size)) < .025)
    grime = np.clip(grime, .12, .88)
    image = bpy.data.images.new('Original sediment wear', width=size, height=size)
    image.pixels = np.stack([grime, grime * .98, grime * .89, np.ones_like(grime)], axis=-1).ravel().tolist()
    image.filepath_raw = str(TEMP / 'cable-weathering.png')
    image.file_format = 'PNG'
    image.save()
    subprocess.run(['python', '-c',
                    'from PIL import Image; import sys; Image.open(sys.argv[1]).save(sys.argv[2], lossless=True)',
                    str(TEMP / 'cable-weathering.png'), str(OUT / 'weathering.webp')], check=True)
    colors = {'route_star': (.4, .3, .2), 'route_urchin': (.15, .14, .12),
              'route_cable': (.14, .16, .14), 'route_damage': (.5, .48, .4),
              'route_steel': (.25, .23, .19), 'route_concrete': (.48, .47, .41),
              'route_sign': (.6, .59, .5), 'route_rope': (.35, .32, .25), 'snag': (.38, .37, .31)}
    mats = {}
    for kind, color in colors.items():
        mat = bpy.data.materials.new(kind)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (*color, 1)
        shader.inputs['Roughness'].default_value = .94
        if kind != 'route_sign':
            tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = image
            mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        mats[kind] = mat
    obstacles, data = layout()
    for ob in obstacles:
        if hasattr(ob, 'half'):
            bpy.ops.mesh.primitive_cube_add(size=2, location=(*ob.center[:2], -ob.center[2]))
            obj = bpy.context.object
            obj.scale = ob.half
            obj.rotation_euler.z = math.radians(ob.yaw_deg)
        else:
            a, b = (Vector((p[0], p[1], -p[2])) for p in (ob.p0, ob.p1))
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=ob.radius,
                                               depth=max(.001, (b - a).length), location=(a + b) / 2)
            obj = bpy.context.object
            obj.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
        obj.name = ob.name
        obj.data.materials.append(mats[ob.kind])
    for kind, mat in mats.items():
        objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.data.materials[0] == mat]
        if not objects:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(TEMP / 'cable-route.glb'), export_format='GLB')
    subprocess.run(['npx', '--yes', '@gltf-transform/cli@4.5.1', 'optimize',
                    str(TEMP / 'cable-route.glb'), str(OUT / 'route.glb'),
                    '--compress', 'meshopt', '--texture-compress', 'webp'], check=True)
    (OUT / 'mission.json').write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    main()
