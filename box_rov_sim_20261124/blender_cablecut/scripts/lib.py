"""Shared helpers for ROV-01 cable-cut Blender scripts (run via blender -b -P).
Real-world scale in metres. X forward, Y left, Z up.
Own original design: ROV-01 work-class open frame, cyan/slate livery."""
import bpy, bmesh, math, os, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

ROOT = "/workspace/rov_sim/blender_cablecut"
TEXDIR = ROOT + "/textures"
os.makedirs(TEXDIR, exist_ok=True)
TS = 1024  # texture size

# ---------------------------------------------------------------- noise / textures
def fbm(n, beta=2.0, seed=0, aniso=(1.0, 1.0)):
    """Tileable fractal noise via spectral synthesis, 0..1."""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f * aniso[0], f * aniso[1], indexing="ij")
    r = np.sqrt(fx ** 2 + fy ** 2); r[0, 0] = 1.0
    spec = (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))) / r ** (beta / 2)
    spec[0, 0] = 0
    a = np.real(np.fft.ifft2(spec))
    a = (a - a.min()) / (a.max() - a.min() + 1e-9)
    return a

def smoothstep(a, lo, hi):
    t = np.clip((a - lo) / (hi - lo + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)

def height_to_normal(h, strength=2.0):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength * TS / 256
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength * TS / 256
    nz = np.ones_like(h)
    ln = np.sqrt(gx ** 2 + gy ** 2 + nz ** 2)
    return np.stack([-gx / ln * .5 + .5, gy / ln * .5 + .5, nz / ln * .5 + .5], -1)

def scratches(n, count, seed, length=0.15):
    rng = np.random.default_rng(seed)
    img = np.zeros((n, n))
    for _ in range(count):
        x, y = rng.random(2) * n
        ang = rng.random() * math.pi
        L = rng.random() * length * n + 8
        for t in np.linspace(0, L, int(L)):
            xi = int(x + math.cos(ang) * t) % n; yi = int(y + math.sin(ang) * t) % n
            img[yi, xi] = 0.4 + 0.6 * rng.random()
    return img

def _save_img(name, arr, colorspace="sRGB"):
    path = f"{TEXDIR}/{name}.png"
    h, w = arr.shape[:2]
    a = np.clip(arr, 0, 1).astype(np.float32)
    if a.ndim == 2: a = np.stack([a] * 3, -1)
    rgba = np.concatenate([a, np.ones((h, w, 1), np.float32)], -1)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path; img.file_format = "PNG"
    img.save()
    img.colorspace_settings.name = colorspace
    return path

_img_cache = {}
def load_img(path, colorspace):
    key = (path, colorspace)
    if key in _img_cache: return _img_cache[key]
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    img.pack() if False else None
    _img_cache[key] = img
    return img

def tex_set(name, base, rough, metal, grime=0.5, scratch=0.5, ns=3.0, bump=1.0, brushed=0.0,
            streak=0.3, seed=1, grime_col=(0.05, 0.045, 0.035), pattern=None, rough_var=0.15):
    """Generate (albedo, orm, normal) PNGs once, return paths."""
    pa, po, pn = (f"{TEXDIR}/{name}_{k}.png" for k in ("alb", "orm", "nrm"))
    if os.path.exists(pn) and os.path.exists(pa) and os.path.exists(po):
        return pa, po, pn
    base = np.array(base[:3])
    n1 = fbm(TS, 2.6, seed); n2 = fbm(TS, 1.6, seed + 7)
    fine = fbm(TS, 0.8, seed + 3)
    streaks = fbm(TS, 2.0, seed + 11, aniso=(1.0, 0.04))
    sc = scratches(TS, 160, seed) * scratch
    gmask = smoothstep(n1 * .6 + n2 * .4 + streaks * streak * .6, 1.0 - grime * .62, 1.0 - grime * .62 + .35) * min(1, grime * 1.6)
    h = fine * 0.35 + n2 * 0.2 + sc * 0.5
    br = 0
    if brushed > 0:
        br = fbm(TS, 1.2, seed + 5, aniso=(1.0, 0.03)); h = h + br * brushed * 0.6
    if pattern is not None:
        pat = pattern(TS, seed); h = h * 0.4 + pat
    col = base[None, None, :] * (0.88 + 0.24 * n2[..., None] + 0.08 * (fine[..., None] - .5))
    if brushed > 0: col = col * (0.93 + 0.14 * br[..., None])
    col = col * (1 - gmask[..., None]) + np.array(grime_col)[None, None, :] * gmask[..., None] * (0.6 + .8 * n1[..., None])
    col = col + sc[..., None] * 0.25 * (1 - gmask[..., None])
    r = np.clip(rough + (n2 - .5) * rough_var * 2 + gmask * .35 - sc * .25, 0.03, 1.0)
    m = np.clip(metal * (1 - gmask * 0.65) + sc * 0.2 * metal, 0, 1) if metal > 0 else np.zeros_like(r)
    orm = np.stack([np.ones_like(r), r, m], -1)  # R=occlusion, G=rough, B=metal (glTF)
    nrm = height_to_normal(h, bump * 2.2)
    _save_img(name + "_alb", col, "sRGB"); _save_img(name + "_orm", orm, "Non-Color"); _save_img(name + "_nrm", nrm, "Non-Color")
    return pa, po, pn

def make_pbr(name, base=(0.5, 0.5, 0.5), rough=0.5, metal=0.0, uvscale=1.0, emission=None, emit_strength=0,
             grime=0.4, scratch=0.4, bump=1.0, brushed=0.0, seed=None, pattern=None, streak=0.3,
             alpha=None, grime_col=(0.05, 0.045, 0.035), ior=1.45, transmission=0.0, flat=False, rough_var=0.15):
    if name in bpy.data.materials: return bpy.data.materials[name]
    seed = seed if seed is not None else (sum(map(ord, name)) % 1000)
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    mat.use_backface_culling = False
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (800, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (500, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    if flat:
        bsdf.inputs["Base Color"].default_value = (*base[:3], 1)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
    else:
        pa, po, pn = tex_set(name, base, rough, metal, grime, scratch, bump=bump, brushed=brushed, seed=seed,
                              pattern=pattern, streak=streak, grime_col=grime_col, rough_var=rough_var)
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (uvscale, uvscale, uvscale)
        nt.links.new(tc.outputs["UV"], mp.inputs[0])
        def img(path, cs, y):
            t = nt.nodes.new("ShaderNodeTexImage"); t.location = (-100, y)
            t.image = load_img(path, cs); t.interpolation = "Smart"; t.extension = "REPEAT"
            nt.links.new(mp.outputs[0], t.inputs[0]); return t
        ta = img(pa, "sRGB", 300); to = img(po, "Non-Color", 0); tn = img(pn, "Non-Color", -300)
        nt.links.new(ta.outputs[0], bsdf.inputs["Base Color"])
        sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(to.outputs[0], sep.inputs[0])
        nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"]); nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 1.0
        nt.links.new(tn.outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1); bsdf.inputs["Emission Strength"].default_value = emit_strength
    if transmission:
        bsdf.inputs["Transmission Weight"].default_value = transmission
        bsdf.inputs["IOR"].default_value = ior
    if alpha is not None:
        bsdf.inputs["Alpha"].default_value = alpha; mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
    return mat

# ------------------------------------------------------------------- mesh builder
def _orient(a, b):
    d = (Vector(b) - Vector(a))
    L = d.length
    q = d.to_track_quat("Z", "Y") if L > 1e-9 else Quaternion()
    return q.to_matrix().to_4x4(), L

class Part:
    """Accumulates primitives of ONE material in a bmesh."""
    def __init__(self, mat, bevel=0.003, uv=1.0, smooth_deg=48, seg_bevel=2):
        self.mat = mat; self.bm = bmesh.new(); self.bevel = bevel; self.uvs = uv
        self.smooth = smooth_deg; self.seg = seg_bevel; self.n = 0; self.base = Matrix.Identity(4)

    def _add(self, M, res):
        bm = self.bm
        verts = [v for v in res["verts"]]
        bmesh.ops.transform(bm, matrix=self.base @ M, verts=verts)
        self.n += 1

    def box(self, center, size, rot=None):
        M = Matrix.Translation(center)
        if rot is not None: M = M @ Euler(rot).to_matrix().to_4x4()
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=Matrix.Diagonal((*size, 1)))
        self._add(M, r); return self

    def cyl(self, a, b, r0, r1=None, seg=24, caps=True):
        r1 = r0 if r1 is None else r1
        M, L = _orient(a, b)
        M = Matrix.Translation(a) @ M
        r = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=L,
                                  matrix=Matrix.Translation((0, 0, L / 2)))
        self._add(M, r); return self

    def sphere(self, c, rad, seg=16, scale=(1, 1, 1)):
        r = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=max(6, seg // 2), radius=rad,
                                      matrix=Matrix.Diagonal((*scale, 1)))
        self._add(Matrix.Translation(c), r); return self

    def torus(self, c, axis, R, r, seg=32, seg2=10):
        verts = []
        bm = self.bm
        ring = []
        for i in range(seg):
            t = 2 * math.pi * i / seg
            row = []
            for j in range(seg2):
                p = 2 * math.pi * j / seg2
                x = (R + r * math.cos(p)) * math.cos(t); y = (R + r * math.cos(p)) * math.sin(t); z = r * math.sin(p)
                row.append(bm.verts.new((x, y, z)))
            ring.append(row)
        for i in range(seg):
            for j in range(seg2):
                a = ring[i][j]; b = ring[(i + 1) % seg][j]; c2 = ring[(i + 1) % seg][(j + 1) % seg2]; d = ring[i][(j + 1) % seg2]
                bm.faces.new((a, b, c2, d))
        vs = [v for row in ring for v in row]
        M, _ = _orient((0, 0, 0), axis)
        bmesh.ops.transform(bm, matrix=self.base @ Matrix.Translation(c) @ M, verts=vs); self.n += 1
        return self

    def lathe(self, profile, a, b, seg=32, close=False, loop=False):
        """profile: list of (t along a->b in 0..1, radius). Revolve around axis a->b."""
        bm = self.bm; M, L = _orient(a, b)
        rows = []
        for t, rad in profile:
            row = [bm.verts.new((rad * math.cos(2 * math.pi * i / seg), rad * math.sin(2 * math.pi * i / seg), t * L)) for i in range(seg)]
            rows.append(row)
        for k in range(len(rows) - 1):
            for i in range(seg):
                bm.faces.new((rows[k][i], rows[k][(i + 1) % seg], rows[k + 1][(i + 1) % seg], rows[k + 1][i]))
        if loop:
            for i in range(seg):
                bm.faces.new((rows[-1][i], rows[-1][(i + 1) % seg], rows[0][(i + 1) % seg], rows[0][i]))
        if close:
            for row, flip in ((rows[0], True), (rows[-1], False)):
                if row[0].co.xy.length > 1e-6:
                    f = bm.faces.new(row[::-1] if flip else row)
        vs = [v for row in rows for v in row]
        bmesh.ops.transform(bm, matrix=self.base @ Matrix.Translation(a) @ M, verts=vs); self.n += 1
        return self

    def tube(self, a, b, r, seg=12):
        return self.cyl(a, b, r, r, seg)

    def poly_prism(self, pts2d, z0, z1, mat4=None):
        """Extrude a 2D polygon (x,y) between z0..z1 (concave ok via triangulate fill)."""
        bm = self.bm
        v0 = [bm.verts.new((x, y, z0)) for x, y in pts2d]; v1 = [bm.verts.new((x, y, z1)) for x, y in pts2d]
        n = len(pts2d)
        for i in range(n):
            bm.faces.new((v0[i], v0[(i + 1) % n], v1[(i + 1) % n], v1[i]))
        f0 = bm.faces.new(v0[::-1]); f1 = bm.faces.new(v1)
        bmesh.ops.triangulate(bm, faces=[f0, f1], quad_method="BEAUTY", ngon_method="EAR_CLIP")
        bmesh.ops.transform(bm, matrix=self.base @ (mat4 if mat4 is not None else Matrix.Identity(4)), verts=v0 + v1)
        self.n += 1; return self

    def loft(self, sections, mat4=None, caps=True):
        """sections: list of closed loops (lists of 3D points), same length each."""
        bm = self.bm; rows = [[bm.verts.new(p) for p in sec] for sec in sections]
        n = len(rows[0])
        for k in range(len(rows) - 1):
            for i in range(n):
                bm.faces.new((rows[k][i], rows[k][(i + 1) % n], rows[k + 1][(i + 1) % n], rows[k + 1][i]))
        if caps:
            bm.faces.new(rows[0][::-1]); bm.faces.new(rows[-1])
        vs = [v for r in rows for v in r]
        bmesh.ops.transform(bm, matrix=self.base @ (mat4 if mat4 is not None else Matrix.Identity(4)), verts=vs)
        self.n += 1; return self

    def hexbolt(self, c, normal, r=0.008, h=0.006):
        n = Vector(normal).normalized()
        return self.cyl(Vector(c), Vector(c) + n * h, r, r * 0.95, seg=6)

    # ------------------------------------------------------------------
    def finalize(self, name, parent=None, collection=None, location=(0, 0, 0)):
        bm = self.bm
        if not bm.verts:
            bm.free(); return None
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        if getattr(self, 'recalc', True): bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if self.bevel and self.bevel > 0:
            edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(35)]
            if edges:
                try:
                    bmesh.ops.bevel(bm, geom=edges, offset=self.bevel, segments=self.seg, profile=0.6, affect="EDGES",
                                    clamp_overlap=True, loop_slide=True)
                except Exception as ex:
                    print("bevel failed", name, ex)
        for f in bm.faces: f.smooth = True
        lim = math.radians(self.smooth)
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0) > lim: e.smooth = False
            elif len(e.link_faces) == 1: e.smooth = False
        # box-projected UVs, uvs = tiles per metre
        uvl = bm.loops.layers.uv.verify()
        for f in bm.faces:
            n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
            for l in f.loops:
                p = l.vert.co
                if ax == 0: uv = (p.y, p.z)
                elif ax == 1: uv = (p.x, p.z)
                else: uv = (p.x, p.y)
                l[uvl].uv = (uv[0] * self.uvs, uv[1] * self.uvs)
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        me.materials.append(self.mat)
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        ob.location = location
        if parent is not None: ob.parent = parent
        return ob

class Group:
    """Per-assembly collection of Parts keyed by material name."""
    def __init__(self, name, collection=None, parent=None):
        self.name = name; self.parts = {}; self.col = collection; self.parent = parent; self.M = Matrix.Identity(4)
    def part(self, mat, bevel=0.003, uv=1.0, recalc=True, **kw):
        key = (mat.name, bevel, uv, recalc)
        if key not in self.parts: self.parts[key] = Part(mat, bevel, uv, **kw); self.parts[key].recalc = recalc
        self.parts[key].base = self.M
        return self.parts[key]
    def finalize(self, location=(0, 0, 0)):
        obs = []
        for (mn, b, u, rc), p in self.parts.items():
            ob = p.finalize(f"{self.name}__{mn}", self.parent, self.col, location)
            if ob: obs.append(ob)
        return obs

def empty(name, loc=(0, 0, 0), parent=None, rot=(0, 0, 0), collection=None, size=0.05, display="PLAIN_AXES"):
    e = bpy.data.objects.new(name, None); e.empty_display_type = display; e.empty_display_size = size
    (collection or bpy.context.scene.collection).objects.link(e)
    e.location = loc; e.rotation_euler = rot
    if parent is not None: e.parent = parent
    return e

def text_decal(txt, loc, rot, size, mat, parent=None, extrude=0.0008, name="decal", collection=None):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = txt; cu.size = size; cu.extrude = extrude
    cu.align_x = "CENTER"; cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc; ob.rotation_euler = rot
    ob.data.materials.append(mat)
    if parent is not None: ob.parent = parent
    return ob

def clear_scene():
    _img_cache.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)
V = Vector
