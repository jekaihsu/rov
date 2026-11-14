"""A2 non-destructive surface detailing; execute in the source scene through Blender MCP.

Deterministic original geometry and packed PBR atlases, no downloaded assets.
Existing hulls, collision proxies, labels and route are never moved or reshaped.
"""

import math
import random
import hashlib
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(bpy.data.filepath).parents[2]
RNG = random.Random(2202)
TAU = math.tau


def geometry_digest():
    digest = hashlib.sha256()
    for name in sorted(o.name for o in bpy.data.objects if not o.name.startswith("A2_")):
        obj = bpy.data.objects[name]
        if obj.type != "MESH" or name == "Seabed_sand_ripples":
            continue
        digest.update(name.encode())
        digest.update(np.array(obj.matrix_world, dtype="<f4").tobytes())
        digest.update(np.array([v.co[:] for v in obj.data.vertices], dtype="<f4").tobytes())
    return digest.hexdigest()


ORIGINAL_DIGEST = geometry_digest()


def noise(size, cells, seed):
    rng = np.random.default_rng(seed)
    grid = rng.random((cells + 1, cells + 1), dtype=np.float32)
    p = np.linspace(0, cells - 0.001, size, dtype=np.float32)
    idx = p.astype(int)
    t = p - idx
    t = t * t * (3 - 2 * t)
    a = grid[idx[:, None], idx[None, :]]
    b = grid[idx[:, None] + 1, idx[None, :]]
    c = grid[idx[:, None], idx[None, :] + 1]
    d = grid[idx[:, None] + 1, idx[None, :] + 1]
    return (a * (1 - t[:, None]) + b * t[:, None]) * (1 - t[None, :]) + (c * (1 - t[:, None]) + d * t[:, None]) * t[
        None, :
    ]


def packed_image(name, array, data=False):
    h, w = array.shape[:2]
    img = bpy.data.images.new(name, width=w, height=h, alpha=False)
    if data:
        img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = array
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    return img


def steel_material(index):
    size = 2048
    broad = noise(size, 9, 20 + index)
    medium = noise(size, 53, 80 + index)
    fine = noise(size, 900, 120 + index)
    micro = noise(size, 1900, 180 + index)
    corrosion = broad * 0.50 + medium * 0.25 + fine * 0.15 + micro * 0.10
    paint = np.clip((corrosion - 0.54) * 70, 0, 1)
    pit = np.clip((0.35 - fine) * 7, 0, 1)
    rows = np.arange(size)[:, None]
    height = (rows % (size // 2)) / (size / 2)
    silt = np.clip((0.25 - height) * 2.5, 0, 0.6) * (0.4 + medium * 0.6)
    # Broad nonperiodic islands, chipped margins and fine oxide pitting.
    rust = np.stack([0.12 + medium * 0.16, 0.075 + fine * 0.08, 0.045 + fine * 0.055], axis=-1)
    coating = np.stack([0.10 + fine * 0.09, 0.16 + fine * 0.11, 0.145 + fine * 0.10], axis=-1)
    color = rust * (1 - paint[:, :, None]) + coating * paint[:, :, None]
    color *= (1 - 0.35 * pit[:, :, None]) * (0.65 + 0.7 * micro[:, :, None])
    color = color * (1 - silt[:, :, None]) + np.array([0.25, 0.24, 0.16]) * silt[:, :, None]
    heightmap = fine * 0.55 + micro * 0.18 - pit * 0.22 + paint * 0.12
    dy, dx = np.gradient(heightmap)
    normal = np.stack([-dx * 2.5, -dy * 2.5, np.ones_like(dx)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    normal = normal * 0.5 + 0.5
    roughness = np.clip(0.88 + 0.1 * micro - 0.14 * paint, 0.6, 1)
    rough = np.repeat(roughness[:, :, None], 3, axis=-1)
    mat = bpy.data.materials.new(f"A2_Steel_atlas_{index}_2K")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Metallic"].default_value = 0.12
    for label, arr, socket, is_data in [
        ("BaseColor", color, "Base Color", False),
        ("Roughness", rough, "Roughness", True),
        ("Normal", normal, "Normal", True),
    ]:
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = packed_image(f"A2_Steel_{index}_{label}_2K", arr, is_data)
        texture.extension = "EXTEND"
        if label == "Normal":
            normal_node = nodes.new("ShaderNodeNormalMap")
            normal_node.inputs["Strength"].default_value = 0.6
            links.new(texture.outputs["Color"], normal_node.inputs["Color"])
            links.new(normal_node.outputs["Normal"], bsdf.inputs[socket])
        else:
            links.new(texture.outputs["Color"], bsdf.inputs[socket])
    return mat


def plain_material(name, color, roughness=0.85, metal=0):
    mat = bpy.data.materials.new("A2_" + name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Roughness"].default_value = roughness
    node.inputs["Metallic"].default_value = metal
    return mat


class Batch:
    def __init__(self, name, material, collection):
        self.name = "A2_" + name
        self.material = material
        self.collection = collection
        self.verts = []
        self.faces = []

    def add(self, vertices, faces):
        start = len(self.verts)
        self.verts.extend(tuple(v) for v in vertices)
        self.faces.extend(tuple(start + i for i in f) for f in faces)

    def tube(self, points, radius, sides=5):
        points = [Vector(p) for p in points]
        vertices = []
        for i, p in enumerate(points):
            direction = points[min(i + 1, len(points) - 1)] - points[max(0, i - 1)]
            normal = direction.normalized()
            u = normal.cross(Vector((0, 0, 1)))
            if u.length < 0.01:
                u = normal.cross(Vector((0, 1, 0)))
            u.normalize()
            v = normal.cross(u)
            r = radius[i] if isinstance(radius, list) else radius
            vertices.extend(
                p + r * (math.cos(j * TAU / sides) * u + math.sin(j * TAU / sides) * v) for j in range(sides)
            )
        faces = []
        for i in range(len(points) - 1):
            for j in range(sides):
                a = i * sides + j
                b = i * sides + (j + 1) % sides
                faces.append((a, b, b + sides, a + sides))
        faces.extend([tuple(reversed(range(sides))), tuple(range(len(vertices) - sides, len(vertices)))])
        self.add(vertices, faces)

    def box(self, center, dims, angle=0):
        vertices = []
        for z in [-1, 1]:
            for y in [-1, 1]:
                for x in [-1, 1]:
                    a, b = x * dims[0] / 2, y * dims[1] / 2
                    vertices.append(
                        (
                            center[0] + a * math.cos(angle) - b * math.sin(angle),
                            center[1] + a * math.sin(angle) + b * math.cos(angle),
                            center[2] + z * dims[2] / 2,
                        )
                    )
        self.add(vertices, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])

    def finish(self):
        if not self.verts:
            return None
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.materials.append(self.material)
        mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.data.collections[self.collection].objects.link(obj)
        for face in mesh.polygons:
            face.use_smooth = True
        return obj


def atlas_uv(obj, lo, hi):
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="A2_atlas")
    for poly in obj.data.polygons:
        # Separate port and starboard sheets; no modulo or repeat over the hull length.
        side = 0.5 if poly.center.y >= 1 else 0
        for loop in poly.loop_indices:
            p = obj.matrix_world @ obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u = max(0.001, min(0.999, (p.x - lo) / (hi - lo)))
            v = max(0.002, min(0.498, (p.z + 2) / 22 * 0.496)) + side
            # Transverse bulkheads and horizontal decks need a non-degenerate projection.
            if "HullShell" not in obj.name:
                axis = max(range(3), key=lambda i: abs(poly.normal[i]))
                if axis == 0:
                    u = (p.y + 14) / 28 * 0.6 + (poly.center.x - lo) / (hi - lo) * 0.35
                    u = max(0.001, min(0.999, u))
                elif axis == 2:
                    v = max(0.002, min(0.498, (p.y + 14) / 28 * 0.496)) + side
            uv.data[loop].uv = (u, v)


def basis(normal):
    normal = Vector(normal).normalized()
    u = normal.cross(Vector((1, 0, 0)))
    if u.length < 0.1:
        u = normal.cross(Vector((0, 1, 0)))
    u.normalize()
    return u, normal.cross(u)


def barnacle(batch, p, n, radius):
    u, v = basis(n)
    vertices = []
    for r, h in [(radius, 0), (radius * 0.55, radius * 0.9), (radius * 0.3, radius * 0.68)]:
        for j in range(7):
            vertices.append(p + n * h + (u * math.cos(j * TAU / 7) + v * math.sin(j * TAU / 7)) * r)
    faces = []
    for row in range(2):
        for j in range(7):
            a = row * 7 + j
            b = row * 7 + (j + 1) % 7
            faces.append((a, b, b + 7, a + 7))
    faces.append(tuple(range(14, 21)))
    batch.add(vertices, faces)


def mussel(batch, p, n, length):
    u, v = basis(n)
    angle = RNG.random() * TAU
    u, v = u * math.cos(angle) + v * math.sin(angle), v * math.cos(angle) - u * math.sin(angle)
    vertices = []
    for t in [0, 0.25, 0.6, 1]:
        width = math.sin(math.pi * (0.08 + t * 0.9)) * length * 0.33
        for j in range(6):
            angle = j * TAU / 6
            vertices.append(
                p
                + u * ((t - 0.5) * length)
                + v * (math.cos(angle) * width)
                + n * (0.025 + math.sin(angle) * width * 0.65)
            )
    faces = []
    for row in range(3):
        for j in range(6):
            a = row * 6 + j
            b = row * 6 + (j + 1) % 6
            faces.append((a, b, b + 6, a + 6))
    faces.extend([tuple(reversed(range(6))), tuple(range(18, 24))])
    batch.add(vertices, faces)


def main():
    if any(obj.name.startswith("A2_") for obj in bpy.data.objects):
        raise RuntimeError("Run against the pristine base scene, not an already detailed scene")
    materials = [steel_material(i) for i in range(3)]
    shell_names = ["01_BOW_HullShell", "02_MID_HullShell", "03_STERN_HullShell"]
    intervals = [(-1, 46), (46, 109), (109, 152)]
    for i, collection in enumerate(["01_BOW", "02_MID", "03_STERN"]):
        for obj in bpy.data.collections[collection].objects:
            if obj.type == "MESH" and "Silted" not in obj.name:
                obj.data.materials.clear()
                obj.data.materials.append(materials[i])
                atlas_uv(obj, *intervals[i])
    rust = plain_material("Dark_oxide_seams", (0.11, 0.047, 0.022), 0.94, 0.1)
    shell = plain_material("Barnacle_calcite", (0.42, 0.39, 0.29), 0.94)
    shell2 = plain_material("Barnacle_old_calcite", (0.29, 0.31, 0.24), 0.97)
    mussel_mat = plain_material("Mussel_shell", (0.034, 0.044, 0.049), 0.42, 0.08)
    polyp = plain_material("Anemone_tissue", (0.38, 0.29, 0.18), 0.73)
    coral_mat = plain_material("Soft_coral", (0.36, 0.19, 0.105), 0.85)
    seams = Batch("Plate_laps_and_rivet_rows", rust, "04_ENCRUSTATION")
    barnacles = [
        Batch("Barnacle_colonies_cream", shell, "04_ENCRUSTATION"),
        Batch("Barnacle_colonies_grey", shell2, "04_ENCRUSTATION"),
    ]
    mussels = Batch("Mussel_beds", mussel_mat, "04_ENCRUSTATION")
    anemones = Batch("Anemone_colonies", polyp, "04_ENCRUSTATION")
    corals = Batch("Soft_coral_colonies", coral_mat, "04_ENCRUSTATION")
    for objname in shell_names:
        obj = bpy.data.objects[objname]
        vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
        tree = BVHTree.FromPolygons(vertices, [p.vertices[:] for p in obj.data.polygons])
        xmin, xmax = min(v.x for v in vertices), max(v.x for v in vertices)
        # Lap seams and rivets conform to the original shell, including its list.
        for side in [-1, 1]:
            for z in np.arange(1.2, 12, 1.65):
                previous = None
                for i, x in enumerate(np.arange(xmin + 0.3, xmax - 0.3, 0.23)):
                    p, n, face, distance = tree.ray_cast(Vector((x, side * 35, z)), Vector((0, -side, 0)))
                    if p is None:
                        previous = None
                        continue
                    if n.y * side < 0:
                        n = -n
                    p += n * 0.012
                    if previous is not None and (p - previous).length < 0.5:
                        seams.tube([previous, p], 0.012, 4)
                    if i % 2 == 0:
                        seams.tube([p, p + n * 0.035], [0.031, 0.022], 6)
                    previous = p
            for x in np.arange(xmin + 1, xmax - 1, 3.8):
                previous = None
                for z in np.arange(0.65, 11.8, 0.24):
                    p, n, face, distance = tree.ray_cast(Vector((x, side * 35, z)), Vector((0, -side, 0)))
                    if p is None:
                        previous = None
                        continue
                    if n.y * side < 0:
                        n = -n
                    p += n * 0.014
                    if previous is not None and (p - previous).length < 0.5:
                        seams.tube([previous, p], 0.013, 4)
                    previous = p
        obj.data.calc_loop_triangles()
        triangles = obj.data.loop_triangles
        areas = [t.area for t in triangles]
        # Cluster seeds are area-weighted, with much greater density near the seabed.
        for triangle in RNG.choices(list(triangles), weights=areas, k=2200):
            a, b, c = [vertices[j] for j in triangle.vertices]
            r, s = math.sqrt(RNG.random()), RNG.random()
            p = a * (1 - r) + b * r * (1 - s) + c * r * s
            n = (b - a).cross(c - a).normalized()
            if n.y * (p.y - 1) < 0:
                n = -n
            if p.z < 0.05 or RNG.random() > 0.22 + 0.78 * math.exp(-p.z / 3.8):
                continue
            u, v = basis(n)
            for j in range(RNG.randint(3, 7)):
                q = p + u * RNG.uniform(-0.25, 0.25) + v * RNG.uniform(-0.25, 0.25)
                nearest, norm, idx, dist = tree.find_nearest(q)
                if nearest is None or nearest.z < 0.02:
                    continue
                q = nearest + n * 0.016
                if RNG.random() < 0.52:
                    barnacle(RNG.choice(barnacles), q, n, RNG.uniform(0.035, 0.095))
                else:
                    mussel(mussels, q, n, RNG.uniform(0.08, 0.19))
            if RNG.random() < 0.065:
                top = p + n * RNG.uniform(0.11, 0.2)
                anemones.tube([p, top], [0.045, 0.065], 7)
                for j in range(9):
                    d = u * math.cos(j * TAU / 9) + v * math.sin(j * TAU / 9)
                    anemones.tube(
                        [top, top + d * 0.08 + n * 0.035, top + d * 0.11 + n * 0.012], [0.012, 0.008, 0.0035], 4
                    )
            if RNG.random() < 0.035:
                top = p + n * 0.22
                corals.tube([p, top], [0.026, 0.014], 5)
                for j in range(4):
                    d = u * math.cos(j * TAU / 4) + v * math.sin(j * TAU / 4)
                    corals.tube([p + n * 0.1, top + d * 0.09, top + d * 0.12 + n * 0.07], [0.018, 0.012, 0.005], 5)
    for batch in [seams, *barnacles, mussels, anemones, corals]:
        batch.finish()
    print("A2 surface colonies and riveted seams complete")
    add_fractures(materials)
    add_debris(materials[1], rust)
    add_sediment()
    weather_existing_growth()
    add_runtime_lod()
    assert geometry_digest() == ORIGINAL_DIGEST, "Original vertex positions or transforms changed"
    bpy.context.scene["A2_original_geometry_sha256"] = ORIGINAL_DIGEST
    bpy.context.scene["A2_basis"] = "Illustrative aging, not surveyed biology; seed 2202; original geometry preserved"
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "cad/korean_castle/Korean_Castle_Display.blend"), compress=True)
    print("A2 saved; original geometry fingerprint:", ORIGINAL_DIGEST)


def add_fractures(materials):
    for i, name in enumerate(
        ["01_BOW_Torn_fracture_plates", "02_MID_Torn_fracture_plates", "03_STERN_Torn_fracture_plates"]
    ):
        obj = bpy.data.objects[name]
        batch = Batch(f"Torn_plate_laminations_{i}", materials[i], ["01_BOW", "02_MID", "03_STERN"][i])
        # Thin curled delamination on existing fracture faces, not a moved break.
        for poly in obj.data.polygons:
            pts = [obj.matrix_world @ obj.data.vertices[j].co for j in poly.vertices]
            if len(pts) < 3:
                continue
            a, b = pts[0], pts[1]
            n = poly.normal
            for j in range(3):
                t = (j + 0.2) / 3
                start = a.lerp(b, t)
                end = a.lerp(b, min(t + 0.2, 0.98))
                bend = (start + end) * 0.5 + n * RNG.uniform(0.03, 0.10)
                batch.add([start, end, bend + Vector((0, 0, -0.12))], [(0, 1, 2)])
        new = batch.finish()
        if new:
            atlas_uv(new, *[(-1, 46), (46, 109), (109, 152)][i])


def add_debris(material, rust):
    batch = Batch("Debris_hatches_and_winch", material, "05_SEABED")
    pipes = Batch("Debris_pipes_and_cable", rust, "05_SEABED")
    # All debris outside the hull and well away from inspection stand-off positions.
    for x, y, angle in [(32, 19, 0.4), (81, -19, -0.6), (118, 21, 0.7)]:
        batch.box((x, y, 0.16), (2.2, 1.6, 0.12), angle)
        for offset in [-0.55, 0, 0.55]:
            batch.box((x + offset, y, 0.26), (0.06, 1.35, 0.14), angle)
    x, y = 94, 19
    batch.box((x, y, 0.24), (2.3, 1.5, 0.3), 0.1)
    batch.tube([(x - 1, y, 0.8), (x + 1, y, 0.8)], 0.28, 12)
    for dx in [-0.75, 0.75]:
        batch.tube([(x + dx - 0.06, y, 0.8), (x + dx + 0.06, y, 0.8)], 0.58, 12)
    for x, y in [(18, -18), (53, 19), (123, -19), (103, 18)]:
        # Open pipes: rings connected along a bent centreline.
        points = [Vector((x, y, 0.22)), Vector((x + 1.6, y + 0.2, 0.24)), Vector((x + 2, y + 0.7, 0.26))]
        verts = []
        for p in points:
            for j in range(10):
                a = j * TAU / 10
                verts.append(p + Vector((0, math.cos(a) * 0.16, math.sin(a) * 0.16)))
        faces = []
        for k in range(2):
            for j in range(10):
                a = k * 10 + j
                b = k * 10 + (j + 1) % 10
                faces.append((a, b, b + 10, a + 10))
        pipes.add(verts, faces)
        cable = [
            (x + 4 + math.cos(t) * (0.5 + t * 0.035), y + math.sin(t) * (0.5 + t * 0.035), 0.15 + 0.012 * t)
            for t in np.linspace(0, TAU * 2.6, 75)
        ]
        pipes.tube(cable, 0.025, 5)
    obj = batch.finish()
    atlas_uv(obj, 46, 109)
    add_debris_collision(obj)
    pipes.finish()


def add_debris_collision(visual):
    """Large fallen hatches and winch must stop an ROV; sub-grid shells remain visual detail."""
    proxy = bpy.data.objects.new("A2_COL_Debris_hatches_and_winch", visual.data.copy())
    proxy.data.materials.clear()
    proxy.data.materials.append(bpy.data.materials["Dark recess steel"])
    bpy.data.collections["09_COLLISION"].objects.link(proxy)
    proxy.hide_render = True


def add_sediment():
    """Sculpt shallow scour and irregular depositional shoulders into the actual seabed."""
    obj = bpy.data.objects["Seabed_sand_ripples"]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    edges = [e for e in bm.edges if all(-15 < v.co.x < 168 and abs(v.co.y) < 28 for v in e.verts)]
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=3, use_grid_fill=True)
    pits = [(43, -12, 8, 2.4), (48, 13, 7, 2.7), (106, -12, 7, 2.3), (112, 14, 8, 2.6)]
    for vertex in bm.verts:
        x, y, z = vertex.co
        delta = 0
        for cx, cy, rx, ry in pits:
            r = math.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
            irregular = 1 + 0.12 * math.sin(x * 0.73 + y * 1.3)
            delta += -0.19 * math.exp(-r * r * 3) + 0.17 * math.exp(-(((r - 0.95) / 0.25) ** 2)) * irregular
        if 6 < x < 145:
            delta += 0.13 * math.exp(-(((abs(y - 1) - 12.2) / 1.8) ** 2)) * (0.7 + 0.3 * math.sin(x * 0.27))
        vertex.co.z += delta
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def weather_existing_growth():
    """Give the original accretion masses a granular living crust instead of flat facets."""
    RNG.seed(2202)
    size = 2048
    n = noise(size, 210, 772)
    m = noise(size, 37, 773)
    color = np.stack([0.16 + n * 0.23, 0.19 + n * 0.2, 0.12 + n * 0.15], axis=-1)
    freckles = np.clip((n - 0.64) * 6, 0, 1)
    color = color * (1 - freckles[:, :, None] * 0.7) + freckles[:, :, None] * 0.35
    color *= 0.7 + m[:, :, None] * 0.6
    texture = packed_image("A2_Living_crust_BaseColor_2K", color)
    normal = bpy.data.images.get("encrusted_steel_normal.png")
    for mat in bpy.data.materials:
        if not mat.name.startswith("Marine growth") and mat.name != "Encrusted debris":
            continue
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = texture
        links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bump = nodes.new("ShaderNodeTexImage")
        bump.image = normal
        norm = nodes.new("ShaderNodeNormalMap")
        norm.inputs["Strength"].default_value = 0.8
        links.new(bump.outputs["Color"], norm.inputs["Color"])
        links.new(norm.outputs["Normal"], bsdf.inputs["Normal"])
    for obj in list(bpy.data.collections["04_ENCRUSTATION"].objects) + [bpy.data.objects["Rubble_apron"]]:
        if obj.name.startswith("A2_") or obj.type != "MESH":
            continue
        uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="Growth_coordinates")
        for face in obj.data.polygons:
            axis = max(range(3), key=lambda i: abs(face.normal[i]))
            axes = [i for i in range(3) if i != axis]
            for loop in face.loop_indices:
                p = obj.data.vertices[obj.data.loops[loop].vertex_index].co
                uv.data[loop].uv = (p[axes[0]] * 0.09, p[axes[1]] * 0.09)
    # Mature colonies grow on the window frames as well as on the hull itself.
    mat = bpy.data.materials["A2_Barnacle_calcite"]
    batch = Batch("Window_frame_barnacles", mat, "04_ENCRUSTATION")
    obj = bpy.data.objects["Aft_window_frames"]
    obj.data.calc_loop_triangles()
    triangles = list(obj.data.loop_triangles)
    for tri in RNG.choices(triangles, weights=[t.area for t in triangles], k=700):
        a, b, c = [obj.matrix_world @ obj.data.vertices[i].co for i in tri.vertices]
        r, t = math.sqrt(RNG.random()), RNG.random()
        p = a * (1 - r) + b * r * (1 - t) + c * r * t
        n = (b - a).cross(c - a).normalized()
        barnacle(batch, p, n, RNG.uniform(0.025, 0.065))
    batch.finish()


def add_runtime_lod():
    """Keep authored detail for offline closeups, use a lighter evaluated mesh for glTF."""
    for obj in bpy.data.objects:
        if not obj.name.startswith("A2_") or obj.type != "MESH":
            continue
        if not any(word in obj.name for word in ["Barnacle", "Mussel", "Anemone", "Soft_coral", "barnacle"]):
            continue
        modifier = obj.modifiers.new("A2_Runtime_LOD", "DECIMATE")
        modifier.ratio = 0.27
        modifier.use_collapse_triangulate = True
        modifier.show_render = False
        modifier.show_viewport = True
        obj["A2_lod"] = "Full source for Cycles; 27 percent evaluated surface geometry for runtime glTF"


main()
