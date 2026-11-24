"""ROV-01 original work-class open-frame ROV. build_rov(variant) -> dict of handles."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

V = Vector
def Rx(a): return Matrix.Rotation(a, 4, "X")
def Ry(a): return Matrix.Rotation(a, 4, "Y")
def Rz(a): return Matrix.Rotation(a, 4, "Z")
def T(*v): return Matrix.Translation(v)
def look_z(d):  # matrix with +Z along d
    return d.to_track_quat("Z", "Y").to_matrix().to_4x4()

L_UP, L_FORE = 0.40, 0.36

# -------------------------------------------------------------------- thruster
def thruster(G, M, prop_holder, idx, center, axis, rootobj, col, flip=1):
    """Ducted thruster, axis along `axis` (unit). Fixed parts into G, prop as own object."""
    axis = V(axis).normalized()
    Mx = T(*center) @ look_z(axis)
    G.M = Mx
    slate = G.part(M["slate_lt"], 0.004)
    # duct (closed profile revolve)
    prof = [(0.0, 0.150), (0.012, 0.128), (0.07, 0.118), (0.14, 0.116), (0.21, 0.124), (0.26, 0.132),
            (0.268, 0.147), (0.262, 0.166), (0.20, 0.170), (0.10, 0.170), (0.03, 0.168), (0.006, 0.162)]
    slate.lathe([(t / 0.27, rr) for t, rr in prof], V((0, 0, -0.135)), V((0, 0, 0.135)), seg=40, loop=True)
    # intake bellmouth ring (alu)
    alu = G.part(M["alu"], 0.003)
    alu.torus((0, 0, -0.123), (0, 0, 1), 0.162, 0.005, seg=40, seg2=8)
    # hub motor + nose/tail
    cy = G.part(M["cyan_dk"], 0.004)
    cy.lathe([(t / 0.27, rr) for t, rr in [(0, 0.0), (0.02, 0.026), (0.05, 0.040), (0.10, 0.046), (0.20, 0.046), (0.24, 0.036), (0.27, 0.0)]],
             V((0, 0, -0.12)), V((0, 0, 0.15)), seg=24)
    # struts
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        d = V((math.cos(a), math.sin(a), 0))
        rot = Euler((0, 0, a)).to_matrix().to_4x4()
        slate.box((0, 0, 0.0), (0.0, 0.0, 0.0)) if False else None
        G.M = Mx @ rot
        sp = G.part(M["slate"], 0.003)
        sp.box((0.083, 0, 0.065), (0.07, 0.012, 0.08), rot=(0, 0.0, 0))
        G.M = Mx
    # hub flange bolts
    st = G.part(M["steel_dk"], 0.0015)
    for k in range(8):
        a = 2 * math.pi * k / 8
        st.hexbolt((0.168 * math.cos(a), 0.168 * math.sin(a), 0.15), (0, 0, 1), r=0.006, h=0.005) if False else None
        st.hexbolt((0.17 * math.cos(a), 0.17 * math.sin(a), 0.0 + 0.0), (math.cos(a), math.sin(a), 0), r=0.006, h=0.006) if False else None
    for k in range(10):
        a = 2 * math.pi * k / 10
        st.hexbolt((0.152 * math.cos(a), 0.152 * math.sin(a), -0.121), (0, 0, -1), r=0.0055, h=0.005)
    # clamp bracket tabs to frame
    G.M = Mx
    # prop (separate object; spins about local Z)
    pg = Group(f"prop_{idx}", None, rootobj); pg.M = Matrix.Identity(4)
    pp = pg.part(M["prop"], 0.0015, seg_bevel=1)
    nb = 5
    for b in range(nb):
        a0 = 2 * math.pi * b / nb
        secs = []
        for i in range(9):
            r = 0.040 + (0.114 - 0.040) * i / 8
            chord = 0.030 * (0.55 + 0.45 * math.sin(math.pi * min(1, (i + 1.2) / 9.5)))
            tw = math.radians(30 - 16 * i / 8)
            th = 0.0045 * (1 - 0.5 * i / 8)
            pts = []
            for (u, w) in ((-0.5, 0), (-0.2, th), (0.2, th * 0.7), (0.5, 0), (0.2, -th * 0.35), (-0.2, -th * 0.5)):
                x = r; y = u * chord; z = w
                yy = y * math.cos(tw) - z * math.sin(tw); zz = y * math.sin(tw) + z * math.cos(tw)
                pts.append(V((x * math.cos(a0) - yy * math.sin(a0), x * math.sin(a0) + yy * math.cos(a0), zz + 0.0)))
            secs.append(pts)
        pp.loft(secs)
    pp.lathe([(t / 0.095, rr) for t, rr in [(0.0, 0.0), (0.01, 0.038), (0.04, 0.048), (0.07, 0.048), (0.085, 0.03), (0.095, 0.0)]], V((0, 0, -0.03)), V((0, 0, 0.065)), seg=24)
    pobs = pg.finalize()
    for ob in pobs:
        ob.name = f"prop_{idx}"
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = rootobj.matrix_world.inverted() @ Matrix.Identity(4) @ Mx if False else Mx
    G.M = Matrix.Identity(4)
    prop_holder.extend(pobs)

# ---------------------------------------------------------------------- arm
def build_arm(root, M, tool, base_loc, ident):
    H = {}
    ar = empty(f"{ident}_arm_root", base_loc, root, size=0.06)
    H["arm_root"] = ar
    j_slew = empty(f"{ident}_j_slew", (0, 0, 0.0), ar, size=0.05); H["j_slew"] = j_slew
    j_sh = empty(f"{ident}_j_shoulder", (0, 0, 0.13), j_slew, size=0.05); H["j_shoulder"] = j_sh
    j_el = empty(f"{ident}_j_elbow", (L_UP, 0, 0), j_sh, size=0.05); H["j_elbow"] = j_el
    j_wr = empty(f"{ident}_j_wrist", (L_FORE, 0, 0), j_el, size=0.05); H["j_wrist"] = j_wr
    j_roll = empty(f"{ident}_j_roll", (0.07, 0, 0), j_wr, size=0.05); H["j_roll"] = j_roll
    # ---- base (fixed): mounting plate + slew drive
    g = Group(f"{ident}_arm_base", None, ar)
    p = g.part(M["alu"], 0.004); p.box((0, 0, -0.015), (0.22, 0.2, 0.014))
    for sx in (-1, 1):
        for sy in (-1, 1): g.part(M["steel_dk"], 0.001).hexbolt((sx * 0.09, sy * 0.08, -0.008), (0, 0, 1), 0.0085, 0.008)
    g.part(M["cyan_dk"], 0.004).cyl(V((0, 0, -0.008)), V((0, 0, 0.065)), 0.075, 0.07, seg=32)
    g.part(M["steel"], 0.002).cyl(V((0, 0, 0.065)), V((0, 0, 0.075)), 0.082, 0.082, seg=32)
    for k in range(10):
        a = 2 * math.pi * k / 10
        g.part(M["steel_dk"], 0.001).hexbolt((0.067 * math.cos(a), 0.067 * math.sin(a), 0.075), (0, 0, 1), 0.005, 0.005)
    g.finalize()
    # ---- slew turret + shoulder housing
    g = Group(f"{ident}_arm_turret", None, j_slew)
    g.part(M["cyan"], 0.005).cyl(V((0, 0, 0.075)), V((0, 0, 0.19)), 0.068, 0.062, seg=32)
    g.part(M["cyan"], 0.005).box((0, 0, 0.13), (0.14, 0.14, 0.10))
    g.part(M["alu"], 0.003).cyl(V((0, -0.085, 0.13)), V((0, 0.085, 0.13)), 0.052, 0.052, seg=28)
    for sy in (-1, 1):
        g.part(M["steel"], 0.002).cyl(V((0, sy * 0.085, 0.13)), V((0, sy * 0.095, 0.13)), 0.04, 0.04, seg=24)
        for k in range(6):
            a = 2 * math.pi * k / 6
            g.part(M["steel_dk"], 0.001).hexbolt((0.03 * math.cos(a), sy * 0.095, 0.13 + 0.03 * math.sin(a)), (0, sy, 0), 0.005, 0.005)
    # shoulder hydraulic cylinder barrel (static visual, mounts on turret rear)
    g.part(M["cyan_dk"], 0.003).cyl(V((-0.06, 0.07, 0.10)), V((0.15, 0.07, 0.17)), 0.026, 0.026, seg=20)
    g.part(M["chrome"], 0.001).cyl(V((0.15, 0.07, 0.17)), V((0.24, 0.07, 0.205)), 0.010, 0.010, seg=12)
    g.part(M["steel"], 0.002).sphere((-0.06, 0.07, 0.10), 0.03, 12)
    g.finalize()
    # ---- upper arm
    g = Group(f"{ident}_arm_upper", None, j_sh)
    g.part(M["cyan"], 0.006).poly_prism([(0.0, -0.055), (0.0, 0.055), (L_UP - 0.04, 0.045), (L_UP, 0.04), (L_UP, -0.04), (L_UP - 0.04, -0.045)],
                                         -0.045, 0.045, mat4=Rx(math.radians(90)) @ T(0, 0, 0))
    g.part(M["alu"], 0.003).cyl(V((0, -0.065, 0)), V((0, 0.065, 0)), 0.048, 0.048, seg=28)
    g.part(M["alu"], 0.003).cyl(V((L_UP, -0.07, 0)), V((L_UP, 0.07, 0)), 0.042, 0.042, seg=28)
    for sy in (-1, 1):
        g.part(M["steel"], 0.002).cyl(V((L_UP, sy * 0.07, 0)), V((L_UP, sy * 0.078, 0)), 0.03, 0.03, seg=20)
    # elbow cylinder on top
    g.part(M["cyan_dk"], 0.003).cyl(V((0.05, -0.0, 0.08)), V((0.27, 0.0, 0.08)), 0.024, 0.024, seg=20)
    g.part(M["chrome"], 0.001).cyl(V((0.27, 0, 0.08)), V((L_UP - 0.02, 0, 0.075)), 0.009, 0.009, seg=12)
    for xx in (0.07, 0.16, 0.25, 0.34):
        g.part(M["steel_dk"], 0.001).hexbolt((xx, 0, 0.0 + 0.056), (0, 0, 1), 0.0075, 0.006)
        g.part(M["steel_dk"], 0.001).hexbolt((xx, 0.0, -0.056), (0, 0, -1), 0.0075, 0.006)
    g.part(M["hose"], 0.001).tube(V((0.04, 0.05, 0.055)), V((0.30, 0.05, 0.055)), 0.0085, 10)
    g.part(M["hose_cy"], 0.001).tube(V((0.04, 0.036, 0.062)), V((0.30, 0.036, 0.062)), 0.0085, 10)
    g.finalize()
    # ---- forearm
    g = Group(f"{ident}_arm_fore", None, j_el)
    g.part(M["cyan"], 0.006).poly_prism([(0.0, -0.045), (0.0, 0.045), (L_FORE - 0.05, 0.035), (L_FORE, 0.032), (L_FORE, -0.032), (L_FORE - 0.05, -0.035)],
                                         -0.04, 0.04, mat4=Rx(math.radians(90)))
    g.part(M["alu"], 0.003).cyl(V((0, -0.058, 0)), V((0, 0.058, 0)), 0.038, 0.038, seg=26)
    g.part(M["alu"], 0.003).cyl(V((L_FORE, -0.05, 0)), V((L_FORE, 0.05, 0)), 0.034, 0.034, seg=26)
    g.part(M["cyan_dk"], 0.003).cyl(V((0.03, 0, -0.07)), V((0.21, 0, -0.07)), 0.021, 0.021, seg=18)
    g.part(M["chrome"], 0.001).cyl(V((0.21, 0, -0.07)), V((L_FORE - 0.03, 0, -0.045)), 0.008, 0.008, seg=12)
    for xx in (0.06, 0.15, 0.24):
        g.part(M["steel_dk"], 0.001).hexbolt((xx, 0, 0.042), (0, 0, 1), 0.007, 0.006)
    g.part(M["hose"], 0.001).tube(V((0.03, -0.04, 0.04)), V((L_FORE, -0.04, 0.036)), 0.008, 10)
    g.part(M["hose_cy"], 0.001).tube(V((0.03, -0.028, 0.044)), V((L_FORE, -0.028, 0.04)), 0.008, 10)
    g.finalize()
    # ---- wrist housing + roll
    g = Group(f"{ident}_arm_wrist", None, j_wr)
    g.part(M["cyan_dk"], 0.004).cyl(V((0.0, 0, 0)), V((0.075, 0, 0)), 0.04, 0.036, seg=28)
    g.part(M["steel"], 0.002).cyl(V((0.075, 0, 0)), V((0.082, 0, 0)), 0.043, 0.043, seg=28)
    g.finalize()
    # ---- hand + tool (children of roll joint)
    g = Group(f"{ident}_arm_hand", None, j_roll)
    g.part(M["alu"], 0.003).cyl(V((0, 0, 0)), V((0.06, 0, 0)), 0.042, 0.042, seg=28)
    g.part(M["cyan"], 0.004).box((0.045, 0, 0), (0.07, 0.10, 0.09))
    for k in range(8):
        a = 2 * math.pi * k / 8
        g.part(M["steel_dk"], 0.001).hexbolt((0.0, 0.037 * math.cos(a), 0.037 * math.sin(a)), (-1, 0, 0), 0.0045, 0.004)
    g.finalize()
    H["tool"] = tool
    if tool == "grip":
        HX = 0.07
        g = Group(f"{ident}_jaw_housing", None, j_roll)
        g.part(M["cyan"], 0.004).box((0.05, 0, 0), (0.07, 0.12, 0.075))
        for sy in (-1, 1):
            g.part(M["steel"], 0.002).cyl(V((HX, sy * 0.058, 0)), V((HX, sy * 0.07, 0)), 0.022, 0.022, seg=20)
            for k in range(6):
                a_ = 2 * math.pi * k / 6
                g.part(M["steel_dk"], 0.001).hexbolt((HX + 0.014 * math.cos(a_), sy * 0.07, 0.014 * math.sin(a_)), (0, sy, 0), 0.0035, 0.004)
        g.part(M["cyan_dk"], 0.003).cyl(V((0.0, 0.0, 0.058)), V((0.08, 0.0, 0.058)), 0.018, 0.018, seg=16)
        g.finalize()
        for name, sgn in (("up", 1), ("lo", -1)):
            jj = empty(f"{ident}_jaw_{name}", (HX, 0, 0), j_roll, size=0.04); H[f"jaw_{name}"] = jj
            g = Group(f"{ident}_jaw_{name}_g", None, jj)
            poly = [(-0.025, sgn * -0.012), (-0.025, sgn * 0.032), (0.10, sgn * 0.036), (0.19, sgn * 0.014), (0.225, sgn * -0.03),
                    (0.185, sgn * -0.036), (0.15, sgn * -0.016), (0.0, sgn * -0.012)]
            pr = g.part(M["steel"], 0.003)
            for yy in (-0.040, 0.054):   # prism thickness along -Y after Rx(90)
                pr.poly_prism(poly, 0, 0.014, mat4=Matrix.Translation((0, yy, 0)) @ Rx(math.radians(90)))
            rp = g.part(M["rubber"], 0.002)
            ang = math.radians(8)
            rp.box((0.18, 0.007, sgn * -0.034), (0.07, 0.095, 0.014), rot=(0, sgn * -ang, 0))
            for k in range(6):
                rp.box((0.15 + k * 0.012, 0.007, sgn * -0.041), (0.004, 0.095, 0.007), rot=(0, sgn * -ang, 0))
            g.part(M["steel_dk"], 0.001).hexbolt((0.06, 0.054, sgn * 0.03), (0, 1, 0), 0.007, 0.006)
            g.finalize()
        H["tool_point"] = empty(f"{ident}_tool_point", (0.232, 0, 0.0), j_roll, size=0.04)
    else:
        # guillotine hydraulic cable cutter: C-head with sliding blade (+ cylinder) in z
        g = Group(f"{ident}_shear_head", None, j_roll)
        cpoly = [(0.0, -0.10), (0.25, -0.10), (0.25, -0.062), (0.11, -0.062), (0.11, 0.058), (0.25, 0.058), (0.25, 0.17), (0.0, 0.17)]
        pc = g.part(M["cyan"], 0.004)
        for yy in (-0.040, 0.052):
            pc.poly_prism(cpoly, 0, 0.012, mat4=Matrix.Translation((0.0, yy, 0)) @ Rx(math.radians(90)))
        g.part(M["alu"], 0.003).box((0.075, 0.0, 0.035), (0.05, 0.1, 0.27))
        g.part(M["blade"], 0.0015).box((0.19, 0.0, -0.069), (0.14, 0.095, 0.014))   # anvil
        g.part(M["steel_dk"], 0.002).box((0.19, 0.0, -0.081), (0.15, 0.1, 0.014))
        # blade guide cheeks + spacers
        for yy in (-0.034, 0.034):
            g.part(M["steel"], 0.002).box((0.215, yy * 1.0, 0.115), (0.04, 0.01, 0.10))
        # cylinder housing above head
        g.part(M["cyan_dk"], 0.004).cyl(V((0.185, 0, 0.17)), V((0.185, 0, 0.36)), 0.045, 0.045, seg=28)
        g.part(M["alu"], 0.003).cyl(V((0.185, 0, 0.36)), V((0.185, 0, 0.385)), 0.04, 0.03, seg=24)
        g.part(M["steel"], 0.002).cyl(V((0.185, 0, 0.17)), V((0.185, 0, 0.18)), 0.058, 0.058, seg=28)
        for k in range(8):
            a = 2 * math.pi * k / 8
            g.part(M["steel_dk"], 0.001).hexbolt((0.185 + 0.05 * math.cos(a), 0.05 * math.sin(a), 0.18), (0, 0, 1), 0.0055, 0.005)
        g.part(M["hose"], 0.001).tube(V((0.10, 0.07, 0.30)), V((0.15, 0.07, 0.34)), 0.009, 10)
        g.part(M["hose_cy"], 0.001).tube(V((0.10, 0.056, 0.26)), V((0.15, 0.056, 0.32)), 0.009, 10)
        g.part(M["steel_dk"], 0.001).hexbolt((0.15, 0.06, 0.0), (0, 1, 0), 0.008, 0.006)
        g.finalize()
        jb = empty(f"{ident}_blade_slide", (0, 0, 0), j_roll, size=0.04); H["blade"] = jb
        g = Group(f"{ident}_shear_blade", None, jb)
        # blade plate with V chisel edge, travel along -z; rest position z = +0.0 (retracted: bottom at z=0.065)
        bpoly = [(0.135, 0.17), (0.235, 0.17), (0.235, 0.075), (0.188, 0.062), (0.135, 0.075)]
        g.part(M["blade"], 0.0015).poly_prism(bpoly, -0.0125, 0.0125, mat4=Rx(math.radians(90)))
        g.part(M["chrome"], 0.001).cyl(V((0.185, 0, 0.17)), V((0.185, 0, 0.25)), 0.0165, 0.0165, seg=20)
        g.finalize()
        H["tool_point"] = empty(f"{ident}_tool_point", (0.185, 0, -0.005), j_roll, size=0.04)
    return H

# -------------------------------------------------------------------- body
def build_rov(variant="A", ident="rovA", tool="grip", M=None):
    from mats import build_mats
    M = M or build_mats()
    body_mat = M["cyan"] if variant == "A" else M["slate_lt"]
    accent = M["cyan"] if variant == "B" else M["slate"]
    root = empty(f"{ident}_root", (0, 0, 0), None, size=0.3, display="ARROWS")
    G = Group(f"{ident}_frame", None, root)
    al = G.part(M["alu"], 0.004, uv=1.0)
    xs, ys, zs = 0.85, 0.50, 0.35
    r = 0.022
    # --- aluminium tube frame
    for z in (-zs, zs):
        for y in (-ys, ys): al.tube(V((-xs, y, z)), V((xs, y, z)), r, 14)
        for x in (-xs, xs): al.tube(V((x, -ys, z)), V((x, ys, z)), r, 14)
    for x in (-xs, xs):
        for y in (-ys, ys): al.tube(V((x, y, -zs)), V((x, y, zs)), r, 14)
    for y in (-ys, ys):
        al.tube(V((-xs, y, 0)), V((xs, y, 0)), r * 0.8, 12)
        al.tube(V((-xs, y, -zs)), V((0.0, y, 0)), r * 0.65, 12); al.tube(V((xs, y, -zs)), V((0.0, y, 0)), r * 0.65, 12)
    for x in (-0.45, 0.45):
        al.tube(V((x, -ys, -zs)), V((x, ys, -zs)), r * 0.9, 12); al.tube(V((x, -ys, zs)), V((x, ys, zs)), r * 0.9, 12)
    # corner nodes
    nd = G.part(M["steel"], 0.006)
    for x in (-xs, xs):
        for y in (-ys, ys):
            for z in (-zs, zs):
                nd.box((x, y, z), (0.062, 0.062, 0.062))
                bs = G.part(M["steel_dk"], 0.001)
                bs.hexbolt((x, y, z + math.copysign(0.031, z)), (0, 0, math.copysign(1, z)), 0.009, 0.006)
                bs.hexbolt((x + math.copysign(0.031, x), y, z), (math.copysign(1, x), 0, 0), 0.009, 0.006)
                bs.hexbolt((x, y + math.copysign(0.031, y), z), (0, math.copysign(1, y), 0), 0.009, 0.006)
    # skids
    for y in (-0.42, 0.42):
        al.tube(V((-0.88, y, -0.52)), V((0.74, y, -0.52)), 0.026, 16)
        al.tube(V((0.74, y, -0.52)), V((0.92, y, -0.40)), 0.026, 16)
        al.tube(V((-0.88, y, -0.52)), V((-0.96, y, -0.40)), 0.026, 16)
        for x in (-0.60, 0.0, 0.60):
            al.tube(V((x, y, -0.52)), V((x, y, -zs)), 0.02, 12)
            G.part(M["rubber"], 0.004).box((x, y, -0.545), (0.16, 0.07, 0.016))
        nd.sphere(V((0.92, y, -0.40)), 0.03, 14); nd.sphere(V((-0.96, y, -0.40)), 0.03, 14)
    # payload tray plate + lightening slots
    pl = G.part(M["alu"], 0.003)
    pl.box((0, 0, -zs - 0.012), (1.20, 0.84, 0.012))
    for i in range(5):
        G.part(M["steel_dk"], 0.001).box((-0.4 + i * 0.2, 0, -zs - 0.005), (0.10, 0.5, 0.004))
    # --- foam
    f = G.part(M["foam"], 0.045, uv=1.0, seg_bevel=4)
    f.box((0.0, 0, 0.5), (1.56, 0.92, 0.30))
    f.box((0.72, 0, 0.465), (0.30, 0.86, 0.22))   # stepped nose
    f.box((-0.76, 0, 0.47), (0.28, 0.84, 0.24))
    # top cover plate + straps
    tc = G.part(body_mat, 0.004)
    tc.box((0.0, 0, 0.658), (1.10, 0.72, 0.014))
    st = G.part(M["alu"], 0.003)
    for x in (-0.52, 0.0, 0.52):
        st.box((x, 0, 0.5), (0.05, 0.965, 0.325))
        for yy in (-0.49, 0.49):
            G.part(M["steel_dk"], 0.001).hexbolt((x, yy, 0.56), (0, math.copysign(1, yy), 0), 0.009, 0.006)
            G.part(M["steel_dk"], 0.001).hexbolt((x, yy, 0.44), (0, math.copysign(1, yy), 0), 0.009, 0.006)
    # side body panels (cyan/slate) low on foam + livery stripe
    for sy in (-1, 1):
        tc.box((0.0, sy * 0.462, 0.5), (1.0, 0.006, 0.19))
        G.part(accent, 0.002).box((0.0, sy * 0.466, 0.585), (1.0, 0.004, 0.025))
        if variant == "B": G.part(accent, 0.002).box((0.0, sy * 0.466, 0.545), (1.0, 0.004, 0.012))
    # lift eye
    al.torus((0.0, 0, 0.745), (0, 1, 0), 0.04, 0.009, seg=28, seg2=10)
    G.part(M["steel"], 0.002).cyl(V((0, 0, 0.665)), V((0, 0, 0.73)), 0.03, 0.022, seg=20)
    # --- pressure housings (electronics) in lower bay
    ph = G.part(M["cyan_dk"], 0.004)
    for y in (-0.19, 0.19):
        ph.cyl(V((-0.46, y, -0.13)), V((0.46, y, -0.13)), 0.115, 0.115, seg=36)
        ph.sphere(V((0.46, y, -0.13)), 0.115, 22, (0.3, 1, 1)); ph.sphere(V((-0.46, y, -0.13)), 0.115, 22, (0.3, 1, 1))
        for x in (-0.40, 0.40):
            G.part(M["alu"], 0.003).cyl(V((x - 0.015, y, -0.13)), V((x + 0.015, y, -0.13)), 0.123, 0.123, seg=36)
            for k in range(14):
                a = 2 * math.pi * k / 14
                G.part(M["steel_dk"], 0.001).hexbolt((x, y + 0.123 * math.cos(a), -0.13 + 0.123 * math.sin(a)), (0, math.cos(a), math.sin(a)), 0.0055, 0.004)
        for x in (-0.22, 0.22):   # cradle straps
            G.part(M["steel"], 0.003).box((x, y, -0.13), (0.04, 0.25, 0.25)) if False else None
            G.part(M["steel"], 0.003).cyl(V((x - 0.02, y, -0.13)), V((x + 0.02, y, -0.13)), 0.123, 0.123, seg=36)
        # connector bulkheads at back
        for k in range(3):
            G.part(M["brass"], 0.001).cyl(V((-0.575 + 0.0, y + (k - 1) * 0.045, -0.13)), V((-0.60, y + (k - 1) * 0.045, -0.13)), 0.014, 0.014, seg=14)
    # hydraulic power unit between
    G.part(M["slate"], 0.004).box((0.0, 0, -0.22), (0.50, 0.26, 0.12))
    G.part(M["cyan"], 0.004).cyl(V((-0.20, 0, -0.17)), V((0.20, 0, -0.17)), 0.058, 0.058, seg=28)
    G.part(M["alu"], 0.002).cyl(V((0.20, 0, -0.17)), V((0.24, 0, -0.17)), 0.045, 0.045, seg=28)
    G.part(M["steel"], 0.002).cyl(V((0.05, 0.0, -0.17)), V((0.05, 0.0, -0.06)), 0.02, 0.02, seg=14)  # filler neck
    G.part(M["glass"], 0.0).cyl(V((0.0, 0.131, -0.22)), V((0.0, 0.14, -0.22)), 0.03, 0.03, seg=20)
    G.part(M["glass"], 0.0).cyl(V((0.0, -0.131, -0.22)), V((0.0, -0.14, -0.22)), 0.03, 0.03, seg=20)
    # --- thrusters (4 vectored + 2 vertical), 6 total
    props = []
    tcy = 0.6 * math.sqrt(0.5)
    specs = [((0.78, 0.60, -0.02), (1, 1, 0)), ((0.78, -0.60, -0.02), (1, -1, 0)), ((-0.78, 0.60, -0.02), (-1, 1, 0)), ((-0.78, -0.60, -0.02), (-1, -1, 0)),
             ((0.0, 0.62, 0.10), (0, 0, 1)), ((0.0, -0.62, 0.10), (0, 0, 1))]
    tg = Group(f"{ident}_thrusters", None, root)
    for i, (c, ax) in enumerate(specs):
        thruster(tg, M, props, i, c, ax, root, None)
        # mounting bracket to frame
        c = V(c)
        y_edge = math.copysign(0.5, c.y); x_edge = math.copysign(0.85, c.x) if abs(c.x) > 0.5 else c.x
        bk = tg.part(M["alu"], 0.003)
        if abs(c.x) > 0.5:
            bk.tube(V((x_edge, y_edge, c.z)), V(c), 0.018, 12)
            bk.box(V(c) - V((0, 0, 0)) * 0 + V((0, 0, 0)), (0.0, 0.0, 0.0)) if False else None
        else:
            bk.tube(V((c.x, y_edge, 0.22)), V((c.x, c.y, c.z)), 0.02, 12)
            bk.tube(V((c.x - 0.1, y_edge, 0.0)), V((c.x - 0.05, c.y, c.z - 0.05)), 0.012, 10) if False else None
            bk.box((c.x, math.copysign(0.56, c.y), c.z), (0.07, 0.04, 0.22)) if False else None
    tg.finalize()
    # --- camera, tilt unit, lights
    cp = Group(f"{ident}_sensors", None, root)
    cp.part(M["steel"], 0.003).box((0.93, 0, 0.0), (0.04, 0.2, 0.14)) if False else None
    cp.part(M["cyan_dk"], 0.003).cyl(V((0.86, 0, 0.06)), V((1.00, 0, 0.06)), 0.056, 0.052, seg=32)
    cp.part(M["alu"], 0.003).cyl(V((1.00, 0, 0.06)), V((1.012, 0, 0.06)), 0.060, 0.060, seg=32)
    cp.part(M["glass"], 0.003).sphere(V((1.012, 0, 0.06)), 0.044, 20, (0.45, 1, 1))
    cp.part(M["rubber"], 0.002).cyl(V((1.012, 0, 0.06)), V((1.03, 0, 0.06)), 0.058, 0.062, seg=32, caps=False)
    cp.part(M["steel"], 0.003).box((0.88, 0, 0.0), (0.05, 0.16, 0.028))
    for sy in (-1, 1):
        cp.part(M["steel"], 0.003).box((0.91, sy * 0.08, 0.03), (0.04, 0.018, 0.12))
    cp.part(M["status_led"], 0.0).cyl(V((0.995, 0.0, 0.113)), V((0.995, 0.0, 0.118)), 0.004, 0.004, seg=8)
    # down camera
    cp.part(M["cyan_dk"], 0.003).cyl(V((0.5, 0, -0.38)), V((0.5, 0, -0.45)), 0.05, 0.05, seg=28)
    cp.part(M["glass"], 0.002).cyl(V((0.5, 0, -0.45)), V((0.5, 0, -0.455)), 0.038, 0.038, seg=24)
    # lights
    L = {}
    for name, pos, dirv in (("light_FL", (0.88, 0.32, 0.30), (1, 0, 0)), ("light_FR", (0.88, -0.32, 0.30), (1, 0, 0)),
                            ("light_RL", (-0.88, 0.32, 0.30), (-1, 0, 0)), ("light_RR", (-0.88, -0.32, 0.30), (-1, 0, 0))):
        d = V(dirv); p0 = V(pos)
        cp.part(M["slate"], 0.003).cyl(p0, p0 + d * 0.11, 0.05, 0.05, seg=32)
        for k in range(4):
            cp.part(M["alu"], 0.001).cyl(p0 + d * (0.015 + 0.02 * k), p0 + d * (0.025 + 0.02 * k), 0.056, 0.056, seg=32)
        cp.part(M["alu"], 0.002).cyl(p0 + d * 0.11, p0 + d * 0.122, 0.054, 0.054, seg=32)
        cp.part(M["lens_emit"], 0.0).cyl(p0 + d * 0.122, p0 + d * 0.126, 0.042, 0.042, seg=32)
        cp.part(M["steel"], 0.003).box(p0 - d * 0.0 + V((0, 0, -0.045)), (0.06, 0.03, 0.03))
        L[name] = empty(f"{ident}_{name}", tuple(p0 + d * 0.13), root, size=0.04)
    cp.finalize()
    # --- tether termination (rear top)
    tt = Group(f"{ident}_tether", None, root)
    tt.part(M["steel"], 0.004).cyl(V((-0.86, 0, 0.20)), V((-1.02, 0, 0.20)), 0.075, 0.075, seg=32)
    tt.part(M["alu"], 0.003).cyl(V((-1.02, 0, 0.20)), V((-1.06, 0, 0.20)), 0.08, 0.08, seg=32)
    for k in range(10):
        a = 2 * math.pi * k / 10
        tt.part(M["steel_dk"], 0.001).hexbolt((-1.06, 0.065 * math.cos(a), 0.2 + 0.065 * math.sin(a)), (-1, 0, 0), 0.006, 0.005)
    tt.part(M["rubber"], 0.004).lathe([(0, 0.08), (0.25, 0.058), (0.6, 0.038), (1.0, 0.028)], V((-1.06, 0, 0.20)), V((-1.32, 0, 0.20)), seg=24)
    tt.part(M["steel"], 0.003).box((-0.86, 0, 0.20), (0.06, 0.20, 0.22)) if False else None
    for sy in (-1, 1): tt.part(M["alu"], 0.003).tube(V((-0.85, sy * 0.5, 0.35)), V((-0.9, sy * 0.06, 0.2)), 0.014, 10)
    tt.part(M["hose"], 0.003).tube(V((-1.32, 0, 0.20)), V((-1.5, 0, 0.12)), 0.026, 14)
    tt.finalize()
    H = {"root": root, "props": props, "lights": L}
    H["tether_anchor"] = empty(f"{ident}_tether_anchor", (-1.5, 0, 0.12), root, size=0.04)
    # hoses across frame (cosmetic)
    hs = Group(f"{ident}_hoses", None, root)
    pts = [(0.5, 0.2, -0.20), (0.7, 0.22, -0.28), (0.8, 0.0, -0.31), (0.82, -0.2, -0.30)]
    for a, b in zip(pts[:-1], pts[1:]):
        hs.part(M["hose"], 0.002).tube(V(a), V(b), 0.013, 12); hs.part(M["hose"], 0.002).sphere(V(b), 0.013, 10)
    pts2 = [(0.45, -0.19, -0.02), (0.6, -0.19, -0.1), (0.78, -0.24, -0.26)]
    for a, b in zip(pts2[:-1], pts2[1:]):
        hs.part(M["hose_cy"], 0.002).tube(V(a), V((b)), 0.012, 12); hs.part(M["hose_cy"], 0.002).sphere(V(b), 0.012, 10)
    hs.finalize()

    # --- extra detail: zinc anodes, hydraulic manifold + hose loops, id plates, rear junction box
    ex = Group(f"{ident}_detail", None, root)
    an = ex.part(M["steel"], 0.004)
    for (x, y, z) in [(0.85, 0.5, 0.0), (0.85, -0.5, 0.0), (-0.85, 0.5, 0.0), (-0.85, -0.5, 0.0), (0.0, 0.5, -0.35), (0.0, -0.5, -0.35), (0.45, 0.5, 0.35), (-0.45, -0.5, 0.35)]:
        an.box((x, y + math.copysign(0.04, y) if abs(y) > 0.4 and abs(x) < 0.6 else y, z), (0.09, 0.03, 0.05) if abs(x) < 0.6 else (0.05, 0.03, 0.09))
        for dxx in (-0.03, 0.03):
            ex.part(M["steel_dk"], 0.001).hexbolt((x + (dxx if abs(x) < 0.6 else 0), (y + math.copysign(0.056, y)) if abs(x) < 0.6 else y + math.copysign(0.016, y), z + (0 if abs(x) < 0.6 else dxx)), (0, math.copysign(1, y), 0), 0.006, 0.006)
    # manifold block with valve stacks
    ex.part(M["alu"], 0.003).box((0.34, 0.0, -0.285), (0.22, 0.14, 0.07))
    for k in range(5):
        ex.part(M["cyan_dk"], 0.002).cyl(V((0.26 + k * 0.04, 0.0, -0.25)), V((0.26 + k * 0.04, 0.0, -0.20)), 0.016, 0.016, seg=14)
        ex.part(M["steel"], 0.001).cyl(V((0.26 + k * 0.04, 0.0, -0.20)), V((0.26 + k * 0.04, 0.0, -0.188)), 0.009, 0.009, seg=10)
        for sy in (-1, 1):
            ex.part(M["brass"], 0.001).cyl(V((0.26 + k * 0.04, sy * 0.07, -0.285)), V((0.26 + k * 0.04, sy * 0.095, -0.285)), 0.009, 0.009, seg=10)
    # hose loops from manifold to arm base / thrusters (arcs of tube segments)
    def arc(p0, p1, bulge, mat, rad=0.013, n=9):
        pts = []
        for i in range(n + 1):
            t = i / n
            p = V(p0) * (1 - t) + V(p1) * t + V(bulge) * math.sin(math.pi * t)
            pts.append(p)
        for a, b in zip(pts[:-1], pts[1:]):
            ex.part(mat, 0.0).tube(a, b, rad, 10); ex.part(mat, 0.0).sphere(b, rad, 8)
    arc((0.40, 0.07, -0.285), (0.80, -0.20, -0.30), (0.0, 0.0, -0.10), M["hose"])
    arc((0.36, -0.07, -0.285), (0.80, -0.35, -0.28), (0.0, 0.0, 0.10), M["hose_cy"])
    arc((0.30, 0.07, -0.285), (0.55, 0.45, -0.1), (0.0, 0.0, -0.12), M["hose"], 0.011)
    arc((0.30, -0.07, -0.285), (0.55, -0.45, -0.1), (0.0, 0.0, -0.12), M["hose"], 0.011)
    arc((-0.2, 0.2, -0.26), (-0.6, 0.45, -0.05), (0.0, 0.0, -0.15), M["hose_cy"], 0.011)
    # rear junction box + glands
    ex.part(M["slate_lt"], 0.004).box((-0.74, 0.0, 0.0), (0.16, 0.34, 0.20))
    for k in range(4):
        ex.part(M["brass"], 0.001).cyl(V((-0.82, -0.12 + k * 0.08, 0.0)), V((-0.855, -0.12 + k * 0.08, 0.0)), 0.014, 0.014, seg=12)
    # ID plates (no text geometry, blank engraved plate) on frame posts
    for (x, y) in [(0.85, 0.5), (-0.85, -0.5)]:
        ex.part(M["blade"], 0.001).box((x, y, 0.2), (0.07, 0.004, 0.05) if True else None)
    # thruster guard hoops over vertical thrusters
    for sy in (-1, 1):
        ex.part(M["alu"], 0.002).torus((0.0, sy * 0.62, 0.245), (0, 0, 1), 0.17, 0.008, seg=40, seg2=8)
    ex.finalize()
    # --- arm: front-right of vehicle
    ARM = build_arm(root, M, tool, (0.80, -0.28, -0.30 + 0.0), ident)
    H.update(ARM)
    # --- decals: only 'ROV-01'
    dm = M["decal"]
    for sy in (-1, 1):
        text_decal(f"ROV-01{variant}", (0.0, sy * 0.4685, 0.50), (math.pi / 2, 0, 0 if sy < 0 else math.pi), 0.07, dm, root, name=f"{ident}_decal_side")
    text_decal(f"ROV-01{variant}", (0.0, 0, 0.6665), (0, 0, math.pi / 2), 0.11, dm, root, name=f"{ident}_decal_top")
    text_decal("ROV-01", (0.0, 0.5, 0.0), (math.pi / 2, 0, 0), 0.0, dm, root) if False else None
    # variant marker: I / II bars on foam nose
    for k in range(1 if variant == "A" else 2):
        G2 = Group(f"{ident}_marker{k}", None, root)
        G2.part(M["decal"], 0.0).box((0.865, (k - (0 if variant == "A" else 0.5)) * 0.07, 0.465), (0.004, 0.03, 0.12))
        G2.finalize()
    G.finalize()
    return H

def to_meshes():
    """Convert text decals to mesh so exporters/Cycles treat them uniformly."""
    for ob in list(bpy.data.objects):
        if ob.type == "FONT":
            bpy.context.view_layer.objects.active = ob
            for o in bpy.context.selected_objects: o.select_set(False)
            ob.select_set(True)
            mw = ob.matrix_world.copy(); par = ob.parent
            bpy.ops.object.convert(target="MESH")
            # box UV so exporter has uvs
            me = ob.data
            if not me.uv_layers: me.uv_layers.new(name="UVMap")

if __name__ == "__main__":
    import sys
    clear_scene()
    from mats import build_mats
    M = build_mats()
    h = build_rov("A", "rovA", "grip", M)
    to_meshes()
    bpy.ops.wm.save_as_mainfile(filepath=ROOT + "/test_rovA.blend")
    print("OBJECTS", len(bpy.data.objects))
