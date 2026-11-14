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


TEXTURES = {}


def surface_map(channel):
    """Shared 2K original maps: machining grain, fine scratches and sealed panel seams."""
    import numpy as np
    if channel in TEXTURES:
        return TEXTURES[channel]
    size = 2048
    y, x = np.mgrid[:size, :size]
    seams = ((x % 512 < 4) | (y % 512 < 4)).astype(np.float32)
    scratches = ((x * 13 + y * 7) % 997 < 2).astype(np.float32)
    grain = .008 * np.sin(y * .8) + .005 * np.sin(x * .17 + y * .3)
    pixels = np.ones((size, size, 4), dtype=np.float32)
    if channel == 'Base Color':
        value = .85 + grain - seams * .24 - scratches * .07
        pixels[:, :, :3] = value[:, :, None]
    elif channel == 'Normal':
        pixels[:, :, 0] = .5 + grain
        pixels[:, :, 1] = .5 - seams * .08
        pixels[:, :, 2] = 1
    else:
        value = .65 + grain + scratches * .12 if channel == 'Roughness' else 1 - seams * .25
        pixels[:, :, :3] = value[:, :, None]
    image = bpy.data.images.new('Original 2K ' + channel, width=size, height=size)
    if channel != 'Base Color':
        image.colorspace_settings.name = 'Non-Color'
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    TEXTURES[channel] = image
    return image


def material(name, color, metal, rough):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat['original_base_color'] = list(color) + [1]
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Roughness'].default_value = rough
    for channel in ['Base Color', 'Roughness', 'Normal', 'Occlusion']:
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = surface_map(channel)
        if channel == 'Occlusion':
            group = bpy.data.node_groups.get('glTF Material Output')
            if group is None:
                group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
                group.interface.new_socket(name='Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
            output = nodes.new('ShaderNodeGroup')
            output.node_tree = group
            links.new(texture.outputs['Color'], output.inputs['Occlusion'])
        elif channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            normal.inputs['Strength'].default_value = .25
            links.new(texture.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], shader.inputs[channel])
        elif channel == 'Base Color':
            tint = nodes.new('ShaderNodeMixRGB')
            tint.blend_type = 'MULTIPLY'
            tint.inputs[0].default_value = 1
            tint.inputs[2].default_value = (*color, 1)
            links.new(texture.outputs['Color'], tint.inputs[1])
            links.new(tint.outputs['Color'], shader.inputs[channel])
        else:
            links.new(texture.outputs['Color'], shader.inputs[channel])
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
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector(axis).to_track_quat('Z', 'Y')
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
        for offset in [-.025, .025]:
            bpy.ops.mesh.primitive_torus_add(major_radius=.052, minor_radius=.004,
                                            major_segments=40, minor_segments=8)
            rim = bpy.context.object
            rim.name = 'Duct lip'
            rim.parent = mount
            rim.location = (0, 0, offset)
            rim.data.materials.append(steel)
        for j in range(4):
            angle = j * math.tau / 4
            support = box('Motor stator', (.03 * math.cos(angle), .03 * math.sin(angle), -.02),
                          (.045, .006, .008), steel, mount)
            support.rotation_euler.z = angle
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
    if identifier == 'x1':
        add_observation_detail(steel, foam, dark, shell)
    out = ROOT / '.runtime/assets'
    out.mkdir(parents=True, exist_ok=True)
    for lod, ratio in enumerate([1, .55, .25]):
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                modifier = obj.modifiers.get('LOD') or obj.modifiers.new('LOD', 'DECIMATE')
                modifier.ratio = ratio
        bpy.ops.export_scene.gltf(filepath=str(out / f'{slug}-lod{lod}.glb'), export_format='GLB',
                                  export_extras=True, export_apply=True)


def cable(name, points, radius, mat):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for point_node, position in zip(spline.bezier_points, points):
        point_node.co = position
        point_node.handle_left_type = 'AUTO'
        point_node.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def add_observation_detail(steel, foam, dark, shell):
    # Split buoyancy cassettes with retaining bands and recessed fasteners.
    for x in [-.088, .088]:
        for y in [-.15, .02, .16]:
            box('Cassette retention strap', (x, y, .247), (.125, .012, .008), steel)
            for dx in [-.047, .047]:
                cylinder('Recessed socket screw', (x + dx, y, .253), .006, .004, (0, 0, 1), dark)
        box('Cassette seam', (x, -.065, .243), (.122, .004, .005), dark)
    for x in [-.16, .16]:
        cable('Insulated lifting handle', [(x, -.13, .12), (x, -.08, .30), (x, .10, .30),
                                          (x, .15, .12)], .012, dark)
        for y in [-.22, .22]:
            box('Corner gusset', (x, y, -.10), (.05, .07, .065), shell)
            for z in [-.12, -.08]:
                cylinder('Frame fastener', (x, y, z), .005, .055, (1, 0, 0), steel)
    # Pressure vessel saddles, bolted end caps, wet-mate electrical connectors.
    for y in [-.20, .12]:
        box('Vessel saddle', (0, y, -.055), (.16, .035, .03), shell)
        for i in range(10):
            angle = i * math.tau / 10
            cylinder('End cap bolt', (.071 * math.cos(angle), y - .02, .02 + .071 * math.sin(angle)),
                     .005, .012, (0, 1, 0), steel)
    for x in [-.04, 0, .04]:
        cylinder('Bulkhead connector', (x, .23, .015), .014, .04, (0, 1, 0), steel)
        cylinder('Connector strain relief', (x, .256, .015), .010, .025, (0, 1, 0), dark)
        cable('Wet mate harness', [(x, .27, .015), (x, .30, -.03), (x + .06, .18, -.07),
                                   (x + .06, -.06, -.06)], .004, dark)
    gland = point(VEHICLE_DEFINITIONS['x1'].gland_body)
    cable('Tether strain relief', [gland, (gland[0], gland[1] + .03, gland[2] + .06),
                                   (.04, .28, .14)], .009, dark)
    for x in [-.12, .12]:
        cable('Lamp electrical harness', [(x, -.36, -.02), (x, -.28, .01), (x, -.15, -.05)], .004, dark)
    for y in [-.08, .08]:
        box('Fairing panel joint', (0, y, .153), (.20, .003, .004), dark)
        for x in [-.08, .08]:
            cylinder('Panel quarter-turn fastener', (x, y, .157), .004, .006, (0, 0, 1), steel)
    # Original maintenance plate, converted to mesh so no font dependency ships.
    box('Service plate', (0, -.02, .157), (.12, .055, .003), steel)
    bpy.ops.object.text_add(location=(-.05, -.03, .160))
    label = bpy.context.object
    label.name = 'Original service engraving'
    label.data.body = 'OBS / 01'
    label.data.size = .016
    label.data.extrude = .00015
    label.data.materials.append(dark)
    bpy.ops.object.convert(target='MESH')


for identifier, slug in [('x1', 'observation')]:
    build(identifier, slug)
