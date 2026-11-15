"""Rebuild the original reservoir collision blockout; not the final photo-matched art asset.

blender -b --python cad/build_reservoir.py
No input photographs or .blend files. Exports meshopt GLBs at two resolutions.
"""
import math
import subprocess
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.reservoir import layout

OUT = ROOT / 'simulator/viewer/models/reservoir'
TEMP = ROOT / 'simulator/output'
COLORS = {'concrete': (.45, .46, .4), 'steel': (.3, .22, .18), 'wood': (.22, .18, .1),
          'white': (.8, .8, .7), 'orange': (.75, .3, .06), 'blue': (.06, .2, .4),
          'rope': (.5, .45, .3), 'cable': (.7, .9, .01), 'red': (.5, .03, .02)}


def build(tier, segments):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    materials = {}
    for kind, color in COLORS.items():
        mat = bpy.data.materials.new(kind)
        mat.diffuse_color = (*color, 1)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (*color, 1)
        shader.inputs['Roughness'].default_value = .9
        materials[kind] = mat
    for ob in layout():
        if hasattr(ob, 'half'):
            bpy.ops.mesh.primitive_cube_add(size=2, location=(ob.center[0], ob.center[1], -ob.center[2]))
            obj = bpy.context.object
            obj.scale = ob.half
            obj.rotation_euler.z = math.radians(ob.yaw_deg)
        else:
            a = Vector((ob.p0[0], ob.p0[1], -ob.p0[2]))
            b = Vector((ob.p1[0], ob.p1[1], -ob.p1[2]))
            bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=ob.radius,
                                               depth=(b-a).length, location=(a+b)/2)
            obj = bpy.context.object
            obj.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
        obj.name = ob.name
        obj.data.materials.append(materials[ob.kind[10:]])
    raw = TEMP / f'reservoir-{tier}.glb'
    bpy.ops.export_scene.gltf(filepath=str(raw), export_format='GLB')
    subprocess.run(['npx', '--yes', '@gltf-transform/cli@4.5.1', 'optimize', str(raw),
                    str(OUT / f'reservoir-{tier}.glb'), '--compress', 'meshopt',
                    '--texture-compress', 'webp'], check=True)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(exist_ok=True)
    build('low', 6)
    build('medium', 12)
