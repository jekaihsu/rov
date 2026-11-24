import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

def V3(*a):
    return Vector(a if len(a) > 1 else a[0])
V = V3
CS = 1.3
R_OUT = 0.0381 * CS          # yarn outer radius  (~0.0495 m, 99 mm cable)
R_SHEATH_O = 0.0295 * CS
R_SHEATH_I = 0.0248 * CS
R_BED = R_SHEATH_O + 0.0006
R_WIRE = 0.0028 * CS
R_WIRE_C = 0.0323 * CS
N_WIRE = 34
LAY = 0.95                    # armour lay length (m)
R_INS = 0.0115 * CS
R_COND = 0.0058 * CS
CORE_D = 0.01328 * CS
STEP = 0.04
WSEG = 8
YSEG = 40

def path_frame(zf, x):
    e = 1e-3
    z0, z1 = zf(x - e), zf(x + e)
    ph = math.atan2(z1 - z0, 2 * e)
    t = V3(math.cos(ph), 0, math.sin(ph)); n = V3(-math.sin(ph), 0, math.cos(ph)); b = V3(0, 1, 0)
    return V3(x, 0, zf(x)), t, n, b

def ring_pts(c, n, b, cx_, cy_, r, seg, rot=0.0):
    pts = []
    for i in range(seg):
        a = rot + 2 * math.pi * i / seg
        pts.append(c + b * (cx_ + r * math.cos(a)) + n * (cy_ + r * math.sin(a)))
    return pts

def build_segment(M, name, zf, x0, x1, ext0=0.0, ext1=0.0, ends=(False, False), col=None, parent=None):
    """Cable segment between x0..x1 (x forward). ends=(start_cap, end_cap) -> cut-face detail."""
    n_s = max(2, int(round((x1 - x0) / STEP)))
    xs = [x0 + (x1 - x0) * i / n_s for i in range(n_s + 1)]
    G = Group(name, col, parent)
    # yarn serving tube (rope textured)
    yp = G.part(M["yarn"], 0.0, uv=2.0, recalc=True)
    rng = random.Random(hash(name) & 0xffff)
    secs = []
    for x in xs:
        c, t, n, b = path_frame(zf, x)
        rr = R_OUT * (1 + 0.012 * math.sin(x * 37.0) + 0.006 * math.sin(x * 91.0 + 2))
        secs.append(ring_pts(c, n, b, 0, 0, rr, YSEG))
    # inner shell to close hollow: reuse loft with caps (hidden); end annulus drawn separately
    yp.loft(secs, caps=False)
    # armour wires (helical)
    aw = G.part(M["armour"], 0.0, uv=2.0)
    xa0, xa1 = x0 - ext0, x1 + ext1
    na = max(2, int(round((xa1 - xa0) / STEP)))
    for w in range(N_WIRE):
        ph0 = 2 * math.pi * w / N_WIRE
        secs = []
        for i in range(na + 1):
            x = xa0 + (xa1 - xa0) * i / na
            c, t, n, b = path_frame(zf, x)
            th = ph0 + 2 * math.pi * x / LAY
            cc = c + b * (R_WIRE_C * math.cos(th)) + n * (R_WIRE_C * math.sin(th))
            rad_b = b * math.cos(th) + n * math.sin(th); tang = t
            # wire cross-section in plane (rad, binormal-of-helix) approx: use (rad, perp)
            perp = rad_b.cross(t)
            secs.append([cc + rad_b * (R_WIRE * math.cos(a)) + perp * (R_WIRE * math.sin(a)) for a in [2 * math.pi * k / WSEG for k in range(WSEG)]])
        aw.loft(secs, caps=True)
    # end details
    for which, flag in enumerate(ends):
        if not flag: continue
        x = x0 if which == 0 else x1
        c, t, n, b = path_frame(zf, x)
        out = -t if which == 0 else t
        # local basis: z=out, x=b, y=out x b ... keep right-handed
        zax = out; xax = b; yax = zax.cross(xax)
        Bm = Matrix(((xax.x, yax.x, zax.x, c.x), (xax.y, yax.y, zax.y, c.y), (xax.z, yax.z, zax.z, c.z), (0, 0, 0, 1)))
        def ring(mat, ri, ro, h, cen=(0, 0), seg=40, bev=0.0006):
            p = G.part(mat, bev, uv=2.0)
            p.base = Bm @ Matrix.Translation((cen[0], cen[1], 0))
            p.lathe([(0, ri), (0, ro), (h, ro), (h, ri)] if ri > 0 else [(0, 0.0), (0, ro), (h, ro), (h, 0.0)], V3((0, 0, 0)), V3((0, 0, 1)), seg=seg, loop=(ri > 0)) if ri > 0 else p.cyl(V3((0, 0, 0)), V3((0, 0, h)), ro, ro, seg=seg)
        # yarn annulus (flush) + bedding disc inside
        ring(M["yarn"], R_SHEATH_O, R_OUT, 0.0005)
        ring(M["bedding"], 0.0, R_SHEATH_O + 0.0004, 0.004)
        ring(M["sheath"], R_SHEATH_I, R_SHEATH_O, 0.009)
        for k in range(3):
            a = math.radians(90 + 120 * k)
            cen = (CORE_D * math.cos(a), CORE_D * math.sin(a))
            ring([M["xlpe_a"], M["xlpe_b"], M["xlpe_c"]][k], R_COND + 0.0003, R_INS, 0.014, cen)
            p = G.part(M["copper"], 0.0003, uv=8.0)
            p.base = Bm @ Matrix.Translation((cen[0], cen[1], 0))
            sr = 0.0015 * CS * 0.99
            pos = [(0, 0)] + [(2 * sr * 1.0 * math.cos(math.radians(60 * j)), 2 * sr * math.sin(math.radians(60 * j))) for j in range(6)]
            pos += [(4 * sr * math.cos(math.radians(30 * j)) * (1 if j % 2 == 0 else 0.866), 4 * sr * math.sin(math.radians(30 * j)) * (1 if j % 2 == 0 else 0.866)) for j in range(12)]
            for (sx, sy) in pos:
                h = 0.020 + 0.002 * ((sx * 977 + sy * 733) % 1 > 0.5)
                p.cyl(V3((sx, sy, 0)), V3((sx, sy, h)), sr, sr, seg=8)
        # cut faces of armour wire ends are in wire loft caps; add bright cut material discs on top of each wire end
        cut = G.part(M["armour_cut"], 0.0, uv=4.0)
        for w in range(N_WIRE):
            th = 2 * math.pi * w / N_WIRE + 2 * math.pi * x / LAY
            cx_ = R_WIRE_C * math.cos(th); cy_ = R_WIRE_C * math.sin(th)
            # wire end sits at z=ext (outward); cap disc slightly beyond
            e = ext0 if which == 0 else ext1
            cut.cyl(V3((0, 0, 0)), V3((0, 0, 0)), 0.0001, 0.0001, seg=3) if False else None
        # frayed yarn strands
        fr = G.part(M["yarn"], 0.0, uv=6.0)
        for k in range(34):
            a = rng.random() * 2 * math.pi; rr = rng.uniform(R_WIRE_C + R_WIRE + 0.001, R_OUT - 0.002)
            L = rng.uniform(0.004, 0.017); tilt = rng.uniform(-0.7, 0.7); az = rng.random() * 2 * math.pi
            p0 = V3(rr * math.cos(a), rr * math.sin(a), 0.0)
            p1 = p0 + V3(L * math.sin(tilt) * math.cos(az), L * math.sin(tilt) * math.sin(az), L * math.cos(tilt))
            fr.base = Bm
            fr.cyl(p0, p1, 0.0011, 0.0004, seg=5)
    obs = G.finalize()
    return obs

def build_cable(M, zf, cut_x, stub_len=2.0, x_min=-9.0, x_max=9.0, col=None):
    """Three rigid pieces. L (held side), STUB (severed free end, rotates down), FAR (static)."""
    L = build_segment(M, "cable_L", zf, x_min, cut_x, ext0=0, ext1=0.0045, ends=(False, True), col=col)
    S = build_segment(M, "cable_stub", zf, cut_x, cut_x + stub_len, ext0=0.0045, ext1=0.0, ends=(True, False), col=col)
    F = build_segment(M, "cable_far", zf, cut_x + stub_len, x_max, col=col)
    return L, S, F

if __name__ == "__main__":
    clear_scene()
    from mats import build_mats
    M = build_mats()
    zf = lambda x: 0.05 + 0.2 * max(0, math.cos(math.pi * (x - 0.0) / 3.0)) ** 2 * (abs(x) < 1.5)
    L, S, F = build_cable(M, zf, 0.35, x_min=-3, x_max=5)
    # separate the stub for the closeup test
    for o in S:
        o.location = (0.12, 0, -0.08)
    bpy.ops.wm.save_as_mainfile(filepath=ROOT + "/test_cable.blend")
    print("verts", sum(len(o.data.vertices) for o in L + S + F))
