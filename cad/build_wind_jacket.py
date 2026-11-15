"""Export the authoritative wind foundation as GLB using headless Blender and a fixed seed.

Run with Python (not Blender): python cad/build_wind_jacket.py
Intermediate files stay in simulator/output/wind-jacket; never writes a .blend or reads reference photos.
The live viewer remains collider-driven so random jackets and sensors share their geometry.
"""
from pathlib import Path
import json
import math
import random
import subprocess
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "simulator/output/wind-jacket"
SEED = 1101


def export_blender():
    import bpy
    from mathutils import Vector
    random.seed(SEED)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    data = json.loads((OUTPUT / "colliders.json").read_text())
    tier = sys.argv[-1]
    radial = 12 if tier == "low" else 28
    colors = {"paint": (0.72, 0.48, 0.025, 1), "tower": (0.78, 0.81, 0.8, 1),
              "rubber": (0.025, 0.03, 0.026, 1), "metal": (0.32, 0.34, 0.3, 1)}
    materials = {}
    image = bpy.data.images.new("Original procedural corrosion", width=256, height=256)
    pixels = []
    for _ in range(256 * 256):
        value = random.uniform(0.65, 1)
        pixels.extend((value, value, value, 1))
    image.pixels = pixels
    image.pack()
    for name, color in colors.items():
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.78
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])
        materials[name] = mat
    totals = {"underwater_triangles": 0, "above_water_triangles": 0}
    # Blender (-E, -N, -D) exports to the viewer's glTF axes (-E, -D, N).
    for ob in data["obstacles"]:
        kind = ob["kind"]
        if ob["type"] == "cylinder":
            a = Vector((-ob["p0"][1], -ob["p0"][0], -ob["p0"][2]))
            b = Vector((-ob["p1"][1], -ob["p1"][0], -ob["p1"][2]))
            bpy.ops.mesh.primitive_cylinder_add(vertices=radial, radius=ob["radius"],
                                                depth=(b - a).length, location=(a + b) / 2)
            obj = bpy.context.object
            obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
            depth = max(ob["p0"][2], ob["p1"][2])
        elif ob["type"] == "box":
            c = ob["center"]
            bpy.ops.mesh.primitive_cube_add(size=2, location=(-c[1], -c[0], -c[2]))
            obj = bpy.context.object
            obj.scale = (ob["half"][1], ob["half"][0], ob["half"][2])
            obj.rotation_euler.z = -math.radians(ob.get("yaw_deg", 0))
            depth = c[2] + ob["half"][2]
        else:
            continue
        obj.name = ob["name"]
        material = "tower" if kind == "wind_tower" else "paint"
        if kind == "fender":
            material = "rubber"
        elif kind in ("anode", "anode_strap", "scour_rock", "mudmat"):
            material = "metal"
        obj.data.materials.append(materials[material])
        obj.data.calc_loop_triangles()
        key = "underwater_triangles" if depth > 0 else "above_water_triangles"
        totals[key] += len(obj.data.loop_triangles)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT / f"wind-jacket-{tier}-raw.glb"), export_format="GLB")
    assert totals["underwater_triangles"] <= 250000
    assert totals["above_water_triangles"] <= 80000
    (OUTPUT / f"{tier}-geometry.json").write_text(json.dumps(totals, indent=2))


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "simulator"))
    from qysim.scenarios import jacket_inspection
    from qysim.world import World
    scene = jacket_inspection()
    world = World(scene.seabed_depth)
    world.obstacles = scene.obstacles
    (OUTPUT / "colliders.json").write_text(json.dumps(world.as_dict()))
    report = {"seed": SEED, "textures": "original procedural 256x256", "tiers": {}}
    for tier in ("high", "low"):
        subprocess.run(["blender", "--background", "--python", __file__, "--", "--worker", tier], check=True)
        raw = OUTPUT / f"wind-jacket-{tier}-raw.glb"
        webp = OUTPUT / f"wind-jacket-{tier}-webp.glb"
        final = OUTPUT / f"wind-jacket-{tier}.glb"
        cli = ["npx", "--yes", "@gltf-transform/cli@4.2.1"]
        subprocess.run(cli + ["webp", str(raw), str(webp)], check=True)
        subprocess.run(cli + ["meshopt", str(webp), str(final)], check=True)
        binary = final.read_bytes()
        json_length = struct.unpack_from("<I", binary, 12)[0]
        asset = json.loads(binary[20:20 + json_length])
        assert {"EXT_meshopt_compression", "EXT_texture_webp"} <= set(asset["extensionsUsed"])
        assert all(image["mimeType"] == "image/webp" for image in asset["images"])
        calls = sum(len(mesh["primitives"]) for mesh in asset["meshes"])
        stats = json.loads((OUTPUT / f"{tier}-geometry.json").read_text())
        stats.update(file_bytes=final.stat().st_size, texture_gpu_bytes_with_mips=349524 * len(asset["images"]),
                     draw_calls=calls, representation="collider-derived export, not the live procedural renderer")
        report["tiers"][tier] = stats
    (OUTPUT / "asset-report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        export_blender()
    else:
        main()
