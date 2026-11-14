"""Build the ROV support work boat (original design) and export it as a GLB.

    python cad/build_support_vessel.py OUT.glb [--textures DIR]      # needs `pip install bpy` (or Blender's Python)

An 11.6 m welded-aluminium survey / dive-support workboat of the kind used to run observation-class ROVs from
the stern: hard-chine hull with flared bow, forward wheelhouse, open aft working deck with a stern A-frame,
a powered tether winch, a deck control cabinet, a shade canopy over the pilot table, rails, bitts, fenders,
tyres, boarding ladder, navigation lights and a mast with antennas. Below the waterline: antifouling, skeg,
twin shafts with P-brackets, propellers, rudders, anodes and a transducer fairing, since the ROV sees the
hull from below during launch and recovery. Registration lettering is a generic placeholder.

Units are metres. Boat coordinates used below: x to port, s forward from the transom, z up from the design
waterline. Blender (Z up) gets (x, L/2 - s, z); after the glTF Y-up conversion three.js sees the stern at
-Z, the bow at +Z, port at +X and the waterline at y = 0. The root node carries extras (deckY, sternZ,
transomY, ...) that simulator/viewer/deploy_intro.js reads; the node "TetherDrum" spins about its local X.
The A-frame, its rams, the sheave block and the lifting hook are separate nodes so the launch intro can luff
the frame and lower the vehicle on the lifting wire (see build_a_frame). Detail levels: "LOD0" (full), "LOD1"
and "LOD2" (decimated copies, switch distances in the root extras "lodDistances"), plus a hidden closed
"CollisionProxy" mesh (extras proxy = "collision") for collision and occlusion queries.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy  # noqa: I001  (bpy must be imported before bmesh/mathutils)
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import support_assets_lib as kit  # noqa: E402

L = 11.6
GMAX = 3.6
DECK_Z = 0.45
NB = 10
NT = 12
STATIONS = 96
SEAMS_S = (1.25, 3.65, 6.05, 8.45, 10.35)
SCUPPERS_S = (0.75, 1.95, 3.15, 4.35)
REGISTRATION = 'SV-1142'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


# ───────────────────────────── hull shape ─────────────────────────────


def half_beam(t):
    """Half beam at the sheer."""
    if t <= 0.5:
        return 1.86 + 0.09 * math.sin(math.pi * t)
    u = (t - 0.5) / 0.5
    return 1.95 * max(0.0, 1.0 - u ** 2.3) ** 0.55


def sheer_z(t):
    return 1.02 + 0.55 * t ** 2.4


def keel_z(t):
    z = -0.56 - 0.06 * math.sin(math.pi * min(t / 0.7, 1.0))
    if t > 0.6:
        z += 2.2 * ((t - 0.6) / 0.4) ** 2.1
    return min(z, sheer_z(t))


def deck_z(t):
    return DECK_Z + 0.5 * float(kit.smoothstep(0.7, 0.95, t))


def section(t):
    """Half section from keel (x = 0) to sheer: NB+1 bottom points, chine flat, NT topside points."""
    b = half_beam(t)
    zs = sheer_z(t)
    zk = keel_z(t)
    xc = b * (0.9 - 0.12 * t * t)
    zc = -0.06 + 0.7 * float(kit.smoothstep(0.35, 1.0, t)) ** 1.4
    zc = min(max(zc, zk), zs)
    pts = []
    for i in range(NB + 1):
        u = i / NB
        pts.append((xc * u, zk + (zc - zk) * u - 0.035 * math.sin(math.pi * u) * (1.0 - t)))
    xf = xc + 0.045 * (1.0 - t)
    pts.append((xf, zc))
    for i in range(1, NT + 1):
        u = i / NT
        pts.append((xf + (b - xf) * u + 0.025 * math.sin(math.pi * u) * (1.0 - t), zc + (zs - zc) * u))
    return pts


def girth(pts):
    g = [0.0]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        g.append(g[-1] + math.hypot(x1 - x0, z1 - z0))
    return g


def station_ts():
    return [1.0 - (1.0 - i / STATIONS) ** 1.25 for i in range(STATIONS + 1)]


def hull_x_at(t, z):
    """Outer hull half-width at height z on the topside/bottom (first crossing from the keel)."""
    pts = section(t)
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if (z0 - z) * (z1 - z) <= 0 and z1 != z0:
            return x0 + (x1 - x0) * (z - z0) / (z1 - z0)
    return pts[-1][0]


def B(x, s, z):
    """Boat coordinates -> Blender coordinates."""
    return Vector((x, L / 2 - s, z))


# ───────────────────────────── textures ─────────────────────────────


def paint_bands(z, zs, noise, fine):
    """Shared colour logic for hull and transom: antifouling, slime, boot top, topside paint, scum line."""
    af = np.array([0.50, 0.16, 0.11])
    slime = np.array([0.20, 0.22, 0.13])
    boot = np.array([0.065, 0.08, 0.11])
    top = np.array([0.80, 0.815, 0.82])
    scum = np.array([0.36, 0.31, 0.21])
    w_af = 1.0 - kit.smoothstep(0.05, 0.065, z)
    w_boot = kit.smoothstep(0.05, 0.065, z) * (1.0 - kit.smoothstep(0.205, 0.22, z))
    w_top = kit.smoothstep(0.205, 0.22, z)
    col = (w_af[..., None] * af * (1.0 + 0.14 * noise[..., None])
           + w_boot[..., None] * boot * (1.0 + 0.1 * fine[..., None])
           + w_top[..., None] * top * (1.0 - 0.035 * noise[..., None]))
    w_slime = kit.smoothstep(-0.45, 0.02, z) * (1.0 - kit.smoothstep(0.03, 0.07, z))
    w_slime = w_slime * np.clip(0.55 + 0.6 * noise, 0.0, 1.0) * 0.75
    col = col * (1.0 - w_slime[..., None]) + slime * w_slime[..., None]
    w_scum = np.exp(-((z - 0.08) / 0.045) ** 2) * np.clip(0.5 + 0.7 * fine, 0.0, 1.0) * 0.45
    col = col * (1.0 - w_scum[..., None]) + scum * w_scum[..., None]
    rough = (w_af * (0.86 + 0.05 * noise) + w_boot * 0.4 + w_top * (0.36 + 0.08 * noise))
    rough = np.clip(rough * (1.0 - w_slime) + 0.55 * w_slime + 0.25 * w_scum, 0.05, 1.0)
    return col, rough


def hull_textures(out):
    """2048x1024 hull maps; u = s / L, v = girth / GMAX (both sides share the map)."""
    w, h = 2048, 1024
    s = (np.arange(w) + 0.5) / w * L
    g = (1.0 - (np.arange(h) + 0.5) / h) * GMAX
    z = np.empty((h, w))
    zs = np.empty(w)
    for c in range(w):
        t = s[c] / L
        pts = section(t)
        gg = girth(pts)
        z[:, c] = np.interp(g, gg, [p[1] for p in pts], right=pts[-1][1] + 0.5)
        zs[c] = pts[-1][1]
    zs2 = np.broadcast_to(zs, (h, w))
    s2 = np.broadcast_to(s, (h, w))
    noise = kit.spectral_noise((h, w), 2.3, 11, fmin=3)
    fine = kit.spectral_noise((h, w), 1.2, 12, fmin=40)
    col, rough = paint_bands(z, zs2, noise, fine)
    height = np.zeros((h, w))
    topside = kit.smoothstep(0.1, 0.25, z) * (z < zs2 - 0.01)
    # frames every 0.5 m: slight dishing of the plating between them (shows in grazing light)
    height -= topside * 0.0012 * (0.5 - 0.5 * np.cos(2 * np.pi * s2 / 0.5))
    # welded plate butts and a longitudinal seam on the topside
    for seam in SEAMS_S:
        d = np.abs(s2 - seam)
        height += 0.0012 * np.exp(-(d / 0.008) ** 2)
        col *= (1.0 - 0.12 * np.exp(-(d / 0.008) ** 2))[..., None]
    d = np.abs(z - 0.62)
    height += 0.0012 * np.exp(-(d / 0.008) ** 2) * (z < zs2 - 0.05)
    col *= (1.0 - 0.1 * np.exp(-(d / 0.006) ** 2) * (z < zs2 - 0.05))[..., None]
    # freeing ports at deck level with rust-brown runs below them
    streak_noise = kit.spectral_noise((h, w), 1.4, 13, fmin=3, fy_max=3)
    for sc in SCUPPERS_S:
        port = (np.abs(s2 - sc) < 0.16) & (z > DECK_Z + 0.01) & (z < DECK_Z + 0.1)
        col[port] = (0.05, 0.05, 0.05)
        height[port] -= 0.004
        run = np.exp(-((s2 - sc) / (0.07 + 0.03 * streak_noise)) ** 2) * (z < DECK_Z) * (z > 0.2)
        run = run * kit.smoothstep(0.15, DECK_Z, z) * 0.55
        col = col * (1.0 - run[..., None]) + np.array([0.42, 0.29, 0.18]) * run[..., None]
        rough = rough + 0.2 * run
    # general dirt runs and fender scuffs on the topside
    dirt = kit.smoothstep(0.35, 0.95, streak_noise) * topside * 0.18
    col *= (1.0 - dirt)[..., None]
    scuff_noise = kit.spectral_noise((w, h), 1.2, 14, fmin=6, fy_max=2).T
    scuff = kit.smoothstep(0.55, 0.85, scuff_noise) * kit.smoothstep(0.4, 0.75, z) * topside * 0.45
    col *= (1.0 - scuff)[..., None]
    # exhaust outlets near the stern with soot
    for ex_s, ex_z in ((0.55, 0.3),):
        r = np.hypot((s2 - ex_s) / 1.0, z - ex_z)
        col[r < 0.06] = (0.03, 0.03, 0.03)
        height[r < 0.06] -= 0.01
        soot = np.exp(-((s2 - ex_s + 0.35) / 0.5) ** 2) * np.exp(-((z - ex_z - 0.05) / 0.12) ** 2) * 0.5
        col *= (1.0 - soot)[..., None]
    # draft marks at stern and bow
    for mark_s in (0.3, 10.5):
        for k in range(0, 9):
            zz = -0.5 + k * 0.1
            mark = (np.abs(s2 - mark_s) < 0.05) & (np.abs(z - zz) < 0.012)
            col[mark] = (0.9, 0.9, 0.88)
    occlusion = 1.0 - 0.25 * kit.smoothstep(zs2 - 0.16, zs2 - 0.06, z) * (z < zs2 - 0.03)
    col *= occlusion[..., None]
    height += fine * 0.0002
    normal = kit.normal_from_height(height / 0.0045, 2.5)
    rough = np.clip(rough, 0.05, 1.0)
    return {
        'base': kit.save_image(Path(out) / 'hull_base.png', col),
        'normal': kit.save_image(Path(out) / 'hull_normal.png', normal),
        'orm': kit.save_image(Path(out) / 'hull_orm.png', kit.orm(rough, np.zeros_like(rough))),
    }


TRANSOM_X = (-2.0, 2.0)
TRANSOM_Z = (-0.75, 1.25)


def transom_textures(out):
    """1024x512 transom maps (u along x, v along z), with the registration painted on."""
    w, h = 1024, 512
    x = np.linspace(TRANSOM_X[0], TRANSOM_X[1], w)
    z = np.linspace(TRANSOM_Z[1], TRANSOM_Z[0], h)
    x2, z2 = np.meshgrid(x, z)
    noise = kit.spectral_noise((h, w), 2.3, 21, fmin=3)
    fine = kit.spectral_noise((h, w), 1.2, 22, fmin=40)
    col, rough = paint_bands(z2, np.full_like(z2, sheer_z(0)), noise, fine)
    height = np.zeros((h, w))
    for seam in (-0.62, 0.62):
        d = np.abs(x2 - seam)
        height += 0.0009 * np.exp(-(d / 0.004) ** 2)
        col *= (1.0 - 0.12 * np.exp(-(d / 0.006) ** 2))[..., None]
    streak = kit.spectral_noise((h, w), 1.4, 23, fmin=3, fy_max=3)
    col *= (1.0 - kit.smoothstep(0.4, 0.95, streak) * 0.2 * (z2 > 0.25))[..., None]
    image = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 58)
    text_w = draw.textlength(REGISTRATION, font=font)
    row = int((TRANSOM_Z[1] - 0.78) / (TRANSOM_Z[1] - TRANSOM_Z[0]) * h)
    draw.text(((w - text_w) / 2, row - 29), REGISTRATION, font=font, fill=(26, 30, 36))
    col = np.asarray(image).astype(float) / 255.0
    normal = kit.normal_from_height(height / 0.004, 1.0)
    return {
        'base': kit.save_image(Path(out) / 'transom_base.png', col),
        'normal': kit.save_image(Path(out) / 'transom_normal.png', normal),
        'orm': kit.save_image(Path(out) / 'transom_orm.png', kit.orm(np.clip(rough, 0.05, 1), np.zeros_like(rough))),
    }


def registration_decal(out):
    """Black registration letters on transparent, 1024x256."""
    image = Image.new('RGBA', (1024, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 190)
    text_w = draw.textlength(REGISTRATION, font=font)
    draw.text(((1024 - text_w) / 2, 20), REGISTRATION, font=font, fill=(24, 28, 34, 255))
    path = Path(out) / 'registration.png'
    image.save(path)
    return {'base': path}


def deck_textures(out):
    """Non-slip painted aluminium deck, tile 1.2 m: grit, wear to bare metal, dirt."""
    size = 1024
    grit = kit.spectral_noise((size, size), 0.2, 31, fmin=200)
    wear_field = kit.spectral_noise((size, size), 2.4, 32, fmin=2)
    dirt = kit.spectral_noise((size, size), 2.0, 33, fmin=2)
    wear = kit.smoothstep(0.35, 0.6, wear_field)
    paint = np.array([0.40, 0.45, 0.44])
    metal = np.array([0.62, 0.63, 0.63])
    col = paint * (1.0 + 0.05 * grit[..., None]) * (1.0 - wear[..., None]) + metal * wear[..., None]
    col *= (1.0 - 0.18 * kit.smoothstep(0.1, 0.8, dirt))[..., None]
    rough = np.clip(0.82 + 0.08 * grit - 0.3 * wear, 0.2, 1.0)
    metalness = wear * 0.3
    height = grit * (1.0 - wear) * 0.6 - wear * 0.4
    return {
        'base': kit.save_image(Path(out) / 'deck_base.png', col),
        'normal': kit.save_image(Path(out) / 'deck_normal.png', kit.normal_from_height(height, 1.4)),
        'orm': kit.save_image(Path(out) / 'deck_orm.png', kit.orm(rough, metalness)),
    }


def screen_texture(out):
    """Emissive image for the pilot table monitor: camera view with a simple telemetry strip."""
    w, h = 512, 320
    y = np.linspace(0, 1, h)[:, None, None]
    img = np.array([0.05, 0.32, 0.38]) * (1.0 - y) + np.array([0.01, 0.08, 0.1]) * y
    img = np.broadcast_to(img, (h, w, 3)).copy()
    img[:22] = (0.02, 0.03, 0.04)
    img[-26:] = (0.02, 0.03, 0.04)
    image = Image.fromarray((img * 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 15)
    draw.text((8, 3), 'DEPTH 12.4 m   HDG 214   TETHER 38 m', font=font, fill=(150, 225, 240))
    draw.text((8, h - 22), 'REC 00:14:37', font=font, fill=(240, 90, 90))
    draw.line((w / 2 - 20, h / 2, w / 2 + 20, h / 2), fill=(240, 200, 90), width=2)
    draw.line((w / 2, h / 2 - 20, w / 2, h / 2 + 20), fill=(240, 200, 90), width=2)
    path = Path(out) / 'screen.png'
    image.save(path)
    return {'base': path}


# ───────────────────────────── materials ─────────────────────────────


def build_materials(tex):
    paint = tex['paint']
    metal = tex['metal']
    m = {}
    m['hull'] = kit.make_material('HullPaint', (1, 1, 1), textures=tex['hull'])
    m['transom'] = kit.make_material('TransomPaint', (1, 1, 1), textures=tex['transom'])
    m['decal'] = kit.make_material('Registration', (1, 1, 1), rough=0.4, textures=tex['decal'], alpha_clip=True)
    m['deck'] = kit.make_material('DeckNonSlip', (1, 1, 1), textures=tex['deck'])
    m['bulwark'] = kit.make_material('BulwarkPaint', (0.74, 0.76, 0.77), textures=paint)
    m['white'] = kit.make_material('SuperstructurePaint', (0.9, 0.91, 0.9), textures=paint)
    m['grey'] = kit.make_material('EquipmentGrey', (0.24, 0.27, 0.3), textures=paint)
    m['yellow'] = kit.make_material('EquipmentYellow', (0.93, 0.66, 0.08), textures=paint)
    m['orange'] = kit.make_material('SafetyOrange', (0.95, 0.33, 0.07), textures=paint)
    m['antifoul'] = kit.make_material('AntifoulingWorn', (0.36, 0.13, 0.1), textures=paint)
    m['alu'] = kit.make_material('Aluminium', (0.82, 0.83, 0.84), textures=metal)
    m['steel'] = kit.make_material('Stainless', (0.7, 0.71, 0.72), textures=metal)
    m['rubber'] = kit.make_material('Rubber', (0.035, 0.035, 0.037), rough=0.85)
    m['tyre'] = kit.make_material('TyreRubber', (0.05, 0.05, 0.05), rough=0.93)
    m['glass'] = kit.make_material('WindowGlass', (0.05, 0.07, 0.08), rough=0.04, metal=0.2)
    m['bronze'] = kit.make_material('PropBronze', (0.72, 0.5, 0.3), rough=0.35, metal=0.5)
    m['zinc'] = kit.make_material('ZincAnode', (0.62, 0.64, 0.64), rough=0.7, metal=0.3)
    m['tether'] = kit.make_material('TetherYellow', (0.92, 0.74, 0.12), rough=0.5)
    m['rope'] = kit.make_material('RopeBlue', (0.12, 0.22, 0.42), rough=0.9)
    m['fender'] = kit.make_material('FenderBlue', (0.08, 0.2, 0.42), rough=0.45)
    m['canvas'] = kit.make_material('CanopyFabric', (0.17, 0.22, 0.3), textures=tex['fabric'], double_sided=True)
    m['tape'] = kit.make_material('ReflectiveTape', (0.85, 0.87, 0.88), rough=0.3, metal=0.3)
    m['lamp_red'] = kit.make_material('NavLightRed', (0.6, 0.02, 0.02), rough=0.2, emission=(1, 0.05, 0.03),
                                      emission_strength=2.0)
    m['lamp_green'] = kit.make_material('NavLightGreen', (0.02, 0.5, 0.15), rough=0.2, emission=(0.05, 1, 0.35),
                                        emission_strength=2.0)
    m['lamp_white'] = kit.make_material('NavLightWhite', (0.9, 0.9, 0.85), rough=0.2, emission=(1, 0.97, 0.88),
                                        emission_strength=1.5)
    m['screen'] = kit.make_material('PilotScreen', (0.05, 0.05, 0.05), rough=0.15, textures=tex['screen'],
                                    emissive_map=True)
    m['dark'] = kit.make_material('DarkPlastic', (0.06, 0.065, 0.07), rough=0.55)
    m['lamp_status'] = kit.make_material('StatusLamp', (0.1, 0.6, 0.2), emission=(0.1, 1, 0.3), emission_strength=2)
    return m


class Parts:
    """One Part (mesh accumulator) per material key."""

    def __init__(self, materials, prefix):
        self.materials = materials
        self.prefix = prefix
        self.parts = {}

    def add(self, key, bm, tile=1.0):
        part = self.parts.get(key)
        if part is None:
            part = kit.Part(f'{self.prefix}_{key}', self.materials[key], uv_tile=tile)
            self.parts[key] = part
        part.add_bmesh(bm)

    def build(self, collection, parent):
        return [p.obj(collection, parent) for p in self.parts.values()]


# ───────────────────────────── hull ─────────────────────────────


def build_hull(parts):
    ts = station_ts()
    rows = []
    uv_rows = []
    for t in ts:
        half = section(t)
        g = girth(half)
        full = [(-x, z) for x, z in reversed(half[1:])] + half
        gfull = list(reversed(g[1:])) + g
        rows.append([B(x, t * L, z) for x, z in full])
        uv_rows.append([(t, gg / GMAX) for gg in gfull])
    bm = kit.grid_surface(rows, uv_rows, flip=False)
    bm.normal_update()
    probe = max(bm.faces, key=lambda f: f.calc_center_median().x)
    if probe.normal.x < 0:
        for f in bm.faces:
            f.normal_flip()
    parts.add('hull', bm)
    build_transom(parts)
    build_bulwarks_and_deck(parts)
    build_rub_rail(parts)
    build_spray_rails(parts)
    build_hull_decals(parts)


def build_transom(parts):
    half = section(0.0)
    full = [(-x, z) for x, z in reversed(half[1:])] + half
    bm = bmesh.new()
    layer = bm.loops.layers.uv.new('UVMap')
    verts = [bm.verts.new(B(x, 0.0, z)) for x, z in full]
    face = bm.faces.new(verts)
    face.normal_update()
    if face.normal.y < 0:
        face.normal_flip()
    for loop in face.loops:
        co = loop.vert.co
        u = (TRANSOM_X[1] - co.x) / (TRANSOM_X[1] - TRANSOM_X[0])          # seen from astern, port is left
        v = (co.z - TRANSOM_Z[0]) / (TRANSOM_Z[1] - TRANSOM_Z[0])
        loop[layer].uv = (u, v)
    bmesh.ops.triangulate(bm, faces=[face])
    parts.add('transom', bm)
    # inner face of the transom bulwark and its cap
    zs = sheer_z(0.0)
    xin = hull_x_at(0.0, DECK_Z) - 0.04
    xtop = half[-1][0] - 0.04
    inner = [[B(-xin, 0.05, DECK_Z), B(xin, 0.05, DECK_Z)], [B(-xtop, 0.05, zs), B(xtop, 0.05, zs)],
             [B(-xtop - 0.04, 0.0, zs), B(xtop + 0.04, 0.0, zs)]]
    parts.add('bulwark', kit.grid_surface(inner, flip=True), tile=1.5)


def inner_wall(t):
    """Inner bulwark points from deck to sheer (port side, x > 0), following the hull 40 mm inboard."""
    dz = deck_z(t)
    half = section(t)
    zs = half[-1][1]
    x_deck = hull_x_at(t, dz) - 0.04
    pts = [(max(x_deck, 0.0), dz)]
    for x, z in half:
        if dz + 0.02 < z < zs - 0.01:
            pts.append((max(x - 0.04, 0.0), z))
    pts.append((max(half[-1][0] - 0.04, 0.0), zs))
    pts.append((half[-1][0], zs))
    return pts


def build_bulwarks_and_deck(parts):
    ts = [t for t in station_ts() if t <= 0.93]
    ts = [0.0035] + ts[1:]
    n_wall = 6
    for side in (1, -1):
        rows = []
        for t in ts:
            pts = inner_wall(t)
            lower = pts[:-2]
            idx = np.linspace(0, len(lower) - 1, n_wall).round().astype(int)
            sel = [lower[i] for i in idx] + pts[-2:]
            rows.append([B(side * x, t * L, z) for x, z in sel])
        parts.add('bulwark', kit.grid_surface(rows, flip=(side > 0)), tile=1.5)
    # forepeak bulkhead closing the inner walls at the forward end of the deck
    t_end = ts[-1]
    pts = inner_wall(t_end)
    bm = bmesh.new()
    ring = [B(x, t_end * L, z) for x, z in pts[:-1]] + [B(-x, t_end * L, z) for x, z in reversed(pts[:-1])]
    face = bm.faces.new([bm.verts.new(p) for p in ring])
    face.normal_update()
    if face.normal.y > 0:
        face.normal_flip()
    parts.add('bulwark', bm, tile=1.5)
    # deck
    rows = []
    for t in ts:
        dz = deck_z(t)
        x = inner_wall(t)[0][0]
        rows.append([B(x * (1 - 2 * k / 8), t * L, dz) for k in range(9)])
    parts.add('deck', kit.grid_surface(rows, flip=False), tile=1.2)


def build_rub_rail(parts):
    """Rubber D-fender along both sheers and across the transom, bow to bow."""
    ts = [t for t in station_ts() if t < 0.985]
    port = [B(half_beam(t) + 0.03, t * L, sheer_z(t) - 0.06) for t in ts]
    stbd = [Vector((-p.x, p.y, p.z)) for p in port]
    b0 = half_beam(0.0)
    z0 = sheer_z(0.0) - 0.06
    across = [B(b0 - 0.04, -0.035, z0)]
    across += [B(x, -0.05, z0) for x in np.linspace(b0 - 0.2, -(b0 - 0.2), 8)]
    across += [B(-(b0 - 0.04), -0.035, z0)]
    path = list(reversed(port)) + across + stbd
    profile = [(0.055 * math.cos(a), 0.055 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
    parts.add('rubber', kit.sweep(path, profile=profile), tile=0.5)


def build_spray_rails(parts):
    for side in (1, -1):
        for frac in (0.45, 0.75):
            pts = []
            for t in np.linspace(0.18, 0.82, 30):
                half = section(t)
                i = int(frac * NB)
                x, z = half[i]
                pts.append(B(side * x, t * L, z - 0.012))
            profile = [(0.02, 0.0), (0.0, 0.03), (-0.02, 0.0), (0.0, -0.005)]
            parts.add('antifoul', kit.sweep(pts, profile=profile, up_hint=(side, 0, 0)), tile=1.0)


def build_hull_decals(parts):
    """Registration letters on both bows, conforming to the flared topside, 4 mm proud."""
    s0, s1 = 7.9, 9.9
    z0, z1 = 0.78, 1.18
    for side in (1, -1):
        rows = []
        uvs = []
        for zi, z in enumerate(np.linspace(z0, z1, 6)):
            row = []
            uv_row = []
            for si, s in enumerate(np.linspace(s0, s1, 16)):
                t = s / L
                x = hull_x_at(t, min(z, sheer_z(t) - 0.12)) + 0.004
                row.append(B(side * x, s, z))
                u = si / 15
                uv_row.append((1.0 - u if side > 0 else u, zi / 5))
            rows.append(row)
            uvs.append(uv_row)
        parts.add('decal', kit.grid_surface(rows, uvs, flip=(side < 0)))


# ───────────────────────────── superstructure ─────────────────────────────


def wheelhouse_ring(z):
    sf = 8.6 if z <= 1.45 else 8.6 - 0.35 * (z - 1.45) / 1.0
    k = 1.0 - 0.04 * max(0.0, z - 1.45)
    plan = [(-1.28, 5.3), (1.28, 5.3), (1.25, sf - 0.32), (0.95, sf), (-0.95, sf), (-1.25, sf - 0.32)]
    return [(x * k, s, z) for x, s in plan]


def build_wheelhouse(parts):
    levels = (0.4, 1.45, 2.45)
    rings = [wheelhouse_ring(z) for z in levels]
    bm = bmesh.new()
    vs = [[bm.verts.new(B(*p)) for p in ring] for ring in rings]
    for ra, rb in zip(vs, vs[1:]):
        for i in range(6):
            j = (i + 1) % 6
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    bm.faces.new(vs[-1])
    bm.normal_update()
    vertical = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().z) > 0.7]
    bmesh.ops.bevel(bm, geom=vertical, offset=0.05, segments=3, affect='EDGES', profile=0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    parts.add('white', bm, tile=2.0)
    # windows: (wall index, list of (u0, u1)) along each wall of the upper band
    windows = {0: [(0.55, 0.92)], 1: [(0.08, 0.45), (0.55, 0.92)], 2: [(0.12, 0.88)], 3: [(0.06, 0.48), (0.52, 0.94)],
               4: [(0.12, 0.88)], 5: [(0.08, 0.45), (0.55, 0.92)]}
    lo = rings[1]
    hi = rings[2]
    for wall, spans in windows.items():
        a0, b0 = Vector(B(*lo[wall])), Vector(B(*lo[(wall + 1) % 6]))
        a1, b1 = Vector(B(*hi[wall])), Vector(B(*hi[(wall + 1) % 6]))
        normal = (a1 - a0).cross(b0 - a0).normalized()
        for u0, u1 in spans:
            corners = []
            for u, v in ((u0, 0.12), (u1, 0.12), (u1, 0.86), (u0, 0.86)):
                p = (a0.lerp(b0, u)).lerp(a1.lerp(b1, u), v)
                corners.append(p + normal * 0.012)
            glass = bmesh.new()
            face = glass.faces.new([glass.verts.new(c) for c in corners])
            face.normal_update()
            if face.normal.dot(normal) < 0:
                face.normal_flip()
            parts.add('glass', glass)
            frame_profile = [(0.022, 0.0), (0.0, 0.014), (-0.022, 0.0), (0.0, -0.01)]
            parts.add('rubber', kit.sweep(corners, closed=True, profile=frame_profile, up_hint=tuple(normal)))
    build_wheelhouse_door(parts)
    build_roof(parts, rings[2])


def build_wheelhouse_door(parts):
    y = 5.3 - 0.02
    parts.add('white', kit.box((0.7, 0.05, 1.8), center=B(-0.62, y, 0.45 + 0.92), bevel=0.012), tile=2.0)
    win = kit.box((0.46, 0.01, 0.5), center=B(-0.62, y - 0.03, 1.85))
    parts.add('glass', win)
    parts.add('rubber', kit.sweep([B(-0.86, y - 0.03, 1.59), B(-0.38, y - 0.03, 1.59), B(-0.38, y - 0.03, 2.11),
                                   B(-0.86, y - 0.03, 2.11)], closed=True, radius=0.012, seg=6))
    parts.add('steel', kit.box((0.03, 0.06, 0.18), center=B(-0.36, y - 0.06, 1.35)))
    for z in (0.75, 1.95):
        parts.add('steel', kit.cylinder(B(-0.97, y - 0.03, z - 0.06), B(-0.97, y - 0.03, z + 0.06), 0.018, seg=10))
    parts.add('rubber', kit.box((0.8, 0.12, 0.06), center=B(-0.62, 5.24, 0.43)))


def build_roof(parts, top_ring):
    cx = sum(p[0] for p in top_ring) / 6
    cs = sum(p[1] for p in top_ring) / 6
    outline = []
    for x, s, _ in top_ring:
        ox = cx + (x - cx) * 1.07
        os_ = cs + (s - cs) * 1.05 + (0.32 if s > cs + 1.0 else 0.0)
        outline.append(B(ox, os_, 0).to_2d())
    slab = kit.extrude([tuple(p) for p in outline], 0.1, center=(0, 0, 2.5))
    bmesh.ops.bevel(slab, geom=list(slab.edges), offset=0.015, segments=2, affect='EDGES', profile=0.5)
    parts.add('white', slab, tile=2.0)
    rail = []
    for x, s, _ in top_ring:
        rail.append(B(x * 0.92, cs + (s - cs) * 0.9, 2.82))
    parts.add('steel', kit.sweep(rail, radius=0.017, closed=True, seg=8), tile=0.5)
    for p in rail:
        parts.add('steel', kit.cylinder(Vector((p.x, p.y, 2.55)), p, 0.015, seg=8))
    build_mast(parts)
    build_roof_equipment(parts)


def build_mast(parts):
    base_s = 6.15
    top_z = 3.95
    for x in (-0.48, 0.48):
        parts.add('alu', kit.cylinder(B(x, base_s - 0.2, 2.55), B(x * 0.85, base_s, top_z), 0.045, seg=12), 0.5)
        parts.add('alu', kit.box((0.22, 0.22, 0.02), center=B(x, base_s - 0.2, 2.56)))
    parts.add('alu', kit.cylinder(B(-0.62, base_s, top_z), B(0.62, base_s, top_z), 0.04, seg=12), 0.5)
    parts.add('alu', kit.box((0.6, 0.5, 0.03), center=B(0, base_s + 0.05, top_z + 0.03)))
    radome = kit.lathe([(0.0, 0.0), (0.3, 0.0), (0.31, 0.03), (0.3, 0.2), (0.26, 0.25), (0.0, 0.27)], seg=32,
                       center=B(0, base_s + 0.05, top_z + 0.045))
    parts.add('white', radome, tile=1.0)
    parts.add('alu', kit.cylinder(B(0, base_s + 0.05, top_z + 0.32), B(0, base_s + 0.05, top_z + 0.75), 0.025))
    parts.add('lamp_white', kit.lathe([(0.0, 0.0), (0.05, 0.0), (0.05, 0.08), (0.0, 0.09)], seg=16,
                                      center=B(0, base_s + 0.05, top_z + 0.75)))
    parts.add('lamp_white', kit.box((0.09, 0.07, 0.1), center=B(0, base_s + 0.09, 3.55)))
    parts.add('dark', kit.box((0.11, 0.05, 0.12), center=B(0, base_s + 0.04, 3.55)))
    for x in (-0.6, 0.6):
        parts.add('white', kit.cylinder(B(x, base_s, top_z), B(x, base_s, top_z + 2.3), 0.016, r1=0.005, seg=8))
        parts.add('dark', kit.cylinder(B(x, base_s, top_z - 0.15), B(x, base_s, top_z + 0.15), 0.022, seg=8))
    parts.add('white', kit.cylinder(B(0.3, base_s, top_z + 0.04), B(0.3, base_s, top_z + 1.1), 0.012, r1=0.004))
    for x in (-0.25, 0.22):
        parts.add('white', kit.lathe([(0.0, 0.0), (0.065, 0.0), (0.065, 0.04), (0.045, 0.08), (0.0, 0.09)], seg=16,
                                     center=B(x, base_s - 0.15, top_z + 0.045)))
    for x in (-0.3, 0.3):
        parts.add('grey', kit.box((0.22, 0.08, 0.16), center=B(x, base_s - 0.25, 3.62), bevel=0.01))
        parts.add('lamp_white', kit.box((0.18, 0.01, 0.12), center=B(x, base_s - 0.295, 3.62)))
    parts.add('grey', kit.cylinder(B(0.15, base_s, 3.4), B(0.15, base_s + 0.22, 3.4), 0.03, r1=0.07, seg=14))


def build_roof_equipment(parts):
    # sidelights with screens: red to port (+x), green to starboard
    for side, lamp in ((1, 'lamp_red'), (-1, 'lamp_green')):
        parts.add('dark', kit.box((0.02, 0.3, 0.2), center=B(side * 1.22, 8.2, 2.68)))
        parts.add(lamp, kit.box((0.06, 0.12, 0.1), center=B(side * 1.26, 8.25, 2.66), bevel=0.01))
    # stern light on the aft roof edge
    parts.add('lamp_white', kit.box((0.1, 0.06, 0.08), center=B(0.0, 5.1, 2.6)))
    # searchlight on a post
    parts.add('grey', kit.cylinder(B(0.35, 8.25, 2.55), B(0.35, 8.25, 2.75), 0.03, seg=10))
    light = kit.lathe([(0.0, -0.12), (0.06, -0.12), (0.09, -0.04), (0.1, 0.1), (0.0, 0.1)], seg=18,
                      center=B(0.35, 8.25, 2.85), axis=(0, -1, 0))
    parts.add('grey', light)
    parts.add('lamp_white', kit.cylinder(B(0.35, 8.36, 2.85), B(0.35, 8.37, 2.85), 0.095, seg=18))
    # life raft canister in its cradle
    parts.add('white', kit.lathe([(0.0, -0.45), (0.2, -0.45), (0.27, -0.38), (0.28, 0.0), (0.27, 0.38),
                                  (0.2, 0.45), (0.0, 0.45)], seg=24, center=B(0, 5.75, 2.88), axis=(1, 0, 0)))
    for x in (-0.25, 0.25):
        parts.add('dark', kit.torus(0.285, 0.012, seg=24, ring_seg=6, center=B(x, 5.75, 2.88), axis=(1, 0, 0)))
        parts.add('steel', kit.box((0.05, 0.5, 0.2), center=B(x * 1.4, 5.75, 2.66)))
    # wipers on the front windows
    for x in (-0.45, 0.45):
        wiper = kit.beam(B(x, 8.52, 1.62), B(x + 0.25, 8.4, 2.1), 0.012, 0.02)
        parts.add('dark', wiper)
    # roof ladder on the aft wall (port side)
    for x in (0.98, 1.22):
        parts.add('steel', kit.cylinder(B(x, 5.22, 0.5), B(x, 5.22, 2.75), 0.016, seg=8))
    for z in np.arange(0.75, 2.5, 0.28):
        parts.add('steel', kit.cylinder(B(0.98, 5.22, z), B(1.22, 5.22, z), 0.012, seg=8))
    # life ring on the starboard wheelhouse wall
    ring = kit.torus(0.3, 0.055, seg=32, ring_seg=10, center=B(-1.33, 6.2, 1.05), axis=(1, 0, 0))
    parts.add('orange', ring)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        c = B(-1.33, 6.2 + 0.3 * math.cos(a), 1.05 + 0.3 * math.sin(a))
        parts.add('tape', kit.box((0.125, 0.08, 0.08), center=c))
    parts.add('steel', kit.box((0.04, 0.06, 0.12), center=B(-1.31, 6.2, 1.38)))


# ───────────────────────────── deck equipment ─────────────────────────────


def build_rails(parts):
    for side in (1, -1):
        posts = []
        for s in np.arange(1.0, 9.6, 0.95):
            t = s / L
            x = (half_beam(t) - 0.035) * side
            zs = sheer_z(t)
            top = B(x, s, zs + 0.48)
            parts.add('steel', kit.cylinder(B(x, s, zs), top, 0.018, seg=8), tile=0.5)
            parts.add('steel', kit.cylinder(B(x, s, zs), B(x, s, zs + 0.015), 0.03, seg=10), tile=0.5)
            posts.append((top, B(x, s, zs + 0.24)))
        parts.add('steel', kit.sweep([p[0] for p in posts], radius=0.019, seg=10), tile=0.5)
        parts.add('steel', kit.sweep([p[1] for p in posts], radius=0.013, seg=8), tile=0.5)
    # bow pulpit around the stem
    pulpit = []
    for t in np.linspace(9.5 / L, 0.985, 10):
        pulpit.append((t, half_beam(t) - 0.035))
    path = [B(x, t * L, sheer_z(t) + 0.55) for t, x in pulpit]
    path = path + [B(0.0, 0.993 * L, sheer_z(0.993) + 0.55)] + [B(-p.x, L / 2 - p.y, p.z) for p in reversed(path)]
    parts.add('steel', kit.sweep(path, radius=0.02, seg=10), tile=0.5)
    for p in path[::3]:
        parts.add('steel', kit.cylinder(Vector((p.x, p.y, p.z - 0.55)), p, 0.018, seg=8))


def bitts(parts, x, s, z):
    parts.add('grey', kit.box((0.22, 0.5, 0.03), center=B(x, s, z + 0.015), bevel=0.008))
    for ds in (-0.15, 0.15):
        parts.add('grey', kit.lathe([(0.075, 0), (0.075, 0.26), (0.1, 0.27), (0.1, 0.3), (0.0, 0.31)], seg=16,
                                    center=B(x, s + ds, z + 0.03)))


def build_deck_fittings(parts):
    bitts(parts, 1.45, 1.75, DECK_Z)
    bitts(parts, -1.45, 1.75, DECK_Z)
    bitts(parts, 0.0, 9.95, deck_z(9.95 / L))
    for side in (1, -1):
        t = 6.8 / L
        x = (half_beam(t) - 0.03) * side
        zs = sheer_z(t)
        parts.add('steel', kit.box((0.05, 0.28, 0.03), center=B(x, 6.8, zs + 0.05), bevel=0.01))
        for ds in (-0.07, 0.07):
            parts.add('steel', kit.cylinder(B(x, 6.8 + ds, zs), B(x, 6.8 + ds, zs + 0.05), 0.018, seg=8))
    # flush hatch with coaming and hinges
    parts.add('grey', kit.box((0.74, 0.74, 0.05), center=B(-0.3, 3.35, DECK_Z + 0.025), bevel=0.012))
    parts.add('deck', kit.box((0.66, 0.66, 0.02), center=B(-0.3, 3.35, DECK_Z + 0.055)), tile=1.2)
    for dx in (-0.2, 0.2):
        parts.add('steel', kit.cylinder(B(-0.3 + dx - 0.05, 3.7, DECK_Z + 0.06), B(-0.3 + dx + 0.05, 3.7,
                                                                                    DECK_Z + 0.06), 0.015, seg=8))
    # tie-down sockets
    for x in (-1.25, 1.25):
        for s in (0.85, 2.85, 4.1):
            parts.add('dark', kit.cylinder(B(x, s, DECK_Z), B(x, s, DECK_Z + 0.008), 0.035, seg=12))
    # coiled mooring line near the starboard quarter
    for k in range(5):
        coil = kit.torus(0.24 - k * 0.012, 0.013, seg=28, ring_seg=6, center=B(-1.35, 0.8, DECK_Z + 0.015 + k * 0.022))
        parts.add('rope', coil)
    # windlass, anchor roller, anchor and chain
    zf = deck_z(9.4 / L)
    parts.add('grey', kit.box((0.36, 0.3, 0.22), center=B(0, 9.4, zf + 0.11), bevel=0.02))
    parts.add('steel', kit.cylinder(B(-0.24, 9.4, zf + 0.2), B(0.24, 9.4, zf + 0.2), 0.08, seg=16))
    roller_s = 11.45
    rz = sheer_z(roller_s / L)
    parts.add('steel', kit.beam(B(0, 10.6, rz - 0.15), B(0, roller_s + 0.2, rz + 0.02), 0.16, 0.05))
    parts.add('dark', kit.cylinder(B(-0.06, roller_s + 0.16, rz + 0.06), B(0.06, roller_s + 0.16, rz + 0.06), 0.05))
    shank_top = B(0, roller_s + 0.22, rz + 0.05)
    crown = B(0, roller_s + 0.42, rz - 0.6)
    parts.add('steel', kit.beam(shank_top, crown, 0.05, 0.035))
    for side in (1, -1):
        fluke = kit.extrude([(0, 0), (0.22, 0.05), (0.1, 0.32)], 0.025, center=crown)
        for v in fluke.verts:
            v.co.x = crown.x + (v.co.x - crown.x) * side
        parts.add('steel', fluke)
    chain = [B(0, 9.4, zf + 0.25), B(0, 10.2, zf + 0.2), B(0, 11.0, rz - 0.02), B(0, roller_s + 0.12, rz + 0.1)]
    parts.add('dark', kit.sweep(chain, radius=0.016, seg=6))


A_HINGE_S = 0.32
A_HINGE_Z = DECK_Z + 0.2
A_APEX_S = -0.3
A_APEX_Z = 3.05


class LocalParts(Parts):
    """Parts given in boat coordinates but stored relative to a node origin (and optional node rotation)."""

    def __init__(self, materials, prefix, origin, rotation=None):
        super().__init__(materials, prefix)
        matrix = Matrix.Translation(-Vector(origin))
        if rotation is not None:
            matrix = rotation.inverted().to_matrix().to_4x4() @ matrix
        self.matrix = matrix

    def add(self, key, bm, tile=1.0):
        bm.transform(self.matrix)
        super().add(key, bm, tile)


def make_node(name, collection, parent, location, rotation=None):
    """Empty node (glTF node without mesh); ``location`` is relative to ``parent``."""
    node = bpy.data.objects.new(name, None)
    collection.objects.link(node)
    node.parent = parent
    node.location = Vector(location)
    if rotation is not None:
        node.rotation_mode = 'QUATERNION'
        node.rotation_quaternion = rotation
    return node


def build_a_frame(parts, materials, collection, parent):
    """Luffing stern A-frame with hydraulic rams, a sheave block and a lifting hook, as separate nodes.

    Nodes for deploy_intro.js: "AFrame" pivots about its local X at the deck hinges (rotation 0 = the stowed
    pose, apex 0.3 m aft of the transom); "LiftBlock" hangs from the beam centre and is counter-rotated to stay
    plumb; "SheaveBottom" is where the lifting wire leaves the block; "LiftHook" is moved along the wire;
    "AFrameRam_P/S" have their origin on the deck lug and their local +Y (glTF) along the ram, to be re-aimed
    and stretched towards "RamAttach_P/S" (children of AFrame).
    """
    apex_s = A_APEX_S
    apex_z = A_APEX_Z
    hinge = B(0, A_HINGE_S, A_HINGE_Z)
    frame = LocalParts(materials, 'AFrame', hinge)
    shackle = B(0, apex_s, apex_z - 0.3)
    block = LocalParts(materials, 'LiftBlock', shackle)
    hook_at = B(0, apex_s, apex_z - 0.7)
    hook = LocalParts(materials, 'LiftHook', hook_at)
    frame_node = make_node('AFrame', collection, parent, hinge)
    block_node = make_node('LiftBlock', collection, frame_node, shackle - hinge)
    make_node('SheaveBottom', collection, block_node, B(0, apex_s, apex_z - 0.62) - shackle)
    objects = []
    for x in (-1.5, 1.5):
        parts.add('yellow', kit.box((0.26, 0.42, 0.04), center=B(x, A_HINGE_S, DECK_Z + 0.02), bevel=0.008))
        for dx in (-0.09, 0.09):
            plate = kit.extrude([(-0.16, 0.0), (0.16, 0.0), (0.06, 0.24), (-0.06, 0.24)], 0.025,
                                center=B(x + dx, A_HINGE_S, DECK_Z + 0.04), rot=kit.rot_x(math.pi / 2) @ kit.rot_y(
                                    math.pi / 2))
            parts.add('yellow', plate)
        parts.add('steel', kit.cylinder(B(x - 0.11, A_HINGE_S, A_HINGE_Z), B(x + 0.11, A_HINGE_S, A_HINGE_Z), 0.035))
        frame.add('yellow', kit.beam(B(x, A_HINGE_S, A_HINGE_Z), B(x * 0.97, apex_s, apex_z), 0.13, 0.13,
                                     bevel=0.01), tile=1.0)
        # hydraulic ram: barrel from a deck lug, chrome rod into the leg
        base = B(x, 1.05, DECK_Z + 0.12)
        attach = B(x * 0.985, A_HINGE_S + (apex_s - A_HINGE_S) * 0.42, A_HINGE_Z + (apex_z - A_HINGE_Z) * 0.42)
        side = 'P' if x > 0 else 'S'
        direction = (attach - base).normalized()
        turn = Vector((0, 0, 1)).rotation_difference(direction)
        ram = LocalParts(materials, f'AFrameRam_{side}', base, turn)
        mid = base.lerp(attach, 0.58)
        ram.add('grey', kit.cylinder(base, mid, 0.055, seg=14))
        ram.add('steel', kit.cylinder(mid, attach, 0.026, seg=10))
        ram_node = make_node(f'AFrameRam_{side}', collection, parent, base, turn)
        objects += ram.build(collection, ram_node)
        make_node(f'RamAttach_{side}', collection, frame_node, attach - hinge)
        parts.add('yellow', kit.box((0.14, 0.16, 0.14), center=B(x, 1.05, DECK_Z + 0.07)))
    frame.add('yellow', kit.beam(B(-1.55, apex_s, apex_z), B(1.55, apex_s, apex_z), 0.16, 0.16, bevel=0.012), 1.0)
    for x in (-1.46, 1.46):
        frame.add('yellow', kit.box((0.2, 0.2, 0.2), center=B(x, apex_s, apex_z), bevel=0.01))
    # padeye on the beam; shackle and sheave block hanging from it; hook on the lifting wire
    frame.add('yellow', kit.extrude([(-0.06, 0), (0.06, 0), (0.04, 0.1), (-0.04, 0.1)], 0.03,
                                    center=B(0, apex_s, apex_z - 0.16), rot=kit.rot_x(math.pi)))
    block.add('steel', kit.torus(0.04, 0.011, seg=12, ring_seg=6, center=shackle, axis=(1, 0, 0)))
    for dx in (-0.035, 0.035):
        cheek = kit.cylinder(B(dx - 0.008, apex_s, apex_z - 0.5), B(dx + 0.008, apex_s, apex_z - 0.5), 0.13, seg=24)
        block.add('orange', cheek)
    block.add('steel', kit.cylinder(B(-0.03, apex_s, apex_z - 0.5), B(0.03, apex_s, apex_z - 0.5), 0.1, seg=24))
    hook.add('orange', kit.box((0.05, 0.05, 0.08), center=hook_at + Vector((0, 0, 0.07)), bevel=0.01))
    hook.add('steel', kit.torus(0.06, 0.016, seg=14, ring_seg=6, center=hook_at, axis=(1, 0, 0), arc=4.5))
    hook_node = make_node('LiftHook', collection, parent, hook_at)
    objects += frame.build(collection, frame_node)
    objects += block.build(collection, block_node)
    objects += hook.build(collection, hook_node)
    return objects


# LOD levels: (decimate ratio, switch distance in metres, materials left out at that level)
LOD_LEVELS = (
    (0.4, 35.0, ()),
    (0.12, 90.0, ('rope', 'tape', 'lamp_red', 'lamp_green', 'lamp_white', 'lamp_status', 'screen', 'zinc', 'tether',
                  'decal', 'tyre', 'bronze', 'dark')),
)


def build_lods(collection, root, objects, materials):
    """LOD1/LOD2 groups: decimated, flattened copies of every LOD0 mesh (fine details dropped at LOD2)."""
    bpy.context.view_layer.update()
    skip_names = {key: materials[key].name for key in materials}
    lod_objects = []
    for level, (ratio, distance, skip) in enumerate(LOD_LEVELS, start=1):
        group = make_node(f'LOD{level}', collection, root, (0, 0, 0))
        group['lodDistance'] = distance
        left_out = {skip_names[key] for key in skip}
        for ob in objects:
            if ob.type != 'MESH' or ob.data.materials[0].name in left_out:
                continue
            copy = bpy.data.objects.new(f'{ob.name}_LOD{level}', ob.data.copy())
            collection.objects.link(copy)
            copy.parent = group
            copy.matrix_basis = ob.matrix_world.copy()
            modifier = copy.modifiers.new('decimate', 'DECIMATE')
            modifier.ratio = ratio
            modifier.use_collapse_triangulate = True
            lod_objects.append(copy)
    return lod_objects


def build_collision_proxy(collection, root):
    """Closed low-poly hull + wheelhouse block for collision / occlusion queries (hidden in the viewer)."""
    bm = bmesh.new()
    rings = []
    for t in (0.0, 0.2, 0.45, 0.7, 0.85, 0.95, 1.0):
        half = section(min(t, 0.995))
        keel = half[0]
        chine = half[NB]
        sheer = half[-1]
        s = t * L
        ring = [B(0, s, keel[1]), B(chine[0], s, chine[1]), B(sheer[0], s, sheer[1]),
                B(-sheer[0], s, sheer[1]), B(-chine[0], s, chine[1])]
        rings.append([bm.verts.new(p) for p in ring])
    for ra, rb in zip(rings, rings[1:]):
        for i in range(5):
            j = (i + 1) % 5
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    house = kit.box((2.56, 3.3, 2.05), center=B(0, 6.95, DECK_Z + 1.02))
    mapping = {v: bm.verts.new(v.co) for v in house.verts}
    for f in house.faces:
        bm.faces.new([mapping[v] for v in f.verts])
    house.free()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new('CollisionProxy')
    bm.to_mesh(mesh)
    bm.free()
    proxy = bpy.data.objects.new('CollisionProxy', mesh)
    collection.objects.link(proxy)
    proxy.parent = root
    proxy['proxy'] = 'collision'
    return proxy


def build_winch(parts, drum_parts):
    """Powered tether winch frame (static) and drum (separate node, spins about its axis)."""
    x0 = -0.75
    s0 = 2.25
    za = DECK_Z + 0.52
    half_w = 0.36
    for dx in (-half_w - 0.06, half_w + 0.06):
        x = x0 + dx
        parts.add('grey', kit.beam(B(x, s0 - 0.42, DECK_Z + 0.03), B(x, s0 + 0.42, DECK_Z + 0.03), 0.06, 0.06))
        parts.add('grey', kit.beam(B(x, s0 - 0.36, DECK_Z + 0.03), B(x, s0, za), 0.05, 0.05))
        parts.add('grey', kit.beam(B(x, s0 + 0.36, DECK_Z + 0.03), B(x, s0, za), 0.05, 0.05))
        parts.add('steel', kit.cylinder(B(x - 0.04, s0, za), B(x + 0.04, s0, za), 0.06, seg=16))
    for ds in (-0.42, 0.42):
        parts.add('grey', kit.beam(B(x0 - half_w - 0.06, s0 + ds, DECK_Z + 0.03),
                                   B(x0 + half_w + 0.06, s0 + ds, DECK_Z + 0.03), 0.06, 0.06))
    # slip-ring housing (port end) and motor + gearbox (starboard end)
    parts.add('grey', kit.cylinder(B(x0 + half_w + 0.1, s0, za), B(x0 + half_w + 0.26, s0, za), 0.09, seg=20))
    parts.add('dark', kit.cylinder(B(x0 + half_w + 0.26, s0, za), B(x0 + half_w + 0.3, s0, za), 0.04, seg=12))
    parts.add('grey', kit.box((0.16, 0.24, 0.24), center=B(x0 - half_w - 0.16, s0, za), bevel=0.012))
    parts.add('steel', kit.cylinder(B(x0 - half_w - 0.24, s0, za + 0.02), B(x0 - half_w - 0.52, s0, za + 0.02),
                                    0.085, seg=20))
    # fairlead rollers aft of the drum, where the tether leaves towards the tender
    fs = s0 - 0.5
    for dx in (-0.12, 0.12):
        parts.add('steel', kit.cylinder(B(x0 + dx, fs, DECK_Z + 0.5), B(x0 + dx, fs, DECK_Z + 0.85), 0.025))
    parts.add('steel', kit.cylinder(B(x0 - 0.15, fs, DECK_Z + 0.55), B(x0 + 0.15, fs, DECK_Z + 0.55), 0.025))
    parts.add('grey', kit.beam(B(x0 - 0.2, fs, DECK_Z + 0.87), B(x0 + 0.2, fs, DECK_Z + 0.87), 0.04, 0.04))
    parts.add('grey', kit.beam(B(x0, fs, DECK_Z + 0.87), B(x0, s0 - 0.3, za), 0.04, 0.04))
    # control pendant hanging from the frame
    parts.add('yellow', kit.box((0.07, 0.05, 0.16), center=B(x0 - half_w - 0.08, s0 - 0.3, za - 0.25), bevel=0.01))
    parts.add('dark', kit.sweep([B(x0 - half_w - 0.06, s0 - 0.1, za), B(x0 - half_w - 0.08, s0 - 0.3, za - 0.1),
                                 B(x0 - half_w - 0.08, s0 - 0.3, za - 0.17)], radius=0.006, seg=6))
    # drum geometry in drum-local coordinates (axis along X)
    r_flange = 0.37
    for dx in (-half_w, half_w):
        flange = kit.lathe([(0.06, -0.01), (r_flange, -0.01), (r_flange + 0.01, 0.0), (r_flange, 0.01), (0.06, 0.01)],
                           seg=40, center=(dx, 0, 0), axis=(1, 0, 0))
        drum_parts.add('alu', flange, tile=0.5)
        for k in range(6):
            a = k * math.pi / 3
            out = 1 if dx > 0 else -1
            spoke = kit.beam((dx + out * 0.025, 0.07 * math.cos(a), 0.07 * math.sin(a)),
                             (dx + out * 0.025, 0.33 * math.cos(a), 0.33 * math.sin(a)), 0.03, 0.03)
            drum_parts.add('grey', spoke)
            drum_parts.add('steel', kit.cylinder((dx + out * 0.012, 0.35 * math.cos(a + 0.5), 0.35 * math.sin(a + 0.5)),
                                                 (dx + out * 0.03, 0.35 * math.cos(a + 0.5),
                                                  0.35 * math.sin(a + 0.5)), 0.012, seg=6))
    drum_parts.add('dark', kit.cylinder((-half_w, 0, 0), (half_w, 0, 0), 0.13, seg=24))
    drum_parts.add('tether', kit.cylinder((-half_w + 0.01, 0, 0), (half_w - 0.01, 0, 0), 0.265, seg=40))
    for k in range(15):
        x = -half_w + 0.03 + k * (2 * half_w - 0.06) / 14
        drum_parts.add('tether', kit.torus(0.27, 0.011, seg=40, ring_seg=6, center=(x, 0, 0), axis=(1, 0, 0)))
    drum_parts.add('steel', kit.cylinder((-half_w - 0.08, 0, 0), (half_w + 0.08, 0, 0), 0.03, seg=12))
    return B(x0, s0, za), B(x0, s0 - 0.5, DECK_Z + 0.6)


def build_control_cabinet(parts):
    x0 = -1.3
    s0 = 4.65
    z0 = DECK_Z + 0.3
    for dx in (-0.22, 0.22):
        for ds in (-0.12, 0.12):
            parts.add('steel', kit.beam(B(x0 + dx, s0 + ds, DECK_Z), B(x0 + dx, s0 + ds, z0), 0.035, 0.035))
    parts.add('steel', kit.box((0.6, 0.34, 0.82), center=B(x0, s0, z0 + 0.41), bevel=0.015), tile=1.0)
    parts.add('steel', kit.box((0.54, 0.02, 0.74), center=B(x0, s0 - 0.18, z0 + 0.41), bevel=0.006), tile=1.0)
    parts.add('steel', kit.box((0.66, 0.4, 0.03), center=B(x0, s0, z0 + 0.835), bevel=0.008), tile=1.0)
    parts.add('dark', kit.box((0.03, 0.03, 0.12), center=B(x0 + 0.21, s0 - 0.2, z0 + 0.42)))
    for z in (z0 + 0.12, z0 + 0.7):
        parts.add('dark', kit.cylinder(B(x0 - 0.275, s0 - 0.19, z - 0.04), B(x0 - 0.275, s0 - 0.19, z + 0.04),
                                       0.012, seg=8))
    parts.add('lamp_status', kit.cylinder(B(x0 - 0.12, s0 - 0.19, z0 + 0.72), B(x0 - 0.12, s0 - 0.205, z0 + 0.72),
                                          0.018, seg=12))
    parts.add('orange', kit.cylinder(B(x0, s0 - 0.19, z0 + 0.72), B(x0, s0 - 0.21, z0 + 0.72), 0.026, seg=14))
    label = kit.extrude([(-0.06, -0.05), (0.06, -0.05), (0.0, 0.055)], 0.004, center=B(x0 - 0.12, s0 - 0.19,
                                                                                         z0 + 0.52),
                        rot=kit.rot_x(math.pi / 2))
    parts.add('yellow', label)
    for k in range(4):
        parts.add('dark', kit.cylinder(B(x0 - 0.18 + k * 0.12, s0, z0), B(x0 - 0.18 + k * 0.12, s0, z0 - 0.05),
                                       0.016, seg=8))
    # power and data cables from the cabinet to the winch slip ring
    cable = [B(x0 + 0.06, s0, z0 - 0.05), B(x0 + 0.06, s0 - 0.1, DECK_Z + 0.02), B(-0.6, 3.7, DECK_Z + 0.02),
             B(-0.25, 2.6, DECK_Z + 0.02), B(0.0, 2.25, DECK_Z + 0.06), B(-0.13, 2.25, DECK_Z + 0.52)]
    parts.add('dark', kit.sweep(cable, radius=0.012, seg=8))


def build_pilot_station(parts):
    """Shade canopy over a folding table with a rugged control case, monitor and hand controller."""
    xa, xb = 0.15, 1.7
    sa, sb = 3.25, 5.12
    top = DECK_Z + 2.05
    peak = top + 0.38
    corners = [(xa, sa), (xb, sa), (xb, sb), (xa, sb)]
    for x, s in corners:
        parts.add('alu', kit.beam(B(x, s, DECK_Z), B(x, s, top), 0.035, 0.035), 0.5)
        parts.add('dark', kit.box((0.09, 0.09, 0.02), center=B(x, s, DECK_Z + 0.01)))
    cx = (xa + xb) / 2
    cs = (sa + sb) / 2
    for i in range(4):
        x0, s0 = corners[i]
        x1, s1 = corners[(i + 1) % 4]
        parts.add('alu', kit.beam(B(x0, s0, top), B(x1, s1, top), 0.03, 0.03), 0.5)
        roof = bmesh.new()
        face = roof.faces.new([roof.verts.new(B(x0, s0, top)), roof.verts.new(B(x1, s1, top)),
                               roof.verts.new(B(cx, cs, peak))])
        face.normal_update()
        if face.normal.z < 0:
            face.normal_flip()
        parts.add('canvas', roof, tile=1.0)
        valance = kit.grid_surface([[B(x0, s0, top - 0.2), B(x1, s1, top - 0.2)],
                                    [B(x0, s0, top + 0.005), B(x1, s1, top + 0.005)]])
        parts.add('canvas', valance, tile=1.0)
        under = bmesh.new()
        face = under.faces.new([under.verts.new(B(x0, s0, top - 0.005)), under.verts.new(B(x1, s1, top - 0.005)),
                                under.verts.new(B(cx, cs, peak - 0.005))])
        face.normal_update()
        if face.normal.z > 0:
            face.normal_flip()
        parts.add('canvas', under, tile=1.0)
        parts.add('alu', kit.beam(B(x0, s0, top), B(cx, cs, peak), 0.02, 0.02), 0.5)
    # folding table along the wheelhouse wall
    tz = DECK_Z + 0.74
    parts.add('grey', kit.box((1.15, 0.6, 0.03), center=B(0.95, 4.72, tz), bevel=0.006))
    for x in (0.45, 1.45):
        for s in (4.5, 4.95):
            parts.add('alu', kit.cylinder(B(x, s, DECK_Z), B(x, s, tz - 0.015), 0.014, seg=8))
    # rugged control case: base on the table, lid open with the monitor facing aft
    parts.add('dark', kit.box((0.56, 0.4, 0.17), center=B(0.95, 4.75, tz + 0.1), bevel=0.02))
    parts.add('grey', kit.box((0.5, 0.33, 0.01), center=B(0.95, 4.74, tz + 0.19)))
    lid = kit.box((0.56, 0.06, 0.42), center=B(0.95, 4.96, tz + 0.4), bevel=0.02)
    parts.add('dark', lid)
    screen = kit.grid_surface([[B(1.17, 4.925, tz + 0.24), B(0.73, 4.925, tz + 0.24)],
                               [B(1.17, 4.925, tz + 0.56), B(0.73, 4.925, tz + 0.56)]],
                              uvs=[[(0, 0), (1, 0)], [(0, 1), (1, 1)]], flip=False)
    screen.normal_update()
    if next(iter(screen.faces)).normal.y < 0:                 # face aft (+Y in Blender), towards the operator's stool
        for f in screen.faces:
            f.normal_flip()
    parts.add('screen', screen)
    for k in range(5):
        parts.add('grey', kit.cylinder(B(0.78 + k * 0.08, 4.62, tz + 0.19), B(0.78 + k * 0.08, 4.62, tz + 0.21),
                                       0.012, seg=10))
    # hand controller on the table in front of the case
    parts.add('dark', kit.box((0.3, 0.14, 0.05), center=B(0.95, 4.46, tz + 0.04), bevel=0.02))
    for dx in (-0.08, 0.08):
        parts.add('grey', kit.cylinder(B(0.95 + dx, 4.46, tz + 0.065), B(0.95 + dx, 4.46, tz + 0.11), 0.008))
        parts.add('dark', kit.cylinder(B(0.95 + dx, 4.46, tz + 0.11), B(0.95 + dx, 4.46, tz + 0.125), 0.016))
    parts.add('dark', kit.sweep([B(0.95, 4.53, tz + 0.04), B(0.9, 4.6, tz + 0.02), B(0.85, 4.62, tz + 0.09)],
                                radius=0.005, seg=6))
    # folding stool
    sz = DECK_Z + 0.46
    parts.add('canvas', kit.box((0.4, 0.36, 0.03), center=B(0.95, 3.95, sz), bevel=0.01), tile=1.0)
    for dx in (-0.17, 0.17):
        parts.add('alu', kit.cylinder(B(0.95 + dx, 3.8, DECK_Z), B(0.95 + dx, 4.1, sz), 0.012, seg=8))
        parts.add('alu', kit.cylinder(B(0.95 + dx, 4.1, DECK_Z), B(0.95 + dx, 3.8, sz), 0.012, seg=8))
    # transport case for the vehicle on the starboard side
    parts.add('grey', kit.box((0.62, 0.9, 0.5), center=B(-1.25, 3.55, DECK_Z + 0.26), bevel=0.03))
    for ds in (-0.25, 0.25):
        parts.add('dark', kit.box((0.64, 0.05, 0.08), center=B(-1.25, 3.55 + ds, DECK_Z + 0.42)))


def build_fenders_tyres_ladder(parts):
    def hang(side, s, depth):
        t = s / L
        x = side * (half_beam(t) + 0.17)
        zs = sheer_z(t)
        return x, zs
    for side, s in ((-1, 4.4), (-1, 7.1), (1, 8.0)):
        x, zs = hang(side, s, 0)
        zc = zs - 0.55
        fender = kit.lathe([(0.0, -0.36), (0.07, -0.35), (0.11, -0.28), (0.115, 0.0), (0.11, 0.28),
                            (0.07, 0.35), (0.0, 0.36)], seg=20, center=B(x, s, zc))
        parts.add('fender', fender)
        parts.add('rope', kit.sweep([B(x, s, zc + 0.36), B(x * 0.99, s, zs + 0.2), B(x - side * 0.17, s, zs + 0.47)],
                                    radius=0.008, seg=6))
    for side, s in ((1, 4.25), (1, 6.6), (-1, 1.6)):
        t = s / L
        x = side * (hull_x_at(t, sheer_z(t) - 0.45) + 0.12)
        zc = sheer_z(t) - 0.45
        parts.add('tyre', kit.torus(0.27, 0.095, seg=28, ring_seg=10, center=B(x, s, zc), axis=(1, 0, 0)))
        parts.add('rope', kit.sweep([B(x, s, zc + 0.36), B(x * 0.98, s, sheer_z(t) + 0.1),
                                     B(side * (half_beam(t) - 0.03), s, sheer_z(t) + 0.47)], radius=0.009, seg=6))
    # boarding ladder on the port quarter, hooked over the gunwale
    for s in (2.42, 2.78):
        t = s / L
        pts = [B(half_beam(t) - 0.12, s, sheer_z(t) + 0.12), B(half_beam(t) + 0.06, s, sheer_z(t) + 0.12)]
        for z in np.linspace(sheer_z(t) - 0.05, -0.75, 8):
            pts.append(B(hull_x_at(t, max(z, -0.05)) + 0.09, s, z))
        parts.add('alu', kit.sweep(pts, radius=0.02, seg=8), 0.5)
    for z in np.arange(-0.7, sheer_z(2.6 / L) - 0.1, 0.28):
        x = hull_x_at(2.6 / L, max(z, -0.05)) + 0.09
        parts.add('alu', kit.cylinder(B(x, 2.42, z), B(x, 2.78, z), 0.016, seg=8), 0.5)


# ───────────────────────────── below the waterline ─────────────────────────────


def build_underwater(parts):
    # skeg along the centreline aft
    zk = keel_z(0.1)
    outline = [(0.6, zk + 0.06), (5.6, keel_z(5.6 / L) + 0.06), (5.6, keel_z(5.6 / L) - 0.01), (2.2, zk - 0.27),
               (0.6, zk - 0.27)]
    parts.add('antifoul', kit.plate_yz([(L / 2 - s, z) for s, z in outline], 0.07), tile=1.0)
    for side in (1, -1):
        xs = side * 0.62
        hull_entry = B(xs, 3.4, -0.36)
        prop_s = 1.0
        prop_c = B(xs, prop_s, -0.78)
        parts.add('steel', kit.cylinder(hull_entry, prop_c, 0.032, seg=12))
        parts.add('antifoul', kit.lathe([(0.0, 0.0), (0.09, 0.05), (0.09, 0.45), (0.04, 0.6)], seg=16,
                                        center=B(xs, 3.6, -0.37), axis=(0, 1, 0.17)), tile=1.0)
        bearing = hull_entry.lerp(prop_c, 0.82)
        parts.add('bronze', kit.cylinder(bearing + Vector((0, -0.12, 0.02)), bearing + Vector((0, 0.12, -0.02)),
                                         0.055, seg=14))
        for dx in (-0.16, 0.16):
            top = Vector((xs + dx * 1.3, bearing.y, -0.33 - abs(dx) * 0.2))
            parts.add('antifoul', kit.beam(top, bearing, 0.035, 0.12), tile=1.0)
        hub = kit.lathe([(0.0, -0.12), (0.07, -0.1), (0.075, 0.05), (0.04, 0.12), (0.0, 0.14)], seg=18,
                        center=prop_c, axis=(0, 1, 0))
        parts.add('bronze', hub)
        for k in range(4):
            a = k * math.pi / 2 + (0.3 if side > 0 else -0.3)
            blade = bmesh.new()
            bmesh.ops.create_uvsphere(blade, u_segments=14, v_segments=8, radius=1.0)
            bmesh.ops.scale(blade, vec=(0.012, 0.13, 0.12), verts=blade.verts)
            blade.transform(Matrix.Rotation(side * 0.6, 4, 'Z'))
            blade.transform(Matrix.Translation((0, 0, 0.19)))
            blade.transform(Matrix.Rotation(a, 4, 'Y'))
            blade.transform(Matrix.Translation(prop_c))
            parts.add('bronze', blade)
        # rudder with stock
        rs = 0.42
        stock_top = B(xs, rs, -0.3)
        parts.add('steel', kit.cylinder(stock_top, B(xs, rs, -0.55), 0.035, seg=12))
        blade_outline = [(rs + 0.12, -0.45), (rs - 0.3, -0.45), (rs - 0.27, -1.08), (rs + 0.1, -1.05)]
        rudder = kit.plate_yz([(L / 2 - s, z) for s, z in blade_outline], 0.045, x=xs)
        bmesh.ops.bevel(rudder, geom=list(rudder.edges), offset=0.012, segments=2, affect='EDGES', profile=0.5)
        parts.add('antifoul', rudder, tile=1.0)
        parts.add('zinc', kit.box((0.05, 0.12, 0.08), center=B(xs + side * 0.03, rs - 0.05, -0.8), bevel=0.01))
        # hull anodes beside the shaft and on the transom
        parts.add('zinc', kit.box((0.12, 0.3, 0.05), center=B(side * 1.0, 2.2, hull_bottom_z(1.0, 2.2) - 0.02),
                                  bevel=0.015))
        parts.add('zinc', kit.box((0.3, 0.05, 0.12), center=B(side * 0.55, -0.025, -0.22), bevel=0.015))
        # cooling water intake grate
        parts.add('dark', kit.box((0.18, 0.32, 0.03), center=B(side * 0.35, 4.6, hull_bottom_z(0.35, 4.6) - 0.01)))
    fair = kit.lathe([(0.0, -0.25), (0.06, -0.18), (0.08, 0.0), (0.06, 0.15), (0.0, 0.22)], seg=16,
                     center=B(0.32, 6.6, hull_bottom_z(0.32, 6.6) - 0.03), axis=(0, -1, 0))
    for v in fair.verts:
        v.co.z = min(v.co.z, hull_bottom_z(0.32, 6.6) + 0.02)
    parts.add('antifoul', fair, tile=1.0)


def hull_bottom_z(x, s):
    t = s / L
    half = section(t)
    for (x0, z0), (x1, z1) in zip(half, half[1:]):
        if x0 <= x <= x1 and x1 > x0:
            return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
    return half[0][1]


# ───────────────────────────── assemble ─────────────────────────────


def build(out_glb, texture_dir):
    collection = kit.reset_scene()
    texture_dir = Path(texture_dir)
    texture_dir.mkdir(parents=True, exist_ok=True)
    tex = {
        'hull': hull_textures(texture_dir),
        'transom': transom_textures(texture_dir),
        'decal': registration_decal(texture_dir),
        'deck': deck_textures(texture_dir),
        'paint': kit.worn_paint_set(texture_dir, 'paint', seed=41),
        'metal': kit.brushed_metal_set(texture_dir, 'metal', seed=51),
        'fabric': kit.fabric_set(texture_dir, 'fabric', seed=61),
        'screen': screen_texture(texture_dir),
    }
    materials = build_materials(tex)
    root = bpy.data.objects.new('SupportVessel', None)
    collection.objects.link(root)
    lod0 = make_node('LOD0', collection, root, (0, 0, 0))
    lod0['lodDistance'] = 0.0
    parts = Parts(materials, 'Vessel')
    drum_parts = Parts(materials, 'Drum')
    build_hull(parts)
    build_wheelhouse(parts)
    build_rails(parts)
    build_deck_fittings(parts)
    objects = build_a_frame(parts, materials, collection, lod0)
    drum_axis, tether_exit = build_winch(parts, drum_parts)
    build_control_cabinet(parts)
    build_pilot_station(parts)
    build_fenders_tyres_ladder(parts)
    build_underwater(parts)
    objects += parts.build(collection, lod0)
    drum = bpy.data.objects.new('TetherDrum', None)
    collection.objects.link(drum)
    drum.parent = lod0
    drum.location = drum_axis
    objects += drum_parts.build(collection, drum)
    lod_objects = build_lods(collection, root, objects, materials)
    build_collision_proxy(collection, root)
    exit_node = bpy.data.objects.new('TetherExit', None)
    collection.objects.link(exit_node)
    exit_node.parent = root
    exit_node.location = drum_axis + Vector((0, 0, 0.29))
    fairlead = bpy.data.objects.new('TetherFairlead', None)
    collection.objects.link(fairlead)
    fairlead.parent = root
    fairlead.location = tether_exit
    root['deckY'] = DECK_Z
    root['sternZ'] = -L / 2
    root['transomY'] = sheer_z(0.0)
    root['length'] = L
    root['beam'] = 2 * 1.95
    root['generator'] = 'cad/build_support_vessel.py'
    root['lodDistances'] = [0.0] + [level[1] for level in LOD_LEVELS]
    tris = kit.triangle_count(objects)
    raw = kit.export_glb(out_glb)
    kit.patch_material_factors(raw, list(materials.values()))
    print(f'support vessel: LOD0 {tris} triangles, {len(objects)} meshes (+{len(lod_objects)} LOD meshes) -> {raw}')
    return tris


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('out', type=Path)
    parser.add_argument('--textures', type=Path, default=Path('build/support_textures'))
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    build(args.out, args.textures)


if __name__ == '__main__':
    main()
