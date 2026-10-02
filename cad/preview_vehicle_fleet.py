"""Offline visual checks of generated GLBs, rendered to .runtime/."""
import sys
import os
import shutil
from pathlib import Path
import bpy
from mathutils import Vector

root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
out=root/'.runtime'; out.mkdir(exist_ok=True)
for model in (sys.argv[sys.argv.index('--')+2:] or ('bluerov2_heavy','falcon')):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    path=root/'sim'/'rov.glb' if model=='x1' else root/'simulator'/'viewer'/'models'/f'{model}.glb'
    bpy.ops.import_scene.gltf(filepath=str(path))
    if model=='x1':
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
        centre=Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)])
        for o in list(bpy.context.scene.objects):
            if o.parent is None:o.location-=centre
    scene=bpy.context.scene
    scene.render.engine='CYCLES'; scene.cycles.samples=12;scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=2
    scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-.7
    scene.world.color=(.28,.28,.28)
    bpy.ops.object.camera_add(location=(1.4,-2.0,1.05))
    camera=bpy.context.object; camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'; camera.data.ortho_scale=1.4 if model in ('falcon','x1') else .9; scene.camera=camera
    for name,loc,energy,size in [('key',(0,-2,3),350,3),('fill',(-2,1,2),250,2),('front fill',(0,-3,.25),180,2)]:
        bpy.ops.object.light_add(type='AREA',location=loc); lamp=bpy.context.object; lamp.name=name; lamp.data.energy=energy; lamp.data.shape='DISK';lamp.data.size=size
        lamp.rotation_euler=(-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x=1000;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.filepath=str(out/f'{model}-model.png')
    if model!='falcon':bpy.ops.render.render(write_still=True)
    if model=='falcon':
        for view,location in [('front',(0,-3,-.08)),('side',(3,-.26,-.08)),('quarter',(1.6,-2.3,1.05))]:
            if os.environ.get('ROV_PREVIEW_VIEW') and os.environ['ROV_PREVIEW_VIEW']!=view:continue
            camera.data.ortho_scale=1.2 if view=='front' else 1.8
            camera.location=location
            target=Vector((0,0 if view=='front' else -.26,-.08))
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(out/f'falcon-reference-{view}.png')
            bpy.ops.render.render(write_still=True)
        shutil.copyfile(out/'falcon-reference-quarter.png',out/'falcon-model.png')
