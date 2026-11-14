"""Render fixed A2 review views with identical camera, lights and runtime detail level.

blender -b SOURCE.blend -t 8 --python tools/render_wreck_review.py -- OUT before|after [VIEW]
Does not save changes to the source scene. PNG palette compression is a separate delivery step.
"""

import sys
from pathlib import Path

import bpy
from mathutils import Vector

VIEWS = {
    "overview": ((180, -165, 108), (76, 0, 3), 42),
    "fracture": ((35, -25, 16), (47, 1, 5.7), 38),
    "hold-02": ((61, -14, 24), (61, 1.5, 8), 32),
    "stern-windows": ((145, 23, 17), (137, 8.8, 12), 45),
}


def main():
    args = sys.argv[sys.argv.index("--") + 1 :]
    output, prefix = Path(args[0]), args[1]
    output.mkdir(parents=True, exist_ok=True)
    selected = args[2:] or list(VIEWS)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 100
    scene.world.color = (0.1, 0.1, 0.1)
    for name in ["08_ENGINEERING", "09_COLLISION", "10_ROV_ROUTE"]:
        bpy.data.collections[name].hide_render = True
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.name.startswith("A2_Runtime_LOD"):
                modifier.show_render = True
    camera = bpy.data.objects["CAM_Hero"]
    scene.camera = camera
    camera.data.type = "PERSP"
    for name in selected:
        position, target, lens = VIEWS[name]
        camera.location = position
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = lens
        scene.render.filepath = str(output / f"{prefix}-{name}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
