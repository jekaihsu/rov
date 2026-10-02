"""Blender offline import, GLB export and views of manufacturer reference geometry."""
from pathlib import Path
import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parents[1] / '.runtime' / 'bluerov-reference'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(OUT / 'bluerov2-r3-preview.stl'))
obj = bpy.context.object
obj.name = 'Official_BlueROV2_R3_standard_reference'
obj['source_url'] = 'https://cad.bluerobotics.com/BLUEROV2-R3.zip'
obj['license_status'] = 'Local reference only; commercial redistribution not verified'
obj['geometry_note'] = 'Manufacturer STL, 0.6 mm vertex clustering; standard R3, not Heavy'
material = bpy.data.materials.new('Neutral inspection material (not original finish)')
material.diffuse_color = (.29, .34, .39, 1)
material.use_nodes = True
shader = material.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (.29, .34, .39, 1)
shader.inputs['Roughness'].default_value = .36
shader.inputs['Metallic'].default_value = .15
obj.data.materials.append(material)
print('IMPORTED', len(obj.data.vertices), 'vertices', len(obj.data.polygons), 'faces', tuple(obj.dimensions), flush=True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'bluerov2-r3-reference-preview.glb'), export_format='GLB', use_selection=True, export_extras=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'
scene.render.threads = 3
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.17, .19, .22, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .6
for name, loc, energy, size in [('key', (1,-1,2), 180, 1.5), ('fill', (-1,1,1), 110, 1), ('rim', (0,1,.8), 70, .6)]:
    bpy.ops.object.light_add(type='AREA', location=loc)
    light = bpy.context.object
    light.name = name; light.data.energy = energy; light.data.size = size
    light.rotation_euler = (-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add()
camera = bpy.context.object; scene.camera = camera
camera.data.type = 'ORTHO'; camera.data.ortho_scale = .66
scene.render.resolution_x = 1200; scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
for view, loc in [('quarter', (.8,-1,.6)), ('opposite', (-.8,1,.6)), ('side', (0,-1,.02))]:
    camera.location = loc
    camera.rotation_euler = (-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = str(OUT / f'bluerov2-r3-{view}.png')
    bpy.ops.render.render(write_still=True)
print('REFERENCE_READY', OUT, flush=True)
