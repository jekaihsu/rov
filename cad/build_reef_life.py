"""Rebuild CC0 reef-life GLBs from photogrammetry scans (Blender 4.x, headless).

Downloads stay outside the repository (see --source). For each model this script:
  1. Imports the source glTF/GLB (or OBJ inside an extracted Sketchfab zip).
  2. Joins meshes, orients, and scales to a real-world length in metres.
  3. Decimates to a near LOD and a far LOD.
  4. Bakes colour + tangent normals from the high-poly source onto 512 px maps.
     Corals discard the dry-specimen albedo and receive a procedural living colour.
  5. Exports GLB, then compresses with glTF-Transform (meshopt + WebP).

Usage (repository root):
  blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources --only acropora_palmata
  blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources   # all present sources
  blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources --render

Outputs:
  simulator/viewer/models/reef/<id>.glb and <id>_lo.glb
  docs/design/reef-life/<id>.jpg studio stills (with --render) and README.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "simulator" / "viewer" / "models" / "reef"
DOCS = ROOT / "docs" / "design" / "reef-life"
TEMP = ROOT / "simulator" / "output" / "reef_life"
TEX_SIZE = 512
GLB_BUDGET = 400 * 1024

# Real lengths (m) and LOD triangle budgets from docs/prompts/N3-reef-life.md.
MODELS = {
    "urchin": {
        "kind": "invert",
        "length_m": 0.07,
        "hi": 1500,
        "lo": 300,
        "axis": "up",
        "patterns": ["urchin", "heliocidaris", "4cbc27da"],
    },
    "starfish": {
        "kind": "invert",
        "length_m": 0.12,
        "hi": 1500,
        "lo": 300,
        "axis": "up",
        "patterns": ["starfish", "patiria", "14319712"],
    },
    "crab": {
        "kind": "invert",
        "length_m": 0.10,
        "hi": 1500,
        "lo": 300,
        "axis": "up",
        "patterns": ["crab", "charybdis", "4915ee5a"],
    },
    "sea_cucumber": {
        "kind": "invert",
        "length_m": 0.25,
        "hi": 1500,
        "lo": 300,
        "axis": "forward",
        "patterns": ["cucumber", "apostichopus", "c8fcb7b0", "sea_cucumber"],
    },
    "mussel": {
        "kind": "invert",
        "length_m": 0.08,
        "hi": 1500,
        "lo": 300,
        "axis": "up",
        "patterns": ["mussel", "mytilus", "0920004b"],
    },
    "barnacle": {
        "kind": "invert",
        "length_m": 0.04,
        "hi": 1500,
        "lo": 300,
        "axis": "up",
        "patterns": ["barnacle", "tetraclita", "7e2bbead"],
    },
    "butterflyfish": {
        "kind": "fish",
        "length_m": 0.16,
        "hi": 2500,
        "lo": 700,
        "axis": "fish",
        "patterns": ["butterfly", "heniochus", "27f435f8", "pennant"],
    },
    "angelfish": {
        "kind": "fish",
        "length_m": 0.18,
        "hi": 2500,
        "lo": 700,
        "axis": "fish",
        "patterns": ["angel", "chaetodontoplus", "a5c0bb68", "キンチャク"],
    },
    "stripey": {
        "kind": "fish",
        "length_m": 0.14,
        "hi": 2500,
        "lo": 700,
        "axis": "fish",
        "patterns": ["stripey", "microcanthus", "32e3ef9d", "カゴカキ"],
    },
    "wrasse": {
        "kind": "fish",
        "length_m": 0.22,
        "hi": 2500,
        "lo": 700,
        "axis": "fish",
        "patterns": ["wrasse", "bodianus", "parajulis", "a1fa2be4", "e664129f", "キュウセン", "キツネ"],
    },
    "acropora_palmata": {
        "kind": "coral",
        "length_m": 0.45,
        "hi": 4000,
        "lo": 800,
        "axis": "up",
        "patterns": ["acropora_palmata", "palmata", "8cb98631"],
        # Living elkhorn: golden-brown colony, paler growing tips (text descriptions only).
        # Living elkhorn colony: saturated golden-brown tissue, paler tips (text refs only).
        "coral_base": (0.78, 0.42, 0.10),
        "coral_tip": (0.95, 0.78, 0.28),
        "coral_shadow": (0.42, 0.18, 0.05),
    },
    "acropora_hyacinthus": {
        "kind": "coral",
        "length_m": 0.40,
        "hi": 4000,
        "lo": 800,
        "axis": "up",
        "patterns": ["madrepora_hyacinthus", "hyacinthus", "5e8f3939"],
        "coral_base": (0.70, 0.40, 0.08),
        "coral_tip": (0.92, 0.74, 0.30),
        "coral_shadow": (0.36, 0.16, 0.05),
    },
    "brain_coral": {
        "kind": "coral",
        "length_m": 0.35,
        "hi": 4000,
        "lo": 800,
        "axis": "up",
        "patterns": ["diploria", "labyrinthiformis", "brain", "cbbf64f2"],
        "coral_base": (0.86, 0.62, 0.12),
        "coral_tip": (0.96, 0.84, 0.38),
        "coral_shadow": (0.32, 0.18, 0.05),
    },
    "pocillopora": {
        "kind": "coral",
        "length_m": 0.22,
        "hi": 4000,
        "lo": 800,
        "axis": "up",
        "patterns": ["pocillopora", "damicornis", "925b1db0"],
        "coral_base": (0.90, 0.32, 0.42),
        "coral_tip": (0.98, 0.70, 0.68),
        "coral_shadow": (0.48, 0.12, 0.20),
    },
    "porites": {
        "kind": "coral",
        "length_m": 0.30,
        "hi": 4000,
        "lo": 800,
        "axis": "up",
        "patterns": ["porites", "monticulosa", "68c44f23"],
        "coral_base": (0.72, 0.68, 0.12),
        "coral_tip": (0.90, 0.86, 0.28),
        "coral_shadow": (0.28, 0.32, 0.06),
    },
}


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Scratch folder with downloaded scans")
    parser.add_argument("--only", nargs="*", default=None, help="Subset of model ids")
    parser.add_argument("--render", action="store_true", help="Write 1600x900 studio JPEGs")
    parser.add_argument("--skip-pack", action="store_true", help="Skip glTF-Transform compress")
    # Blender leaves its own flags before "--".
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    return parser.parse_args(argv)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False


def mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def triangle_count(objects=None):
    total = 0
    for obj in objects or mesh_objects():
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def find_source(source_root: Path, spec: dict) -> Path | None:
    """Locate a downloaded source file for one model under --source (recursive)."""
    candidates = []
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if path.suffix.lower() not in {".glb", ".gltf", ".obj", ".zip"}:
            continue
        if any(pat.lower() in name or pat.lower() in str(path).lower() for pat in spec["patterns"]):
            candidates.append(path)
    if not candidates:
        return None
    # Prefer uncompressed engine GLBs, then any GLB, then zip/obj.
    def rank(path: Path):
        s = str(path).lower()
        score = 0
        if "engine" in s:
            score += 30
        if path.suffix.lower() == ".glb":
            score += 20
        elif path.suffix.lower() == ".gltf":
            score += 15
        elif path.suffix.lower() == ".obj":
            score += 10
        elif path.suffix.lower() == ".zip":
            score += 5
        score += path.stat().st_size / 1e9
        return score

    return sorted(candidates, key=rank, reverse=True)[0]


def extract_if_zip(path: Path, scratch: Path) -> Path:
    if path.suffix.lower() != ".zip":
        return path
    dest = scratch / path.stem
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(dest)
    for pattern in ("*.glb", "*.gltf", "*.obj"):
        hits = list(dest.rglob(pattern))
        if hits:
            # Prefer scene.gltf from Sketchfab exports.
            hits.sort(key=lambda p: (0 if p.name.lower() == "scene.gltf" else 1, p.stat().st_size))
            return hits[0]
    raise FileNotFoundError(f"no mesh in {path}")


def import_source(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise ValueError(f"unsupported source {path}")
    objects = mesh_objects()
    if not objects:
        raise RuntimeError(f"no mesh imported from {path}")
    return objects


def join_meshes(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_c = Vector((min(c[i] for c in corners) for i in range(3)))
    max_c = Vector((max(c[i] for c in corners) for i in range(3)))
    return min_c, max_c


def orient_and_scale(obj, spec: dict):
    """Centre the mesh, put it on axes expected by the viewer, scale to length_m."""
    min_c, max_c = bounds(obj)
    centre = (min_c + max_c) * 0.5
    size = max_c - min_c
    obj.location -= centre
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Dominant horizontal extent becomes the "length" for fish; max AABB for the rest.
    if spec["axis"] == "fish":
        # Guess current nose axis as the longest AABB axis, then map to +Z; back to +Y.
        axes = sorted([(size[i], i) for i in range(3)], reverse=True)
        length_axis = axes[0][1]
        # Height is usually the second for reef fish (laterally compressed).
        height_axis = axes[1][1] if axes[1][1] != length_axis else axes[2][1]
        rot = Matrix.Identity(3)
        # Build a basis: X = length × up guess, Y = up, Z = length.
        src_z = Vector((0, 0, 0))
        src_z[length_axis] = 1
        src_y = Vector((0, 0, 0))
        src_y[height_axis] = 1
        # If the mesh is taller than long on Y already, keep.
        target = Matrix.Identity(3)
        # Rotate so length_axis -> Z, height_axis -> Y.
        mapping = {length_axis: 2, height_axis: 1}
        remaining = [i for i in range(3) if i not in mapping]
        mapping[remaining[0]] = 0
        cols = [None, None, None]
        for src, dst in mapping.items():
            vec = Vector((0, 0, 0))
            vec[src] = 1
            cols[dst] = vec
        basis = Matrix((cols[0], cols[1], cols[2])).transposed()
        obj.matrix_world = basis.to_4x4() @ obj.matrix_world
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        # Ensure nose points +Z by checking vertex centroid of the +Z half vs -Z half density —
        # photogrammetry fish often face either way; flip 180° around Y if needed later via bbox.
        min_c, max_c = bounds(obj)
        size = max_c - min_c
        # Lateral axis should be X (smallest for reef fish). If Y is smallest, rotate 90° around Z.
        if size.y < size.x * 0.85:
            obj.rotation_euler[2] = math.radians(90)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            min_c, max_c = bounds(obj)
            size = max_c - min_c
        length = size.z
    else:
        # Upright invertebrates / corals: largest horizontal span is length; sit on XY, +Z up.
        # Many scans already have Z up; if Y is tallest, rotate X by -90°.
        if size.y >= size.z and size.y >= size.x:
            obj.rotation_euler[0] = math.radians(-90)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            min_c, max_c = bounds(obj)
            size = max_c - min_c
        length = max(size.x, size.y, size.z)

    if length <= 1e-6:
        raise RuntimeError("degenerate mesh bounds")
    scale = spec["length_m"] / length
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    min_c, max_c = bounds(obj)
    centre = (min_c + max_c) * 0.5
    obj.location -= Vector((centre.x, centre.y, min_c.z if spec["axis"] != "fish" else centre.z))
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def duplicate(obj, name):
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.name = name
    bpy.context.collection.objects.link(copy)
    return copy


def decimate(obj, target_tris: int):
    current = triangle_count([obj])
    if current <= target_tris:
        return obj
    ratio = max(0.01, target_tris / current)
    mod = obj.modifiers.new("decimate", "DECIMATE")
    mod.ratio = ratio
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # Second pass if still over (collapse ratio is approximate).
    current = triangle_count([obj])
    if current > target_tris * 1.05:
        mod = obj.modifiers.new("decimate2", "DECIMATE")
        mod.ratio = max(0.01, target_tris / current)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def ensure_uv(obj):
    if not obj.data.uv_layers:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.03)
        bpy.ops.object.mode_set(mode="OBJECT")


def make_image(name, size, is_data=False):
    image = bpy.data.images.new(name, width=size, height=size, alpha=False, float_buffer=False)
    image.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    return image


def clear_material_nodes(mat):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    return nodes, links


def assign_source_material(obj):
    """Keep the first existing Principled material so Cycles can bake diffuse colour."""
    if obj.data.materials:
        return obj.data.materials[0]
    mat = bpy.data.materials.new("source")
    mat.use_nodes = True
    obj.data.materials.append(mat)
    return mat


def living_coral_color_nodes(nodes, links, spec: dict):
    """Shared colour graph: object-Z + noise → ramp. Returns the Colour output socket."""
    texcoord = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 14.0
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.55
    ramp = nodes.new("ShaderNodeValToRGB")
    base = spec["coral_base"]
    tip = spec["coral_tip"]
    shadow = spec["coral_shadow"]
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*shadow, 1.0)
    mid = ramp.color_ramp.elements.new(0.42)
    mid.color = (*base, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (*tip, 1.0)
    combine = nodes.new("ShaderNodeMix")
    combine.data_type = "FLOAT"
    combine.inputs["Factor"].default_value = 0.5
    # Normalise object Z roughly into 0–1 via a map range so tip/base separate on real sizes.
    zmap = nodes.new("ShaderNodeMapRange")
    zmap.inputs["From Min"].default_value = 0.0
    zmap.inputs["From Max"].default_value = max(spec["length_m"] * 0.9, 0.05)
    zmap.inputs["To Min"].default_value = 0.0
    zmap.inputs["To Max"].default_value = 1.0
    links.new(texcoord.outputs["Object"], separate.inputs["Vector"])
    links.new(texcoord.outputs["Object"], noise.inputs["Vector"])
    links.new(separate.outputs["Z"], zmap.inputs["Value"])
    links.new(zmap.outputs["Result"], combine.inputs["A"])
    links.new(noise.outputs["Fac"], combine.inputs["B"])
    links.new(combine.outputs["Result"], ramp.inputs["Fac"])
    return ramp.outputs["Color"]


def assign_living_coral_material(obj, spec: dict, emission: bool = False):
    """Procedural living-coral albedo (no photographs). Geometry detail comes from normal bake.

    When emission=True the same colour drives an Emission shader so Cycles can bake it with type=EMIT.
    """
    mat = bpy.data.materials.new("living_coral_emit" if emission else "living_coral")
    nodes, links = clear_material_nodes(mat)
    output = nodes.new("ShaderNodeOutputMaterial")
    colour = living_coral_color_nodes(nodes, links, spec)
    if emission:
        emit = nodes.new("ShaderNodeEmission")
        emit.inputs["Strength"].default_value = 1.0
        links.new(colour, emit.inputs["Color"])
        links.new(emit.outputs["Emission"], output.inputs["Surface"])
    else:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        links.new(colour, bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.55
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def prepare_bake_shell(obj, colour_image, normal_image):
    """Image nodes only (not wired into the shader) so Cycles bake has no circular dependency."""
    mat = bpy.data.materials.new(f"bake_{obj.name}")
    nodes, links = clear_material_nodes(mat)
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    col = nodes.new("ShaderNodeTexImage")
    col.image = colour_image
    col.name = "BakeColor"
    norm = nodes.new("ShaderNodeTexImage")
    norm.image = normal_image
    norm.name = "BakeNormal"
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def save_image(image, path: Path, is_data: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    image.save()
    image.pack()
    return path


def apply_baked_material(obj, colour_image, normal_image):
    mat = bpy.data.materials.new(f"pbr_{obj.name}")
    nodes, links = clear_material_nodes(mat)
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    uv = nodes.new("ShaderNodeTexCoord")
    col = nodes.new("ShaderNodeTexImage")
    col.image = colour_image
    col.interpolation = "Closest" if False else "Linear"
    norm = nodes.new("ShaderNodeTexImage")
    norm.image = normal_image
    normal_map = nodes.new("ShaderNodeNormalMap")
    links.new(uv.outputs["UV"], col.inputs["Vector"])
    links.new(uv.outputs["UV"], norm.inputs["Vector"])
    links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(norm.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.55
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def bake_maps(hi_obj, lo_obj, colour_image, normal_image, emit_colour: bool = False):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8 if emit_colour else 4
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.max_ray_distance = 0.0

    bpy.ops.object.select_all(action="DESELECT")
    hi_obj.select_set(True)
    lo_obj.select_set(True)
    bpy.context.view_layer.objects.active = lo_obj

    mat = lo_obj.data.materials[0]
    nodes = mat.node_tree.nodes
    nodes.active = nodes["BakeColor"]
    if emit_colour:
        bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=0.05)
    else:
        bpy.ops.object.bake(
            type="DIFFUSE",
            pass_filter={"COLOR"},
            use_selected_to_active=True,
            cage_extrusion=0.05,
        )
    colour_image.pack()

    nodes.active = nodes["BakeNormal"]
    bpy.ops.object.bake(
        type="NORMAL",
        normal_space="TANGENT",
        use_selected_to_active=True,
        cage_extrusion=0.05,
    )
    normal_image.pack()


def export_glb(objects, path: Path):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )


def pack_glb(raw: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx", "--yes", "@gltf-transform/cli@4.5.1", "optimize",
        str(raw), str(dest),
        "--compress", "meshopt",
        "--texture-compress", "webp",
        "--texture-size", str(TEX_SIZE),
    ]
    subprocess.run(cmd, check=True)
    size = dest.stat().st_size
    if size > GLB_BUDGET:
        # Retry with smaller textures.
        cmd[-1] = str(TEX_SIZE // 2)
        subprocess.run(cmd, check=True)
        size = dest.stat().st_size
    return size


def glb_triangle_count(path: Path) -> int:
    data = path.read_bytes()
    length = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + length])
    accessors = gltf.get("accessors", [])
    total = 0
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if "indices" in prim:
                total += accessors[prim["indices"]]["count"] // 3
            else:
                total += accessors[prim["attributes"]["POSITION"]]["count"] // 3
    return total


def studio_render(obj, dest: Path):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 84
    scene.render.filepath = str(dest)
    # Standard view keeps albedo chroma readable for documentation stills.
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = -0.35
    scene.view_settings.gamma = 1.0

    for light in [o for o in scene.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(light, do_unlink=True)
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
    key.data.energy = 40
    key.data.size = 1.4
    key.data.color = (1.0, 0.97, 0.92)
    key.location = (0.55, -0.9, 0.65)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy = 18
    fill.data.size = 1.8
    fill.data.color = (0.85, 0.95, 1.0)
    fill.location = (-0.8, -0.2, 0.35)
    rim = bpy.data.objects.new("rim", bpy.data.lights.new("rim", "AREA"))
    rim.data.energy = 12
    rim.data.size = 1.0
    rim.location = (0.2, 0.9, 0.5)
    for light in (key, fill, rim):
        bpy.context.collection.objects.link(light)

    cam_data = bpy.data.cameras.new("studio")
    cam = bpy.data.objects.new("studio", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    min_c, max_c = bounds(obj)
    centre = (min_c + max_c) * 0.5
    radius = max((max_c - min_c).length * 0.95, 0.15)
    cam.location = centre + Vector((radius * 0.85, -radius * 1.35, radius * 0.5))
    direction = centre - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = 50

    world = bpy.data.worlds.new("studio_world")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.09, 0.12, 1.0)
    bg.inputs[1].default_value = 0.25

    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.hide_render = False
    obj.select_set(True)
    bpy.ops.render.render(write_still=True)
    if dest.exists() and dest.stat().st_size > 300 * 1024:
        scene.render.image_settings.quality = 72
        bpy.ops.render.render(write_still=True)


def process_model(model_id: str, spec: dict, source_path: Path, scratch: Path, do_render: bool, skip_pack: bool):
    print(f"=== {model_id} from {source_path}")
    reset_scene()
    imported = extract_if_zip(source_path, scratch / model_id)
    objects = import_source(imported)
    hi = join_meshes(objects)
    hi.name = f"{model_id}_hi"
    orient_and_scale(hi, spec)

    living = spec["kind"] == "coral"
    if living:
        # Emission so colour bake (EMIT) captures the procedural living palette, not the bone albedo.
        assign_living_coral_material(hi, spec, emission=True)
    else:
        assign_source_material(hi)

    near = duplicate(hi, f"{model_id}_near")
    far = duplicate(hi, f"{model_id}_far")
    decimate(near, spec["hi"])
    decimate(far, spec["lo"])
    ensure_uv(near)
    ensure_uv(far)

    TEMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    colour = make_image(f"{model_id}_c", TEX_SIZE, is_data=False)
    normal = make_image(f"{model_id}_n", TEX_SIZE, is_data=True)
    prepare_bake_shell(near, colour, normal)
    bake_maps(hi, near, colour, normal, emit_colour=living)
    save_image(colour, TEMP / f"{model_id}_c.png", is_data=False)
    save_image(normal, TEMP / f"{model_id}_n.png", is_data=True)
    apply_baked_material(near, colour, normal)
    apply_baked_material(far, colour, normal)

    raw_hi = TEMP / f"{model_id}_raw.glb"
    raw_lo = TEMP / f"{model_id}_lo_raw.glb"
    hi.hide_render = True
    hi.hide_viewport = True
    hi.hide_set(True)
    export_glb([near], raw_hi)
    export_glb([far], raw_lo)

    if do_render:
        DOCS.mkdir(parents=True, exist_ok=True)
        # Render the near LOD before meshopt packing (Blender cannot import EXT_meshopt).
        far.hide_set(True)
        studio_render(near, DOCS / f"{model_id}.jpg")
        far.hide_set(False)

    out_hi = OUT / f"{model_id}.glb"
    out_lo = OUT / f"{model_id}_lo.glb"
    if skip_pack:
        shutil.copy(raw_hi, out_hi)
        shutil.copy(raw_lo, out_lo)
        size_hi = out_hi.stat().st_size
        size_lo = out_lo.stat().st_size
    else:
        size_hi = pack_glb(raw_hi, out_hi)
        size_lo = pack_glb(raw_lo, out_lo)

    report = {
        "id": model_id,
        "source": str(source_path),
        "kind": spec["kind"],
        "length_m": spec["length_m"],
        "triangles_hi_prepack": triangle_count([near]),
        "triangles_lo_prepack": triangle_count([far]),
        "triangles_hi": glb_triangle_count(out_hi),
        "triangles_lo": glb_triangle_count(out_lo),
        "bytes_hi": size_hi,
        "bytes_lo": size_lo,
        "living_coral_recolour": living,
    }
    print(json.dumps(report, ensure_ascii=False))
    return report


def write_readme(reports):
    DOCS.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 礁區生命模型（N3）",
        "",
        "來源為 Sketchfab／Smithsonian 的 **CC0** 實物掃描；以 `cad/build_reef_life.py` 減面、烘焙後輸出。",
        "珊瑚捨棄乾燥標本白骨色，改以程序色（參考公開水下描述）上成活珊瑚色，**未使用任何照片貼圖**。",
        "",
        "| 檔名 | 三角形（近／遠） | 大小（近／遠） | 授權 |",
        "|---|---:|---:|---|",
    ]
    for r in reports:
        lines.append(
            f"| `{r['id']}.glb` / `_lo` | {r['triangles_hi']} / {r['triangles_lo']} | "
            f"{r['bytes_hi']//1024} KB / {r['bytes_lo']//1024} KB | CC0 |"
        )
    lines.append("")
    lines.append("重建：`blender -b -P cad/build_reef_life.py -- --source <scratch> --render`")
    lines.append("")
    (DOCS / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (TEMP / "report.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    args = parse_args(sys.argv)
    source_root = args.source.expanduser().resolve()
    if not source_root.is_dir():
        raise SystemExit(f"--source not a directory: {source_root}")
    wanted = args.only or list(MODELS)
    reports = []
    missing = []
    with tempfile.TemporaryDirectory(prefix="reef_life_") as tmp:
        scratch = Path(tmp)
        for model_id in wanted:
            if model_id not in MODELS:
                raise SystemExit(f"unknown model id {model_id}")
            spec = MODELS[model_id]
            src = find_source(source_root, spec)
            if src is None:
                missing.append(model_id)
                print(f"SKIP {model_id}: no source under {source_root}")
                continue
            reports.append(
                process_model(model_id, spec, src, scratch, args.render, args.skip_pack)
            )
    if reports:
        write_readme(reports)
    summary = {"built": [r["id"] for r in reports], "missing": missing}
    print("SUMMARY", json.dumps(summary, ensure_ascii=False))
    if not reports:
        raise SystemExit("no models built")


if __name__ == "__main__":
    main()
