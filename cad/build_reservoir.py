"""Rebuild original CC0 reservoir primitives and procedural hex concrete, no reference imagery.
Run blender -b --python cad/build_reservoir.py. No blend saved; pinned meshopt/WebP exporter.
"""
import sys
import json
import math
import subprocess
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'simulator'))
from qysim.reservoir import layout, CAMERAS

OUT = ROOT/'simulator/viewer/models/reservoir'
TEMP = ROOT/'simulator/output/reservoir'
COLORS = dict(concrete=(.51,.49,.42),steel=(.28,.34,.32),wood=(.33,.26,.2),white=(.84,.84,.78),
              blue=(.13,.42,.71),orange=(.88,.49,.2),lime=(.77,.93,.15))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    TEMP.mkdir(parents=True,exist_ok=True)
    # Hand-generated hexagonal joint pattern, deterministic; no photographs enter this pipeline.
    subprocess.run(['python','-c', '''from PIL import Image, ImageDraw
import random, math, sys
r=random.Random(71)
im=Image.new('RGB',(256,256),(58,59,51))
d=ImageDraw.Draw(im)
for col in range(-1,10):
 for row in range(-1,9):
  x=col*32
  y=(row+(col%2)*.5)*256/7
  shade=r.randrange(115,155)
  pts=[(x+dx,y+dy) for dx,dy in [(21,0),(10.5,128/7),(-10.5,128/7),(-21,0),(-10.5,-128/7),(10.5,-128/7)]]
  d.polygon(pts,fill=(shade,shade,shade-12),outline=(60,61,53),width=2)
im.save(sys.argv[1])
im.save(sys.argv[2],lossless=True)
''',str(TEMP/'concrete.png'),str(OUT/'concrete.webp')],check=True)
    report = {}
    for tier,segments in [('default',12),('low',6)]:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        mats = {}
        for kind,color in COLORS.items():
            mat = bpy.data.materials.new(kind)
            mat.use_nodes = True
            shader = mat.node_tree.nodes.get('Principled BSDF')
            shader.inputs['Base Color'].default_value = (*color,1)
            shader.inputs['Roughness'].default_value = .87
            if kind == 'concrete':
                tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex.image = bpy.data.images.load(str(TEMP/'concrete.png'))
                mat.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
            mats[kind] = mat
        for ob in layout():
            if hasattr(ob,'half'):
                bpy.ops.mesh.primitive_cube_add(size=2,location=(ob.center[0],ob.center[1],-ob.center[2]))
                obj = bpy.context.object
                obj.scale = ob.half
            else:
                a = Vector((ob.p0[0],ob.p0[1],-ob.p0[2]))
                b = Vector((ob.p1[0],ob.p1[1],-ob.p1[2]))
                bpy.ops.mesh.primitive_cylinder_add(vertices=segments,radius=ob.radius,depth=(b-a).length,
                                                    location=(a+b)/2)
                obj = bpy.context.object
                obj.rotation_euler = (b-a).to_track_quat('Z','Y').to_euler()
            obj.name = ob.name
            obj.data.materials.append(mats[ob.kind[4:]])
        # The distant bank and bridge use the same deterministic formula as viewer/reservoir.js.
        forest = bpy.data.materials.new('forest')
        forest.diffuse_color = (.15,.25,.13,1)
        mats['forest'] = forest
        for i in range(15):
            bank = (i-7)*32
            height = 32+18*math.sin(i*7)**2
            north = 230+18*math.sin(i*.7)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=14,ring_count=8,location=(north,-bank,-8))
            obj = bpy.context.object
            obj.scale = (58,57,height)
            obj.data.materials.append(forest)
            count = 12 if tier == 'low' else 36
            for j in range(count):
                angle = j*2.39996
                radius = 48*math.sqrt((j+.5)/count)
                x,z = radius*math.cos(angle),radius*math.sin(angle)
                y = height*math.sqrt(max(0,1-(x/65)**2-(z/58)**2))
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,
                    location=(north+z,-bank-x,-8+y+3))
                obj = bpy.context.object
                obj.scale = (5,5,6)
                obj.data.materials.append(forest)
        bridge_parts = [(0,19,150,180,1.4,6)]
        bridge_parts += [(i*24,9,150,2,20,3) for i in range(-3,4)]
        bridge_parts += [(0,20.5,z,180,.6,.3) for z in (147,153)]
        for x,y,z,a,b,c in bridge_parts:
            bpy.ops.mesh.primitive_cube_add(size=1,location=(z,-x,y))
            obj = bpy.context.object
            obj.scale = (c,a,b)
            obj.data.materials.append(mats['concrete'])
        bpy.context.view_layer.update()
        counts = dict(above=0,underwater=0)
        for obj in list(bpy.context.scene.objects):
            obj.data.calc_loop_triangles()
            # Crossing meshes count against both budgets.
            zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
            n = len(obj.data.loop_triangles)
            if max(zs)>=0:
                counts['above'] += n
            if min(zs)<=0:
                counts['underwater'] += n
        assert counts['above'] <= 200_000, counts
        assert counts['underwater'] <= 150_000, counts
        for kind,mat in mats.items():
            bpy.ops.object.select_all(action='DESELECT')
            objects = [o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.materials[0]==mat]
            for obj in objects:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = objects[0]
            bpy.ops.object.join()
        raw = TEMP/f'{tier}.glb'
        target = OUT/f'{tier}.glb'
        bpy.ops.export_scene.gltf(filepath=str(raw),export_format='GLB')
        subprocess.run(['npx','--yes','@gltf-transform/cli@4.5.1','optimize',str(raw),str(target),
                        '--compress','meshopt','--texture-compress','webp'],check=True)
        report[tier] = dict(portable_triangles=counts,bytes=target.stat().st_size)
    (OUT/'cameras.json').write_text(json.dumps(CAMERAS,indent=2)+'\n')
    (OUT/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
