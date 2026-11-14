"""Render one fixed evidence view; staging is never saved into the source model.

Via Blender MCP: runpy.run_path(this_file, init_globals={MODEL, STAGE, VIEW}).
All before/after pairs use identical lighting, color management and cameras.
"""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
MODEL = globals().get('MODEL', 'falcon')
STAGE = globals().get('STAGE', 'after')
VIEW = globals().get('VIEW', 'quarter')
source = ROOT / ('.runtime/a3/before' if STAGE == 'before' else 'cad') / (MODEL + '.blend')
bpy.ops.wm.open_mainfile(filepath=str(source))
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'
scene.render.threads = 8
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = -.5
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.16, .19, .23, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .45
heavy = MODEL == 'bluerov2_heavy'
scale = .53 if heavy else 1
centre = Vector((0, -.02 if heavy else -.22, -.025 if heavy else -.08))
if VIEW == 'quarter':
    target = centre
    location = centre + Vector((1.6, -2.3, 1.2)) * scale
    width = 1.9 * scale
elif VIEW == 'side':
    target = centre
    location = centre + Vector((3, 0, .20)) * scale
    width = 2.0 * scale
else:
    target = bpy.data.objects['Rotor_0'].matrix_world.translation.copy()
    axis = bpy.data.objects['Rotor_0'].matrix_world.to_quaternion() @ Vector((0, 0, 1))
    location = target + (axis * .8 + Vector((0, 0, .10))) * scale
    width = .65 * scale
bpy.ops.object.camera_add(location=location)
camera = bpy.context.object
camera.rotation_euler = (target - location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = width
scene.camera = camera
if VIEW != 'thruster':
    # Fit all original geometry, including the extended manipulator, with identical margins.
    points = [obj.matrix_world @ Vector(corner) for obj in scene.objects
              if obj.type in {'MESH', 'CURVE'} for corner in obj.bound_box]
    right = camera.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
    up = camera.rotation_euler.to_quaternion() @ Vector((0, 1, 0))
    px = [(point - target).dot(right) for point in points]
    py = [(point - target).dot(up) for point in points]
    camera.location += right * ((min(px) + max(px)) / 2) + up * ((min(py) + max(py)) / 2)
    camera.data.ortho_scale = max(max(px) - min(px), (max(py) - min(py)) * 1600 / 900) * 1.12
for position, energy, size in [((1, -2, 3), 330, 2.5), ((-2, -1, 1.3), 230, 2), ((0, 2, 2), 420, 2)]:
    bpy.ops.object.light_add(type='AREA', location=Vector(position) * scale)
    lamp = bpy.context.object
    lamp.data.energy = energy * scale ** 2
    lamp.data.shape = 'DISK'
    lamp.data.size = size * scale
    lamp.rotation_euler = (centre - lamp.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.render.image_settings.compression = 100
out = ROOT / 'docs/design/training-vehicles'
out.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(out / f'{MODEL}-{VIEW}-{STAGE}.png')
bpy.ops.render.render(write_still=True)
print(scene.render.filepath)
