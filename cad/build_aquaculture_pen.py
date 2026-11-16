"""Rebuild original CC0 pen reference GLB and NED mission manifest; the runtime WebP net is rebuilt by
simulator/tools/build_pen_net_texture.py, which this script calls.

blender -b --python cad/build_aquaculture_pen.py
Requires system Python with Pillow, Node/npm; exporter invokes pinned glTF Transform.
Runtime draws the same authoritative primitives (structures.js); the GLB is a portable review asset.
No blend file is saved. Fixed seed 71; no external textures or models.
"""
import json
import math
import sys
import subprocess
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulator"))
from qysim.aquaculture import layout

OUT = ROOT / "simulator/viewer/models/aquaculture"
OUT.mkdir(parents=True, exist_ok=True)
TEMP = ROOT / "simulator/output"
TEMP.mkdir(exist_ok=True)


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    rng = np.random.default_rng(71)
    size = 256
    y, x = np.mgrid[:size, :size] / size
    distance = np.minimum(np.abs((x + y + .5) % 1 - .5), np.abs((x - y + .5) % 1 - .5))
    alpha = (distance < .055 + .016 * rng.random((size, size))).astype(float)
    image = bpy.data.images.new("Original diamond net", width=size, height=size, alpha=True)
    pixels = np.stack((.48 + .12 * rng.random((size, size)),
                       .53 + .10 * rng.random((size, size)), np.full((size, size), .31), alpha), axis=-1)
    image.pixels = pixels.flatten().tolist()
    image.filepath_raw = str(TEMP / "net.png")
    image.file_format = "PNG"
    image.save()
    # The diamond image above only textures the portable reference GLB. The runtime net texture (square
    # knotless mesh with a soft alpha ramp, see viewer/aquaculture.js) has its own generator.
    subprocess.run(["python", str(ROOT / "simulator/tools/build_pen_net_texture.py")], check=True)
    mats = {}
    colors = {"pen_net": (.48, .53, .31), "pen_frame": (.03, .07, .08),
              "pen_sinker": (.2, .2, .17), "pen_rope": (.38, .32, .2),
              "pen_buoy": (.8, .46, .05), "pen_anchor": (.3, .3, .27)}
    for kind, color in colors.items():
        mat = bpy.data.materials.new(kind)
        mat.diffuse_color = (*color, 1.)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (*color, 1.)
        shader.inputs["Roughness"].default_value = .85
        if kind == "pen_net":
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = image
            mat.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
            mat.node_tree.links.new(tex.outputs["Alpha"], shader.inputs["Alpha"])
            if hasattr(mat, "blend_method"):
                mat.blend_method = "CLIP"
        mats[kind] = mat
    obstacles, data = layout()
    for ob in obstacles:
        if hasattr(ob, "half"):
            bpy.ops.mesh.primitive_cube_add(size=2, location=(ob.center[0], ob.center[1], -ob.center[2]))
            obj = bpy.context.object
            obj.scale = ob.half
            obj.rotation_euler.z = math.radians(ob.yaw_deg)
            if ob.kind == 'pen_net':
                uv = obj.data.uv_layers.active
                for loop in obj.data.loops:
                    vertex = obj.data.vertices[loop.vertex_index].co
                    v = vertex.z * ob.half[2] if ob.half[2] > .1 else vertex.y * ob.half[1]
                    uv.data[loop.index].uv = (vertex.x * ob.half[0] * 5, v * 5)
        else:
            a = Vector((ob.p0[0], ob.p0[1], -ob.p0[2]))
            b = Vector((ob.p1[0], ob.p1[1], -ob.p1[2]))
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=ob.radius, depth=(b-a).length,
                                                location=(a+b)/2)
            obj = bpy.context.object
            obj.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
        obj.name = ob.name
        obj.data.materials.append(mats[ob.kind])
    # Merge static parts per material for the portable asset as for runtime.
    for kind in mats:
        bpy.ops.object.select_all(action="DESELECT")
        objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.data.materials[0] == mats[kind]]
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(TEMP / "aquaculture.glb"), export_format='GLB')
    subprocess.run(["npx", "--yes", "@gltf-transform/cli@4.5.1", "optimize",
                    str(TEMP / "aquaculture.glb"), str(OUT / "pen.glb"),
                    "--compress", "meshopt", "--texture-compress", "webp"], check=True)
    (OUT / "mission.json").write_text(json.dumps(data, indent=2) + "\n")
    triangles = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.data.calc_loop_triangles()
            triangles += len(obj.data.loop_triangles)
    print(json.dumps(dict(reference_triangles=triangles, materials=len(mats), seed=71)))


if __name__ == '__main__':
    main()
