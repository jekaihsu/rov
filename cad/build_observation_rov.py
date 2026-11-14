"""Build the original observation-class ROV (Steam asset set) in headless Blender and bake its PBR textures.

The vehicle is a generic open-frame design: two machined side plates and two bulkheads carry a split
syntactic-foam float, an aluminium electronics housing with an acrylic camera dome, a battery canister,
six ducted thrusters, two lamps, a DVL and a tether termination. It is not modelled on any manufacturer's
vehicle. Every mount point that the simulator uses comes from the `x1` definition in
simulator/qysim/vehicles.py, so the model replaces the training visual without any physics change.

Run with Blender 4.2+ or the `bpy` wheel (tested with bpy 5.0.1):
  blender --background --python cad/build_observation_rov.py -- PROJECT_ROOT [--quick]
  python cad/build_observation_rov.py PROJECT_ROOT [--quick]
Outputs go to simulator/output/observation_rov/ (raw GLB, baked textures); cad/pack_observation_rov.py then
writes the compressed LODs to simulator/viewer/models/. --quick bakes 512 px textures for fast iteration.

Coordinates: geometry is written in the simulator body frame (FRD: x forward, y starboard, z down, metres,
origin at CG) and converted to Blender (+X port, -Y forward, +Z up); the glTF exporter then gives three.js
+Z forward, +Y up, which is what simulator/viewer/vehicle_models.js expects.
"""
import math
import sys
from pathlib import Path

import bpy  # must precede bmesh when running from the bpy wheel
import bmesh
import numpy as np
from mathutils import Matrix, Vector


def parse_args():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    root = Path(args[0]).resolve() if args and not args[0].startswith('--') else Path(__file__).resolve().parents[1]
    return root, '--quick' in args


ROOT, QUICK = parse_args()
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.vehicles import get_vehicle_definition  # noqa: E402

DEF = get_vehicle_definition('x1')
OUT = ROOT / 'simulator' / 'output' / 'observation_rov'
BODY_SIZE = 512 if QUICK else 2048
THRUSTER_SIZE = 256 if QUICK else 1024
TAU = 2 * math.pi

# ───────────────────────── dimensions (FRD metres) ─────────────────────────
HOUSING_Z = -0.03
HOUSING_R = 0.075
HOUSING_X = (-0.235, 0.285)
BATTERY_Z = 0.105
BATTERY_R = 0.04
PLATE_Y = 0.275
PLATE_T = 0.012
BULKHEAD_X = (0.155, -0.165)
FOAM_TOP = -0.212
FOAM_BOTTOM = -0.117
FOAM_GAP = 0.04
DUCT_R = 0.047
LAMP_PIVOT_X = 0.348


# ───────────────────────── small math helpers ─────────────────────────
def to_blender(p):
    x, y, z = p
    return Vector((-y, -x, -z))


def v3(p):
    return Vector((float(p[0]), float(p[1]), float(p[2])))


def normalized(p):
    return v3(p).normalized()


def frame_from_axis(axis):
    """Orthonormal (u, v, w) with w along axis, in FRD."""
    w = normalized(axis)
    helper = Vector((0, 0, 1)) if abs(w.z) < 0.9 else Vector((1, 0, 0))
    u = w.cross(helper).normalized()
    v = w.cross(u).normalized()
    return u, v, w


def fillet(points, radius, segments=4, closed=True):
    """Round the corners of a 2D polyline; radius may be a number or a per-point list."""
    count = len(points)
    result = []
    for i in range(count):
        p1 = Vector(points[i])
        r = radius[i] if isinstance(radius, (list, tuple)) else radius
        at_end = not closed and (i == 0 or i == count - 1)
        if at_end or r <= 0:
            result.append(tuple(p1))
            continue
        p0 = Vector(points[i - 1])
        p2 = Vector(points[(i + 1) % count])
        d1 = p0 - p1
        d2 = p2 - p1
        l1 = d1.length
        l2 = d2.length
        d1.normalize()
        d2.normalize()
        cosine = max(-1.0, min(1.0, d1.dot(d2)))
        theta = math.acos(cosine)
        if theta < 1e-3 or theta > math.pi - 1e-3:
            result.append(tuple(p1))
            continue
        tangent = r / math.tan(theta / 2)
        tangent = min(tangent, 0.45 * l1, 0.45 * l2)
        r_eff = tangent * math.tan(theta / 2)
        a = p1 + d1 * tangent
        b = p1 + d2 * tangent
        bisector = (d1 + d2).normalized()
        centre = p1 + bisector * (r_eff / math.sin(theta / 2))
        start = math.atan2(a.y - centre.y, a.x - centre.x)
        end = math.atan2(b.y - centre.y, b.x - centre.x)
        sweep = end - start
        while sweep > math.pi:
            sweep -= TAU
        while sweep < -math.pi:
            sweep += TAU
        for k in range(segments + 1):
            angle = start + sweep * k / segments
            result.append((centre.x + r_eff * math.cos(angle), centre.y + r_eff * math.sin(angle)))
    return result


def rounded_rect(cx, cy, w, h, r, segments=4):
    corners = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
    return fillet(corners, r, segments)


def circle2d(cx, cy, r, segments=24):
    return [(cx + r * math.cos(TAU * i / segments), cy + r * math.sin(TAU * i / segments)) for i in range(segments)]


def catmull(points, samples=6):
    """Catmull-Rom resample of a 3D polyline (endpoints kept)."""
    pts = [v3(p) for p in points]
    padded = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    result = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for k in range(samples):
            t = k / samples
            t2 = t * t
            t3 = t2 * t
            point = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                           + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            result.append(point)
    result.append(pts[-1])
    return result


# ───────────────────────── mesh construction ─────────────────────────
def lathe(profile, segments=48):
    """Revolve (r, h) points about local +Z. Counter-clockwise profiles give outward normals."""
    verts = []
    rings = []
    for r, h in profile:
        if r < 1e-7:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, h))
            continue
        ring = []
        for i in range(segments):
            angle = TAU * i / segments
            ring.append(len(verts))
            verts.append((r * math.cos(angle), r * math.sin(angle), h))
        rings.append(ring)
    faces = []
    for a, b in zip(rings, rings[1:]):
        faces.extend(bridge(a, b, segments))
    return verts, faces


def bridge(a, b, segments):
    faces = []
    if len(a) == 1 and len(b) == 1:
        return faces
    for i in range(segments):
        j = (i + 1) % segments
        if len(a) == 1:
            faces.append((a[0], b[j], b[i]))
        elif len(b) == 1:
            faces.append((a[i], a[j], b[0]))
        else:
            faces.append((a[i], a[j], b[j], b[i]))
    return faces


def sweep(path, radius, sides=8, cap=True):
    """Tube along a 3D path using rotation-minimising frames; radius may vary per point."""
    pts = [v3(p) for p in path]
    radii = radius if isinstance(radius, (list, tuple)) else [radius] * len(pts)
    tangents = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        tangents.append((b - a).normalized())
    normal, _, _ = frame_from_axis(tangents[0])
    verts = []
    for i, point in enumerate(pts):
        if i:
            normal = normal - tangents[i] * normal.dot(tangents[i])
            normal.normalize()
        binormal = tangents[i].cross(normal)
        for k in range(sides):
            angle = TAU * k / sides
            offset = normal * math.cos(angle) + binormal * math.sin(angle)
            verts.append(tuple(point + offset * radii[i]))
    faces = []
    for i in range(len(pts) - 1):
        for k in range(sides):
            n = (k + 1) % sides
            faces.append((i * sides + k, (i + 1) * sides + k, (i + 1) * sides + n, i * sides + n))
    if cap:
        faces.append(tuple(reversed(range(sides))))
        last = (len(pts) - 1) * sides
        faces.append(tuple(last + k for k in range(sides)))
    return verts, faces


def blade_surface(radius_hub, radius_tip, blades=4, pitch=0.055, z0=0.004):
    """Twisted, cambered, skewed propeller blades about local +Z."""
    stations = 7
    chordwise = 7
    verts = []
    faces = []
    for blade in range(blades):
        phase = TAU * blade / blades
        loops = []
        for i in range(stations):
            s = i / (stations - 1)
            r = radius_hub * 0.92 + (radius_tip - radius_hub * 0.92) * s
            chord = 0.024 * (1 - 0.72 * s ** 3) + 0.004
            beta = math.atan(pitch / (TAU * r))
            skew = 0.32 * s * s
            thickness = 0.0026 * (1 - s) + 0.0008
            loop = []
            upper = []
            lower = []
            for k in range(chordwise):
                t = -0.5 + k / (chordwise - 1)
                shape = max(0.0, 1 - (2 * t) ** 2)
                camber = 0.06 * chord * shape
                half = 0.5 * thickness * shape ** 0.6
                upper.append((t * chord, camber + half))
                lower.append((t * chord, camber - half))
            outline = upper + list(reversed(lower[1:-1]))
            for along, across in outline:
                tangential = along * math.cos(beta) + across * math.sin(beta)
                axial = -along * math.sin(beta) + across * math.cos(beta)
                angle = phase + skew + tangential / r
                loop.append(len(verts))
                verts.append((r * math.cos(angle), r * math.sin(angle), z0 + axial))
            loops.append(loop)
        size = len(loops[0])
        for a, b in zip(loops, loops[1:]):
            for k in range(size):
                n = (k + 1) % size
                faces.append((a[k], a[n], b[n], b[k]))
        faces.append(tuple(loops[-1]))
    return verts, faces


def box(size, centre=(0, 0, 0), bevel=0.0, segments=2):
    """Axis-aligned box with optional bevelled edges, as (verts, faces)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vert in bm.verts:
        vert.co = Vector((vert.co.x * size[0] + centre[0], vert.co.y * size[1] + centre[1],
                          vert.co.z * size[2] + centre[2]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segments, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    verts = [tuple(v.co) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return verts, faces


def transform(verts, origin, u, v, w):
    """Map local (a, b, c) to FRD origin + a*u + b*v + c*w."""
    o = v3(origin)
    return [tuple(o + u * p[0] + v * p[1] + w * p[2]) for p in verts]


def merge(*parts):
    verts = []
    faces = []
    for part_verts, part_faces in parts:
        offset = len(verts)
        verts.extend(part_verts)
        faces.extend(tuple(i + offset for i in face) for face in part_faces)
    return verts, faces


COLLECTION = None


def link(obj):
    COLLECTION.objects.link(obj)
    return obj


def mesh_object(name, verts, faces, material, frd=True, smooth=34, parent=None, recalc=False):
    mesh = bpy.data.meshes.new(name)
    coords = [tuple(to_blender(p)) for p in verts] if frd else verts
    mesh.from_pydata(coords, [], faces)
    mesh.validate(clean_customdata=False)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
    finish_mesh(mesh, smooth)
    mesh.materials.append(material)
    obj = link(bpy.data.objects.new(name, mesh))
    if parent:
        obj.parent = parent
    return obj


def finish_mesh(mesh, smooth):
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    if smooth:
        mesh.set_sharp_from_angle(angle=math.radians(smooth))
    mesh.update()


def local_object(name, verts, faces, material, matrix, smooth=34, parent=None):
    """Mesh built in a local Blender-space frame and placed with an object matrix."""
    obj = mesh_object(name, verts, faces, material, frd=False, smooth=smooth, parent=parent)
    obj.matrix_world = matrix
    return obj


def evaluated_mesh(obj, name):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), depsgraph=depsgraph)


def profile_solid(name, outline, holes, thickness, bevel, place, material, smooth=40):
    """Extrude a 2D outline (with holes) by thickness with rounded edges; place maps (u, v, w) to FRD."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '2D'
    curve.fill_mode = 'BOTH'
    curve.extrude = max(thickness / 2 - bevel, 1e-4)
    curve.bevel_depth = bevel
    curve.bevel_resolution = 2 if bevel > 0.008 else 1
    for poly in [outline] + list(holes):
        spline = curve.splines.new('POLY')
        spline.points.add(len(poly) - 1)
        for i, (a, b) in enumerate(poly):
            spline.points[i].co = (a, b, 0.0, 1.0)
        spline.use_cyclic_u = True
        spline.use_smooth = True
    holder = link(bpy.data.objects.new(name + '_curve', curve))
    mesh = evaluated_mesh(holder, name)
    bpy.data.objects.remove(holder)
    bpy.data.curves.remove(curve)
    for vert in mesh.vertices:
        vert.co = to_blender(place(vert.co))
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    finish_mesh(mesh, smooth)
    mesh.materials.clear()
    mesh.materials.append(material)
    return link(bpy.data.objects.new(name, mesh))


def place_on_axis(origin, axis):
    """Matrix placing a local +Z-axis part at FRD origin pointing along FRD axis (Blender space)."""
    rotation = Vector((0, 0, 1)).rotation_difference(to_blender(normalized(axis)))
    return Matrix.Translation(to_blender(origin)) @ rotation.to_matrix().to_4x4()


# ───────────────────────── materials ─────────────────────────
class Nodes:
    """Tiny helper for building shader graphs."""

    def __init__(self, material):
        self.tree = material.node_tree
        self.tree.nodes.clear()

    def add(self, kind, **settings):
        node = self.tree.nodes.new(kind)
        for key, value in settings.items():
            setattr(node, key, value)
        return node

    def connect(self, socket, target):
        if hasattr(socket, 'is_output'):
            self.tree.links.new(socket, target)
        elif isinstance(socket, (tuple, list)):
            target.default_value = socket if len(target.default_value) == len(socket) else (*socket, 1.0)
        else:
            target.default_value = socket

    def math(self, operation, a, b=0.0, clamp=False):
        node = self.add('ShaderNodeMath', operation=operation, use_clamp=clamp)
        self.connect(a, node.inputs[0])
        self.connect(b, node.inputs[1])
        return node.outputs[0]

    def mix(self, factor, a, b):
        node = self.add('ShaderNodeMix', data_type='RGBA')
        self.connect(factor, node.inputs['Factor'])
        self.connect(a, node.inputs[6])
        self.connect(b, node.inputs[7])
        return node.outputs[2]

    def noise(self, vector, scale, detail=4.0, roughness=0.55):
        node = self.add('ShaderNodeTexNoise')
        self.connect(vector, node.inputs['Vector'])
        node.inputs['Scale'].default_value = scale
        node.inputs['Detail'].default_value = detail
        node.inputs['Roughness'].default_value = roughness
        return node.outputs['Fac']

    def ramp(self, value, low, high):
        node = self.add('ShaderNodeMapRange', clamp=True)
        self.connect(value, node.inputs['Value'])
        node.inputs['From Min'].default_value = low
        node.inputs['From Max'].default_value = high
        return node.outputs['Result']

    def stretch(self, vector, scale):
        node = self.add('ShaderNodeMapping')
        self.connect(vector, node.inputs['Vector'])
        node.inputs['Scale'].default_value = scale
        return node.outputs['Vector']


SURFACES = {
    # base colour (linear), roughness, metallic, wear colour, wear roughness, wear metallic, bump scale/strength,
    # brushed-streak scale, edge wear amount, grime amount
    'foam': dict(base=(0.50, 0.485, 0.435), rough=0.62, tape=(0.205, 0.235), seam=-(FOAM_TOP + FOAM_BOTTOM) / 2,
                 metal=0.0,
                 wear=(0.36, 0.34, 0.30), wear_rough=0.85,
                 wear_metal=0.0, bump=420.0, bump_strength=0.12, brushed=None, edge=0.85, grime=0.55),
    'plate': dict(base=(0.040, 0.044, 0.048), rough=0.58, metal=0.0, wear=(0.11, 0.115, 0.12), wear_rough=0.78,
                  wear_metal=0.0, bump=900.0, bump_strength=0.05, brushed=(1.0, 1.0, 40.0), edge=0.75, grime=0.35),
    'anodised': dict(base=(0.33, 0.35, 0.37), rough=0.34, metal=1.0, wear=(0.82, 0.82, 0.80), wear_rough=0.22,
                     wear_metal=1.0, bump=1400.0, bump_strength=0.025, brushed=(1.0, 90.0, 90.0), edge=0.6,
                     grime=0.45),
    'dark_anodised': dict(base=(0.035, 0.040, 0.046), rough=0.32, metal=0.85, wear=(0.70, 0.70, 0.68),
                          wear_rough=0.25, wear_metal=1.0, bump=1400.0, bump_strength=0.025, brushed=None,
                          edge=0.55, grime=0.3),
    'black_polymer': dict(base=(0.022, 0.024, 0.027), rough=0.48, metal=0.0, wear=(0.09, 0.09, 0.09),
                          wear_rough=0.7, wear_metal=0.0, bump=700.0, bump_strength=0.04, brushed=None, edge=0.6,
                          grime=0.25),
    'stainless': dict(base=(0.56, 0.56, 0.54), rough=0.28, metal=1.0, wear=(0.70, 0.70, 0.68), wear_rough=0.18,
                      wear_metal=1.0, bump=1600.0, bump_strength=0.02, brushed=(1.0, 1.0, 120.0), edge=0.3,
                      grime=0.5),
    'orange': dict(base=(0.78, 0.20, 0.025), rough=0.5, metal=0.0, wear=(0.30, 0.12, 0.05), wear_rough=0.75,
                   wear_metal=0.0, bump=600.0, bump_strength=0.05, brushed=None, edge=0.7, grime=0.4),
    'uhmw': dict(base=(0.018, 0.02, 0.022), rough=0.66, metal=0.0, wear=(0.15, 0.15, 0.15), wear_rough=0.9,
                 wear_metal=0.0, bump=500.0, bump_strength=0.15, brushed=(1.0, 30.0, 1.0), edge=1.0, grime=0.2),
    'zinc': dict(base=(0.42, 0.43, 0.44), rough=0.72, metal=0.9, wear=(0.55, 0.56, 0.56), wear_rough=0.5,
                 wear_metal=0.9, bump=260.0, bump_strength=0.25, brushed=None, edge=0.4, grime=0.6),
    'propeller': dict(base=(0.05, 0.055, 0.06), rough=0.38, metal=0.2, wear=(0.20, 0.20, 0.20),
                      wear_rough=0.5, wear_metal=0.1, bump=900.0, bump_strength=0.02, brushed=None, edge=0.8,
                      grime=0.15),
}

BAKE_MATERIALS = {}
BAKE_SOCKETS = {}


def mask_graph(graph):
    """Ray-traced masks, baked once at reduced resolution: edge (bevel normal vs true normal), cavity, AO."""
    geometry = graph.add('ShaderNodeNewGeometry')
    bevel = graph.add('ShaderNodeBevel', samples=8)
    bevel.inputs['Radius'].default_value = 0.0025
    dot = graph.add('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    graph.connect(bevel.outputs['Normal'], dot.inputs[0])
    graph.connect(geometry.outputs['Normal'], dot.inputs[1])
    edge = graph.ramp(graph.math('SUBTRACT', 1.0, dot.outputs['Value']), 0.02, 0.18)
    cavity = graph.add('ShaderNodeAmbientOcclusion', samples=12)
    cavity.inputs['Distance'].default_value = 0.035
    ambient = graph.add('ShaderNodeAmbientOcclusion', samples=12)
    ambient.inputs['Distance'].default_value = 0.08
    combine = graph.add('ShaderNodeCombineColor')
    graph.connect(edge, combine.inputs['Red'])
    graph.connect(cavity.outputs['AO'], combine.inputs['Green'])
    graph.connect(ambient.outputs['AO'], combine.inputs['Blue'])
    return combine.outputs['Color']


def surface_material(key, atlas):
    """Procedural shader used only for baking; atlas names the image the bake writes into."""
    name = f'bake_{atlas}_{key}'
    if name in BAKE_MATERIALS:
        return BAKE_MATERIALS[name]
    spec = SURFACES[key]
    material = bpy.data.materials.new(name)
    graph = Nodes(material)
    coords = graph.add('ShaderNodeTexCoord').outputs['Object']
    mask_socket = mask_graph(graph)
    # Later passes read the baked mask (R edge, G cavity occlusion, B ambient occlusion) instead of tracing rays.
    mask_node = graph.add('ShaderNodeTexImage')
    mask_node.name = 'mask_source'
    masks = graph.add('ShaderNodeSeparateColor')
    graph.connect(mask_node.outputs['Color'], masks.inputs['Color'])
    edge = masks.outputs['Red']
    breakup = graph.noise(coords, 38.0, 4.0, 0.7)
    wear_noise = graph.ramp(graph.math('MULTIPLY', breakup, edge), 0.22, 0.42)
    wear = graph.math('MULTIPLY', wear_noise, spec['edge'], clamp=True)
    cavity = graph.ramp(masks.outputs['Green'], 0.85, 0.35)
    grime = graph.math('MULTIPLY', cavity, spec['grime'], clamp=True)
    streak_coords = graph.stretch(coords, (36.0, 36.0, 1.6))
    streak = graph.ramp(graph.noise(streak_coords, 3.0, 3.0, 0.5), 0.45, 0.75)
    variation = graph.noise(coords, 7.0, 3.0, 0.5)
    tone = graph.ramp(variation, 0.3, 0.7)
    base_low = tuple(c * 0.86 for c in spec['base'])
    colour = graph.mix(tone, base_low, spec['base'])
    stained = tuple(c * 0.72 for c in spec['base'])
    colour = graph.mix(graph.math('MULTIPLY', streak, 0.22), colour, stained)
    grime_colour = (0.075, 0.072, 0.055) if spec['metal'] < 0.5 else (0.10, 0.095, 0.08)
    colour = graph.mix(grime, colour, grime_colour)
    colour = graph.mix(wear, colour, spec['wear'])
    rough = graph.math('ADD', spec['rough'] - 0.05, graph.math('MULTIPLY', variation, 0.1))
    if spec['brushed']:
        brushed = graph.noise(graph.stretch(coords, spec['brushed']), 60.0, 2.0, 0.4)
        rough = graph.math('ADD', rough, graph.math('MULTIPLY', graph.math('SUBTRACT', brushed, 0.5), 0.12))
    rough = graph.math('ADD', rough, graph.math('MULTIPLY', grime, 0.15))
    rough_mix = graph.add('ShaderNodeMix', data_type='FLOAT')
    graph.connect(wear, rough_mix.inputs['Factor'])
    graph.connect(rough, rough_mix.inputs[2])
    graph.connect(spec['wear_rough'], rough_mix.inputs[3])
    rough = graph.math('MAXIMUM', rough_mix.outputs[0], 0.05, clamp=True)
    metal_mix = graph.add('ShaderNodeMix', data_type='FLOAT')
    graph.connect(wear, metal_mix.inputs['Factor'])
    graph.connect(spec['metal'], metal_mix.inputs[2])
    graph.connect(spec['wear_metal'], metal_mix.inputs[3])
    height = graph.math('ADD', graph.noise(coords, spec['bump'], 3.0, 0.6),
                        graph.math('MULTIPLY', breakup, 0.4))
    if 'seam' in spec:
        # Moulded parting line around the float, at mid height in Blender object space.
        split = graph.add('ShaderNodeSeparateXYZ')
        graph.connect(coords, split.inputs[0])
        distance = graph.math('ABSOLUTE', graph.math('SUBTRACT', split.outputs['Z'], spec['seam']))
        groove = graph.math('SUBTRACT', 1.0, graph.ramp(distance, 0.0005, 0.0016))
        height = graph.math('SUBTRACT', height, graph.math('MULTIPLY', groove, 3.0))
        colour = graph.mix(graph.math('MULTIPLY', groove, 0.5), colour, grime_colour)
    if 'tape' in spec:
        # Retroreflective tape along the outboard top edge of each float (|FRD y| in the tape band).
        split = graph.add('ShaderNodeSeparateXYZ')
        graph.connect(coords, split.inputs[0])
        lateral = graph.math('ABSOLUTE', split.outputs['X'])
        inner_edge = graph.ramp(lateral, spec['tape'][0], spec['tape'][0] + 0.0008)
        outer_edge = graph.ramp(lateral, spec['tape'][1], spec['tape'][1] + 0.0008)
        inside = graph.math('MULTIPLY', inner_edge, graph.math('SUBTRACT', 1.0, outer_edge))
        on_top = graph.ramp(split.outputs['Z'], -FOAM_TOP - 0.004, -FOAM_TOP - 0.001)
        tape = graph.math('MULTIPLY', inside, on_top)
        tape_colour = graph.mix(graph.math('MULTIPLY', grime, 0.6), (0.52, 0.11, 0.012), grime_colour)
        colour = graph.mix(graph.math('MULTIPLY', tape, graph.math('SUBTRACT', 1.0, wear)), colour, tape_colour)
        height = graph.math('ADD', height, graph.math('MULTIPLY', tape, 0.4))
    bump = graph.add('ShaderNodeBump')
    bump.inputs['Strength'].default_value = spec['bump_strength']
    bump.inputs['Distance'].default_value = 0.004
    graph.connect(height, bump.inputs['Height'])
    shader = graph.add('ShaderNodeBsdfPrincipled')
    graph.connect(colour, shader.inputs['Base Color'])
    graph.connect(rough, shader.inputs['Roughness'])
    graph.connect(metal_mix.outputs[0], shader.inputs['Metallic'])
    graph.connect(bump.outputs['Normal'], shader.inputs['Normal'])
    output = graph.add('ShaderNodeOutputMaterial')
    graph.connect(shader.outputs[0], output.inputs['Surface'])
    combine = graph.add('ShaderNodeCombineXYZ')
    graph.connect(rough, combine.inputs['Y'])
    graph.connect(metal_mix.outputs[0], combine.inputs['Z'])
    image_node = graph.add('ShaderNodeTexImage')
    image_node.name = 'bake_target'
    BAKE_SOCKETS[name] = dict(colour=colour, orm=combine.outputs[0], shader=shader.outputs[0], output=output,
                              graph=graph, atlas=atlas, mask=mask_socket)
    BAKE_MATERIALS[name] = material
    return material


def flat_material(name, colour, rough, metal, emission=None, alpha=1.0):
    material = bpy.data.materials.new(name)
    graph = Nodes(material)
    shader = graph.add('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (*colour, 1.0)
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Metallic'].default_value = metal
    if emission:
        shader.inputs['Emission Color'].default_value = (*emission[0], 1.0)
        shader.inputs['Emission Strength'].default_value = emission[1]
    if alpha < 1.0:
        shader.inputs['Alpha'].default_value = alpha
        material.surface_render_method = 'BLENDED'
    output = graph.add('ShaderNodeOutputMaterial')
    graph.connect(shader.outputs[0], output.inputs['Surface'])
    return material


FLAT = {}


def flat_materials():
    FLAT['steel'] = flat_material('Stainless fastener', (0.62, 0.62, 0.60), 0.26, 1.0)
    FLAT['rubber'] = flat_material('Neoprene cable jacket', (0.018, 0.019, 0.021), 0.62, 0.0)
    FLAT['acrylic'] = flat_material('Acrylic dome', (0.80, 0.86, 0.90), 0.04, 0.0, alpha=0.16)
    FLAT['glass'] = flat_material('Lamp cover glass', (0.85, 0.90, 0.95), 0.05, 0.0, alpha=0.22)
    FLAT['lens'] = flat_material('Coated camera lens', (0.010, 0.020, 0.030), 0.08, 0.6)
    FLAT['led'] = flat_material('LED phosphor', (0.95, 0.86, 0.55), 0.3, 0.0, emission=((1.0, 0.92, 0.70), 1.6))
    FLAT['reflector'] = flat_material('Lamp reflector', (0.86, 0.87, 0.88), 0.12, 1.0)
    FLAT['transducer'] = flat_material('Acoustic transducer face', (0.06, 0.065, 0.07), 0.55, 0.0)


# ───────────────────────── parts ─────────────────────────
BODY_OBJECTS = []
THRUSTER_BAKE_OBJECTS = []
SCREW_MESH = None


def body(obj):
    BODY_OBJECTS.append(obj)
    return obj


def screw_mesh():
    """M5 socket head cap screw with hex recess; head top on local +Z."""
    global SCREW_MESH
    if SCREW_MESH:
        return SCREW_MESH
    r = 0.0042
    h = 0.005
    segments = 12
    verts = []
    faces = []
    profile = [(r, 0.0), (r, h - 0.0008), (r * 0.86, h)]
    rings = []
    for radius, z in profile:
        ring = []
        for i in range(segments):
            angle = TAU * i / segments
            ring.append(len(verts))
            verts.append((radius * math.cos(angle), radius * math.sin(angle), z))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        faces.extend(bridge(a, b, segments))
    hex_r = 0.0022
    top = []
    bottom = []
    for j in range(6):
        angle = TAU * j / 6
        top.append(len(verts))
        verts.append((hex_r * math.cos(angle), hex_r * math.sin(angle), h))
    for j in range(6):
        angle = TAU * j / 6
        bottom.append(len(verts))
        verts.append((hex_r * math.cos(angle), hex_r * math.sin(angle), h - 0.0025))
    outer = rings[-1]
    for j in range(6):
        c0 = outer[2 * j]
        c1 = outer[2 * j + 1]
        c2 = outer[(2 * j + 2) % segments]
        faces.append((c0, c1, top[j]))
        faces.append((c1, c2, top[(j + 1) % 6]))
        faces.append((c1, top[(j + 1) % 6], top[j]))
    for j in range(6):
        n = (j + 1) % 6
        faces.append((top[j], top[n], bottom[n], bottom[j]))
    faces.append(tuple(reversed(bottom)))
    mesh = bpy.data.meshes.new('screw_m5')
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    finish_mesh(mesh, 40)
    mesh.materials.append(FLAT['steel'])
    SCREW_MESH = mesh
    return mesh


SCREW_COUNT = [0]


def screw(position, normal, parent=None):
    """Place a screw head on a surface at FRD position, head facing the FRD normal."""
    SCREW_COUNT[0] += 1
    obj = link(bpy.data.objects.new(f'fastener_{SCREW_COUNT[0]:03d}', screw_mesh()))
    obj.matrix_world = place_on_axis(position, normal)
    if parent:
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
    return obj


def side_plates():
    outline = [(-0.17, -0.117), (0.17, -0.117), (0.215, 0.03), (0.352, 0.03), (0.37, 0.11), (0.33, 0.176),
               (-0.33, 0.176), (-0.37, 0.11), (-0.352, 0.03), (-0.215, 0.03)]
    outline = fillet(outline, [0.02, 0.02, 0.035, 0.012, 0.03, 0.03, 0.03, 0.03, 0.012, 0.035], 5)
    holes = [
        fillet([(-0.075, -0.088), (0.075, -0.088), (0.075, -0.058), (-0.075, -0.058)], 0.0149, 6),
        circle2d(-0.061, 0.068, 0.04, 36),
        rounded_rect(0.07, 0.09, 0.11, 0.075, 0.018),
        rounded_rect(0.283, 0.115, 0.075, 0.05, 0.016),
        rounded_rect(-0.283, 0.115, 0.075, 0.05, 0.016),
        rounded_rect(-0.165 + 0.0, 0.135, 0.07, 0.03, 0.012),
    ]
    for side in (-1, 1):
        def place(p, side=side):
            return (p[0], side * (PLATE_Y + p[2]), p[1])
        name = 'side_plate_port' if side < 0 else 'side_plate_starboard'
        body(profile_solid(name, outline, holes, PLATE_T, 0.0025, place, surface_material('plate', 'body')))


def bulkheads():
    outline = [(-0.269, -0.117), (0.269, -0.117), (0.269, 0.175), (-0.269, 0.175)]
    outline = fillet(outline, 0.008, 3)
    holes = [circle2d(0.0, HOUSING_Z, HOUSING_R + 0.004, 48), circle2d(0.0, BATTERY_Z, BATTERY_R + 0.004, 36)]
    for side in (-1, 1):
        holes.append(rounded_rect(side * 0.178, 0.035, 0.105, 0.17, 0.03, 5))
        holes.append(rounded_rect(side * 0.085, 0.152, 0.07, 0.024, 0.01, 4))
    for index, x in enumerate(BULKHEAD_X):
        def place(p, x=x):
            return (x + p[2], p[0], p[1])
        name = 'bulkhead_front' if index == 0 else 'bulkhead_aft'
        body(profile_solid(name, outline, holes, PLATE_T, 0.002, place, surface_material('plate', 'body')))
        grommet_r = HOUSING_R + 0.004
        verts, faces = lathe([(grommet_r - 0.001, -0.01), (grommet_r + 0.006, -0.009), (grommet_r + 0.007, 0.0),
                              (grommet_r + 0.006, 0.009), (grommet_r - 0.001, 0.01)], 48)
        verts = transform(verts, (x, 0, HOUSING_Z), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0)))
        body(mesh_object(f'housing_grommet_{index}', verts, faces + [], surface_material('black_polymer', 'body')))
        for side in (-1, 1):
            for z in (-0.085, 0.145):
                screw((x, side * (PLATE_Y + PLATE_T / 2), z), (0, side, 0))


def foam_blocks():
    """Split syntactic foam float with thruster bays, nose taper and stainless hold-down inserts."""
    plan = [(-0.36, FOAM_GAP), (0.31, FOAM_GAP), (0.31, 0.128), (0.178, 0.128), (0.178, 0.281),
            (-0.18, 0.281), (-0.18, 0.12), (-0.36, 0.12)]
    plan = fillet(plan, [0.03, 0.03, 0.03, 0.022, 0.03, 0.03, 0.022, 0.03], 4)
    thickness = FOAM_BOTTOM - FOAM_TOP
    for side in (-1, 1):
        def place(p, side=side):
            return (p[0], side * p[1], FOAM_TOP + thickness / 2 - p[2])
        name = 'foam_port' if side < 0 else 'foam_starboard'
        obj = profile_solid(name, [(x, y) for x, y in plan], [], thickness, 0.016, place,
                            surface_material('foam', 'body'), smooth=50)
        add_cross_loops(obj)
        taper_nose(obj)
        body(obj)
        for x, y in ((0.06, 0.16), (-0.12, 0.16), (0.2, 0.085), (-0.3, 0.085)):
            top = FOAM_TOP + foam_drop(x)
            insert = [(0.0055, top - 0.0004), (0.0085, top - 0.0004), (0.009, top + 0.0006), (0.0055, top + 0.0006)]
            verts, faces = lathe([(r, h) for r, h in insert], 20)
            verts = [(p[0] + x, p[1] + side * y, p[2]) for p in verts]
            body(mesh_object(f'foam_insert_{side}_{x:+.2f}', verts, faces, surface_material('stainless', 'body')))
            if abs(y - 0.16) > 1e-6:
                screw((x, side * y, top + 0.0005), (0, 0, -1))
        accessory_rail(side)


def accessory_rail(side):
    """Low stainless accessory rail bolted through the float inserts, for payload brackets."""
    y = side * 0.16
    verts, faces = box((0.25, 0.016, 0.007), centre=(-0.03, y, FOAM_TOP - 0.0035), bevel=0.0018)
    body(mesh_object(f'accessory_rail_{side}', verts, faces, surface_material('stainless', 'body'), smooth=30))
    for x in (0.06, -0.12):
        screw((x, y, FOAM_TOP - 0.007), (0, 0, -1))
    for x in (-0.14, 0.08):
        verts, faces = box((0.01, 0.016, 0.003), centre=(x, y, FOAM_TOP - 0.0085), bevel=0.0008)
        body(mesh_object(f'accessory_rail_stop_{side}_{x:+.2f}', verts, faces,
                         surface_material('black_polymer', 'body')))


def add_cross_loops(obj):
    """Insert edge loops across the foam (constant x) so the taper bends smoothly instead of creasing."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    stations = [0.17 + 0.025 * k for k in range(6)] + [-0.28 - 0.025 * k for k in range(3)]
    for x in stations:
        geometry = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geometry, plane_co=to_blender((x, 0, 0)), plane_no=(0.0, 1.0, 0.0))
    bm.to_mesh(obj.data)
    bm.free()
    finish_mesh(obj.data, 50)


def foam_drop(x):
    if x > 0.17:
        return 0.05 * ((x - 0.17) / 0.14) ** 1.6
    if x < -0.28:
        return 0.022 * ((-0.28 - x) / 0.08) ** 1.5
    return 0.0


def taper_nose(obj):
    """Slope the upper surface of the foam towards the bow and stern."""
    for vert in obj.data.vertices:
        x = -vert.co.y
        z = -vert.co.z
        upper = (FOAM_BOTTOM - z) / (FOAM_BOTTOM - FOAM_TOP)
        vert.co.z -= foam_drop(x) * max(0.0, upper)
    obj.data.update()


def housing():
    """Electronics pressure housing, end caps with bolt circles and penetrators, acrylic dome."""
    x0, x1 = HOUSING_X
    r = HOUSING_R
    tube = [(0.0, x0 + 0.004), (r - 0.002, x0 + 0.004), (r, x0 + 0.006), (r, x0 + 0.03), (r - 0.0015, x0 + 0.032),
            (r - 0.0015, x0 + 0.035), (r, x0 + 0.037), (r, x1 - 0.037), (r - 0.0015, x1 - 0.035),
            (r - 0.0015, x1 - 0.032), (r, x1 - 0.03), (r, x1 - 0.006), (r - 0.002, x1 - 0.004), (0.0, x1 - 0.004)]
    axis_place(body, 'housing_tube', tube, 48, 'anodised')
    flange_r = r + 0.009
    rear = [(0.0, x0 - 0.028), (flange_r - 0.012, x0 - 0.028), (flange_r - 0.004, x0 - 0.026),
            (flange_r, x0 - 0.022), (flange_r, x0 - 0.004), (flange_r - 0.003, x0), (r - 0.004, x0 + 0.004),
            (0.0, x0 + 0.004)]
    axis_place(body, 'housing_end_cap_aft', rear, 48, 'dark_anodised')
    front = [(r - 0.012, x1 - 0.004), (r - 0.004, x1 - 0.004), (flange_r - 0.003, x1), (flange_r, x1 + 0.004),
             (flange_r, x1 + 0.016), (flange_r - 0.003, x1 + 0.02), (r - 0.012, x1 + 0.02)]
    axis_place(body, 'housing_dome_flange', front, 48, 'dark_anodised')
    for k in range(8):
        angle = TAU * (k + 0.5) / 8
        y = math.cos(angle) * (r + 0.0045)
        z = HOUSING_Z + math.sin(angle) * (r + 0.0045)
        screw((x0 - 0.028, y, z), (-1, 0, 0))
        screw((x1 + 0.02, y, z), (1, 0, 0))
    dome = []
    for i in range(10):
        a = (math.pi / 2) * i / 9
        dome.append((0.069 * math.cos(a), x1 + 0.02 + 0.069 * math.sin(a)))
    inner = [(0.066 * math.cos(a), x1 + 0.02 + 0.066 * math.sin(a)) for a in
             [(math.pi / 2) * (9 - i) / 9 for i in range(10)]]
    dome_obj = axis_object('camera_dome', dome + inner, 40, FLAT['acrylic'])
    dome_obj['role'] = 'camera_dome'
    penetrators()


def axis_object(name, profile, segments, material, axis=(1, 0, 0), origin=(0, 0, HOUSING_Z)):
    verts, faces = lathe(profile, segments)
    u, v, w = Vector((0, 1, 0)), Vector((0, 0, 1)), normalized(axis)
    if abs(w.x) < 0.9:
        u, v, w = frame_from_axis(axis)
    verts = transform(verts, origin, u, v, w)
    return mesh_object(name, verts, faces, material)


def axis_place(collector, name, profile, segments, surface, axis=(1, 0, 0), origin=(0, 0, HOUSING_Z)):
    return collector(axis_object(name, profile, segments, surface_material(surface, 'body'), axis, origin))


PENETRATORS = {}


def penetrators():
    """Wet-mate penetrators on the aft end cap, one per thruster plus tether, lamps and battery."""
    x = HOUSING_X[0] - 0.028
    layout = {'tether': (0.0, 0.0)}
    for k, angle in enumerate([90, 135, 180, 225, 270, 315, 0, 45]):
        a = math.radians(angle)
        layout[f'p{k}'] = (0.048 * math.cos(a), 0.048 * math.sin(a))
    for key, (y, dz) in layout.items():
        origin = (x, y, HOUSING_Z + dz)
        nut = [(0.0, 0.0), (0.0085, 0.0), (0.0085, 0.006), (0.006, 0.0075), (0.0, 0.0075)]
        verts, faces = lathe(nut, 6)
        verts = transform(verts, origin, Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)))
        mesh_object(f'penetrator_nut_{key}', verts, faces, FLAT['steel'], smooth=20)
        boot = [(0.0, 0.0075), (0.0065, 0.0075), (0.0068, 0.012), (0.006, 0.022), (0.0045, 0.03), (0.0, 0.03)]
        verts, faces = lathe(boot, 16)
        verts = transform(verts, origin, Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)))
        mesh_object(f'penetrator_boot_{key}', verts, faces, FLAT['rubber'])
        PENETRATORS[key] = Vector((x - 0.028, y, HOUSING_Z + dz))


def battery():
    x0, x1 = -0.21, 0.12
    r = BATTERY_R
    origin = (0, 0, BATTERY_Z)
    tube = [(0.0, x0 + 0.012), (r, x0 + 0.012), (r, x1 - 0.012), (0.0, x1 - 0.012)]
    axis_place(body, 'battery_tube', tube, 48, 'anodised', origin=origin)
    for name, a, b in (('battery_cap_aft', x0, x0 + 0.014), ('battery_cap_front', x1 - 0.014, x1)):
        cap = [(0.0, a), (r - 0.004, a), (r + 0.004, a + 0.003), (r + 0.004, b - 0.003), (r - 0.004, b), (0.0, b)]
        axis_place(body, name, cap, 48, 'dark_anodised', origin=origin)
    for k in range(4):
        angle = TAU * k / 4 + math.pi / 4
        screw((x0, math.cos(angle) * (r - 0.006), BATTERY_Z + math.sin(angle) * (r - 0.006)), (-1, 0, 0))


def clamp_band(name, x, radius, z, width=0.012):
    profile = [(radius - 0.0005, x - width / 2), (radius + 0.0015, x - width / 2), (radius + 0.002, x),
               (radius + 0.0015, x + width / 2), (radius - 0.0005, x + width / 2)]
    axis_place(body, name, profile, 48, 'stainless', origin=(0, 0, z))
    for side in (-1, 1):
        verts, faces = box((0.016, 0.012, 0.012), bevel=0.0015)
        verts = [(p[0] + x, p[1] + side * 0.0, p[2] + z - side * (radius + 0.006)) for p in verts]
        body(mesh_object(f'{name}_lug_{side}', verts, faces, surface_material('stainless', 'body')))


def tubes():
    """Stainless cross tubes with bolted end flanges."""
    for name, x, z in (('front_tube_upper', 0.335, 0.066), ('front_tube_lower', 0.33, 0.145),
                       ('aft_tube_lower', -0.33, 0.145)):
        verts, faces = sweep([(x, -0.269, z), (x, 0.269, z)], 0.0095, 16)
        body(mesh_object(name, verts, faces, surface_material('stainless', 'body')))
        for side in (-1, 1):
            flange = [(0.0, 0.0), (0.016, 0.0), (0.016, 0.004), (0.011, 0.006), (0.0105, 0.012), (0.0, 0.012)]
            verts, faces = lathe(flange, 24)
            verts = transform(verts, (x, side * 0.269, z), Vector((1, 0, 0)), Vector((0, 0, side)),
                              Vector((0, -side, 0)))
            body(mesh_object(f'{name}_flange_{side}', verts, faces, surface_material('stainless', 'body')))
            screw((x, side * (PLATE_Y + PLATE_T / 2), z), (0, side, 0))


def skids():
    outline = [(-0.33, 0.0), (0.33, 0.0), (0.345, -0.012), (0.35, -0.022), (-0.35, -0.022), (-0.345, -0.012)]
    outline = fillet(outline, 0.006, 3)
    for side in (-1, 1):
        def place(p, side=side):
            return (p[0], side * (PLATE_Y + p[2]), 0.198 + p[1])
        name = 'skid_port' if side < 0 else 'skid_starboard'
        body(profile_solid(name, outline, [], 0.024, 0.003, place, surface_material('uhmw', 'body')))
        for x in (-0.27, 0.0, 0.27):
            screw((x, side * PLATE_Y, 0.198), (0, 0, 1))
        anode = box((0.05, 0.008, 0.026), bevel=0.003)
        verts = [(p[0] - 0.24, p[1] + side * (PLATE_Y + PLATE_T / 2 + 0.004), p[2] + 0.14) for p in anode[0]]
        body(mesh_object(f'anode_{side}', verts, anode[1], surface_material('zinc', 'body')))
        for x in (-0.255, -0.225):
            screw((x, side * (PLATE_Y + PLATE_T / 2 + 0.008), 0.14), (0, side, 0))


def lift_handle():
    path = [(BULKHEAD_X[1], 0, -0.118), (BULKHEAD_X[1] + 0.004, 0, -0.16), (-0.12, 0, -0.196),
            (0.11, 0, -0.196), (BULKHEAD_X[0] - 0.004, 0, -0.16), (BULKHEAD_X[0], 0, -0.118)]
    verts, faces = sweep(catmull(path, 8), 0.0095, 14)
    body(mesh_object('lift_handle', verts, faces, surface_material('stainless', 'body')))
    grip = catmull([(-0.08, 0, -0.196), (0.07, 0, -0.196)], 2)
    verts, faces = sweep(grip, 0.0135, 16)
    body(mesh_object('lift_handle_grip', verts, faces, surface_material('orange', 'body')))
    for x in BULKHEAD_X:
        verts, faces = box((0.03, 0.05, 0.006), bevel=0.0015)
        verts = [(p[0] + x, p[1], p[2] - 0.12) for p in verts]
        body(mesh_object(f'handle_foot_{x:+.2f}', verts, faces, surface_material('stainless', 'body')))
        for y in (-0.017, 0.017):
            screw((x, y, -0.123), (0, 0, -1))


def tether_termination():
    """Tether bar, clamp block, segmented bend restrictor and the pigtail into the end cap."""
    gland = v3(DEF.gland_body)
    for side in (-1, 1):
        path = [(BULKHEAD_X[1] - 0.006, side * 0.1, -0.1), (-0.3, side * 0.1, -0.1), (-0.34, side * 0.09, -0.085),
                (-0.352, side * 0.05, -0.068), (-0.352, side * 0.02, -0.066)]
        verts, faces = sweep(catmull(path, 5), 0.0075, 10)
        body(mesh_object(f'tether_bar_{side}', verts, faces, surface_material('stainless', 'body')))
        verts, faces = box((0.012, 0.03, 0.04), bevel=0.002)
        verts = [(p[0] + BULKHEAD_X[1] - 0.012, p[1] + side * 0.1, p[2] - 0.1) for p in verts]
        body(mesh_object(f'tether_bar_mount_{side}', verts, faces, surface_material('stainless', 'body')))
        screw((BULKHEAD_X[1] - 0.018, side * 0.1, -0.108), (-1, 0, 0))
        screw((BULKHEAD_X[1] - 0.018, side * 0.1, -0.092), (-1, 0, 0))
    verts, faces = box((0.03, 0.05, 0.032), bevel=0.004, segments=3)
    verts = [(p[0] + gland.x + 0.02, p[1], p[2] + gland.z) for p in verts]
    body(mesh_object('tether_clamp_block', verts, faces, surface_material('black_polymer', 'body')))
    for y in (-0.018, 0.018):
        screw((gland.x + 0.02, y, gland.z - 0.016), (0, 0, -1))
    restrictor = []
    for k in range(7):
        x = gland.x + 0.005 - k * 0.0095
        radius = 0.0145 - k * 0.0007
        restrictor += [(radius - 0.002, x), (radius, x - 0.0015), (radius, x - 0.006), (radius - 0.002, x - 0.0075)]
    restrictor = [(0.0, gland.x + 0.005)] + restrictor + [(0.0, restrictor[-1][1])]
    restrictor = [(r, -h) for r, h in restrictor]
    verts, faces = lathe(restrictor, 18)
    verts = transform(verts, (0, 0, gland.z), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)))
    body(mesh_object('tether_bend_restrictor', verts, faces, surface_material('orange', 'body')))
    stub = [(gland.x - 0.07, 0, gland.z), (gland.x - 0.1, 0, gland.z + 0.004), (gland.x - 0.13, 0, gland.z + 0.012)]
    verts, faces = sweep(catmull(stub, 6), 0.0075, 14)
    mesh_object('tether_lead', verts, faces, FLAT['rubber'])
    pigtail = [(gland.x + 0.035, 0, gland.z), (-0.33, 0, gland.z + 0.004), (-0.305, 0, -0.045),
               tuple(PENETRATORS['tether'])]
    cable('tether_pigtail', pigtail, 0.006)


def cable(name, points, radius=0.0042):
    verts, faces = sweep(catmull(points, 5), radius, 7)
    return mesh_object(name, verts, faces, FLAT['rubber'])


def dvl():
    """Downward four-beam DVL on a drop bracket under the housing."""
    x, z_top, z_bottom = 0.222, 0.098, 0.152
    profile = [(0.0, z_top), (0.034, z_top), (0.036, z_top + 0.003), (0.036, z_bottom - 0.012),
               (0.034, z_bottom - 0.004), (0.03, z_bottom), (0.0, z_bottom)]
    verts, faces = lathe(profile, 40)
    verts = [(p[0] + x, p[1], p[2]) for p in verts]
    body(mesh_object('dvl_body', verts, faces, surface_material('dark_anodised', 'body')))
    for k in range(4):
        angle = TAU * k / 4 + math.pi / 4
        tilt = math.radians(22)
        normal = Vector((math.cos(angle) * math.sin(tilt), math.sin(angle) * math.sin(tilt), math.cos(tilt)))
        centre = Vector((x, 0, z_bottom - 0.004)) + Vector((math.cos(angle), math.sin(angle), 0)) * 0.017
        face = [(0.0, 0.0), (0.0095, 0.0), (0.0095, 0.004), (0.0, 0.004)]
        verts, faces = lathe(face, 24)
        u, v, w = frame_from_axis(normal)
        verts = transform(verts, centre, u, v, w)
        mesh_object(f'dvl_transducer_{k}', verts, faces, FLAT['transducer'])
    for y in (-0.03, 0.03):
        verts, faces = box((0.05, 0.004, 0.056), centre=(x, y, 0.074), bevel=0.0012)
        body(mesh_object(f'dvl_bracket_{y:+.2f}', verts, faces, surface_material('stainless', 'body')))
    clamp_band('dvl_clamp', x, HOUSING_R, HOUSING_Z, 0.014)
    for k in range(4):
        angle = TAU * k / 4
        screw((x + math.cos(angle) * 0.026, math.sin(angle) * 0.026, z_top - 0.0005), (0, 0, -1))


def lamps():
    """Two lamp heads on tilting yokes; children of lamp_pivot_N."""
    for index, position in enumerate(DEF.lamp_body):
        pivot_pos = (LAMP_PIVOT_X, position[1], position[2])
        pivot = link(bpy.data.objects.new(f'lamp_pivot_{index}', None))
        pivot.empty_display_size = 0.03
        pivot.matrix_world = Matrix.Translation(to_blender(pivot_pos))
        pivot['role'] = 'lamp_pivot'
        pivot['lamp_index'] = index
        lamp_head(index, pivot, pivot_pos)
        for sign in (-1, 1):
            y = position[1] + sign * 0.034
            arm = [(LAMP_PIVOT_X, y, position[2]), (LAMP_PIVOT_X - 0.004, y, 0.045), (0.335, y, 0.058)]
            plate_arm(f'lamp_yoke_{index}_{sign:+d}', arm)


def plate_arm(name, path):
    """Flat bar following a short path (cross-section 14 x 4 mm)."""
    pts = catmull(path, 5)
    verts = []
    faces = []
    for i, point in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        tangent = (b - a).normalized()
        across = Vector((0, 1, 0))
        width_dir = tangent.cross(across).normalized()
        for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(tuple(point + width_dir * du * 0.007 + across * dv * 0.002))
    for i in range(len(pts) - 1):
        for k in range(4):
            n = (k + 1) % 4
            faces.append((i * 4 + k, i * 4 + n, (i + 1) * 4 + n, (i + 1) * 4 + k))
    faces.append((3, 2, 1, 0))
    last = (len(pts) - 1) * 4
    faces.append((last, last + 1, last + 2, last + 3))
    body(mesh_object(name, verts, faces, surface_material('stainless', 'body'), smooth=30, recalc=True))


def lamp_head(index, pivot, pivot_pos):
    """Finned lamp body, bezel, reflector, LED and cover glass, built about the pivot."""
    x0 = 0.312 - LAMP_PIVOT_X
    x1 = 0.382 - LAMP_PIVOT_X
    r = 0.026
    profile = [(0.0, x0), (0.008, x0), (0.012, x0 + 0.003), (r - 0.003, x0 + 0.004), (r - 0.003, x0 + 0.008)]
    fin_x = x0 + 0.01
    for k in range(4):
        profile += [(r - 0.003, fin_x), (r + 0.002, fin_x + 0.0015), (r + 0.002, fin_x + 0.004),
                    (r - 0.003, fin_x + 0.0055)]
        fin_x += 0.0092
    profile += [(r - 0.001, x1 - 0.016), (r + 0.003, x1 - 0.012), (r + 0.003, x1 - 0.002), (r + 0.001, x1),
                (r - 0.004, x1), (r - 0.004, x1 - 0.004), (0.0, x1 - 0.004)]
    origin = Vector(pivot_pos)
    lamp_part(f'lamp_{index}_body', profile, 28, surface_material('dark_anodised', 'body'), pivot, origin, True)
    reflector = [(0.004, x1 - 0.016), (0.012, x1 - 0.012), (0.019, x1 - 0.007), (r - 0.004, x1 - 0.0045)]
    lamp_part(f'lamp_{index}_reflector', reflector, 32, FLAT['reflector'], pivot, origin)
    emitter = [(0.0, x1 - 0.0155), (0.0055, x1 - 0.0155), (0.0055, x1 - 0.0145), (0.0, x1 - 0.0145)]
    lamp_part(f'lamp_{index}_emitter', emitter, 20, FLAT['led'], pivot, origin)
    glass = [(0.0, x1 - 0.0025), (r - 0.0035, x1 - 0.0025), (r - 0.0035, x1 - 0.0005), (0.0, x1 - 0.0005)]
    lamp_part(f'lamp_{index}_cover', glass, 32, FLAT['glass'], pivot, origin)
    axle = [(0.0, -0.036), (0.0045, -0.036), (0.0045, 0.036), (0.0, 0.036)]
    verts, faces = lathe(axle, 12)
    verts = transform(verts, origin, Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0)))
    obj = mesh_object(f'lamp_{index}_axle', verts, faces, FLAT['steel'])
    reparent(obj, pivot)
    for k in range(4):
        angle = TAU * (k + 0.5) / 4
        position = origin + Vector((x1, math.cos(angle) * (r + 0.0005), math.sin(angle) * (r + 0.0005)))
        screw(tuple(position), (1, 0, 0), parent=pivot)
    route = [tuple(origin + Vector((x0 - 0.002, 0, 0))), tuple(origin + Vector((x0 - 0.02, 0, 0.01))),
             (HOUSING_X[1] + 0.008, origin.y * 0.6, HOUSING_Z + 0.07),
             (HOUSING_X[1] + 0.01, origin.y * 0.45, HOUSING_Z + 0.06)]
    cable(f'lamp_{index}_cable', route, 0.0035)


def lamp_part(name, profile, segments, material, pivot, origin, bake=False):
    verts, faces = lathe(profile, segments)
    verts = transform(verts, origin, Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0)))
    obj = mesh_object(name, verts, faces, material)
    reparent(obj, pivot)
    if bake:
        body(obj)
    return obj


def reparent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def camera_gimbal():
    """Tilt camera inside the dome; children of camera_gimbal."""
    centre = Vector((HOUSING_X[1] + 0.02, 0.0, HOUSING_Z))
    gimbal = link(bpy.data.objects.new('camera_gimbal', None))
    gimbal.empty_display_size = 0.03
    gimbal.matrix_world = Matrix.Translation(to_blender(centre))
    gimbal['role'] = 'camera_gimbal'
    body_profile = [(0.0, -0.022), (0.02, -0.022), (0.023, -0.019), (0.023, 0.018), (0.02, 0.021), (0.016, 0.021),
                    (0.016, 0.03), (0.014, 0.034), (0.0, 0.034)]
    verts, faces = lathe(body_profile, 36)
    verts = transform(verts, centre, Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0)))
    obj = body(mesh_object('camera_body', verts, faces, surface_material('dark_anodised', 'body')))
    reparent(obj, gimbal)
    lens = [(0.0, 0.0335), (0.0115, 0.0335), (0.0115, 0.0345), (0.006, 0.0365), (0.0, 0.037)]
    verts, faces = lathe(lens, 28)
    verts = transform(verts, centre, Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0)))
    reparent(mesh_object('camera_lens', verts, faces, FLAT['lens']), gimbal)
    for side in (-1, 1):
        verts, faces = box((0.045, 0.004, 0.036), bevel=0.0012)
        verts = [(p[0] + centre.x - 0.012, p[1] + side * 0.027, p[2] + centre.z) for p in verts]
        body(mesh_object(f'camera_yoke_{side}', verts, faces, surface_material('stainless', 'body')))
        verts, faces = lathe([(0.0, 0.0), (0.006, 0.0), (0.006, 0.004), (0.0, 0.004)], 16)
        verts = transform(verts, centre + Vector((0, side * 0.0235, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)),
                          Vector((0, side, 0)))
        reparent(mesh_object(f'camera_tilt_bearing_{side}', verts, faces, FLAT['steel']), gimbal)


# ───────────────────────── thrusters ─────────────────────────
THRUSTER_MESHES = {}


def thruster_meshes():
    """Shared duct/motor/strut, guard and rotor meshes in a local frame with the thrust axis on +Z."""
    if THRUSTER_MESHES:
        return THRUSTER_MESHES
    half = 0.0375
    r = DUCT_R
    duct = [(r + 0.0015, -half), (r + 0.0045, -half + 0.0005), (r + 0.0085, -half + 0.012),
            (r + 0.0105, 0.0), (r + 0.0105, half - 0.012), (r + 0.0085, half - 0.003), (r + 0.004, half),
            (r + 0.0005, half - 0.004), (r, half - 0.012), (r, -half + 0.006)]
    duct = fillet(duct, [0.0008, 0.002, 0.0, 0.0, 0.0, 0.003, 0.003, 0.003, 0.0, 0.001], 2)
    duct_verts, duct_faces = lathe(duct, 48)
    band = [(r + 0.0098, -0.009), (r + 0.0128, -0.008), (r + 0.0128, 0.008), (r + 0.0098, 0.009)]
    band_verts, band_faces = lathe(band, 48)
    motor = [(0.0, -0.068), (0.007, -0.068), (0.012, -0.066), (0.0165, -0.062), (0.019, -0.057)]
    z = -0.054
    for k in range(5):
        motor += [(0.019, z), (0.0175, z + 0.001), (0.0175, z + 0.003), (0.019, z + 0.004)]
        z += 0.0078
    motor += [(0.019, -0.012), (0.0175, -0.008), (0.0125, -0.0065), (0.0125, -0.005), (0.0, -0.005)]
    motor_verts, motor_faces = lathe(motor, 20)
    struts = []
    for k in range(3):
        angle = TAU * k / 3 + 0.3
        bar = box((0.032, 0.0035, 0.012), centre=(0.0335, 0.0, -0.028), bevel=0.0012)
        rotation = Matrix.Rotation(angle, 3, 'Z')
        struts.append(([tuple(rotation @ Vector(p)) for p in bar[0]], bar[1]))
    fixed = merge((duct_verts, duct_faces), (band_verts, band_faces), (motor_verts, motor_faces), *struts)
    THRUSTER_MESHES['fixed'] = (fixed, [len(duct_faces), len(band_faces), len(motor_faces)])
    guards = []
    for end, inner in ((half + 0.0035, 0.014), (-half - 0.0035, 0.0215)):
        for ring_r in (inner, 0.034):
            ring = [(ring_r * math.cos(TAU * i / 24), ring_r * math.sin(TAU * i / 24), end) for i in range(25)]
            guards.append(sweep(ring, 0.0012, 4, cap=False))
        for k in range(6):
            angle = TAU * k / 6
            direction = Vector((math.cos(angle), math.sin(angle), 0))
            spoke = [tuple(direction * inner + Vector((0, 0, end))),
                     tuple(direction * (r + 0.003) + Vector((0, 0, end * 0.97)))]
            guards.append(sweep(spoke, 0.0012, 4))
    THRUSTER_MESHES['guard'] = merge(*guards)
    hub = [(0.0, -0.004), (0.0095, -0.004), (0.0108, -0.002), (0.011, 0.008), (0.0098, 0.013), (0.0072, 0.019),
           (0.0038, 0.0235), (0.0, 0.025)]
    hub_verts, hub_faces = lathe(hub, 20)
    THRUSTER_MESHES['rotor'] = merge((hub_verts, hub_faces), blade_surface(0.0105, 0.0445))
    return THRUSTER_MESHES


def thruster_material_assignments(mesh, counts):
    duct, band, motor = counts
    duct_mat = surface_material('black_polymer', 'thruster')
    band_mat = surface_material('stainless', 'thruster')
    motor_mat = surface_material('dark_anodised', 'thruster')
    for material in (duct_mat, band_mat, motor_mat):
        mesh.materials.append(material)
    indices = []
    for i in range(len(mesh.polygons)):
        if i < duct:
            indices.append(0)
        elif i < duct + band:
            indices.append(1)
        elif i < duct + band + motor:
            indices.append(2)
        else:
            indices.append(0)
    mesh.polygons.foreach_set('material_index', indices)


def thrusters():
    meshes = thruster_meshes()
    (fixed_verts, fixed_faces), counts = meshes['fixed']
    fixed_mesh = bpy.data.meshes.new('thruster_fixed')
    fixed_mesh.from_pydata(fixed_verts, [], fixed_faces)
    fixed_mesh.validate()
    finish_mesh(fixed_mesh, 38)
    thruster_material_assignments(fixed_mesh, counts)
    guard_mesh = bpy.data.meshes.new('thruster_guard')
    guard_mesh.from_pydata(meshes['guard'][0], [], meshes['guard'][1])
    guard_mesh.validate()
    finish_mesh(guard_mesh, 50)
    guard_mesh.materials.append(FLAT['steel'])
    rotor_mesh = bpy.data.meshes.new('thruster_rotor')
    rotor_mesh.from_pydata(meshes['rotor'][0], [], meshes['rotor'][1])
    rotor_mesh.validate()
    finish_mesh(rotor_mesh, 55)
    rotor_mesh.materials.append(surface_material('propeller', 'thruster'))
    for index, (name, position, axis) in enumerate(DEF.thrusters):
        matrix = place_on_axis(position, axis)
        fixed = link(bpy.data.objects.new(f'thruster_{index}_{name.split()[-1].lower()}', fixed_mesh))
        fixed.matrix_world = matrix
        guard = link(bpy.data.objects.new(f'thruster_{index}_guard', guard_mesh))
        guard.matrix_world = matrix
        rotor = link(bpy.data.objects.new(f'Rotor_{index}', None))
        rotor.empty_display_size = 0.03
        rotor.matrix_world = matrix
        rotor['role'] = 'rotor'
        rotor['thruster_index'] = index
        rotor['local_axis'] = [0.0, 0.0, 1.0]
        blades = link(bpy.data.objects.new(f'Rotor_{index}_propeller', rotor_mesh))
        blades.parent = rotor
        if index == 0:
            THRUSTER_BAKE_OBJECTS.extend([fixed, blades])
        thruster_mounts(index, position, axis)
        motor_cable(index, position, axis)


def thruster_mounts(index, position, axis):
    """Flat-bar brackets from the duct clamp band to the side plate and the nearest bulkhead."""
    centre = v3(position)
    w = normalized(axis)
    side = 1 if centre.y > 0 else -1
    long_thruster = abs(w.x) > 0.9
    # Anchor points avoid the lightening holes: the side plate (below the long-thruster port) and, for the
    # corner thrusters, the lower cross tube at the same end of the frame.
    plate_z = 0.14 if long_thruster else max(centre.z, 0.045)
    targets = [Vector((centre.x, side * (PLATE_Y - PLATE_T / 2), plate_z))]
    if not long_thruster:
        tube_x = 0.33 if centre.x > 0 else -0.33
        targets.append(Vector((tube_x, centre.y, 0.145 - 0.009)))
    for k, target in enumerate(targets):
        offset = target - centre
        radial = offset - w * offset.dot(w)
        start = centre + radial.normalized() * (DUCT_R + 0.012)
        along = target - start
        length = along.length
        if length < 0.004:
            continue
        u = along.normalized()
        v = w - u * w.dot(u)
        v.normalize()
        n = u.cross(v)
        verts, faces = box((length + 0.008, 0.014, 0.005), bevel=0.0012)
        verts = [tuple(start + u * (p[0] + length / 2) + v * p[1] + n * p[2]) for p in verts]
        body(mesh_object(f'thruster_{index}_bracket_{k}', verts, faces, surface_material('stainless', 'body')))
        if k == 0:
            normal = Vector((0, side, 0))
            screw(tuple(target + normal * PLATE_T), tuple(normal))
        else:
            clamp = [(0.0, -0.011), (0.0125, -0.011), (0.0125, 0.011), (0.0, 0.011)]
            verts, faces = lathe(clamp, 16)
            verts = transform(verts, target + Vector((0, 0, 0.009)), Vector((1, 0, 0)), Vector((0, 0, 1)),
                              Vector((0, 1, 0)))
            body(mesh_object(f'thruster_{index}_tube_clamp', verts, faces, surface_material('black_polymer', 'body')))


def motor_cable(index, position, axis):
    centre = v3(position)
    w = normalized(axis)
    side = 1 if centre.y > 0 else -1
    start = centre - w * 0.068
    exit_point = start - w * 0.018
    keys = list(PENETRATORS.keys())
    end = PENETRATORS[keys[1 + index]]
    mid = Vector((min(exit_point.x, 0.0) * 0.5 - 0.12, side * 0.105, HOUSING_Z + 0.055))
    if centre.x > 0.1:
        mid = Vector((0.08, side * 0.1, HOUSING_Z + 0.06))
    run = Vector((-0.2, side * 0.085, HOUSING_Z + 0.045))
    points = [start, exit_point, mid, run, end + Vector((-0.03, 0, 0)), end]
    cable(f'thruster_{index}_cable', points, 0.0038)


# ───────────────────────── baking ─────────────────────────
def unwrap(objects, label):
    """Pack every object's UVs into one shared atlas with uniform texel density."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(58), island_margin=0.002, area_weight=0.0,
                             scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f'unwrapped {label}: {len(objects)} objects')


def new_image(name, size, colour):
    image = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
    image.generated_color = (0.5, 0.5, 1.0, 1.0) if name.endswith('normal') else (0.0, 0.0, 0.0, 1.0)
    return image


def set_bake_target(atlas, image):
    for name, material in BAKE_MATERIALS.items():
        if BAKE_SOCKETS[name]['atlas'] != atlas:
            continue
        node = material.node_tree.nodes['bake_target']
        node.image = image
        material.node_tree.nodes.active = node


def set_mask_source(atlas, image):
    for name, material in BAKE_MATERIALS.items():
        if BAKE_SOCKETS[name]['atlas'] == atlas:
            material.node_tree.nodes['mask_source'].image = image


def route_emission(atlas, channel):
    """Send colour or (0, rough, metal) to an emission shader, or restore the BSDF when channel is None."""
    for name, sockets in BAKE_SOCKETS.items():
        if sockets['atlas'] != atlas:
            continue
        graph = sockets['graph']
        output = sockets['output']
        if channel is None:
            graph.connect(sockets['shader'], output.inputs['Surface'])
            continue
        emission = graph.add('ShaderNodeEmission')
        graph.connect(sockets[channel], emission.inputs['Color'])
        emission.inputs['Strength'].default_value = 1.0
        graph.connect(emission.outputs[0], output.inputs['Surface'])


def bake_pass(kind, objects, atlas, image, samples):
    set_bake_target(atlas, image)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    scene = bpy.context.scene
    scene.cycles.samples = samples
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    if kind == 'NORMAL':
        bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
    elif kind == 'AO':
        bpy.ops.object.bake(type='AO')
    else:
        bpy.ops.object.bake(type='EMIT')
    print(f'baked {atlas} {kind} {image.name}')


def pixels(image):
    data = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
    image.pixels.foreach_get(data)
    return data.reshape(image.size[1], image.size[0], 4)


def save_png(array, path):
    from PIL import Image
    rgb = np.clip(np.flipud(array[:, :, :3]) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rgb, 'RGB').save(path)


def bake_proxy(objects, name):
    """One joined copy of the atlas objects: Cycles bakes per object, so one object means one pass."""
    bm = bmesh.new()
    materials = []
    for obj in objects:
        mesh = obj.data.copy()
        mesh.transform(obj.matrix_world)
        remap = []
        for material in obj.data.materials:
            if material not in materials:
                materials.append(material)
            remap.append(materials.index(material))
        mesh.polygons.foreach_set('material_index', [remap[p.material_index] for p in mesh.polygons])
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    merged = bpy.data.meshes.new(name)
    bm.to_mesh(merged)
    bm.free()
    for material in materials:
        merged.materials.append(material)
    return link(bpy.data.objects.new(name, merged))


def bake_atlas(atlas, objects, size, hidden):
    """Bake base colour, ORM and normal maps for one atlas; returns the texture file paths."""
    proxy = bake_proxy(objects, f'{atlas}_bake_proxy')
    hidden = list(hidden) + list(objects)
    for obj in hidden:
        obj.hide_render = True
    objects = [proxy]
    colour = new_image(f'{atlas}_basecolor', size, True)
    orm = new_image(f'{atlas}_rm', size, False)
    normal = new_image(f'{atlas}_normal', size, False)
    mask = new_image(f'{atlas}_mask', max(256, size // 2), False)
    samples = 1 if QUICK else 2
    route_emission(atlas, 'mask')
    bake_pass('EMIT', objects, atlas, mask, 2 if QUICK else 4)
    mask.scale(size, size)
    set_mask_source(atlas, mask)
    route_emission(atlas, 'colour')
    bake_pass('EMIT', objects, atlas, colour, samples)
    route_emission(atlas, 'orm')
    bake_pass('EMIT', objects, atlas, orm, samples)
    route_emission(atlas, None)
    bake_pass('NORMAL', objects, atlas, normal, samples)
    for obj in hidden:
        obj.hide_render = False
    mesh = proxy.data
    bpy.data.objects.remove(proxy)
    bpy.data.meshes.remove(mesh)
    OUT.mkdir(parents=True, exist_ok=True)
    colour_px = pixels(colour)
    from PIL import Image
    paths = {}
    # Colour images hold sRGB-encoded bytes; pixels() reads the stored values so no conversion is needed.
    save_png(colour_px, OUT / f'{atlas}_basecolor.png')
    rm = pixels(orm)
    ao = pixels(mask)[:, :, 2]
    packed = np.stack([0.25 + 0.75 * ao, rm[:, :, 1], rm[:, :, 2], np.ones_like(ao)], axis=2)
    save_png(packed, OUT / f'{atlas}_orm.png')
    save_png(pixels(normal), OUT / f'{atlas}_normal.png')
    for key, quality in (('basecolor', 90), ('orm', 90), ('normal', 94)):
        png = OUT / f'{atlas}_{key}.png'
        jpg = OUT / f'{atlas}_{key}.jpg'
        Image.open(png).save(jpg, quality=quality, optimize=True, subsampling=0 if key == 'normal' else 2)
        paths[key] = jpg
    return paths


def glTF_output_group():
    """Node group the glTF exporter reads for the occlusion texture."""
    group = bpy.data.node_groups.get('glTF Material Output')
    if group:
        return group
    group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    group.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    return group


def export_material(atlas, paths):
    material = bpy.data.materials.new(f'{atlas}_atlas')
    graph = Nodes(material)
    shader = graph.add('ShaderNodeBsdfPrincipled')
    images = {}
    for key, path in paths.items():
        node = graph.add('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(path))
        node.image.colorspace_settings.name = 'sRGB' if key == 'basecolor' else 'Non-Color'
        images[key] = node
    graph.connect(images['basecolor'].outputs['Color'], shader.inputs['Base Color'])
    split = graph.add('ShaderNodeSeparateColor')
    graph.connect(images['orm'].outputs['Color'], split.inputs['Color'])
    graph.connect(split.outputs['Green'], shader.inputs['Roughness'])
    graph.connect(split.outputs['Blue'], shader.inputs['Metallic'])
    normal_map = graph.add('ShaderNodeNormalMap')
    graph.connect(images['normal'].outputs['Color'], normal_map.inputs['Color'])
    graph.connect(normal_map.outputs['Normal'], shader.inputs['Normal'])
    group = graph.add('ShaderNodeGroup')
    group.node_tree = glTF_output_group()
    graph.connect(split.outputs['Red'], group.inputs['Occlusion'])
    output = graph.add('ShaderNodeOutputMaterial')
    graph.connect(shader.outputs[0], output.inputs['Surface'])
    return material


def assign_export_material(objects, material):
    meshes = {obj.data for obj in objects}
    for mesh in meshes:
        mesh.materials.clear()
        mesh.materials.append(material)
        mesh.polygons.foreach_set('material_index', [0] * len(mesh.polygons))


# ───────────────────────── assembly / export ─────────────────────────
def join_static(name, keep):
    """Merge every unparented static mesh into one object to keep draw calls low."""
    static = [obj for obj in COLLECTION.objects if obj.type == 'MESH' and obj.parent is None and obj not in keep]
    bm = bmesh.new()
    materials = []
    for obj in static:
        mesh = obj.data.copy()
        mesh.transform(obj.matrix_world)
        remap = []
        for material in obj.data.materials:
            if material not in materials:
                materials.append(material)
            remap.append(materials.index(material))
        indices = [remap[p.material_index] for p in mesh.polygons]
        mesh.polygons.foreach_set('material_index', indices)
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    merged = bpy.data.meshes.new(name)
    bm.to_mesh(merged)
    bm.free()
    for material in materials:
        merged.materials.append(material)
    for obj in static:
        bpy.data.objects.remove(obj)
    merged_obj = link(bpy.data.objects.new(name, merged))
    print(f'joined {len(static)} static parts into {name}')
    return merged_obj


def triangulate_all():
    """Exporter tangents need triangles; n-gons come from curve caps and blade tips."""
    for mesh in {obj.data for obj in COLLECTION.objects if obj.type == 'MESH'}:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()


def anchors():
    for key, position in [('camera', DEF.camera_body), ('tether', DEF.gland_body)] + \
            [(f'lamp_{i}', p) for i, p in enumerate(DEF.lamp_body)]:
        empty = link(bpy.data.objects.new(f'anchor_{key}', None))
        empty.matrix_world = Matrix.Translation(to_blender(position))
        empty['anchor'] = key


def triangle_report():
    rows = []
    for obj in COLLECTION.objects:
        if obj.type == 'MESH':
            obj.data.calc_loop_triangles()
            rows.append((len(obj.data.loop_triangles), obj.name))
    groups = {}
    for count, name in rows:
        key = name.split('_')[0] if not name.startswith('thruster') else name.split('_')[0] + name.split('_')[-1]
        groups[key] = groups.get(key, 0) + count
    for key, count in sorted(groups.items(), key=lambda item: -item[1])[:25]:
        print(f'  {key:30s} {count}')


def triangle_count():
    total = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in COLLECTION.objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.evaluated_get(depsgraph).data
        mesh.calc_loop_triangles()
        total += len(mesh.loop_triangles)
    return total


def reset_scene():
    global COLLECTION
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.unit_settings.system = 'METRIC'
    world = bpy.data.worlds.new('bake_world')
    scene.world = world
    world.light_settings.distance = 0.06
    COLLECTION = bpy.data.collections.new('observation_rov')
    scene.collection.children.link(COLLECTION)


def build():
    reset_scene()
    flat_materials()
    side_plates()
    bulkheads()
    foam_blocks()
    housing()
    battery()
    clamp_band('housing_clamp_front', 0.115, HOUSING_R, HOUSING_Z)
    clamp_band('housing_clamp_aft', -0.12, HOUSING_R, HOUSING_Z)
    tubes()
    skids()
    lift_handle()
    tether_termination()
    dvl()
    lamps()
    camera_gimbal()
    thrusters()
    anchors()
    print('triangles before bake', triangle_count())
    triangle_report()
    if '--report' in sys.argv:
        return
    unwrap(BODY_OBJECTS, 'body')
    unwrap(THRUSTER_BAKE_OBJECTS, 'thruster')
    transparent = [obj for obj in COLLECTION.objects if obj.type == 'MESH' and obj.data.materials
                   and obj.data.materials[0] in (FLAT['acrylic'], FLAT['glass'])]
    body_paths = bake_atlas('body', BODY_OBJECTS, BODY_SIZE, transparent)
    everything_else = [obj for obj in COLLECTION.objects if obj.type == 'MESH' and obj not in THRUSTER_BAKE_OBJECTS]
    thruster_paths = bake_atlas('thruster', THRUSTER_BAKE_OBJECTS, THRUSTER_SIZE, everything_else)
    assign_export_material(BODY_OBJECTS, export_material('body', body_paths))
    thruster_objects = [obj for obj in COLLECTION.objects if obj.type == 'MESH'
                        and obj.data.name in ('thruster_fixed', 'thruster_rotor')]
    assign_export_material(thruster_objects, export_material('thruster', thruster_paths))
    keep = [obj for obj in COLLECTION.objects if obj.type == 'MESH' and obj.data.name in
            ('thruster_fixed', 'thruster_rotor', 'thruster_guard')]
    join_static('observation_rov_hull', keep)
    scene = bpy.context.scene
    scene['model_notes'] = 'Original generic observation-class ROV; mount points follow the default vehicle physics.'
    triangulate_all()
    tris = triangle_count()
    print('triangles after join', tris)
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / 'observation_rov_raw.glb'
    bpy.ops.export_scene.gltf(filepath=str(raw), export_format='GLB', export_extras=True, export_yup=True,
                              export_apply=True, export_tangents=True, export_cameras=False, export_lights=False,
                              export_image_format='AUTO', use_selection=False)
    print('exported', raw, raw.stat().st_size, 'bytes', tris, 'triangles')


if __name__ == '__main__':
    build()
