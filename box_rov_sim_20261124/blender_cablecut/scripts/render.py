"""Render stills / frame ranges from scene_cablecut.blend.
env: FRAME, CAM, TGT, LENS, RES, SAMPLES, OUT, F0,F1 (animation range), SUBJ (hide others)"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import scene as S
E = os.environ
bpy.ops.wm.open_mainfile(filepath=E.get("SRC", ROOT + "/scene_cablecut.blend"))
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = int(E.get("SAMPLES", "48"))
sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.03
sc.cycles.volume_step_rate = float(E.get("VSTEP", "2.0")); sc.cycles.volume_max_steps = 128
sc.cycles.max_bounces = 6; sc.cycles.volume_bounces = 1; sc.cycles.transparent_max_bounces = 4
sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 3
sc.render.threads = int(E.get("THREADS", "8"))
res = eval(E.get("RES", "(1920,1080)")); sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "Filmic" if "Filmic" in [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "AgX"
try: sc.view_settings.look = "High Contrast"
except Exception:
    try: sc.view_settings.look = "AgX - High Contrast"
    except Exception: pass
# camera
c = bpy.data.cameras.new("cam"); c.lens = float(E.get("LENS", "32")); c.sensor_width = 36
c.dof.use_dof = E.get("DOF", "0") == "1"
co = bpy.data.objects.new("cam", c); sc.collection.objects.link(co); sc.camera = co
cam = eval(E.get("CAM", "(4.4,-3.6,1.5)")); tgt = eval(E.get("TGT", "(0.1,0,0.45)"))
co.location = cam; S.look(co, tgt)
if c.dof.use_dof:
    c.dof.focus_distance = (V(tgt) - V(cam)).length; c.dof.aperture_fstop = float(E.get("FSTOP", "2.8"))
hide = E.get("HIDE", "")
for ob in bpy.data.objects:
    if hide and any(h in ob.name for h in hide.split(",")): ob.hide_render = True
fr = int(E.get("FRAME", "150")); sc.frame_set(fr)
out = E.get("OUT", ROOT + "/renders/test_scene.png")
t = time.time()
if "F0" in E:
    sc.frame_start, sc.frame_end = int(E["F0"]), int(E["F1"])
    # camera animation path: CAMKEYS="f:(x,y,z):(tx,ty,tz);..."
    if "CAMKEYS" in E:
        tg = bpy.data.objects.new("camtgt", None); sc.collection.objects.link(tg)
        con = co.constraints.new("TRACK_TO"); con.target = tg; con.track_axis = "TRACK_NEGATIVE_Z"; con.up_axis = "UP_Y"
        for part in E["CAMKEYS"].split(";"):
            f, p, tt = part.split(":"); f = int(f)
            co.location = eval(p); co.keyframe_insert("location", frame=f)
            tg.location = eval(tt); tg.keyframe_insert("location", frame=f)
        for ob in (co, tg):
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation = "BEZIER"
    sc.render.filepath = out + "/f_"; sc.render.image_settings.file_format = "PNG"
    os.makedirs(out, exist_ok=True)
    for f in range(int(E["F0"]), int(E["F1"]) + 1, int(E.get("FSTEP", "1"))):
        fp = f"{out}/f_{f:04d}.png"
        if os.path.exists(fp): continue
        sc.frame_set(f); sc.render.filepath = fp
        t1 = time.time(); bpy.ops.render.render(write_still=True); print("FRAME", f, round(time.time() - t1, 1), flush=True)
else:
    sc.render.filepath = out; sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
print("RENDER_SEC", time.time() - t)
