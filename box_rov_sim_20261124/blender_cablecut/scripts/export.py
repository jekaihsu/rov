"""Game-ready GLB export.  blender -b -P scripts/export.py -- rov_holder|rov_cutter|world
LOD0: 512px JPEG textures, full mesh.  LOD1: 256px textures, decimated mesh."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import rov as rovmod, cable as cablemod, env, scene as S
from mats import build_mats
OUTD = ROOT + "/export"; os.makedirs(OUTD, exist_ok=True)

def downscale_images(px):
    for im in bpy.data.images:
        if im.size[0] > px:
            im.scale(px, px)
        im.pack()

def decimate_all(ratio, min_faces=1500):
    for ob in bpy.data.objects:
        if ob.type != "MESH": continue
        if ob.data.shape_keys: continue
        if len(ob.data.polygons) < min_faces: continue
        m = ob.modifiers.new("dec", "DECIMATE"); m.ratio = ratio; m.use_collapse_triangulate = True

def export(name):
    for o in bpy.context.selected_objects: o.select_set(False)
    path = f"{OUTD}/{name}.glb"
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_image_format="JPEG", export_jpeg_quality=80,
                              export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
                              export_animations=False, export_morph=True, export_extras=False, use_selection=False)
    sz = os.path.getsize(path) / 1e6
    tris = 0
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            e = ob.evaluated_get(dg); tris += sum(len(p.vertices) - 2 for p in e.data.polygons)
    print(f"EXPORTED {name} {sz:.2f}MB tris={tris}", flush=True)
    return sz, tris

def build_rov_asset(ident, variant, tool):
    clear_scene()
    M = build_mats()
    H = rovmod.build_rov(variant, ident, tool, M)
    rovmod.to_meshes()
    S.make_spin_empties(H, H["root"])
    for o in bpy.data.objects:
        if o.type == "MESH":
            for p in o.data.polygons: p.use_smooth = p.use_smooth
    return H

def build_world_asset():
    clear_scene()
    M = build_mats()
    cablemod.STEP = 0.1; cablemod.YSEG = 20; cablemod.WSEG = 6
    env.build_seabed(M, 0.25, extent=(-12, 12, -10, 12))
    L, Sg, F = S.add_cable(M)
    env.add_rocks_and_growth(M)
    return None

if __name__ == "__main__":
    what = sys.argv[sys.argv.index("--") + 1:] or ["rov_holder", "rov_cutter", "world"]
    res = {}
    for w in what:
        if w == "rov_holder": build_rov_asset("holder", "A", "grip"); nm = "rov01a_holder"
        elif w == "rov_cutter": build_rov_asset("cutter", "B", "shear"); nm = "rov01b_cutter"
        else: build_world_asset(); nm = "cablecut_world"
        if w != "world":
            downscale_images(512); res[nm + "_lod0"] = export(nm + "_lod0")
            decimate_all(0.35); downscale_images(256); res[nm + "_lod1"] = export(nm + "_lod1")
        else:
            downscale_images(512); res[nm] = export(nm)
    json.dump(res, open(OUTD + f"/export_stats_{'_'.join(what)}.json", "w"))
