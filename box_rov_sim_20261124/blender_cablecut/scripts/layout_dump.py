import bpy, json, os
bpy.ops.wm.open_mainfile(filepath="/workspace/rov_sim/blender_cablecut/scene_v2.blend")
d = json.loads(bpy.context.scene["layout"]); d["blade_stroke"] = -0.123
d["arm"] = {"l_up": 0.40, "l_fore": 0.36}
json.dump(d, open("/workspace/rov_sim/blender_cablecut/export/layout.json", "w"), indent=1)
print("LAYOUT_OK")
