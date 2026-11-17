"""Original YX fleet visuals: Model R, Model O and Model V.

Three levels of detail, authored about the centre of gravity. Thruster positions
and axes come from simulator/qysim/vehicles.py (the spin axis is that thrust
axis). Blade count is an estimated visual (the physics file does not publish a
blade count): three blades, pitched so positive rotation about the thrust axis
produces positive thrust. No logos, lettering or manufacturer appearance.

Movable and anchor names the viewer already looks up (keep these):
  yx_frame                         extras.frame = cg
  ROTOR_i / Rotor_i                extras.role = rotor, thruster_index, axis
  camera_gimbal, lamp_pivot_0, lamp_pivot_1
  anchor_camera, anchor_tether, anchor_arm_mount, anchor_lamp_0, anchor_lamp_1
  Model V only: arm_yaw, arm_shoulder, arm_elbow, arm_wrist,
                arm_jaw_left, arm_jaw_right, arm_tip

Run from the repository root:
  blender -b --factory-startup -P cad/build_yx_vehicles.py -- .
Raw GLBs land in simulator/output/yx-vehicles/raw/. Pack with cad/pack_yx_vehicles.py.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.vehicles import get_vehicle_definition

OUT = ROOT / 'simulator' / 'output' / 'yx-vehicles' / 'raw'
TAU = math.pi * 2
BUDGETS = (40000, 12000, 3000)
FILES = {'x1': 'rov', 'bluerov2_heavy': 'bluerov2_heavy', 'falcon': 'falcon'}
# Segment counts and which close-up parts exist at each level.
LEVELS = (
    {'sides': 24, 'blade': (7, 6), 'screws': True, 'cables': True, 'guard': True, 'struts': True},
    {'sides': 14, 'blade': (4, 3), 'screws': False, 'cables': True, 'guard': False, 'struts': True},
    {'sides': 8, 'blade': (0, 0), 'screws': False, 'cables': False, 'guard': False, 'struts': False},
)
# Shared PBR rules. (base RGB, metallic, roughness). One rule per material class.
PBR = {
    'aluminium': ((0.62, 0.64, 0.66), 0.92, 0.34),
    'polymer': ((0.10, 0.11, 0.12), 0.04, 0.48),
    'foam': ((0.78, 0.76, 0.70), 0.0, 0.74),
    'acrylic': ((0.62, 0.78, 0.84), 0.0, 0.05),
    'propeller': ((0.16, 0.17, 0.18), 0.12, 0.40),
    'fastener': ((0.75, 0.76, 0.77), 0.95, 0.24),
    'cable': ((0.06, 0.07, 0.08), 0.0, 0.64),
    'lamp': ((0.93, 0.95, 0.92), 0.0, 0.16),
    'recess': ((0.02, 0.02, 0.025), 0.4, 0.45),
}


def point(frd):
    """FRD metres to Blender (X port, Y aft, Z up). glTF export then matches Three.js."""
    forward, starboard, down = frd
    return Vector((-starboard, -forward, -down))


def three_axis(frd):
    """Unit thrust axis in Three.js coordinates, stored on the rotor for the viewer."""
    forward, starboard, down = frd
    length = math.sqrt(forward * forward + starboard * starboard + down * down) or 1.0
    return [-starboard / length, -down / length, forward / length]


def axis_matrix(position, axis):
    """Local +Z aligned with a thrust or bolt axis, origin at position."""
    rotation = Vector((0.0, 0.0, 1.0)).rotation_difference(point(axis).normalized())
    matrix = rotation.to_matrix().to_4x4()
    matrix.translation = point(position)
    return matrix


def at_matrix(position):
    matrix = Matrix.Identity(4)
    matrix.translation = point(position)
    return matrix


def finish_mesh(mesh):
    edit = bmesh.new()
    edit.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(edit, faces=edit.faces)
    edit.to_mesh(mesh)
    edit.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.update()


def make_mesh(name, verts, faces, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    finish_mesh(mesh)
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    mesh.update()
    return mesh


def uv_cylinder(mesh):
    """Wrap a lathe so the foam pore map repeats around and along the tube."""
    layer = mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            around = (math.atan2(co.y, co.x) / TAU) * 3.0
            layer.data[loop_index].uv = (around, co.z * 4.0)


def lathe(profile, sides):
    verts = []
    for radius, zed in profile:
        for index in range(sides):
            angle = TAU * index / sides
            verts.append((radius * math.cos(angle), radius * math.sin(angle), zed))
    faces = []
    rows = len(profile)
    for row in range(rows - 1):
        for index in range(sides):
            nxt = (index + 1) % sides
            a = row * sides + index
            b = row * sides + nxt
            c = (row + 1) * sides + nxt
            d = (row + 1) * sides + index
            faces.append((a, b, c, d))
    return verts, faces


def tube(radius, length, sides, wall=0.0):
    """Open cylinder along local +Z. wall > 0 makes a hollow shroud."""
    half = length / 2
    if wall <= 0:
        return lathe([(radius, -half), (radius, half)], sides)
    outer = radius + wall
    profile = [(outer, -half), (outer, half), (radius, half), (radius, -half), (outer, -half)]
    return lathe(profile, sides)


def box_local(size):
    """FRD-aligned box centred on the origin: size is (forward, starboard, down)."""
    hy = size[0] / 2
    hx = size[1] / 2
    hz = size[2] / 2
    verts = []
    for x in (-hx, hx):
        for y in (-hy, hy):
            for z in (-hz, hz):
                verts.append((x, y, z))
    faces = [
        (0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
        (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3),
    ]
    return verts, faces


def set_input(node, names, value):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return


def pore_images():
    """Syntactic-foam colour and pore normal. Original pattern, not a scan."""
    size = 128
    base_color = (0.78, 0.76, 0.70)
    color = bpy.data.images.new('foam_color', size, size, alpha=False, float_buffer=False)
    normal = bpy.data.images.new('foam_pores', size, size, alpha=False, float_buffer=False)
    color.colorspace_settings.name = 'sRGB'
    normal.colorspace_settings.name = 'Non-Color'
    color_px = [0.0] * (size * size * 4)
    normal_px = [0.0] * (size * size * 4)
    height = []
    for y in range(size):
        row = []
        for x in range(size):
            cell_x = (x / size) * 6.0
            cell_y = (y / size) * 6.0
            fx = abs((cell_x % 1.0) - 0.5)
            fy = abs((cell_y % 1.0) - 0.5)
            radius = math.sqrt(fx * fx + fy * fy)
            dent = max(0.0, 1.0 - radius / 0.36) ** 2
            grain = math.sin(x * 0.7) * math.sin(y * 0.5) * 0.04
            row.append(dent * 0.7 + grain)
        height.append(row)
    for y in range(size):
        for x in range(size):
            left = height[y][(x - 1) % size]
            right = height[y][(x + 1) % size]
            down = height[(y - 1) % size][x]
            up = height[(y + 1) % size][x]
            nx = (left - right) * 3.0
            ny = (down - up) * 3.0
            nz = 1.0
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            shade = 1.0 - 0.28 * max(0.0, height[y][x])
            base = (y * size + x) * 4
            color_px[base] = base_color[0] * shade
            color_px[base + 1] = base_color[1] * shade
            color_px[base + 2] = base_color[2] * shade
            color_px[base + 3] = 1.0
            normal_px[base] = nx / length * 0.5 + 0.5
            normal_px[base + 1] = ny / length * 0.5 + 0.5
            normal_px[base + 2] = nz / length * 0.5 + 0.5
            normal_px[base + 3] = 1.0
    color.pixels.foreach_set(color_px)
    normal.pixels.foreach_set(normal_px)
    color.pack()
    normal.pack()
    return color, normal


def new_material(name, color, metallic, roughness, pores=None, emit=0.0, coat=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    set_input(bsdf, ('Base Color',), (*color, 1.0))
    set_input(bsdf, ('Metallic',), metallic)
    set_input(bsdf, ('Roughness',), roughness)
    if emit:
        set_input(bsdf, ('Emission Color', 'Emission'), (*color, 1.0))
        set_input(bsdf, ('Emission Strength',), emit)
    if coat:
        set_input(bsdf, ('Coat Weight', 'Clearcoat'), coat)
        set_input(bsdf, ('Coat Roughness', 'Clearcoat Roughness'), 0.08)
    if pores is not None:
        color_image, normal_image = pores
        tree = material.node_tree
        coord = tree.nodes.new('ShaderNodeTexCoord')
        color_tex = tree.nodes.new('ShaderNodeTexImage')
        color_tex.image = color_image
        normal_tex = tree.nodes.new('ShaderNodeTexImage')
        normal_tex.image = normal_image
        normal = tree.nodes.new('ShaderNodeNormalMap')
        normal.inputs['Strength'].default_value = 1.15
        tree.links.new(coord.outputs['UV'], color_tex.inputs['Vector'])
        tree.links.new(coord.outputs['UV'], normal_tex.inputs['Vector'])
        tree.links.new(color_tex.outputs['Color'], bsdf.inputs['Base Color'])
        tree.links.new(normal_tex.outputs['Color'], normal.inputs['Color'])
        tree.links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])
    return material


def blade_surface(hub, tip, count, stations, chordwise, pitch):
    """Helical blades about local +Z. Positive pitch drives water toward -Z."""
    verts = []
    faces = []
    if stations < 2 or chordwise < 2:
        for blade in range(count):
            phase = TAU * blade / count
            corners = []
            for radius, along in ((hub, -0.012), (hub, 0.008), (tip, 0.006), (tip, -0.010)):
                beta = math.atan(pitch / (TAU * max(radius, 0.01)))
                tangential = along * math.cos(beta)
                axial = -along * math.sin(beta)
                angle = phase + tangential / radius
                corners.append(len(verts))
                verts.append((radius * math.cos(angle), radius * math.sin(angle), axial))
            faces.append((corners[0], corners[1], corners[2], corners[3]))
        return verts, faces
    for blade in range(count):
        phase = TAU * blade / count
        loops = []
        for station in range(stations):
            span = station / (stations - 1)
            radius = hub + (tip - hub) * span
            chord = 0.040 * (1.0 - 0.42 * span * span) + 0.008
            beta = math.atan(pitch / (TAU * radius))
            skew = 0.22 * span * span
            thick = 0.0044 * (1.0 - 0.55 * span) + 0.0014
            upper = []
            lower = []
            for step in range(chordwise):
                t = -0.5 + step / (chordwise - 1)
                shape = max(0.0, 1.0 - (2.0 * t) ** 2)
                camber = 0.055 * chord * shape
                half = 0.5 * thick * shape ** 0.6
                upper.append((t * chord, camber + half))
                lower.append((t * chord, camber - half))
            outline = upper + list(reversed(lower[1:-1]))
            loop = []
            for along, across in outline:
                tangential = along * math.cos(beta) + across * math.sin(beta)
                axial = -along * math.sin(beta) + across * math.cos(beta)
                angle = phase + skew + tangential / radius
                loop.append(len(verts))
                verts.append((radius * math.cos(angle), radius * math.sin(angle), axial))
            loops.append(loop)
        width = len(loops[0])
        for a, b in zip(loops, loops[1:]):
            for index in range(width):
                nxt = (index + 1) % width
                faces.append((a[index], a[nxt], b[nxt], b[index]))
        faces.append(tuple(reversed(loops[0])))
        faces.append(tuple(loops[-1]))
    return verts, faces


class FleetBuilder:
    """One vehicle at one level of detail."""

    def __init__(self, model_id, level):
        self.model_id = model_id
        self.level = level
        self.spec = LEVELS[level]
        self.definition = get_vehicle_definition(model_id)
        self.shared = {}
        self.serial = 0
        self.materials = {}
        clear_scene()
        pores = pore_images()
        for name, (color, metal, rough) in PBR.items():
            emit = 4.0 if name == 'lamp' else 0.0
            coat = 1.0 if name == 'acrylic' else 0.0
            foam = pores if name == 'foam' else None
            self.materials[name] = new_material(name, color, metal, rough, foam, emit, coat)

    def name(self, prefix):
        self.serial += 1
        return f'{prefix}_{self.serial:03d}'

    def add(self, prefix, verts, faces, material, matrix, shared=None, unique=False, smooth=True):
        key = None if unique else shared
        mesh = None if key is None else self.shared.get(key)
        if mesh is None:
            mesh = make_mesh(self.name(prefix), verts, faces, smooth=smooth)
            if material == 'foam' and not mesh.uv_layers:
                uv_cylinder(mesh)
            if not mesh.materials:
                mesh.materials.append(self.materials[material])
            if key is not None:
                self.shared[key] = mesh
        obj = bpy.data.objects.new(self.name(prefix), mesh)
        bpy.context.collection.objects.link(obj)
        obj.matrix_world = matrix
        return obj

    def empty(self, obj_name, position, props=None):
        obj = bpy.data.objects.new(obj_name, None)
        bpy.context.collection.objects.link(obj)
        obj.empty_display_size = 0.04
        obj.matrix_world = at_matrix(position)
        for key, value in (props or {}).items():
            obj[key] = value
        return obj

    def parent(self, obj, parent):
        bpy.context.view_layer.update()
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world

    def screw(self, position, axis):
        if not self.spec['screws']:
            return
        head = lathe([(0.0, 0.0032), (0.0052, 0.0032), (0.0052, 0.0006), (0.0024, 0.0006),
                      (0.0024, -0.004), (0.0, -0.004)], 6)
        recess = lathe([(0.0, 0.0034), (0.0015, 0.0034), (0.0015, 0.0016), (0.0, 0.0016)], 6)
        self.add('screw', head[0], head[1], 'fastener', axis_matrix(position, axis),
                 unique=True, smooth=False)
        self.add('recess', recess[0], recess[1], 'recess', axis_matrix(position, axis),
                 unique=True, smooth=False)

    def rod(self, a, b, radius, material, shared):
        start = Vector(a)
        end = Vector(b)
        direction = end - start
        length = direction.length or 0.001
        centre = tuple((start + end) / 2)
        verts, faces = tube(radius, length, self.spec['sides'])
        self.add('rod', verts, faces, material, axis_matrix(centre, tuple(direction)), shared=shared)

    def thruster(self, index, position, axis):
        sides = self.spec['sides']
        radius = 0.046 if self.model_id != 'falcon' else 0.062
        length = 0.07 if self.model_id != 'falcon' else 0.09
        matrix = axis_matrix(position, axis)
        duct = tube(radius, length, sides, wall=0.007)
        self.add('duct', duct[0], duct[1], 'polymer', matrix, shared='duct')
        band = lathe([
            (radius + 0.006, -0.008), (radius + 0.011, -0.007),
            (radius + 0.011, 0.007), (radius + 0.006, 0.008),
        ], sides)
        self.add('band', band[0], band[1], 'aluminium', matrix, shared='band')
        motor = lathe([
            (0.0, -length * 0.95), (radius * 0.42, -length * 0.95),
            (radius * 0.42, -length * 0.35), (radius * 0.28, -length * 0.22),
            (0.0, -length * 0.22),
        ], max(6, sides // 2))
        self.add('motor', motor[0], motor[1], 'aluminium', matrix, shared='motor')
        if self.spec['struts']:
            strut = box_local((radius * 0.85, 0.006, 0.008))
            for spoke in range(3):
                angle = TAU * spoke / 3 + 0.4
                spoke_matrix = matrix.copy()
                spin = Matrix.Rotation(angle, 4, 'Z')
                offset = Matrix.Translation((math.cos(angle) * radius * 0.45,
                                              math.sin(angle) * radius * 0.45, -length * 0.45))
                self.add('strut', strut[0], strut[1], 'aluminium',
                         spoke_matrix @ offset @ spin, shared='strut')
        if self.spec['guard']:
            lip = length * 0.46
            ring = lathe([
                (radius * 0.72, lip), (radius * 0.97, lip),
                (radius * 0.97, lip + 0.005), (radius * 0.72, lip + 0.005),
            ], sides)
            self.add('guard_ring', ring[0], ring[1], 'polymer', matrix, shared='guard-ring')
            spoke = box_local((radius * 0.58, 0.0035, 0.004))
            for spoke_index in range(4):
                angle = TAU * spoke_index / 4 + 0.35
                offset = Matrix.Translation((math.cos(angle) * radius * 0.46,
                                              math.sin(angle) * radius * 0.46, lip + 0.002))
                spin = Matrix.Rotation(angle, 4, 'Z')
                self.add('guard_spoke', spoke[0], spoke[1], 'polymer',
                         matrix @ offset @ spin, shared='guard-spoke')
        stations, chordwise = self.spec['blade']
        blade_verts, blade_faces = blade_surface(
            radius * 0.22, radius * 0.92, 3, stations, chordwise, pitch=0.055)
        hub_sides = max(6, sides // 2)
        hub = lathe([
            (0.0, -0.004), (radius * 0.2, -0.004), (radius * 0.22, 0.004),
            (radius * 0.12, 0.016), (0.0, 0.022),
        ], hub_sides)
        rotor_verts = hub[0] + [(v[0], v[1], v[2]) for v in blade_verts]
        rotor_faces = list(hub[1])
        base = len(hub[0])
        rotor_faces += [tuple(base + index for index in face) for face in blade_faces]
        mesh = make_mesh(self.name('prop'), rotor_verts, rotor_faces)
        mesh.materials.append(self.materials['propeller'])
        rotor_name = f'ROTOR_{index}' if self.model_id == 'x1' else f'Rotor_{index}'
        rotor = bpy.data.objects.new(rotor_name, mesh)
        bpy.context.collection.objects.link(rotor)
        rotor.matrix_world = matrix
        rotor['role'] = 'rotor'
        rotor['thruster_index'] = index
        rotor['axis'] = three_axis(axis)
        rotor['local_axis'] = [0.0, 0.0, 1.0]
        # Clamp screws around the shroud, on the band, axis radial in FRD via the local matrix.
        if self.spec['screws']:
            for bolt in range(4):
                angle = TAU * bolt / 4 + 0.3
                local = Vector((math.cos(angle) * (radius + 0.01), math.sin(angle) * (radius + 0.01), 0.0))
                world = matrix @ local
                radial = matrix.to_3x3() @ Vector((math.cos(angle), math.sin(angle), 0.0))
                frd_pos = blender_to_frd(world)
                frd_axis = blender_to_frd(radial)
                self.screw(frd_pos, frd_axis)

    def pontoon(self, centre, length, radius, tag):
        sides = self.spec['sides']
        half = length / 2
        cap = lathe([
            (0.0, -half),
            (radius * 0.28, -half + radius * 0.16),
            (radius * 0.62, -half + radius * 0.40),
            (radius * 0.90, -half + radius * 0.72),
            (radius, -half + radius * 1.15),
            (radius, half - radius * 1.15),
            (radius * 0.90, half - radius * 0.72),
            (radius * 0.62, half - radius * 0.40),
            (radius * 0.28, half - radius * 0.16),
            (0.0, half),
        ], sides)
        # Pontoon axis is the vehicle long axis (FRD +X).
        self.add(f'pontoon_{tag}', cap[0], cap[1], 'foam',
                 axis_matrix(centre, (1.0, 0.0, 0.0)), shared=f'pontoon-{tag}')
        collar = lathe([
            (radius * 0.99, -0.014), (radius * 1.045, -0.012),
            (radius * 1.045, 0.012), (radius * 0.99, 0.014),
        ], sides)
        if self.spec['screws']:
            for end in (-1.0, 1.0):
                station = half - radius * 1.2
                collar_pos = (centre[0] + end * station, centre[1], centre[2])
                self.add('collar', collar[0], collar[1], 'aluminium',
                         axis_matrix(collar_pos, (1.0, 0.0, 0.0)), shared='collar')
                for bolt in range(4):
                    angle = TAU * bolt / 4
                    pos = (collar_pos[0],
                           collar_pos[1] + math.cos(angle) * radius * 1.02,
                           collar_pos[2] + math.sin(angle) * radius * 1.02)
                    self.screw(pos, (0.0, math.cos(angle), math.sin(angle)))

    def housing(self, centre, radius, length):
        sides = self.spec['sides']
        body = lathe([
            (radius, -length / 2), (radius, length / 2),
        ], sides)
        self.add('housing', body[0], body[1], 'polymer',
                 axis_matrix(centre, (1.0, 0.0, 0.0)), shared='housing')
        cap = lathe([
            (0.0, 0.0), (radius * 1.04, 0.0), (radius * 1.04, 0.012), (0.0, 0.012),
        ], sides)
        for end in (-1.0, 1.0):
            pos = (centre[0] + end * length / 2, centre[1], centre[2])
            self.add('endcap', cap[0], cap[1], 'aluminium',
                     axis_matrix(pos, (end, 0.0, 0.0)), shared='endcap')
            if self.spec['screws']:
                for bolt in range(6):
                    angle = TAU * bolt / 6
                    self.screw((pos[0] + end * 0.004,
                                pos[1] + math.cos(angle) * radius * 0.75,
                                pos[2] + math.sin(angle) * radius * 0.55),
                               (end, 0.0, 0.0))

    def connector(self, position, axis):
        plug = lathe([(0.0, 0.0), (0.007, 0.0), (0.007, 0.012), (0.004, 0.018), (0.0, 0.018)],
                     max(6, self.spec['sides'] // 2))
        self.add('connector', plug[0], plug[1], 'aluminium', axis_matrix(position, axis), unique=True)
        boot = lathe([(0.008, 0.006), (0.009, 0.01), (0.006, 0.02), (0.004, 0.028)],
                     max(6, self.spec['sides'] // 2))
        self.add('boot', boot[0], boot[1], 'cable', axis_matrix(position, axis), unique=True)

    def camera(self):
        pos = self.definition.camera_body
        gimbal = self.empty('camera_gimbal', pos, {'role': 'camera_gimbal'})
        sides = self.spec['sides']
        radius = 0.034 if self.model_id != 'falcon' else 0.048
        dome = lathe([
            (0.0, radius * 0.92), (radius * 0.34, radius * 0.84),
            (radius * 0.64, radius * 0.66), (radius * 0.86, radius * 0.38),
            (radius * 0.98, radius * 0.12), (radius, 0.0), (radius * 0.78, -0.006),
        ], sides)
        dome_obj = self.add('dome', dome[0], dome[1], 'acrylic',
                            axis_matrix(pos, (1.0, 0.0, 0.0)), shared='dome')
        barrel = lathe([(radius * 0.72, -0.034), (radius * 0.72, -0.004)], sides)
        barrel_obj = self.add('barrel', barrel[0], barrel[1], 'polymer',
                              axis_matrix(pos, (1.0, 0.0, 0.0)), shared='barrel')
        bezel = lathe([
            (radius * 0.78, -0.008), (radius * 1.12, -0.008),
            (radius * 1.12, 0.004), (radius * 0.86, 0.004),
        ], sides)
        bezel_obj = self.add('bezel', bezel[0], bezel[1], 'aluminium',
                             axis_matrix(pos, (1.0, 0.0, 0.0)), shared='bezel')
        self.parent(dome_obj, gimbal)
        self.parent(barrel_obj, gimbal)
        self.parent(bezel_obj, gimbal)
        if self.spec['screws']:
            for bolt in range(4):
                angle = TAU * (bolt + 0.5) / 4
                self.screw((pos[0] + 0.002, pos[1] + math.cos(angle) * radius * 1.02,
                            pos[2] + math.sin(angle) * radius * 0.72),
                           (1.0, 0.0, 0.0))

    def lamps(self):
        for index, pos in enumerate(self.definition.lamp_body):
            pivot = self.empty(f'lamp_pivot_{index}', pos, {'role': 'lamp_pivot'})
            radius = 0.026 if self.model_id != 'falcon' else 0.038
            sides = self.spec['sides']
            body = lathe([
                (0.0, -0.03), (radius, -0.03), (radius, 0.0), (radius * 0.9, 0.006), (0.0, 0.006),
            ], sides)
            body_obj = self.add('lamp_body', body[0], body[1], 'aluminium',
                                axis_matrix(pos, (1.0, 0.0, 0.0)), shared='lamp-body')
            lens = lathe([(0.0, 0.006), (radius * 0.75, 0.006), (radius * 0.75, 0.01), (0.0, 0.01)],
                         sides)
            lens_obj = self.add('lamp_lens', lens[0], lens[1], 'lamp',
                                axis_matrix(pos, (1.0, 0.0, 0.0)), shared='lamp-lens')
            self.parent(body_obj, pivot)
            self.parent(lens_obj, pivot)
            if self.spec['screws']:
                for bolt in range(4):
                    angle = TAU * (bolt + 0.5) / 4
                    self.screw((pos[0] + 0.004, pos[1] + math.cos(angle) * radius * 0.85,
                                pos[2] + math.sin(angle) * radius * 0.85),
                               (1.0, 0.0, 0.0))

    def tether(self):
        pos = self.definition.gland_body
        sides = max(8, self.spec['sides'] // 2)
        for rib in range(5 if self.level < 2 else 2):
            centre = (pos[0] - 0.012 * rib, pos[1], pos[2])
            ring = lathe([(0.012, -0.003), (0.016, -0.003), (0.016, 0.003), (0.012, 0.003)], sides)
            self.add('gland', ring[0], ring[1], 'polymer',
                     axis_matrix(centre, (1.0, 0.0, 0.0)), shared='gland')
        if self.spec['cables']:
            # The anchor stays on the published gland point. The hose runs from
            # that point onto the housing so the fitting is not left floating.
            mount = (pos[0] + 0.05, 0.0, self.housing_z - self.housing_r * 0.2)
            self.rod(pos, mount, 0.009, 'cable', 'tether-hose')
            self.rod(pos, (pos[0] - 0.16, pos[1], pos[2]), 0.008, 'cable', 'tether-cable')

    def anchors(self):
        pairs = [('camera', self.definition.camera_body),
                 ('tether', self.definition.gland_body),
                 ('arm_mount', self.definition.arm_mount_body)]
        for index, pos in enumerate(self.definition.lamp_body):
            pairs.append((f'lamp_{index}', pos))
        for key, pos in pairs:
            self.empty(f'anchor_{key}', pos, {'anchor': key})
        self.empty('yx_frame', (0.0, 0.0, 0.0), {'frame': 'cg'})

    def frame_box(self, centre, size, material, shared):
        verts, faces = box_local(size)
        self.add('frame', verts, faces, material, at_matrix(centre), shared=shared)

    def build_common_frame(self, length, width, pontoon_y, pontoon_z, pontoon_r, housing_z):
        self.length = length
        self.housing_z = housing_z
        self.housing_r = 0.048 if self.model_id != 'falcon' else 0.06
        self.pontoon((-0.02, pontoon_y, pontoon_z), length, pontoon_r, 'side')
        self.pontoon((-0.02, -pontoon_y, pontoon_z), length, pontoon_r, 'side')
        self.housing((0.0, 0.0, housing_z), 0.048 if self.model_id != 'falcon' else 0.06, length * 0.72)
        for side in (-1.0, 1.0):
            self.frame_box((0.0, side * width, 0.11 if self.model_id != 'falcon' else 0.22),
                           (length, 0.02, 0.018), 'aluminium', 'skid')
            self.frame_box((0.0, side * (width * 0.65), pontoon_z + pontoon_r * 0.2),
                           (length * 0.9, 0.012, 0.012), 'aluminium', 'rail')
        for end in (-length * 0.42, length * 0.42):
            self.frame_box((end, 0.0, 0.04), (0.016, width * 2.1, 0.016), 'aluminium', 'cross')
        if self.spec['cables']:
            self.rod((-length * 0.2, width * 0.4, housing_z),
                     (length * 0.25, width * 0.85, 0.0), 0.004, 'cable', 'harness')
            self.rod((-length * 0.2, -width * 0.4, housing_z),
                     (length * 0.25, -width * 0.85, 0.0), 0.004, 'cable', 'harness')
        # Aft wet-mate row. Each plug is its own mesh so Model O and V clear the mesh-count contract.
        if self.level == 0:
            for index in range(8):
                side = -1.0 if index < 4 else 1.0
                slot = index % 4
                pos = (-length * 0.36, side * 0.018 * (slot - 1.5), housing_z)
                self.connector(pos, (-1.0, 0.0, 0.0))

    def arm(self):
        """Model V manipulator. Joint translations are the viewer's existing chain."""
        base = self.definition.arm_mount_body
        yaw = self.empty('arm_yaw', base, {'arm_node': 'arm_yaw', 'arm_axis': 'yaw'})
        shoulder = self.empty('arm_shoulder', base, {'arm_node': 'arm_shoulder', 'arm_axis': 'bend'})
        elbow_pos = (base[0] + 0.32, base[1], base[2])
        elbow = self.empty('arm_elbow', elbow_pos, {'arm_node': 'arm_elbow', 'arm_axis': 'bend'})
        wrist_pos = (base[0] + 0.62, base[1], base[2])
        wrist = self.empty('arm_wrist', wrist_pos, {'arm_node': 'arm_wrist', 'arm_axis': 'bend'})
        # Parent by setting local translation directly so the glTF translation stays exact.
        shoulder.parent = yaw
        shoulder.location = (0.0, 0.0, 0.0)
        elbow.parent = shoulder
        elbow.location = (0.0, -0.32, 0.0)
        wrist.parent = elbow
        wrist.location = (0.0, -0.30, 0.0)
        tip = bpy.data.objects.new('arm_tip', None)
        bpy.context.collection.objects.link(tip)
        tip.parent = wrist
        tip.location = (0.0, -0.12, 0.0)
        tip['arm_node'] = 'arm_tip'
        sides = max(6, self.spec['sides'] // 2)
        links = ((shoulder, 0.0, 0.32), (elbow, 0.32, 0.30), (wrist, 0.62, 0.12))
        for joint, start, length in links:
            centre = (base[0] + start + length / 2, base[1], base[2])
            if self.level == 2:
                plate = box_local((length, 0.024, 0.032))
                obj = self.add('link', plate[0], plate[1], 'polymer', at_matrix(centre), unique=True)
            else:
                plate = box_local((length * 0.92, 0.032, 0.046))
                obj = self.add('link', plate[0], plate[1], 'polymer', at_matrix(centre), unique=True)
                pin = lathe([(0.018, -0.03), (0.018, 0.03)], sides)
                pin_obj = self.add('pin', pin[0], pin[1], 'fastener',
                                   axis_matrix((base[0] + start, base[1], base[2]), (0.0, 1.0, 0.0)),
                                   unique=True)
                self.parent(pin_obj, joint)
            self.parent(obj, joint)
            if self.spec['screws']:
                for end in (0.04, length - 0.04):
                    bolt_pos = (base[0] + start + end, base[1], base[2] - 0.02)
                    screw_a = self.add('arm_screw', *lathe([(0.0, 0.003), (0.004, 0.003), (0.004, 0.0),
                                                            (0.0, 0.0)], 6),
                                       'fastener', axis_matrix(bolt_pos, (0.0, 0.0, 1.0)),
                                       unique=True, smooth=False)
                    self.parent(screw_a, joint)
        for side, label in ((-1.0, 'left'), (1.0, 'right')):
            jaw = bpy.data.objects.new(f'arm_jaw_{label}', None)
            bpy.context.collection.objects.link(jaw)
            jaw.parent = wrist
            jaw.location = (0.0, -0.075, 0.0)
            jaw['arm_node'] = f'arm_jaw_{label}'
            finger = box_local((0.07, 0.012, 0.016))
            # Shift the finger forward of the jaw origin (FRD +X is blender -Y).
            shifted = [(v[0], v[1] - 0.04, v[2]) for v in finger[0]]
            mesh_obj = self.add('jaw', shifted, finger[1], 'polymer', at_matrix(base), unique=True)
            self.parent(mesh_obj, jaw)
        pedestal = lathe([(0.04, 0.0), (0.04, 0.03), (0.02, 0.04)], max(6, sides))
        ped = self.add('pedestal', pedestal[0], pedestal[1], 'polymer',
                       axis_matrix(base, (0.0, 0.0, -1.0)), unique=True)
        self.parent(ped, yaw)
        shoulder.rotation_euler.x = math.radians(-15)
        elbow.rotation_euler.x = math.radians(30)
        wrist.rotation_euler.x = math.radians(-15)

    def build(self):
        if self.model_id == 'x1':
            self.build_common_frame(0.62, 0.145, 0.075, -0.105, 0.048, 0.01)
        elif self.model_id == 'bluerov2_heavy':
            self.build_common_frame(0.52, 0.16, 0.07, -0.12, 0.05, 0.02)
            for side in (-1.0, 1.0):
                self.rod((0.13, side * 0.16, -0.04), (0.13, side * 0.24, -0.11),
                         0.008, 'aluminium', 'outrigger')
                self.rod((-0.13, side * 0.16, -0.04), (-0.13, side * 0.24, -0.11),
                         0.008, 'aluminium', 'outrigger')
        else:
            self.build_common_frame(0.86, 0.22, 0.2, -0.14, 0.065, -0.02)
            self.frame_box((0.05, 0.0, 0.32), (0.7, 0.4, 0.02), 'aluminium', 'tray')
            self.arm()
        for index, (_name, pos, axis) in enumerate(self.definition.thrusters):
            self.thruster(index, pos, axis)
        self.camera()
        self.lamps()
        self.tether()
        self.anchors()
        if self.model_id == 'x1':
            merge_static()
        purge_orphans()
        bpy.context.view_layer.update()
        check_budget(self.model_id, self.level)
        export(self.model_id, self.level)


def blender_to_frd(vector):
    """Inverse of point(): Blender (port, aft, up) back to FRD."""
    port, aft, up = vector
    return (-aft, -port, -up)


def protected(obj):
    if obj.get('role') == 'rotor':
        return True
    parent = obj.parent
    while parent is not None:
        if parent.name in ('camera_gimbal', 'lamp_pivot_0', 'lamp_pivot_1') or parent.get('role') == 'rotor':
            return True
        if str(parent.name).startswith('arm_'):
            return True
        parent = parent.parent
    return False


def merge_static():
    """One mesh per material for Model R, so the draw-call budget stays under 40."""
    bpy.context.view_layer.update()
    groups = {}
    for obj in list(bpy.data.objects):
        if obj.type != 'MESH' or protected(obj):
            continue
        material = obj.data.materials[0] if obj.data.materials else None
        key = material.name if material else 'none'
        groups.setdefault(key, []).append(obj)
    for key, objects in groups.items():
        verts = []
        faces = []
        uvs = []
        material = objects[0].data.materials[0] if objects[0].data.materials else None
        keep_uv = all(obj.data.uv_layers for obj in objects)
        for obj in objects:
            base = len(verts)
            for vert in obj.data.vertices:
                verts.append(tuple(obj.matrix_world @ vert.co))
            for poly in obj.data.polygons:
                faces.append(tuple(base + index for index in poly.vertices))
                if keep_uv:
                    for loop_index in poly.loop_indices:
                        uvs.append(tuple(obj.data.uv_layers.active.data[loop_index].uv))
        mesh = make_mesh(f'yx_{key}', verts, faces)
        if keep_uv:
            layer = mesh.uv_layers.new(name='UVMap')
            for index, uv in enumerate(uvs):
                layer.data[index].uv = uv
        if material is not None:
            mesh.materials.append(material)
        merged = bpy.data.objects.new(f'yx_{key}', mesh)
        bpy.context.collection.objects.link(merged)
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)


def purge_orphans():
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def drawn_triangles():
    total = 0
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for poly in obj.data.polygons:
            total += len(poly.vertices) - 2
    return total


def check_budget(model_id, level):
    triangles = drawn_triangles()
    limit = BUDGETS[level]
    meshes = len([mesh for mesh in bpy.data.meshes if mesh.users > 0])
    draws = len([obj for obj in bpy.data.objects if obj.type == 'MESH'])
    print(f'{model_id} lod{level}: {triangles} tris, {meshes} meshes, {draws} mesh objects')
    if triangles > limit:
        raise SystemExit(f'{model_id} lod{level} has {triangles} triangles (limit {limit})')
    if level == 0 and model_id != 'x1' and meshes <= 60:
        raise SystemExit(f'{model_id} lod0 has {meshes} meshes; the fleet contract needs more than 60')
    if model_id == 'x1' and draws > 40:
        raise SystemExit(f'x1 lod{level} has {draws} draw objects (limit 40)')


def export(model_id, level):
    stem = FILES[model_id]
    name = f'{stem}.glb' if level == 0 else f'{stem}_lod{level}.glb'
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format='GLB',
        export_extras=True,
        export_apply=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_image_format='WEBP',
        export_image_quality=90,
    )
    print('exported', path, path.stat().st_size)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for block in list(collection):
            collection.remove(block)


def main():
    bpy.context.preferences.filepaths.save_version = 0
    for model_id in ('x1', 'bluerov2_heavy', 'falcon'):
        for level in range(3):
            FleetBuilder(model_id, level).build()


if __name__ == '__main__':
    main()
