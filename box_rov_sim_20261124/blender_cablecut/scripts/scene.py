import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from mats import build_mats
import rov as rovmod
import cable as cablemod
import env

XG, CUTX, LIFT, LIFT_W = -0.20, 0.35, 0.26, 1.5
STUB = 2.0
FPS = 24

def lift_fn(x):
    u = (x - XG) / LIFT_W
    return LIFT * (math.cos(math.pi * u / 2) ** 2) if abs(u) < 1 else 0.0

def ik_arm(H, root_obj, target_w, tool_up_off, tool_fwd_off, pitch3=0.0):
    """Planar 2-link IK; returns (phi1, phi2, phi3) absolute pitch angles (up positive)."""
    base = root_obj.matrix_world @ V(H["arm_root"].location)
    S = base + root_obj.matrix_world.to_3x3() @ V((0, 0, 0.13))
    T_ = V(target_w)
    d_vec = T_ - S
    fwd = root_obj.matrix_world.to_3x3() @ V((1, 0, 0))
    d_ = d_vec.dot(fwd); h_ = d_vec.z
    # wrist joint = tool minus tool offset (forward along tool, + up)
    wd = d_ - tool_fwd_off * math.cos(pitch3) + tool_up_off * math.sin(pitch3)
    wh = h_ - tool_fwd_off * math.sin(pitch3) - tool_up_off * math.cos(pitch3)
    D = math.hypot(wd, wh)
    D = min(D, rovmod.L_UP + rovmod.L_FORE - 1e-3)
    cd = (rovmod.L_UP ** 2 + D ** 2 - rovmod.L_FORE ** 2) / (2 * rovmod.L_UP * D)
    dl = math.acos(max(-1, min(1, cd)))
    p1 = math.atan2(wh, wd) + dl
    E = V((rovmod.L_UP * math.cos(p1), rovmod.L_UP * math.sin(p1)))
    p2 = math.atan2(wh - E.y, wd - E.x)
    return p1, p2, pitch3

def set_arm(H, p1, p2, p3, jaw=None, blade=None, roll=0.0, slew=0.0):
    H["j_slew"].rotation_euler = (0, 0, slew)
    H["j_shoulder"].rotation_euler = (0, -p1, 0)
    H["j_elbow"].rotation_euler = (0, -(p2 - p1), 0)
    H["j_wrist"].rotation_euler = (0, -(p3 - p2), 0)
    H["j_roll"].rotation_euler = (roll, 0, 0)
    if jaw is not None:
        H["jaw_up"].rotation_euler = (0, -math.radians(jaw), 0); H["jaw_lo"].rotation_euler = (0, math.radians(jaw), 0)
    if blade is not None:
        H["blade"].location = (0, 0, blade)

def key_arm(H, f):
    for k in ("j_slew", "j_shoulder", "j_elbow", "j_wrist", "j_roll", "jaw_up", "jaw_lo"):
        if k in H: H[k].keyframe_insert("rotation_euler", frame=f)
    if "blade" in H: H["blade"].keyframe_insert("location", frame=f)

def spin_props(H, rpm_turns, f0, f1):
    for i, pv in enumerate(H["spin"]):
        sgn = 1 if i % 2 == 0 else -1
        pv.rotation_euler = (0, 0, 0); pv.keyframe_insert("rotation_euler", frame=f0)
        pv.rotation_euler = (0, 0, sgn * rpm_turns * 2 * math.pi); pv.keyframe_insert("rotation_euler", frame=f1)
        for fc in pv.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

def make_spin_empties(H, root):
    """Re-parent prop meshes under a spin empty (mount empty keeps thruster transform)."""
    H["spin"] = []
    for ob in H["props"]:
        mount = empty(ob.name + "_mount", (0, 0, 0), root, size=0.02)
        mount.matrix_basis = ob.matrix_basis.copy()
        spin = empty(ob.name + "_spin", (0, 0, 0), mount, size=0.02)
        ob.parent = spin; ob.matrix_basis = Matrix.Identity(4); ob.matrix_parent_inverse = Matrix.Identity(4)
        H["spin"].append(spin)

def add_cable(M, with_lift_key=True):
    zl = lambda x: env.lie_z(x)
    L, S, F = cablemod.build_cable(M, zl, CUTX, stub_len=STUB, x_min=-9.0, x_max=9.0)
    for grp in (L, S):
        for ob in grp:
            if with_lift_key:
                ob.shape_key_add(name="Basis", from_mix=False)
                k = ob.shape_key_add(name="lift", from_mix=False)
                for i, v in enumerate(ob.data.vertices):
                    k.data[i].co = (v.co.x, v.co.y, v.co.z + lift_fn(v.co.x))
    return L, S, F

def build_scene(lift_baked=False, do_anim=True, high=True):
    clear_scene()
    sc = bpy.context.scene
    sc.render.fps = FPS
    M = build_mats()
    seabed = env.build_seabed(M, 0.075 if high else 0.2)
    cabL, cabS, cabF = add_cable(M)
    rocks, grow = env.add_rocks_and_growth(M)
    snow = env.add_snow(M)
    # ROVs ------------------------------------------------------------------
    zl_g = env.lie_z(XG) + lift_fn(XG)
    zl_c = env.lie_z(CUTX) + lift_fn(CUTX)
    HA = rovmod.build_rov("A", "holder", "grip", M)
    HB = rovmod.build_rov("B", "cutter", "shear", M)
    rovmod.to_meshes()
    for H in (HA, HB): make_spin_empties(H, H["root"])
    ZR = 0.78
    A_END = V((XG - 0.28, -1.58, ZR)); B_END = V((CUTX + 0.28, 1.58, ZR))
    HA["root"].location = A_END; HA["root"].rotation_euler = (0, 0, math.radians(90))
    HB["root"].location = B_END; HB["root"].rotation_euler = (0, 0, math.radians(-90))
    bpy.context.view_layer.update()
    # IK poses
    tpA = V(HA["tool_point"].location); tpB = V(HB["tool_point"].location)
    offA = (0.07 + tpA.x, tpA.z); offB = (0.07 + tpB.x, tpB.z)
    gA = V((XG, 0, zl_g)); gB = V((CUTX, 0, zl_c))
    posA = ik_arm(HA, HA["root"], gA, offA[1], offA[0]); posB = ik_arm(HB, HB["root"], gB, offB[1], offB[0])
    # pre-grasp: 0.28 m back along heading and 0.06 higher
    def pre(Hh, root, g, off, back=0.30, up=0.10):
        fwd = root.matrix_world.to_3x3() @ V((1, 0, 0))
        return ik_arm(Hh, root, g - fwd * back + V((0, 0, up)), off[1], off[0])
    preA = pre(HA, HA["root"], gA, offA); preB = pre(HB, HB["root"], gB, offB)
    stow = (math.radians(-62), math.radians(-168), math.radians(-120))
    # seabed contact info for the game
    info = {"cut_x": CUTX, "grip_x": XG, "lift": LIFT, "lift_w": LIFT_W, "grip_z": zl_g, "cut_z": zl_c,
            "holder": {"pos": list(A_END), "yaw_deg": 90}, "cutter": {"pos": list(B_END), "yaw_deg": -90},
            "lie_z_samples": [[x, env.lie_z(x)] for x in np.arange(-9, 9.01, 0.5)],
            "arm_base_local": [0.80, -0.28, -0.30], "stub_len": STUB, "grip_angle": 30, "open_angle": 52}
    sc["layout"] = json.dumps(info)
    # tethers
    tA = env.add_tether(M, V(HA["tether_anchor"].matrix_world.translation), (0, -1, 0), 8.0, "tether_holder", 1)
    tB = env.add_tether(M, V(HB["tether_anchor"].matrix_world.translation), (0.25, 1, 0), 8.0, "tether_cutter", 2)
    # stub pivot ----------------------------------------------------------
    piv = empty("stub_pivot", (CUTX + STUB, 0, env.lie_z(CUTX + STUB)), None, size=0.1)
    bpy.context.view_layer.update()
    for ob in cabS:
        ob.parent = piv; ob.matrix_parent_inverse = piv.matrix_world.inverted()
    if do_anim:
        animate(sc, M, HA, HB, A_END, B_END, preA, preB, posA, posB, stow, piv, cabL, cabS)
    return dict(M=M, HA=HA, HB=HB, piv=piv, cabL=cabL, cabS=cabS, cabF=cabF, info=info, seabed=seabed)

def ease(obj, kind="BEZIER"):
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                if kp.interpolation != "LINEAR": kp.interpolation = kind

def animate(sc, M, HA, HB, A_END, B_END, preA, preB, posA, posB, stow, piv, cabL, cabS):
    F = [1, 70, 110, 140, 168, 178, 205, 232]       # key frames @24fps (~9.7 s)
    sc.frame_start, sc.frame_end = 1, F[-1] + 8
    # vehicle approach (y) and retreat
    for H, end, sgn in ((HA, A_END, -1), (HB, B_END, 1)):
        start = V((end.x + (-0.5 if H is HA else 0.5), end.y + sgn * 2.2, end.z + 0.10))
        H["root"].location = start; H["root"].keyframe_insert("location", frame=F[0])
        H["root"].location = end; H["root"].keyframe_insert("location", frame=F[1])
        H["root"].location = end + V((0, 0.0, 0.0)); H["root"].keyframe_insert("location", frame=F[5])
        H["root"].location = end + V((-0.2 if H is HA else 0.2, sgn * 0.5, 0.04)); H["root"].keyframe_insert("location", frame=F[7] + 8)
        ease(H["root"])
        # gentle hover bob
        spin_props(H, 14, 1, F[-1] + 8)
    # arms: stowed -> pregrasp -> grasp
    def arm_key(H, pose, f, jaw=None, blade=None):
        set_arm(H, *pose, jaw=jaw, blade=blade); key_arm(H, f)
    arm_key(HA, stow, F[0], jaw=8); arm_key(HB, stow, F[0], blade=0.0)
    arm_key(HA, stow, 20, jaw=8); arm_key(HB, stow, 20, blade=0.0)
    arm_key(HA, preA, F[1] + 20, jaw=52); arm_key(HB, preB, F[1] + 20, blade=0.0)
    arm_key(HA, posA, F[2], jaw=52); arm_key(HB, preB, F[2], blade=0.0)
    arm_key(HA, posA, F[2] + 14, jaw=30)                         # holder closes on cable
    arm_key(HB, posB, F[3], blade=0.0)                           # cutter moves in
    arm_key(HA, posA, F[3], jaw=30); arm_key(HB, posB, F[3] + 4, blade=0.0)
    arm_key(HA, posA, F[4], jaw=30); arm_key(HB, posB, F[4], blade=-0.123)   # shear closes
    arm_key(HA, posA, F[6], jaw=30); arm_key(HB, posB, F[5] + 20, blade=-0.123)
    arm_key(HB, posB, F[6] + 6, blade=0.0)
    arm_key(HA, preA, F[7], jaw=52); arm_key(HB, preB, F[7], blade=0.0)
    arm_key(HA, stow, F[7] + 8, jaw=8); arm_key(HB, stow, F[7] + 8, blade=0.0)
    for H in (HA, HB): [ease(H[k]) for k in ("j_slew", "j_shoulder", "j_elbow", "j_wrist", "j_roll", "jaw_up", "jaw_lo", "blade") if k in H]
    # cable lift via shape key (holder lifts as it closes)
    for ob in cabL + cabS:
        if ob.data.shape_keys:
            kb = ob.data.shape_keys.key_blocks["lift"]
            kb.value = 0.0; kb.keyframe_insert("value", frame=F[2] + 10)
            kb.value = 1.0; kb.keyframe_insert("value", frame=F[2] + 38)
            ease_k = ob.data.shape_keys.animation_data.action.fcurves
            for fc in ease_k:
                for kp in fc.keyframe_points: kp.interpolation = "BEZIER"
    # severed stub falls away
    piv.rotation_euler = (0, 0, 0); piv.keyframe_insert("rotation_euler", frame=F[4] - 2)
    piv.location = (CUTX + STUB, 0, env.lie_z(CUTX + STUB)); piv.keyframe_insert("location", frame=F[4] - 2)
    piv.rotation_euler = (0, math.radians(-8.0), math.radians(5)); piv.keyframe_insert("rotation_euler", frame=F[4] + 24)
    piv.location = (CUTX + STUB + 0.14, 0.0, env.lie_z(CUTX + STUB)); piv.keyframe_insert("location", frame=F[4] + 24)
    piv.rotation_euler = (0, math.radians(-8.6), math.radians(7.0)); piv.keyframe_insert("rotation_euler", frame=F[7])
    piv.location = (CUTX + STUB + 0.16, 0.0, env.lie_z(CUTX + STUB)); piv.keyframe_insert("location", frame=F[7])
    ease(piv)

def setup_world(sc, vol=0.05, strong=True):
    w = bpy.data.worlds.new("uw"); w.use_nodes = True; sc.world = w
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs[0].default_value = (0.004, 0.035, 0.05, 1); bg.inputs[1].default_value = 1.0
    sca = nt.nodes.new("ShaderNodeVolumeScatter"); sca.inputs["Color"].default_value = (0.20, 0.70, 0.78, 1)
    sca.inputs["Density"].default_value = 0.075; sca.inputs["Anisotropy"].default_value = 0.55
    ab = nt.nodes.new("ShaderNodeVolumeAbsorption"); ab.inputs["Color"].default_value = (0.12, 0.62, 0.78, 1); ab.inputs["Density"].default_value = 0.16
    ad = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(sca.outputs[0], ad.inputs[0]); nt.links.new(ab.outputs[0], ad.inputs[1])
    nt.links.new(bg.outputs[0], out.inputs["Surface"]); nt.links.new(ad.outputs[0], out.inputs["Volume"])

def beam_material():
    m = bpy.data.materials.new("beam_vol"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); sc_ = nt.nodes.new("ShaderNodeVolumeScatter")
    sc_.inputs["Color"].default_value = (1.0, 0.97, 0.88, 1); sc_.inputs["Density"].default_value = 0.22; sc_.inputs["Anisotropy"].default_value = 0.6
    nt.links.new(sc_.outputs[0], out.inputs["Volume"]); return m

def add_beam(sc, spot, mat):
    bm = bmesh.new(); n = 20; L_ = 7.0; Rr = math.tan(math.radians(22)) * L_
    ap = bm.verts.new((0, 0, -0.02)); ring = [bm.verts.new((Rr * math.cos(2 * math.pi * i / n), Rr * math.sin(2 * math.pi * i / n), -L_)) for i in range(n)]
    for i in range(n): bm.faces.new((ap, ring[(i + 1) % n], ring[i]))
    bm.faces.new(ring[::-1]); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("beam"); bm.to_mesh(me); bm.free(); me.materials.append(mat)
    ob = bpy.data.objects.new("beam", me); sc.collection.objects.link(ob); ob.parent = spot
    ob.visible_camera = True; ob.visible_shadow = False; return ob

def add_lights(sc, HA, HB):
    M_beam = beam_material()
    for H in (HA, HB):
        for nm, e in H["lights"].items():
            if nm.endswith(("FL", "FR")):
                l = bpy.data.lights.new(nm, "SPOT"); l.energy = 9000; l.spot_size = math.radians(48); l.spot_blend = 0.35
                l.color = (1.0, 0.96, 0.88); l.shadow_soft_size = 0.04
                o = bpy.data.objects.new(nm + "_L", l); sc.collection.objects.link(o)
                o.parent = H["root"]; o.location = e.location; o.rotation_euler = (0, math.radians(90), 0)   # -Z -> +X
                add_beam(sc, o, M_beam)
    # downwelling ambient
    l = bpy.data.lights.new("sunlight", "AREA"); l.energy = 7000; l.size = 14; l.color = (0.55, 0.85, 0.95)
    o = bpy.data.objects.new("sunlight", l); sc.collection.objects.link(o); o.location = (1, -1, 9); o.rotation_euler = (0, 0, 0)
    l2 = bpy.data.lights.new("fill", "AREA"); l2.energy = 220; l2.size = 6; l2.color = (0.6, 0.9, 1.0)
    o2 = bpy.data.objects.new("fill", l2); sc.collection.objects.link(o2); o2.location = (4, -4, 2.5)
    o2.rotation_euler = (math.radians(65), 0, math.radians(40))

def look(cam, tgt, roll=0):
    cam.rotation_euler = (V(tgt) - V(cam.location)).to_track_quat("-Z", "Y").to_euler()

if __name__ == "__main__":
    t0 = __import__("time").time()
    S = build_scene()
    sc = bpy.context.scene
    setup_world(sc); add_lights(sc, S["HA"], S["HB"])
    bpy.ops.wm.save_as_mainfile(filepath=os.environ.get("OUTBLEND", ROOT + "/scene_cablecut.blend"))
    print("BUILD_SEC", __import__("time").time() - t0, "objects", len(bpy.data.objects))
