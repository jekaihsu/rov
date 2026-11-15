"""Build an original 48 m coastal freighter wreck with headless bpy; no external assets.

Run: python cad/build_wreck_chenjiao.py. Outputs raw GLBs, collision triangles and local snag metadata.
Coordinates: X longitudinal, Y transverse, Z up, centre at seabed. Roll is baked into every output.
"""

import json
import math
from pathlib import Path

import bpy
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "simulator/output/chenjiao"
OUT.mkdir(parents=True, exist_ok=True)
VERTS = []
FACES = []
FEATURES = []
ROLL = math.radians(15)


def tilt(p):
    x, y, z = p
    if abs(x) < 2.2:
        x += 0.45 * math.sin(z * 3.7 + y * 2.1) * (2.2 - abs(x))
    return (x, y * math.cos(ROLL) - z * math.sin(ROLL), y * math.sin(ROLL) + z * math.cos(ROLL) - 1)


def mesh(vertices, faces):
    offset = len(VERTS)
    VERTS.extend(tilt(p) for p in vertices)
    FACES.extend(tuple(offset + i for i in face) for face in faces)


def bar(a, b, radius, sides=10):
    a, b = np.array(a, float), np.array(b, float)
    axis = b - a
    axis /= np.linalg.norm(axis)
    u = np.cross(axis, (0, 0, 1) if abs(axis[2]) < 0.9 else (0, 1, 0))
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    vertices = [
        p + radius * (u * math.cos(t) + v * math.sin(t))
        for p in (a, b)
        for t in np.linspace(0, 2 * math.pi, sides, endpoint=False)
    ]
    faces = [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides)]
    faces.extend([tuple(range(sides - 1, -1, -1)), tuple(range(sides, 2 * sides))])
    mesh(vertices, faces)


def box(c, size):
    vertices = [
        (c[0] + x * size[0] / 2, c[1] + y * size[1] / 2, c[2] + z * size[2] / 2)
        for x, y, z in (
            (-1, -1, -1),
            (1, -1, -1),
            (1, 1, -1),
            (-1, 1, -1),
            (-1, -1, 1),
            (1, -1, 1),
            (1, 1, 1),
            (-1, 1, 1),
        )
    ]
    mesh(vertices, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])


def line(points, radius, sides=8):
    for a, b in zip(points, points[1:]):
        bar(a, b, radius, sides)


def snag(name, points, radius, item):
    # Sphere capsules sample the actual angled geometry; SnagFeature's native axis is vertical.
    for i, p in enumerate(points):
        q = tilt(p)
        direction = np.array(tilt(points[min(i + 1, len(points) - 1)])) - tilt(points[max(0, i - 1)])
        direction /= max(np.linalg.norm(direction), 1e-9)
        FEATURES.append(
            dict(
                name=f"Chenjiao {name} {len(FEATURES)}",
                point=q,
                radius=radius,
                height=radius + 0.01,
                direction=direction.tolist(),
                item=item,
                hold_n=[150, 400],
            )
        )


def width(x):
    return 4.5 * max(0.06, min(1, (24 - abs(x)) / (7 if x > 0 else 4))) ** 0.55


def ring(x):
    w = width(x)
    return [(x, y * w, z) for y, z in ((-1, 6), (-1, 3), (-0.8, 1), (-0.4, 0), (0.4, 0), (0.8, 1), (1, 3), (1, 6))]


def build(lod):
    VERTS.clear()
    FACES.clear()
    FEATURES.clear()
    # Discontinuous sections and missing shell panels expose frames and the hold interior.
    for start, end in ((-24, -1.4), (1.4, 24)):
        xs = np.linspace(start, end, 31)
        for n, (a, b) in enumerate(zip(xs, xs[1:])):
            ra, rb = ring(a), ring(b)
            for j in range(7):
                if j in (0, 6) and ((-10 < a < -5) or (3 < a < 8)):
                    continue
                vertices = [ra[j], rb[j], rb[j + 1], ra[j + 1]]
                mesh(vertices, [(0, 1, 2, 3)])
            # Side walkways; large open cargo holds, with one fallen hatch panel.
            for sign in (-1, 1):
                w = min(width(a), width(b))
                if w > 0.7:
                    box(((a + b) / 2, sign * (w - 0.35), 5.85), (b - a, 0.7, 0.16))
            if abs(a) > 16:
                box(((a + b) / 2, 0, 5.8), (b - a, max(0.1, 2 * min(width(a), width(b)) - 0.8), 0.18))
        for x in np.arange(start + 0.7, end, 0.85 if lod < 2 else 1.7):
            line(ring(x), 0.095, 8 if lod < 2 else 4)
            if lod == 0:
                for y in (-width(x), width(x)):
                    for z in (3.3, 4.2, 5.2, 5.7):
                        bar((x, y - 0.025, z), (x, y + 0.025, z), 0.055, 8)
        for x in (start + 0.2, end - 0.2):
            points = ring(x)
            line(points, 0.16)
            if abs(x) < 2:
                snag("fracture", points, 0.16, "debris")
        for y in (-3.5, 3.5):
            for x in np.arange(max(start, -16), min(end, 16), 1):
                box((x, y, 5.65), (0.95, 0.12, 0.55))
    # Collapse into the central hold, supported by buckled beams.
    for i in range(8):
        box((5 + i * 0.7, 0, 2.3 + i * 0.17), (0.68, 5, 0.12))
    for x in (-8, -6, 4, 6):
        points = ring(x)
        snag("exposed rib", points[0:2], 0.1, "debris")
        snag("exposed rib", points[-2:], 0.1, "debris")
    # Aft wheelhouse is assembled around true open windows, with roof and door opening.
    for x in (-20, -15):
        box((x, 0, 6.4), (0.16, 5.7, 1))
        box((x, 0, 8.3), (0.16, 5.7, 0.35))
        for y in np.linspace(-2.8, 2.8, 7):
            box((x, y, 7.4), (0.18, 0.16, 1.1))
    for y in (-2.8, 2.8):
        box((-17.5, y, 6.4), (5, 0.16, 1))
        box((-17.5, y, 8.3), (5, 0.16, 0.35))
        for x in np.linspace(-20, -15, 6):
            box((x, y, 7.4), (0.15, 0.18, 1.1))
    box((-17.5, 0, 8.55), (5.5, 6.1, 0.16))
    box((-18, 0, 9.15), (1.1, 1.1, 1.1))
    # Circular porthole rims, bitts, windlass drums, flanges and drive shafts.
    for x in (-22, -21, 17, 19):
        for sign in (-1, 1):
            points = [
                (x + 0.28 * math.cos(t), sign * (width(x) + 0.025), 4.8 + 0.28 * math.sin(t))
                for t in np.linspace(0, 2 * math.pi, 25)
            ]
            line(points, 0.045, 6)
    for x in (-21, 18):
        for y in (-1, 1):
            box((x, y, 6.05), (1.5, 1.2, 0.25))
            bar((x, y - 0.55, 6.6), (x, y + 0.55, 6.6), 0.36, 24)
            for dy in (-0.55, 0.55):
                bar((x, y + dy - 0.07, 6.6), (x, y + dy + 0.07, 6.6), 0.55, 24)
            for xx in (-0.55, 0.55):
                bar((x + xx, y, 6), (x + xx, y, 6.65), 0.1)
    # Fallen mast, spar and rigging, lying across the forward deck.
    line([(10, -2, 5.9), (2, 2.8, 6.1), (-3, 6, 2)], 0.16, 16)
    line([(3, -0.5, 6), (6, 4.5, 6)], 0.09)
    rope = [(12 - t * 16, -2 + math.sin(t * 8) * 1.3, 6 - 0.7 * t) for t in np.linspace(0, 1, 65)]
    line(rope, 0.055, 6)
    snag("rope", rope[::4], 0.065, "rope")
    # Sagging fishing mesh hung from the broken starboard rail.
    for i in range(13 if lod < 2 else 7):
        u = i / (12 if lod < 2 else 6)
        points = [(2 + u * 7, 3.9 + v * 2, 5.8 - v * 4 - 0.6 * math.sin(math.pi * u)) for v in np.linspace(0, 1, 12)]
        line(points, 0.027, 5)
        if i % 3 == 0:
            snag("net", points[::3], 0.045, "rope")
    for v in np.linspace(0, 1, 12 if lod < 2 else 6):
        line(
            [(2 + u * 7, 3.9 + v * 2, 5.8 - v * 4 - 0.6 * math.sin(math.pi * u)) for u in np.linspace(0, 1, 25)],
            0.027,
            5,
        )
    # Alternating elliptical anchor-chain links lead down to a buried fluked anchor.
    for i in range(56 if lod < 2 else 28):
        t = i / (55 if lod < 2 else 27)
        centre = np.array((20 - 4 * t, -2 - 4 * t, 5.9 - 5.4 * t))
        points = [
            centre
            + np.array((0.18 * math.cos(a), 0.12 * math.sin(a) if i % 2 else 0, 0.12 * math.sin(a) if not i % 2 else 0))
            for a in np.linspace(0, 2 * math.pi, 13 if lod < 2 else 7)
        ]
        line(points, 0.035, 5)
    line([(16, -6, 0.5), (14, -6, 0.5)], 0.12)
    line([(14.5, -7, 0.3), (14, -6, 0.5), (14.5, -5, 0.3)], 0.15)
    # Encrustation clusters on upper plates; seeded placement is reproducible.
    rng = np.random.default_rng(71)
    if lod < 2:
        for _ in range(1100 if lod == 0 else 250):
            x = rng.uniform(-22, 22)
            if abs(x) < 2:
                continue
            y = rng.choice([-1, 1]) * width(x)
            z = rng.uniform(3, 5.8)
            r = rng.uniform(0.025, 0.09)
            bar((x, y, z), (x, y + math.copysign(r, y), z), r, 5)


def material():
    rng = np.random.default_rng(7)
    size = 1024
    y, x = np.mgrid[:size, :size] / size
    noise = rng.random((size, size))
    mottled = (noise - 0.5) * 0.15
    for resolution, weight in ((8, 0.6), (32, 0.4), (128, 0.2)):
        layer = Image.fromarray(np.uint8(rng.random((resolution, resolution)) * 255))
        layer = layer.resize((size, size), Image.Resampling.BICUBIC)
        mottled += (np.asarray(layer) / 255 - 0.5) * weight
    streaks = Image.fromarray(np.uint8(rng.random((32, 256)) * 255))
    streaks = np.asarray(streaks.resize((size, size), Image.Resampling.BICUBIC)) / 255
    mottled -= np.maximum(streaks - 0.65, 0) * 0.4
    rust = np.stack((0.24 + mottled * 0.28, 0.12 + mottled * 0.12, 0.055 + mottled * 0.06), -1)
    mud = np.array([0.27, 0.25, 0.18])
    algae = np.array([0.12, 0.20, 0.095])
    lower = np.clip((0.4 - y) * 4, 0, 1)[..., None]
    upper = (np.clip((y - 0.55) * 2, 0, 0.5) * (mottled > 0.05))[..., None]
    color = rust * (1 - lower) + mud * lower
    color = color * (1 - upper) + algae * upper
    Image.fromarray(np.uint8(np.clip(color, 0, 1) * 255)).save(OUT / "surface.png")
    grain = rng.random((size, size))
    normal = np.stack(
        (0.5 + (grain - 0.5) * 0.2, 0.5 + (np.roll(grain, 1, axis=0) - 0.5) * 0.2, np.ones_like(grain)), axis=-1
    )
    Image.fromarray(np.uint8(normal * 255)).save(OUT / "normal.png")
    m = bpy.data.materials.new("Self-authored rust silt algae")
    m.use_nodes = True
    shader = m.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = 0.92
    shader.inputs["Metallic"].default_value = 0.18
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(OUT / "surface.png"))
    m.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    detail = m.node_tree.nodes.new("ShaderNodeTexImage")
    detail.image = bpy.data.images.load(str(OUT / "normal.png"))
    detail.image.colorspace_settings.name = "Non-Color"
    normal_map = m.node_tree.nodes.new("ShaderNodeNormalMap")
    normal_map.inputs["Strength"].default_value = 0.6
    m.node_tree.links.new(detail.outputs["Color"], normal_map.inputs["Color"])
    m.node_tree.links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
    return m


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    mat = material()
    for lod in range(3):
        build(lod)
        data = bpy.data.meshes.new("Chenjiao mesh")
        data.from_pydata(VERTS, [], FACES)
        data.update()
        obj = bpy.data.objects.new("Chenjiao", data)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        obj.data.materials.append(mat)
        if lod == 2:
            modifier = obj.modifiers.new("Distant silhouette", "DECIMATE")
            modifier.ratio = 0.25
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            data = obj.data
            data.validate()
        uv = data.uv_layers.new()
        for loop in data.loops:
            p = data.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = ((p.x / 8 + p.y / 11), max(0.01, min(0.99, (p.z + 1) / 11)))
        if lod == 0:
            data.calc_loop_triangles()
            tri = np.array([[VERTS[i] for i in t.vertices] for t in data.loop_triangles], np.float32)
            np.save(OUT / "collision_tris.npy", tri)
            (OUT / "snags.json").write_text(json.dumps(FEATURES, indent=2) + "\n")
            target = ROOT / "simulator/qysim/assets/wreck_chenjiao_snags.json"
            target.write_text(json.dumps(FEATURES, indent=2) + "\n")
        bpy.ops.export_scene.gltf(filepath=str(OUT / f"lod{lod}.glb"), export_format="GLB", use_selection=True)
        bpy.data.objects.remove(obj, do_unlink=True)


if __name__ == "__main__":
    main()
