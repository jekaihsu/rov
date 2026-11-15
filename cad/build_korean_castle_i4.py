"""I4: rebuild Korean Castle visuals within triangle and texture budgets (headless bpy).

Opens the existing illustrative .blend, replaces packed 1K PBR maps with softer
low-saturation underwater atlases (deep rust, muted fouling, neutral rubble),
raises hull texel density via UV tiling, drops the embedded flat seabed plane
(scene uses seabed.js), trims heavy accretion, adds sparse fracture flakes and
depth-weighted biofouling, then exports LOD0/1/2 raw GLBs plus collision/route
arrays. Never writes the .blend back.

Run from the repository root:
  /tmp/i4env/bin/python cad/build_korean_castle_i4.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BLEND = ROOT / "cad/korean_castle/Korean_Castle_Display.blend"
OUT = ROOT / "simulator/output/korean_castle_i4"
VIS = ["01_BOW", "02_MID", "03_STERN", "04_ENCRUSTATION", "05_SEABED"]
# Scene terrain (seabed.js) already draws rippled sand; keep rubble / fallen steel only.
EXCLUDE_VISUAL = {"Seabed_sand_ripples"}
RNG = random.Random(1404)
TAU = math.tau
SIZE = 1024
# Metres of hull per atlas tile: denser than the authored unwrap so 1 m shots keep grit.
HULL_UV_SCALE = 4.2
GROWTH_UV_SCALE = 0.28
ROCK_UV_SCALE = 0.22


def noise(size: int, cells: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid = rng.random((cells + 1, cells + 1), dtype=np.float32)
    p = np.linspace(0, cells - 0.001, size, dtype=np.float32)
    idx = p.astype(np.int32)
    t = p - idx
    t = t * t * (3 - 2 * t)
    a = grid[idx[:, None], idx[None, :]]
    b = grid[idx[:, None] + 1, idx[None, :]]
    c = grid[idx[:, None], idx[None, :] + 1]
    d = grid[idx[:, None] + 1, idx[None, :] + 1]
    return (a * (1 - t[:, None]) + b * t[:, None]) * (1 - t[None, :]) + (
        c * (1 - t[:, None]) + d * t[:, None]
    ) * t[None, :]


def write_image(image: bpy.types.Image, rgb: np.ndarray, data: bool = False) -> None:
    h, w = rgb.shape[:2]
    if tuple(image.size) != (w, h):
        image.scale(w, h)
    if data:
        image.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = rgb
    image.pixels.foreach_set(rgba.ravel())
    image.pack()


def ensure_image(name: str) -> bpy.types.Image:
    image = bpy.data.images.get(name)
    if image is None:
        image = bpy.data.images.new(name, width=SIZE, height=SIZE, alpha=False)
    return image


def set_repeat(image: bpy.types.Image | None) -> None:
    if image is None:
        return
    image.alpha_mode = "NONE"


def steel_maps() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Deep brown / dark ochre rust with soft grey-green film — not bright orange or mint."""
    broad = noise(SIZE, 11, 41)
    medium = noise(SIZE, 47, 42)
    fine = noise(SIZE, 180, 43)
    micro = noise(SIZE, 900, 44)
    rows = np.arange(SIZE, dtype=np.float32)[:, None]
    cols = np.arange(SIZE, dtype=np.float32)[None, :]
    seam_u = np.abs(((cols / SIZE) * 18) % 1 - 0.5)
    seam_v = np.abs(((rows / SIZE) * 10) % 1 - 0.5)
    rivet = ((np.sin(cols * 0.22) * np.sin(rows * 0.22)) > 0.92).astype(np.float32)
    # Soft paint-loss mask (no hard camouflage edges).
    paint = np.clip((broad * 0.55 + medium * 0.3 + fine * 0.15 - 0.42) * 3.2, 0, 1)
    pit = np.clip((0.32 - fine) * 6, 0, 1)
    silt = np.clip(0.55 - rows / SIZE, 0, 1) * (0.35 + medium * 0.65)
    # Deep brown / dark ochre (low chroma). Lifted slightly so real-mode optics still read grit.
    rust = np.stack(
        [
            0.18 + medium * 0.07 + fine * 0.03,
            0.11 + fine * 0.04 + micro * 0.02,
            0.07 + micro * 0.02,
        ],
        axis=-1,
    )
    # Soft green-grey / brown-grey film (desaturated fouling remnant), not mint.
    coating = np.stack(
        [
            0.15 + fine * 0.03 + medium * 0.02,
            0.16 + fine * 0.04 + micro * 0.02,
            0.14 + micro * 0.02,
        ],
        axis=-1,
    )
    color = rust * (1 - paint[:, :, None]) + coating * paint[:, :, None]
    color *= 1 - 0.18 * pit[:, :, None]
    silt_col = np.array([0.20, 0.18, 0.14], dtype=np.float32)
    color = color * (1 - 0.28 * silt[:, :, None]) + silt_col * silt[:, :, None]
    color = np.clip(color, 0, 1)
    height = fine * 0.45 + micro * 0.2 - pit * 0.25 + paint * 0.08
    height -= np.clip(0.08 - seam_u, 0, 0.08) * 0.35
    height -= np.clip(0.1 - seam_v, 0, 0.1) * 0.2
    height += rivet * 0.08
    dy, dx = np.gradient(height)
    normal = np.stack([-dx * 3.2, -dy * 3.2, np.ones_like(dx)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    normal = normal * 0.5 + 0.5
    roughness = np.clip(0.84 + 0.12 * micro - 0.14 * paint + 0.08 * pit, 0.58, 1.0)
    rough = np.repeat(roughness[:, :, None], 3, axis=-1)
    return color, rough, normal


def growth_maps() -> tuple[np.ndarray, np.ndarray]:
    """Soft low-sat green-grey and brown-grey fouling; mottled depth layers in one atlas."""
    n = noise(SIZE, 160, 90)
    m = noise(SIZE, 28, 91)
    speck = noise(SIZE, 700, 92)
    depth = noise(SIZE, 8, 93)
    # Brown-grey (deeper / siltier) ↔ green-grey (shallower film). Both low chroma.
    brown = np.stack(
        [0.23 + n * 0.07, 0.20 + n * 0.05, 0.16 + n * 0.04],
        axis=-1,
    )
    green_grey = np.stack(
        [0.19 + n * 0.05, 0.21 + n * 0.05 + m * 0.02, 0.18 + n * 0.04],
        axis=-1,
    )
    mix = np.clip(0.35 + depth * 0.45 + m * 0.15, 0, 1)[:, :, None]
    color = brown * (1 - mix) + green_grey * mix
    freckles = np.clip((speck - 0.62) * 5, 0, 1)
    freckle_col = np.array([0.28, 0.24, 0.18], dtype=np.float32)
    color = color * (1 - freckles[:, :, None] * 0.35) + freckles[:, :, None] * freckle_col
    color = np.clip(color, 0, 1)
    height = n * 0.55 + speck * 0.25
    dy, dx = np.gradient(height)
    normal = np.stack([-dx * 2.8, -dy * 2.8, np.ones_like(dx)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    normal = normal * 0.5 + 0.5
    return color, normal


def rock_maps() -> np.ndarray:
    """Neutral rock / rubble albedo — no fluorescent growth tint.

    Shares the steel normal atlas so the packed set stays at six 1K maps (≤32 MiB).
    Multi-octave noise avoids the large square cells that read as pixel blocks.
    """
    broad = noise(SIZE, 18, 70)
    medium = noise(SIZE, 64, 71)
    fine = noise(SIZE, 220, 72)
    micro = noise(SIZE, 800, 73)
    base = 0.20 + broad * 0.07 + medium * 0.06 + fine * 0.04
    color = np.stack(
        [
            base + micro * 0.03,
            base * 0.97 + micro * 0.02,
            base * 0.92 + micro * 0.02,
        ],
        axis=-1,
    )
    wet = np.clip((0.48 - fine) * 2.2, 0, 1)
    color = color * (1 - 0.14 * wet[:, :, None])
    cooler = np.clip((medium - 0.6) * 2.0, 0, 1)
    color = color * (1 - cooler[:, :, None] * 0.1) + cooler[:, :, None] * np.array(
        [0.17, 0.17, 0.16], dtype=np.float32
    )
    return np.clip(color, 0, 1)


def wire_pbr(
    mat: bpy.types.Material,
    *,
    color: bpy.types.Image,
    normal: bpy.types.Image | None = None,
    rough: bpy.types.Image | None = None,
    roughness: float = 0.9,
    metallic: float = 0.0,
    normal_strength: float = 0.7,
    tint: tuple[float, float, float] | None = None,
    tint_factor: float = 0.0,
) -> None:
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    for node in list(nodes):
        if node != bsdf and node.type != "OUTPUT_MATERIAL":
            nodes.remove(node)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = color
    tex.extension = "REPEAT"
    color_out = tex.outputs["Color"]
    if tint is not None and tint_factor > 0:
        # Multiply so glTF keeps baseColorFactor = tint (depth variants stay distinct after pack).
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        # Effective factor: lerp(1, tint, tint_factor) so mild bias survives export.
        biased = tuple(1.0 - tint_factor + tint_factor * channel for channel in tint)
        mix.inputs[7].default_value = (*biased, 1.0)
        links.new(color_out, mix.inputs[6])
        color_out = mix.outputs[2]
    links.new(color_out, bsdf.inputs["Base Color"])
    if rough is not None:
        rtex = nodes.new("ShaderNodeTexImage")
        rtex.image = rough
        rtex.extension = "REPEAT"
        links.new(rtex.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = roughness
    if normal is not None:
        ntex = nodes.new("ShaderNodeTexImage")
        ntex.image = normal
        ntex.extension = "REPEAT"
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = normal_strength
        links.new(ntex.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic


def replace_steel_textures() -> None:
    color, rough, normal = steel_maps()
    write_image(ensure_image("encrusted_steel_basecolor.png"), color)
    write_image(ensure_image("encrusted_steel_roughness.png"), rough, data=True)
    write_image(ensure_image("encrusted_steel_normal.png"), normal, data=True)
    for name in ("encrusted_steel_basecolor.png", "encrusted_steel_roughness.png", "encrusted_steel_normal.png"):
        set_repeat(bpy.data.images.get(name))
    mat = bpy.data.materials.get("Weathered steel | original PBR maps")
    if mat and mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf and "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.12
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.extension = "REPEAT"


def apply_growth_textures() -> None:
    color, normal = growth_maps()
    base = ensure_image("I4_growth_basecolor.png")
    norm = ensure_image("I4_growth_normal.png")
    write_image(base, color)
    write_image(norm, normal, data=True)
    set_repeat(base)
    set_repeat(norm)
    # Depth layering via tint: limestone (deeper/brown-grey) vs olive (shallower green-grey).
    variants = {
        "Marine growth | limestone": ((0.22, 0.19, 0.15), 0.28),
        "Marine growth | olive": ((0.17, 0.21, 0.17), 0.22),
        "Marine growth | mustard": ((0.23, 0.20, 0.15), 0.25),
    }
    for name in list(bpy.data.materials.keys()):
        if not name.startswith("Marine growth"):
            continue
        tint, factor = variants.get(name, ((0.20, 0.20, 0.17), 0.18))
        wire_pbr(
            bpy.data.materials[name],
            color=base,
            normal=norm,
            roughness=0.93,
            normal_strength=0.65,
            tint=tint,
            tint_factor=factor,
        )


def apply_rock_textures() -> None:
    color = rock_maps()
    base = ensure_image("I4_rock_basecolor.png")
    write_image(base, color)
    set_repeat(base)
    # Reuse steel normals (no seventh unique map) so GPU mips stay ≤32 MiB.
    steel_n = bpy.data.images.get("encrusted_steel_normal.png")
    rock_mat = bpy.data.materials.get("Encrusted debris")
    if rock_mat is None:
        rock_mat = bpy.data.materials.new("I4_rubble_rock")
    wire_pbr(rock_mat, color=base, normal=steel_n, roughness=0.95, normal_strength=0.9)
    rubble = bpy.data.objects.get("Rubble_apron")
    if rubble is not None:
        rubble.data.materials.clear()
        rubble.data.materials.append(rock_mat)
        project_uv(rubble, ROCK_UV_SCALE)


def apply_oxide_texture() -> None:
    """Reuse the steel atlas; bias toward deep brown oxide, not bright orange."""
    mat = bpy.data.materials.get("Fresh exposed oxide")
    if not mat:
        return
    wire_pbr(
        mat,
        color=bpy.data.images.get("encrusted_steel_basecolor.png"),
        rough=bpy.data.images.get("encrusted_steel_roughness.png"),
        normal=bpy.data.images.get("encrusted_steel_normal.png"),
        metallic=0.28,
        normal_strength=0.55,
        tint=(0.22, 0.11, 0.06),
        tint_factor=0.4,
    )


def scale_uvs(obj: bpy.types.Object, scale: float) -> None:
    if obj is None or obj.type != "MESH" or scale == 1.0:
        return
    uv = obj.data.uv_layers.active
    if uv is None:
        return
    for loop in uv.data:
        loop.uv = (loop.uv[0] * scale, loop.uv[1] * scale)


def project_uv(obj: bpy.types.Object, scale: float = 0.08) -> None:
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="I4_uv")
    for poly in obj.data.polygons:
        axis = max(range(3), key=lambda i: abs(poly.normal[i]))
        axes = [i for i in range(3) if i != axis]
        for loop in poly.loop_indices:
            p = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.data[loop].uv = (p[axes[0]] * scale, p[axes[1]] * scale)


def triangle_count(obj: bpy.types.Object) -> int:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    count = len(me.loop_triangles)
    ev.to_mesh_clear()
    return count


def visual_objects() -> list[bpy.types.Object]:
    keep: set[str] = set()
    for name in VIS:
        for obj in bpy.data.collections[name].all_objects:
            if obj.name in EXCLUDE_VISUAL:
                continue
            keep.add(obj.name)
    return [obj for obj in bpy.data.objects if obj.name in keep and obj.type == "MESH"]


def total_visual_tris() -> int:
    return sum(triangle_count(obj) for obj in visual_objects())


def decimate(obj: bpy.types.Object, ratio: float) -> None:
    if ratio >= 0.999 or obj.type != "MESH":
        return
    modifier = obj.modifiers.new("I4_Decimate", "DECIMATE")
    modifier.ratio = max(0.05, min(1.0, ratio))
    modifier.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def trim_heavy_accretion() -> None:
    """Free triangle budget so LOD0 stays ≤300k after adding sparse detail."""
    targets = {
        "Surface_accretion_0": 0.62,
        "Surface_accretion_1": 0.62,
        "Surface_accretion_2": 0.62,
        "Surface_accretion_3": 0.62,
        "Sparse_branching_growth": 0.55,
        "Rubble_apron": 0.72,
    }
    for name, ratio in targets.items():
        obj = bpy.data.objects.get(name)
        if obj:
            decimate(obj, ratio)
            project_uv(obj, GROWTH_UV_SCALE if name != "Rubble_apron" else ROCK_UV_SCALE)


def basis(normal: Vector) -> tuple[Vector, Vector]:
    normal = Vector(normal).normalized()
    side = normal.cross(Vector((1, 0, 0)))
    if side.length < 0.1:
        side = normal.cross(Vector((0, 1, 0)))
    side.normalize()
    return side, normal.cross(side)


class Batch:
    def __init__(self, name: str, material: bpy.types.Material, collection: str):
        self.name = "I4_" + name
        self.material = material
        self.collection = collection
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[tuple[int, ...]] = []

    def add(self, vertices, faces) -> None:
        start = len(self.verts)
        self.verts.extend(tuple(v) for v in vertices)
        self.faces.extend(tuple(start + i for i in face) for face in faces)

    def finish(self) -> bpy.types.Object | None:
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
        project_uv(obj, GROWTH_UV_SCALE)
        return obj


def add_barnacle(batch: Batch, point: Vector, normal: Vector, radius: float) -> None:
    u, v = basis(normal)
    verts = []
    for r, h in ((radius, 0.0), (radius * 0.55, radius * 0.85), (radius * 0.25, radius * 0.55)):
        for j in range(6):
            a = j * TAU / 6
            verts.append(point + normal * h + (u * math.cos(a) + v * math.sin(a)) * r)
    faces = []
    for row in range(2):
        for j in range(6):
            a = row * 6 + j
            b = row * 6 + (j + 1) % 6
            faces.append((a, b, b + 6, a + 6))
    faces.append(tuple(range(12, 18)))
    batch.add(verts, faces)


def add_mussel(batch: Batch, point: Vector, normal: Vector, length: float) -> None:
    u, v = basis(normal)
    angle = RNG.random() * TAU
    u = u * math.cos(angle) + v * math.sin(angle)
    v = normal.cross(u)
    verts = []
    for t in (0.0, 0.45, 1.0):
        width = math.sin(math.pi * (0.1 + t * 0.8)) * length * 0.3
        for j in range(5):
            a = j * TAU / 5
            verts.append(
                point
                + u * ((t - 0.5) * length)
                + v * (math.cos(a) * width)
                + normal * (0.02 + math.sin(a) * width * 0.55)
            )
    faces = []
    for row in range(2):
        for j in range(5):
            a = row * 5 + j
            b = row * 5 + (j + 1) % 5
            faces.append((a, b, b + 5, a + 5))
    faces.append(tuple(range(10, 15)))
    batch.add(verts, faces)


def add_biofouling() -> None:
    # Deeper / lower hull → limestone (brown-grey); mid → olive (green-grey).
    limestone = bpy.data.materials.get("Marine growth | limestone") or bpy.data.materials[0]
    olive = bpy.data.materials.get("Marine growth | olive") or limestone
    barnacles = Batch("Barnacles", limestone, "04_ENCRUSTATION")
    mussels = Batch("Mussels", olive, "04_ENCRUSTATION")
    hulls = [
        bpy.data.objects.get(name)
        for name in ("01_BOW_HullShell", "02_MID_HullShell", "03_STERN_HullShell")
    ]
    for obj in hulls:
        if obj is None:
            continue
        obj.data.calc_loop_triangles()
        tris = list(obj.data.loop_triangles)
        if not tris:
            continue
        weights = [max(t.area, 1e-6) for t in tris]
        picks = RNG.choices(tris, weights=weights, k=900)
        for tri in picks:
            a, b, c = [obj.matrix_world @ obj.data.vertices[i].co for i in tri.vertices]
            r = math.sqrt(RNG.random())
            s = RNG.random()
            point = a * (1 - r) + b * r * (1 - s) + c * r * s
            normal = (b - a).cross(c - a)
            if normal.length < 1e-6:
                continue
            normal.normalize()
            depth_w = math.exp(-point.z / 3.5)
            if point.z < 0.08 or RNG.random() > 0.18 + 0.7 * depth_w:
                continue
            # Near the bed: barnacles (limestone). Higher: mussels (olive).
            if point.z < 2.2 or RNG.random() < 0.35 + 0.45 * depth_w:
                add_barnacle(barnacles, point + normal * 0.012, normal, RNG.uniform(0.03, 0.08))
            else:
                add_mussel(mussels, point + normal * 0.012, normal, RNG.uniform(0.07, 0.16))
    barnacles.finish()
    mussels.finish()


def add_fracture_flakes() -> None:
    oxide = bpy.data.materials.get("Fresh exposed oxide") or bpy.data.materials[0]
    for index, name in enumerate(
        ("01_BOW_Torn_fracture_plates", "02_MID_Torn_fracture_plates", "03_STERN_Torn_fracture_plates")
    ):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        batch = Batch(f"Fracture_flakes_{index}", oxide, ["01_BOW", "02_MID", "03_STERN"][index])
        for poly in obj.data.polygons:
            if poly.area < 0.15 or RNG.random() > 0.35:
                continue
            pts = [obj.matrix_world @ obj.data.vertices[i].co for i in poly.vertices]
            if len(pts) < 3:
                continue
            a, b = pts[0], pts[min(1, len(pts) - 1)]
            normal = Vector(poly.normal)
            for step in range(2):
                t = (step + 0.25) / 2
                start = a.lerp(b, t)
                end = a.lerp(b, min(t + 0.18, 0.95))
                bend = (start + end) * 0.5 + normal * RNG.uniform(0.04, 0.11)
                batch.add([start, end, bend + Vector((0, 0, -0.08))], [(0, 1, 2)])
        batch.finish()


def clear_i4_objects() -> None:
    for obj in list(bpy.data.objects):
        if obj.name.startswith("I4_"):
            bpy.data.objects.remove(obj, do_unlink=True)


def densify_hull_uvs() -> None:
    for name in ("01_BOW_HullShell", "02_MID_HullShell", "03_STERN_HullShell"):
        obj = bpy.data.objects.get(name)
        if obj:
            scale_uvs(obj, HULL_UV_SCALE)


def export_visual(path: Path) -> None:
    for obj in bpy.data.objects:
        obj.select_set(False)
    keep = {obj.name for obj in visual_objects()}
    for obj in bpy.data.objects:
        if obj.name in keep:
            obj.select_set(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_image_format="JPEG",
        export_image_quality=82,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
    )


def export_collision_and_route() -> None:
    dg = bpy.context.evaluated_depsgraph_get()

    def tris_of(obj):
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        matrix = obj.matrix_world
        verts = np.array([tuple(matrix @ v.co) for v in me.vertices], float)
        faces = np.array([tuple(t.vertices) for t in me.loop_triangles], int)
        ev.to_mesh_clear()
        return verts, faces

    cols = []
    for obj in bpy.data.collections["09_COLLISION"].objects:
        if obj.type != "MESH":
            continue
        verts, faces = tris_of(obj)
        cols.append(verts[faces])
    tri = np.concatenate(cols)
    np.save(OUT / "collision_tris.npy", tri.astype(np.float32))
    route = bpy.data.objects["Preview_ROV_path"]
    verts, _ = tris_of(route)
    np.save(OUT / "route_verts.npy", verts.astype(np.float32))
    print("collision tris", tri.shape[0], "route verts", len(verts))


def apply_lod_decimate(ratio: float) -> list[str]:
    applied = []
    for obj in visual_objects():
        if obj.name.startswith("COL_"):
            continue
        before = triangle_count(obj)
        if before < 200:
            continue
        decimate(obj, ratio)
        applied.append(obj.name)
    return applied


def purge_unused_seabed_image() -> None:
    """Drop the unused ripple-sand atlas so packed GPU memory stays ≤32 MiB with rock maps."""
    for name in ("seabed_basecolor.png", "seabed_basecolor"):
        image = bpy.data.images.get(name)
        if image is not None:
            bpy.data.images.remove(image)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    clear_i4_objects()
    print("baseline tris", total_visual_tris())
    replace_steel_textures()
    apply_growth_textures()
    apply_oxide_texture()
    apply_rock_textures()
    densify_hull_uvs()
    for name in (
        "Surface_accretion_0",
        "Surface_accretion_1",
        "Surface_accretion_2",
        "Surface_accretion_3",
        "Sparse_branching_growth",
    ):
        obj = bpy.data.objects.get(name)
        if obj:
            project_uv(obj, GROWTH_UV_SCALE)
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if any(slot.material and slot.material.name == "Fresh exposed oxide" for slot in obj.material_slots):
            if not obj.data.uv_layers:
                project_uv(obj, 0.18)
    trim_heavy_accretion()
    add_fracture_flakes()
    add_biofouling()
    purge_unused_seabed_image()
    # Hide / unlink the flat seabed plane so it cannot sneak into exports.
    seabed = bpy.data.objects.get("Seabed_sand_ripples")
    if seabed is not None:
        seabed.hide_render = True
        seabed.hide_viewport = True
    lod0 = total_visual_tris()
    print("LOD0 tris before export", lod0)
    if lod0 > 300_000:
        for name in ("I4_Barnacles", "I4_Mussels", "Rubble_apron"):
            obj = bpy.data.objects.get(name)
            if obj:
                decimate(obj, 0.7)
        lod0 = total_visual_tris()
        print("LOD0 tris after emergency trim", lod0)
    assert lod0 <= 300_000, lod0
    export_collision_and_route()
    export_visual(OUT / "lod0_raw.glb")
    apply_lod_decimate(0.34)
    lod1 = total_visual_tris()
    print("LOD1 tris", lod1)
    if lod1 > 100_000:
        apply_lod_decimate(100_000 / max(lod1, 1))
        print("LOD1 tris after trim", total_visual_tris())
    export_visual(OUT / "lod1_raw.glb")
    apply_lod_decimate(0.18)
    lod2 = total_visual_tris()
    print("LOD2 tris", lod2)
    if lod2 > 20_000:
        apply_lod_decimate(20_000 / max(lod2, 1) * 0.95)
        print("LOD2 tris after trim", total_visual_tris())
    assert total_visual_tris() <= 20_000, total_visual_tris()
    export_visual(OUT / "lod2_raw.glb")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
