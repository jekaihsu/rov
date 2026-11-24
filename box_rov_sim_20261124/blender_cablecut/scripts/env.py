import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

X0, X1, Y0, Y1 = -14.0, 14.0, -12.0, 14.0
_F = {}
def _field():
    if "f" not in _F:
        _F["f"] = fbm(512, 2.9, 77); _F["g"] = fbm(512, 1.8, 78)
    return _F["f"], _F["g"]

def _samp(a, X, Y, scale):
    n = a.shape[0]
    u = (X / scale) % 1.0 * n; v = (Y / scale) % 1.0 * n
    i0 = np.floor(u).astype(int) % n; j0 = np.floor(v).astype(int) % n
    fu = u - np.floor(u); fv = v - np.floor(v)
    i1 = (i0 + 1) % n; j1 = (j0 + 1) % n
    return (a[i0, j0] * (1 - fu) * (1 - fv) + a[i1, j0] * fu * (1 - fv) + a[i0, j1] * (1 - fu) * fv + a[i1, j1] * fu * fv)

def seabed_h(X, Y, trench=True):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    f, g = _field()
    big = (_samp(f, X, Y, 40.0) - 0.5) * 1.1
    mid = (_samp(g, X, Y, 9.0) - 0.5) * 0.18
    fine = (_samp(g, X + 3.1, Y - 1.7, 1.3) - 0.5) * 0.02
    d = np.maximum(np.abs(X) / 7.0, np.abs(Y) / 4.5)
    win = np.clip((d - 0.8) / 1.0, 0, 1); win = win * win * (3 - 2 * win)
    amp = 0.05 + 0.95 * win
    warp = _samp(g, X, Y, 6.0) * 0.5
    rip = 0.012 * np.sin((0.85 * X + 0.5 * Y + warp * 3) * 2 * np.pi / 0.42) * (0.4 + 0.6 * win)
    h = (big * 0.6 + mid) * amp + rip + fine
    if trench:
        h = h - 0.045 * np.exp(-(Y / 0.12) ** 2) + 0.012 * np.exp(-((np.abs(Y) - 0.2) / 0.08) ** 2)
    return h

def lie_z(x):
    return float(seabed_h(x, 0.0, trench=False)) + 0.012

def build_seabed(M, step=0.08, name="seabed", extent=None):
    x0, x1, y0, y1 = extent or (X0, X1, Y0, Y1)
    xs = np.arange(x0, x1 + 1e-6, step); ys = np.arange(y0, y1 + 1e-6, step)
    XX, YY = np.meshgrid(xs, ys, indexing="ij")
    H = seabed_h(XX, YY)
    nx, ny = len(xs), len(ys)
    verts = np.stack([XX, YY, H], -1).reshape(-1, 3)
    idx = np.arange(nx * ny).reshape(nx, ny)
    a = idx[:-1, :-1].ravel(); b = idx[1:, :-1].ravel(); c = idx[1:, 1:].ravel(); d = idx[:-1, 1:].ravel()
    faces = np.stack([a, b, c, d], -1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    # world-planar UV (1 uv unit = 1 m)
    co = np.array([v.co[:2] for v in me.vertices])
    luv = np.array([co[l.vertex_index] for l in me.loops])
    uv.data.foreach_set("uv", luv.ravel())
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.materials.append(M["sand"])
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    return ob

def rock_mesh(rng, rad, M, subdiv=3):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    ph = [rng.random() * 6.28 for _ in range(6)]; fr = [rng.uniform(1.5, 4.5) for _ in range(6)]
    for v in bm.verts:
        p = v.co.copy(); r = 1.0
        for k in range(3):
            r += 0.18 / (k + 1) * math.sin(p.x * fr[k] * (k + 1) + ph[k]) * math.cos(p.y * fr[k + 3] + ph[k + 3]) * math.sin(p.z * fr[k] + ph[3 + k])
        r += 0.05 * math.sin(p.x * 11 + ph[0]) * math.sin(p.y * 13 + ph[1])
        v.co = p * r
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((rad * rng.uniform(0.9, 1.4), rad * rng.uniform(0.8, 1.2), rad * rng.uniform(0.5, 0.8), 1)), verts=bm.verts)
    return bm

def add_rocks_and_growth(M, seed=5, corridor=True):
    rng = random.Random(seed)
    rockP = Part(M["rock"], 0.0); rockP.recalc = True
    alg = Part(M["algae"], 0.0, uv=2.0); alg.recalc = False
    spo = Part(M["sponge"], 0.0, uv=2.0)
    shl = Part(M["shell"], 0.0, uv=4.0)
    bar = Part(M["shell"], 0.0, uv=6.0)
    rocks = []
    for i in range(46):
        for _ in range(20):
            x = rng.uniform(-11, 11); y = rng.uniform(-9.5, 11)
            if abs(x) < 6.5 and abs(y) < 5.8: continue      # keep the work area clear
            break
        rad = rng.choice([0.15, 0.2, 0.3, 0.45, 0.7, 1.0, 1.5]) * rng.uniform(0.7, 1.2)
        z = float(seabed_h(x, y)) + rad * 0.12
        bm = rock_mesh(rng, rad, M, 3 if rad > 0.25 else 2)
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Euler((0, 0, rng.random() * 6.28)).to_matrix(), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(x, y, z), verts=bm.verts)
        verts = [v.co.copy() for v in bm.verts]
        # merge into the rock part bmesh
        rockP.bm.from_mesh(bpy.data.meshes.new("tmp")) if False else None
        mp = {}
        for v in bm.verts: mp[v] = rockP.bm.verts.new(v.co)
        for f in bm.faces: rockP.bm.faces.new([mp[v] for v in f.verts])
        bm.free()
        rocks.append((x, y, z, rad))
        # marine growth on rocks
        if rad > 0.2:
            for k in range(int(rad * 14)):
                a = rng.random() * 6.28; rr = rad * rng.uniform(0.2, 0.9)
                px = x + rr * math.cos(a); py = y + rr * math.sin(a)
                pz = z + rad * 0.5 * math.sqrt(max(0, 1 - (rr / rad) ** 2)) * 0.9
                kind = rng.random()
                if kind < 0.35:   # tube sponge
                    hh = rng.uniform(0.05, 0.16)
                    spo.cyl(V((px, py, pz - 0.01)), V((px, py, pz + hh)), 0.018, 0.026, seg=10)
                    spo.cyl(V((px, py, pz + hh - 0.005)), V((px, py, pz + hh)), 0.014, 0.014, seg=10)
                elif kind < 0.7:   # algae fronds
                    for b in range(3):
                        ang = rng.random() * 6.28; hh = rng.uniform(0.12, 0.35)
                        pts = []
                        for s in range(6):
                            t = s / 5
                            pts.append(V((px + math.cos(ang) * 0.06 * t * t * hh * 3, py + math.sin(ang) * 0.06 * t * t * hh * 3, pz + hh * t)))
                        w = 0.03 * (1 - 0.0)
                        secs = []
                        for t_i, p in enumerate(pts):
                            ww = w * (1 - 0.7 * t_i / 5)
                            dvec = V((-math.sin(ang), math.cos(ang), 0))
                            secs.append([p - dvec * ww, p + dvec * ww])
                        for s in range(5):
                            q = [alg.bm.verts.new(c) for c in (secs[s][0], secs[s][1], secs[s + 1][1], secs[s + 1][0])]
                            alg.bm.faces.new(q)
                else:
                    bar.cyl(V((px, py, pz)), V((px, py, pz + 0.012)), 0.010, 0.004, seg=7)
    # seabed shells / small pebbles & tufts
    for i in range(420):
        x = rng.uniform(-12, 12); y = rng.uniform(-10, 12)
        if abs(y) < 0.1: continue
        z = float(seabed_h(x, y))
        r = rng.uniform(0.012, 0.04)
        if rng.random() < 0.55:
            shl.sphere(V((x, y, z)), r, 8, (1, 1, 0.35))
        else:
            for b in range(4):
                ang = rng.random() * 6.28; hh = rng.uniform(0.08, 0.22)
                dvec = V((-math.sin(ang), math.cos(ang), 0)); ww = 0.012
                p0 = V((x, y, z)); p1 = p0 + V((math.cos(ang) * 0.05, math.sin(ang) * 0.05, hh))
                q = [alg.bm.verts.new(c) for c in (p0 - dvec * ww, p0 + dvec * ww, p1 + dvec * 0.002, p1 - dvec * 0.002)]
                alg.bm.faces.new(q)
    obs = []
    for nm, p in (("rocks", rockP), ("algae", alg), ("sponges", spo), ("shells", shl), ("barnacles", bar)):
        if p.bm.verts:
            p.bevel = 0.0
            ob = p.finalize(nm)
            if ob: obs.append(ob)
    return rocks, obs

def add_snow(M, n=1100, seed=9, box=((-7, 7), (-6, 6), (0.05, 3.2))):
    rng = random.Random(seed)
    p = Part(M["snow"], 0.0, uv=1.0); p.recalc = True
    for i in range(n):
        c = V((rng.uniform(*box[0]), rng.uniform(*box[1]), rng.uniform(*box[2])))
        p.sphere(c, rng.uniform(0.0015, 0.005), 5)
    return p.finalize("marine_snow")

def add_tether(M, start, direction, length=7.0, name="tether", seed=3):
    """Hose lying on the seabed with lazy S-curves; returns curve object."""
    rng = random.Random(seed)
    pts = []
    p = V(start); d = V(direction).normalized()
    n = 28
    for i in range(n):
        t = i / (n - 1)
        # drop from anchor to seabed then wander
        q = V(p) + d * (length * t) + V((-d.y, d.x, 0)) * (0.7 * math.sin(t * 5.0 + seed))
        zb = float(seabed_h(q.x, q.y)) + 0.026
        zq = zb + max(0.0, (start[2] - zb)) * max(0.0, 1 - t * 3.2) ** 2
        pts.append(V((q.x, q.y, zq)))
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    cu.bevel_depth = 0.024; cu.bevel_resolution = 3; cu.resolution_u = 4
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
    for bp, c in zip(sp.bezier_points, pts):
        bp.co = c; bp.handle_left_type = bp.handle_right_type = "AUTO"
    cu.materials.append(M["hose"])
    ob = bpy.data.objects.new(name, cu); bpy.context.scene.collection.objects.link(ob)
    return ob
