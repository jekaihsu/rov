"""I4: rebuild Korean Castle visuals within triangle and texture budgets (headless bpy).

Opens the existing illustrative .blend, replaces packed 1K PBR maps with seamless
fBm/Worley underwater atlases (deep rust, muted fouling, neutral rubble), keeps
authored SurfaceMeters UVs (no 4.2× wallpaper), textures aft superstructure and
flat silt/recess materials, drops the embedded flat seabed plane (scene uses
seabed.js), trims heavy accretion, adds sparse fracture flakes and depth-weighted
biofouling, then exports LOD0/1/2 raw GLBs plus collision/route arrays. Never
writes the .blend back.

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
# Keep authored SurfaceMeters UVs (no 4.2× densify — that caused brick seams).
HULL_UV_SCALE = 1.0
GROWTH_UV_SCALE = 0.12
ROCK_UV_SCALE = 0.1


def seamless_value_noise(size: int, cells: int, seed: int) -> np.ndarray:
    """Axis-aligned value noise that tiles: lattice wraps, so atlas edges match."""
    rng = np.random.default_rng(seed)
    grid = rng.random((cells, cells), dtype=np.float32)
    p = np.linspace(0, cells, size, endpoint=False, dtype=np.float32)
    idx = np.floor(p).astype(np.int32)
    t = p - idx
    t = t * t * (3 - 2 * t)
    i0 = idx % cells
    i1 = (idx + 1) % cells
    a = grid[i0[:, None], i0[None, :]]
    b = grid[i1[:, None], i0[None, :]]
    c = grid[i0[:, None], i1[None, :]]
    d = grid[i1[:, None], i1[None, :]]
    return (a * (1 - t[:, None]) + b * t[:, None]) * (1 - t[None, :]) + (
        c * (1 - t[:, None]) + d * t[:, None]
    ) * t[None, :]


def fbm(size: int, seed: int, octaves: int = 5, base_cells: int = 4) -> np.ndarray:
    """Smooth multi-octave seamless noise; soft transitions, no hard square cells."""
    total = np.zeros((size, size), dtype=np.float32)
    amp = 1.0
    norm = 0.0
    cells = base_cells
    for octave in range(octaves):
        total += amp * seamless_value_noise(size, cells, seed + octave * 17)
        norm += amp
        amp *= 0.5
        cells = min(cells * 2, size // 2)
    return total / max(norm, 1e-6)


def worley(size: int, cells: int, seed: int) -> np.ndarray:
    """Soft periodic Worley (F1); used for barnacle-scale mottling, not hard bricks."""
    rng = np.random.default_rng(seed)
    points = rng.random((cells, cells, 2), dtype=np.float32)
    yy, xx = np.meshgrid(
        np.linspace(0, cells, size, endpoint=False, dtype=np.float32),
        np.linspace(0, cells, size, endpoint=False, dtype=np.float32),
        indexing="ij",
    )
    best = np.full((size, size), 1e9, dtype=np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cell_y = np.floor(yy).astype(np.int32)
            cell_x = np.floor(xx).astype(np.int32)
            ny = (cell_y + dy) % cells
            nx = (cell_x + dx) % cells
            py = cell_y + dy + points[ny, nx, 0]
            px = cell_x + dx + points[ny, nx, 1]
            dist = (yy - py) ** 2 + (xx - px) ** 2
            best = np.minimum(best, dist)
    return np.sqrt(best)


def noise(size: int, cells: int, seed: int) -> np.ndarray:
    """Back-compat alias: seamless value noise at the requested cell density."""
    return seamless_value_noise(size, max(2, cells), seed)


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
    """High-contrast seamless rust + green-grey fouling (match main grit, no brick cells).

    Main's atlas has albedo std≈20 and normal std≈15; earlier I4 drafts were too flat
    (std≈5 / 1.5) and washed out under real-mode lamps. Soft fBm + Worley stay tileable.
    """
    broad = fbm(SIZE, 41, octaves=4, base_cells=2)
    medium = fbm(SIZE, 42, octaves=5, base_cells=5)
    fine = fbm(SIZE, 43, octaves=6, base_cells=10)
    micro = fbm(SIZE, 44, octaves=6, base_cells=22)
    # Barnacle-scale pits / clumps — soft Worley, not axis-aligned bricks.
    pits = worley(SIZE, 14, 45)
    pits = np.clip(1.0 - pits / max(float(pits.max()), 1e-6), 0, 1)
    clumps = worley(SIZE, 8, 46)
    clumps = np.clip(1.0 - clumps / max(float(clumps.max()), 1e-6), 0, 1)
    rows = np.arange(SIZE, dtype=np.float32)[:, None]
    cols = np.arange(SIZE, dtype=np.float32)[None, :]
    plate = 0.5 + 0.5 * np.sin(cols * (TAU / SIZE) * 2.5) * np.sin(rows * (TAU / SIZE) * 1.8)
    rivet = ((np.sin(cols * 0.2) * np.sin(rows * 0.2)) > 0.91).astype(np.float32)

    # Soft masks with enough range that WebP keeps grit (target albedo std ~18–22).
    fouling = np.clip((broad * 0.45 + medium * 0.4 + fine * 0.15 - 0.38) * 3.5, 0, 1)
    rust_mask = np.clip((0.55 - medium) * 2.8 + fine * 0.4, 0, 1)
    pit = np.clip(pits * 0.85 + clumps * 0.35 + (0.4 - fine) * 1.8, 0, 1)
    dark = np.clip(1.0 - broad * 0.7 - medium * 0.4, 0, 1)

    # Deep brown / dark ochre steel base.
    rust = np.stack(
        [
            0.24 + medium * 0.22 + fine * 0.12 + micro * 0.08,
            0.13 + fine * 0.1 + micro * 0.05,
            0.07 + micro * 0.04,
        ],
        axis=-1,
    )
    # Soft green-grey film (like main), low chroma — not mint.
    coating = np.stack(
        [
            0.11 + fine * 0.09 + micro * 0.05,
            0.2 + medium * 0.14 + fine * 0.1 + micro * 0.05,
            0.1 + fine * 0.07 + micro * 0.04,
        ],
        axis=-1,
    )
    # Near-black recesses between patches.
    charcoal = np.stack(
        [
            0.03 + micro * 0.03,
            0.028 + micro * 0.02,
            0.022 + micro * 0.015,
        ],
        axis=-1,
    )
    color = rust * (1 - fouling[:, :, None]) + coating * fouling[:, :, None]
    color = color * (1 - 0.6 * dark[:, :, None]) + charcoal * (0.6 * dark[:, :, None])
    color = color * (1 - 0.4 * pit[:, :, None]) + rust * rust_mask[:, :, None] * 0.3
    # Large-scale break-up so many tiled metres do not read as wallpaper.
    color *= 0.65 + 0.7 * broad[:, :, None]
    # Salt-pepper grit (seamless via high-cell fBm) so close-ups keep grain like main.
    grit = (micro - 0.5) * 0.22
    color = np.clip(color + grit[:, :, None], 0, 1)

    # Strong height for barnacle-scale normals (target normal RGB std ~12–16).
    height = (
        fine * 0.7
        + micro * 0.55
        - pit * 0.55
        + fouling * 0.15
        + plate * 0.08
        + rivet * 0.14
        - dark * 0.2
    )
    dy, dx = np.gradient(height)
    normal = np.stack([-dx * 11.0, -dy * 11.0, np.ones_like(dx)], axis=-1)

    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    normal = normal * 0.5 + 0.5
    roughness = np.clip(0.78 + 0.16 * micro - 0.14 * fouling + 0.1 * pit, 0.55, 1.0)
    rough = np.repeat(roughness[:, :, None], 3, axis=-1)
    return color, rough, normal


def growth_maps() -> tuple[np.ndarray, np.ndarray]:
    """Soft low-sat green-grey and brown-grey fouling; seamless fBm with grit."""
    n = fbm(SIZE, 90, octaves=5, base_cells=5)
    m = fbm(SIZE, 91, octaves=4, base_cells=3)
    speck = fbm(SIZE, 92, octaves=6, base_cells=14)
    depth = fbm(SIZE, 93, octaves=3, base_cells=2)
    clumps = worley(SIZE, 9, 94)
    clumps = np.clip(1.0 - clumps / max(float(clumps.max()), 1e-6), 0, 1)
    brown = np.stack(
        [0.28 + n * 0.16, 0.22 + n * 0.12, 0.14 + n * 0.08],
        axis=-1,
    )
    green_grey = np.stack(
        [0.16 + n * 0.1, 0.24 + n * 0.12 + m * 0.06, 0.15 + n * 0.08],
        axis=-1,
    )
    mix = np.clip(0.35 + depth * 0.45 + m * 0.15, 0, 1)[:, :, None]
    color = brown * (1 - mix) + green_grey * mix
    freckles = np.clip((speck - 0.5) * 3.2, 0, 1) * (0.35 + 0.65 * clumps)
    freckle_col = np.array([0.32, 0.26, 0.16], dtype=np.float32)
    color = color * (1 - freckles[:, :, None] * 0.4) + freckles[:, :, None] * freckle_col
    color *= 0.7 + 0.6 * n[:, :, None]
    color = np.clip(color, 0, 1)
    height = n * 0.55 + speck * 0.35 + clumps * 0.25
    dy, dx = np.gradient(height)
    normal = np.stack([-dx * 6.5, -dy * 6.5, np.ones_like(dx)], axis=-1)
    normal /= np.linalg.norm(normal, axis=-1)[:, :, None]
    normal = normal * 0.5 + 0.5
    return color, normal


def rock_maps() -> np.ndarray:
    """Neutral rock / rubble albedo — no fluorescent growth tint.

    Shares the steel normal atlas so the packed set stays at six 1K maps (≤32 MiB).
    Seamless multi-octave fBm avoids the large square cells that read as pixel blocks.
    """
    broad = fbm(SIZE, 70, octaves=4, base_cells=3)
    medium = fbm(SIZE, 71, octaves=5, base_cells=6)
    fine = fbm(SIZE, 72, octaves=5, base_cells=12)
    micro = fbm(SIZE, 73, octaves=4, base_cells=20)
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
        "Marine growth | limestone": ((0.55, 0.48, 0.38), 0.35),
        "Marine growth | olive": ((0.42, 0.52, 0.42), 0.3),
        "Marine growth | mustard": ((0.55, 0.48, 0.36), 0.32),
        "Marine growth | grey green": ((0.4, 0.48, 0.42), 0.28),
        "Marine growth | muted ochre": ((0.52, 0.45, 0.34), 0.3),
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


def apply_flat_materials() -> None:
    """Give previously flat-grey materials the steel/growth atlases (silt, recesses)."""
    steel_c = bpy.data.images.get("encrusted_steel_basecolor.png")
    steel_r = bpy.data.images.get("encrusted_steel_roughness.png")
    steel_n = bpy.data.images.get("encrusted_steel_normal.png")
    growth_c = bpy.data.images.get("I4_growth_basecolor.png")
    growth_n = bpy.data.images.get("I4_growth_normal.png")
    silt = bpy.data.materials.get("Dark settled silt inside cargo holds")
    if silt is not None:
        wire_pbr(
            silt,
            color=growth_c or steel_c,
            normal=growth_n or steel_n,
            roughness=0.96,
            normal_strength=0.45,
            tint=(0.18, 0.16, 0.13),
            tint_factor=0.45,
        )
    recess = bpy.data.materials.get("Dark recess steel")
    if recess is not None:
        wire_pbr(
            recess,
            color=steel_c,
            rough=steel_r,
            normal=steel_n,
            metallic=0.18,
            normal_strength=0.5,
            tint=(0.12, 0.1, 0.08),
            tint_factor=0.5,
        )


def texture_aft_superstructure() -> None:
    """Ensure aft deckhouse / roof / rails keep authored UVs and steel+oxide materials.

    Review called these flat grey; they already use Weathered steel, but some faces
    lacked useful UV span after edits. Re-assert steel maps and mild UV density.
    """
    steel = bpy.data.materials.get("Weathered steel | original PBR maps")
    oxide = bpy.data.materials.get("Fresh exposed oxide")
    growth = bpy.data.materials.get("Marine growth | limestone")
    for name in (
        "Aft_deckhouse_broken_walls",
        "Aft_partial_roof",
        "Aft_bent_railings",
        "Aft_mast_remnants",
        "Aft_window_frames",
    ):
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            continue
        if not obj.data.uv_layers:
            project_uv(obj, 0.08)
        # Mild densify only on sparse-UV roofs so 1 m shots keep grit without 4.2× bricks.
        if name in ("Aft_partial_roof", "Aft_deckhouse_broken_walls"):
            scale_uvs(obj, 1.35)
        if not obj.data.materials:
            obj.data.materials.append(steel or oxide)
        # Splatter a growth slot on deckhouse walls for mud/fouling read.
        if name == "Aft_deckhouse_broken_walls" and growth is not None:
            if growth.name not in [m.name if m else "" for m in obj.data.materials]:
                obj.data.materials.append(growth)
            # Assign ~30% of polygons to growth for silted look.
            for i, poly in enumerate(obj.data.polygons):
                if (i * 17 + 3) % 10 < 3:
                    poly.material_index = len(obj.data.materials) - 1


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
    """Keep authored SurfaceMeters UVs (HULL_UV_SCALE=1). No 4.2× wallpaper tiling."""
    if abs(HULL_UV_SCALE - 1.0) < 1e-6:
        return
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
    apply_flat_materials()
    apply_rock_textures()
    densify_hull_uvs()
    texture_aft_superstructure()
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
