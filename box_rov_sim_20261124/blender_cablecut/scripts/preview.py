import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
src = os.environ.get("SRC", ROOT + "/test_rovA.blend"); out = os.environ.get("OUT", ROOT + "/renders/test.png")
cam = eval(os.environ.get("CAM", "(3.2,-3.0,1.6)")); tgt = eval(os.environ.get("TGT", "(0,0,0.2)"))
res = eval(os.environ.get("RES", "(800,450)")); samples = int(os.environ.get("SAMPLES", "24")); lens = float(os.environ.get("LENS", "42"))
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = res; sc.render.threads = 8
sc.cycles.use_adaptive_sampling = True
w = bpy.data.worlds.new("w"); w.use_nodes = True; sc.world = w
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.35, 0.45, 0.5, 1); bg.inputs[1].default_value = 0.8
def area(loc, energy, size=3):
    l = bpy.data.lights.new("a", "AREA"); l.energy = energy; l.size = size
    o = bpy.data.objects.new("a", l); sc.collection.objects.link(o); o.location = loc
    d = Vector(tgt) - Vector(loc); o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
area((3, -2, 4), 400); area((-3, 3, 2), 150)
c = bpy.data.cameras.new("c"); c.lens = lens; co = bpy.data.objects.new("c", c); sc.collection.objects.link(co)
co.location = cam; co.rotation_euler = (Vector(tgt) - Vector(cam)).to_track_quat("-Z", "Y").to_euler(); sc.camera = co
sc.render.filepath = out; sc.render.image_settings.file_format = "PNG"
import time; t = time.time(); bpy.ops.render.render(write_still=True); print("RENDER_SEC", time.time() - t)
