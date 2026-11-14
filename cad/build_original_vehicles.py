"""Original generic fleet; Blender coordinates are (-starboard, -forward, up), metres.

No photographs, manufacturer CAD, textures or design references are used.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(sys.argv[sys.argv.index('--') + 1])
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.vehicles import VEHICLE_DEFINITIONS


def point(p):
    return (-p[1], -p[0], -p[2])


def material(name, color, metal, rough):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Roughness'].default_value = rough
    nodes = mat.node_tree.nodes
    for channel in ['Base Color', 'Roughness', 'Normal']:
        image = bpy.data.images.new(name + channel, width=128, height=128)
        pixels = []
        for y in range(128):
            for x in range(128):
                grain = ((x * 73 + y * 151) % 31) / 3100
                if channel == 'Base Color':
                    rgb = tuple(max(0, c - grain) for c in color)
                elif channel == 'Normal':
                    rgb = (.5 + grain, .5, 1)
                else:
                    rgb = (rough + grain,) * 3
                pixels.extend((*rgb, 1))
        image.pixels[:] = pixels
        image.pack()
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = image
        if channel != 'Base Color':
            image.colorspace_settings.name = 'Non-Color'
        if channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(texture.outputs['Color'], normal.inputs['Color'])
            mat.node_tree.links.new(normal.outputs['Normal'], shader.inputs[channel])
        else:
            mat.node_tree.links.new(texture.outputs['Color'], shader.inputs[channel])
    return mat


def box(name, pos, size, mat, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new('Machined edge radii', 'BEVEL')
    bevel.width = min(size) * .15
    bevel.segments = 3
    obj.modifiers.new('Corner normals', 'WEIGHTED_NORMAL')
    obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def cylinder(name, pos, radius, depth, axis, mat, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=depth, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_quaternion = Vector(axis).to_track_quat('Z', 'Y')
    obj.rotation_mode = 'QUATERNION'
    obj.data.materials.append(mat)
    obj.parent = parent
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def empty(name, pos, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = pos
    obj.parent = parent
    return obj


def build(identifier, slug):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    definition = VEHICLE_DEFINITIONS[identifier]
    steel = material('Brushed titanium', (.26, .29, .31), .85, .32)
    foam = material('Sealed buoyancy foam', (.32, .39, .30), 0, .68)
    dark = material('Elastomer seals', (.018, .023, .025), 0, .7)
    shell = material('Ceramic coating', (.52, .28, .16), .25, .4)
    glass = material('Optical ports', (.012, .04, .045), .55, .12)
    length = .92 if identifier == 'falcon' else .68 if identifier == 'x1' else .48
    width = .46 if identifier == 'falcon' else .32
    for x in [-width / 2, width / 2]:
        box('Skid rail', (x, 0, -.18), (.035, length, .035), dark)
        for y in [-length * .35, length * .35]:
            box('Upright', (x, y, 0), (.025, .025, .35), steel)
        box('Buoyancy cassette', (x * .55, -.03, .19), (.12, length * .7, .10), foam)
    for y in [-length * .35, length * .35]:
        box('Cross member', (0, y, -.12), (width, .025, .025), steel)
    cylinder('Pressure vessel', (0, -.07, .02), .07, length * .65, (0, 1, 0), steel)
    for y in [-length * .3, length * .2]:
        cylinder('End flange', (0, y, .02), .079, .018, (0, 1, 0), dark)
        for i in range(8):
            a = i * math.tau / 8
            cylinder('Captive bolt', (.068 * math.cos(a), y + .012, .02 + .068 * math.sin(a)),
                     .005, .009, (0, 1, 0), steel)
    if identifier == 'x1':
        box('Observation fairing', (0, .04, .08), (.22, .31, .14), shell)
    if identifier == 'falcon':
        box('Tool electronics tray', (0, -.06, -.22), (.31, .55, .09), shell)
    for i, (_, pos, axis) in enumerate(definition.thrusters):
        mount = empty('Motor mount', point(pos))
        mount.rotation_euler = Vector(point(axis)).to_track_quat('Z', 'Y').to_euler()
        # Open duct: annulus instead of an opaque cylinder across the thrust path.
        bpy.ops.mesh.primitive_torus_add(major_radius=.052, minor_radius=.009, major_segments=40,
                                        minor_segments=12, location=(0, 0, 0))
        duct = bpy.context.object
        duct.name = 'Duct'
        duct.data.materials.append(dark)
        duct.parent = mount
        rotor = empty('Rotor', (0, 0, 0), mount)
        rotor['role'] = 'rotor'
        rotor['thruster_index'] = i
        cylinder('Hub', (0, 0, 0), .013, .04, (0, 0, 1), steel, rotor)
        for j in range(3):
            blade = box('Swept blade', (.025, 0, 0), (.045, .014, .006), shell, rotor)
            a = j * math.tau / 3
            blade.location = (.025 * math.cos(a), .025 * math.sin(a), 0)
            blade.rotation_euler = (.28, .18, a)
    gimbal = empty('camera_gimbal', point(definition.camera_body))
    cylinder('Camera bezel', (0, 0, 0), .038, .045, (0, 1, 0), steel, gimbal)
    cylinder('Camera lens', (0, -.024, 0), .029, .006, (0, 1, 0), glass, gimbal)
    for i, p in enumerate(definition.lamp_body):
        pivot = empty(f'lamp_pivot_{i}', point(p))
        cylinder('Lamp housing', (0, 0, 0), .029, .06, (0, 1, 0), steel, pivot)
        cylinder('Lamp optic', (0, -.032, 0), .024, .006, (0, 1, 0), foam, pivot)
    cylinder('Tether gland', point(definition.gland_body), .022, .055, (0, 0, 1), dark)
    if identifier == 'falcon':
        yaw = empty('arm_yaw', point(definition.arm_mount_body))
        parent = yaw
        for name, offset, length in [('arm_shoulder', 0, .32), ('arm_elbow', .32, .30),
                                     ('arm_wrist', .30, .12)]:
            joint = empty(name, (0, -offset, 0), parent)
            cylinder('Joint pin', (0, 0, 0), .03, .07, (1, 0, 0), steel, joint)
            for x in [-.025, .025]:
                box('Arm link', (x, -length / 2, 0), (.018, length, .025), steel, joint)
            cylinder('Hydraulic ram', (0, -length / 2, .03), .012, length * .7, (0, 1, 0), dark, joint)
            parent = joint
        for name, sign in [('arm_jaw_left', 1), ('arm_jaw_right', -1)]:
            jaw = empty(name, (sign * .03, -.075, 0), parent)
            box('Grip finger', (0, -.04, 0), (.015, .08, .025), steel, jaw)
        empty('arm_tip', (0, -.12, 0), parent)
    out = ROOT / '.runtime/assets'
    out.mkdir(parents=True, exist_ok=True)
    for lod, ratio in enumerate([1, .55, .25]):
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                modifier = obj.modifiers.get('LOD') or obj.modifiers.new('LOD', 'DECIMATE')
                modifier.ratio = ratio
        bpy.ops.export_scene.gltf(filepath=str(out / f'{slug}-lod{lod}.glb'), export_format='GLB',
                                  export_extras=True, export_apply=True)


for identifier, slug in [('x1', 'observation'), ('falcon', 'work'), ('bluerov2_heavy', 'openframe')]:
    build(identifier, slug)
