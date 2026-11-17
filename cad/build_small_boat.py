"""Original swim-platform stern, metres, Blender Z up; no reference image input.

Hull geometry is original procedural work (no CC0 realistic small-boat mesh was available).
Materials: Poly Haven wood_floor_deck (teak) and ambientCG Plastic010 normals / DiamondPlate from
models/boat/ and models/scan/. Rebuild maps with simulator/tools/build_boat_scan_materials.py.

blender -b --python cad/build_small_boat.py -- /tmp/small_boat.glb
python -c "from simulator.tools.build_support_assets import compress; from pathlib import Path; \\
compress(Path('/tmp/small_boat.glb'), Path('simulator/viewer/models/small_boat.glb'), \\
(('*', 512), ('paint*', 256), ('plate*', 256)))"
No .blend is saved. Geometry copyright dedicated to CC0 by this contribution.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import support_assets_lib as kit

ROOT = Path(__file__).resolve().parents[1]
BOAT_MATS = ROOT / 'simulator/viewer/models/boat'
SCAN_MATS = ROOT / 'simulator/viewer/models/scan'


def map_path(stem, kind):
    """Prefer boat/-local maps, else the shared scan/ copies (plate, rust)."""
    for folder in (BOAT_MATS, SCAN_MATS):
        path = folder / f'{stem}_{kind}.webp'
        if path.is_file():
            return path
    raise FileNotFoundError(f'Missing {stem}_{kind}.webp under boat/ or scan/')


def scan_textures(stem, *, colour=True, normal=True, orm=False):
    """Load WebP maps; roughness stays in the normal alpha when orm is false."""
    from PIL import Image

    work = Path(bpy.app.tempdir)
    textures = {}
    if colour:
        base = map_path(stem, 'c')
        base_png = work / f'{stem}_c.png'
        Image.open(base).convert('RGB').save(base_png)
        textures['base'] = base_png
    if normal:
        n_path = map_path(stem, 'n')
        normal_png = work / f'{stem}_n.png'
        n_img = Image.open(n_path).convert('RGBA')
        n_img.save(normal_png)
        textures['normal'] = normal_png
        if orm:
            alpha = np.asarray(n_img.split()[-1], dtype=np.uint8)
            orm_png = work / f'{stem}_orm.png'
            packed = np.zeros((alpha.shape[0], alpha.shape[1], 3), dtype=np.uint8)
            packed[..., 1] = alpha
            Image.fromarray(packed, 'RGB').save(orm_png)
            textures['orm'] = orm_png
    return textures


def build(output):
    collection = kit.reset_scene()
    root = bpy.data.objects.new('SmallBoat', None)
    collection.objects.link(root)
    # Deck sits ~0.42 m above water; keel ~0.55 m below — clear immersion, not a raft.
    for key, value in dict(length=9.2, deckY=0.42, sternZ=-3.05, transomY=0.42).items():
        root[key] = value

    def anchor(name, x, y, z):
        node = bpy.data.objects.new(name, None)
        collection.objects.link(node)
        node.parent = root
        node.location = (x, -z, y)
        return node

    def point(p):
        return (p[0], -p[2], p[1])

    def box(part, size, center, bevel=0.012):
        part.add_bmesh(kit.box((size[0], size[2], size[1]), point(center), bevel=bevel, segments=2))

    def tube(part, points, radius=0.02):
        part.add_bmesh(kit.sweep([point(p) for p in points], radius=radius, seg=10))

    # Gelcoat: scanned normal only (paint_c was a flat colour burning 1.3 MiB). Teak keeps albedo.
    paint = scan_textures('paint', colour=False, normal=True, orm=False)
    plate = scan_textures('plate', colour=False, normal=True, orm=False)
    teak = scan_textures('teak', colour=True, normal=True, orm=False)
    white = kit.Part('Fibreglass', kit.make_material('Gelcoat', (0.90, 0.91, 0.89),
                     rough=0.38, textures=paint), uv_tile=1.8)
    dark = kit.Part('SeamsAndRubber', kit.make_material('Rubber', (0.018, 0.024, 0.028), rough=0.8))
    steel = kit.Part('Stainless', kit.make_material('Stainless', (0.55, 0.61, 0.65), metal=0.55, rough=0.28))
    rusty = kit.Part('RustAccents', kit.make_material('Rust', (0.42, 0.22, 0.10), rough=0.88), uv_tile=0.7)
    yellow = kit.Part('CoiledUmbilical', kit.make_material('UmbilicalGold', (0.85, 0.72, 0.12), rough=0.45))
    rope = kit.Part('SafetyLanyard', kit.make_material('WovenSafetyLine', (0.14, 0.19, 0.24), rough=0.9))
    wood = kit.Part('TeakPlanks', kit.make_material('Teak', (1, 1, 1), rough=0.62, textures=teak), uv_tile=1.4)
    grip = kit.Part('NonSlip', kit.make_material('NonSlipPlate', (0.42, 0.44, 0.45), rough=0.92, metal=0.25,
                    textures=plate), uv_tile=0.45)
    antifoul = kit.Part('Antifoul', kit.make_material('Antifoul', (0.12, 0.18, 0.22), rough=0.78))

    # Stations stern→bow: (z, half_beam_deck, half_beam_chine, keel_y, sheer_y).
    # Sheer rises at the bow; flare = deck wider than chine; deadrise from chine down to keel.
    stations = [
        (-3.05, 1.48, 1.28, -0.42, 0.88),   # transom
        (-2.20, 1.58, 1.38, -0.52, 0.86),
        (-1.20, 1.66, 1.42, -0.58, 0.84),
        (-0.20, 1.68, 1.40, -0.60, 0.86),
        (0.90, 1.62, 1.30, -0.55, 0.92),
        (2.10, 1.42, 1.05, -0.45, 1.02),
        (3.40, 1.05, 0.72, -0.28, 1.12),
        (4.55, 0.55, 0.32, -0.08, 1.18),
        (5.35, 0.02, 0.02, 0.15, 1.22),    # stem tip above water
    ]
    hull = bmesh.new()
    rings = []
    for z, deck_w, chine_w, keel_y, sheer_y in stations:
        # Port→starboard ring: sheer, chine, keel, chine, sheer (hard chine with deadrise).
        rings.append([hull.verts.new(point(v)) for v in [
            (-deck_w, sheer_y, z),
            (-chine_w, 0.05, z),
            (-chine_w * 0.55, keel_y * 0.55, z),
            (0.0, keel_y, z),
            (chine_w * 0.55, keel_y * 0.55, z),
            (chine_w, 0.05, z),
            (deck_w, sheer_y, z),
        ]])
    for a, b in zip(rings, rings[1:]):
        for i in range(6):
            hull.faces.new([a[i], b[i], b[i + 1], a[i + 1]])
    hull.faces.new(rings[0][::-1])  # closed transom
    hull.faces.new(rings[-1])       # stem
    bmesh.ops.recalc_face_normals(hull, faces=list(hull.faces))
    # Split underwater antifoul from topsides roughly at y≈0 for a painted waterline band.
    tops = bmesh.new()
    bottom = bmesh.new()
    for face in list(hull.faces):
        centre = face.calc_center_median()
        target = tops if centre.z > -0.02 else bottom  # Blender Z is viewer Y
        mapping = {}
        for v in face.verts:
            mapping[v] = target.verts.new(v.co)
        try:
            target.faces.new([mapping[v] for v in face.verts])
        except ValueError:
            pass
    hull.free()
    bmesh.ops.recalc_face_normals(tops, faces=list(tops.faces))
    bmesh.ops.recalc_face_normals(bottom, faces=list(bottom.faces))
    white.add_bmesh(tops)
    antifoul.add_bmesh(bottom)

    # Cockpit sole (slight camber) and coaming.
    box(white, (3.05, 0.10, 4.4), (0, 0.36, 0.55))
    for side in (-1, 1):
        tube(dark, [(side * w, sheer, z) for z, w, _c, _k, sheer in stations], 0.04)
        tube(steel, [(side * w, sheer + 0.32, z) for z, w, _c, _k, sheer in stations[1:-1]], 0.02)
        for z, w, _c, _k, sheer in stations[1:-2]:
            tube(steel, [(side * w, sheer - 0.02, z), (side * w, sheer + 0.32, z)], 0.016)
        box(rusty, (0.07, 0.02, 0.4), (side * 1.55, 0.78, -1.85), 0.008)

    # Foredeck following the sheer taper.
    deck = bmesh.new()
    ring = []
    for z, w, _c, _k, sheer in stations[4:]:
        ring.append(deck.verts.new(point((w * 0.92, sheer - 0.02, z))))
    for z, w, _c, _k, sheer in stations[4:][::-1]:
        ring.append(deck.verts.new(point((-w * 0.92, sheer - 0.02, z))))
    if len(ring) >= 3:
        deck.faces.new(ring)
        bmesh.ops.recalc_face_normals(deck, faces=list(deck.faces))
        white.add_bmesh(deck)

    # Swim platform: one continuous teak slab + caulk grooves (not 25 identical plank boxes).
    box(white, (3.35, 0.16, 1.95), (0, 0.20, -2.15), 0.12)
    box(dark, (3.22, 0.02, 1.82), (0, 0.295, -2.15), 0.05)
    box(wood, (3.15, 0.03, 1.76), (0, 0.318, -2.15), 0.02)
    for i in range(1, 12):
        box(dark, (0.012, 0.012, 1.72), (-1.45 + i * 0.24, 0.332, -2.15), 0)

    # Side seats / lockers follow the sheer instead of tall square boxes.
    for side in (-1, 1):
        box(white, (0.55, 0.62, 2.8), (side * 1.38, 0.68, 0.35), 0.04)
        box(white, (0.70, 0.38, 1.35), (side * 1.05, 0.58, -0.35), 0.04)
        box(dark, (0.66, 0.02, 1.28), (side * 1.05, 0.78, -0.35), 0.05)
        box(white, (0.66, 0.07, 1.28), (side * 1.05, 0.82, -0.35), 0.03)
        tube(steel, [(side * 1.52, 1.05, 1.7), (side * 1.55, 1.22, 0.2),
                     (side * 1.52, 1.05, -1.1)], 0.022)

    # Ladder on starboard transom corner.
    for x in (1.05, 1.52):
        tube(steel, [(x, 0.32, -3.0), (x, 0.95, -3.05), (x, 1.05, -3.15),
                     (x, 0.9, -3.15), (x, -0.55, -3.2)], 0.024)
    for y in (-0.45, -0.15, 0.15):
        box(steel, (0.5, 0.04, 0.16), (1.28, y, -3.2), 0.012)
        box(dark, (0.4, 0.01, 0.12), (1.28, y + 0.025, -3.2), 0.006)

    # Umbilical coil + chafe sleeve + closed safety lanyard.
    points = []
    for i in range(320):
        a = i / 319 * math.pi * 10
        r = 0.26 + i / 319 * 0.1
        points.append((1.12 + r * math.cos(a), 0.34 + i / 319 * 0.05, -1.35 + r * math.sin(a)))
    tube(yellow, points, 0.008)
    tube(yellow, [points[-1], (1.2, 0.33, -1.85), (0.7, 0.33, -2.7)], 0.008)
    tube(dark, [(0.7, 0.34, -2.7), (0.7, 0.34, -3.0)], 0.02)
    tube(rope, [(-1.5, .4, -1.2), (-1.3, .34, -1.7), (-1.05, .34, -1.8),
                (-1.18, .34, -1.4), (-1.5, .4, -1.2)], .012)
    tube(steel, [(-1.55, .34, -1.2), (-1.55, .42, -1.2), (-1.45, .42, -1.2),
                 (-1.45, .34, -1.2)], .015)

    # Outboard: cowling + midsection + anti-ventilation plate + lower unit + prop.
    box(white, (0.55, 0.55, 0.22), (1.28, 0.72, -1.25), 0.04)
    box(dark, (0.42, 0.55, 0.48), (1.92, 0.48, -1.25), 0.05)
    box(steel, (0.18, 0.08, 0.32), (1.92, 0.12, -1.25), 0.01)
    box(steel, (0.14, 0.72, 0.18), (1.92, -0.28, -1.25), 0.02)
    tube(steel, [(1.92, -0.62, -1.25), (1.92, -0.62, -1.55)], 0.055)
    for i in range(3):
        a = i * math.tau / 3
        tube(dark, [(1.92, -0.62, -1.55),
                    (1.92 + 0.18 * math.cos(a), -0.62 + 0.18 * math.sin(a), -1.55)], 0.035)

    # Helm console with a slight forward rake; wheel with rim + hub.
    box(white, (1.05, 0.78, 0.55), (0.55, 0.78, 1.85), 0.05)
    box(dark, (1.0, 0.06, 0.58), (0.55, 1.2, 1.85), 0.03)
    glass = kit.Part('Windshield', kit.make_material('SmokedGlass', (.05, .12, .15), rough=.18, metal=.2))
    box(glass, (2.4, 0.55, 0.04), (0, 1.52, 2.25), 0.02)
    for x in (-1.15, 0, 1.15):
        tube(steel, [(x, 1.2, 2.25), (x, 1.85, 2.25)], 0.022)
    tube(steel, [(-1.15, 1.85, 2.25), (1.15, 1.85, 2.25)], 0.022)
    steel.add_bmesh(kit.torus(0.2, 0.016, center=point((0.58, 1.18, 1.55)), axis=(0, 1, 0.35)))
    for i in range(5):
        a = i * math.tau / 5
        tube(steel, [(0.58, 1.18, 1.55),
                     (0.58 + 0.18 * math.cos(a), 1.18 + 0.05 * math.sin(a), 1.55 + 0.18 * math.sin(a))], 0.01)
    box(steel, (0.12, 0.5, 0.12), (0.58, 0.62, 0.95))
    box(dark, (0.58, 0.12, 0.55), (0.58, 0.9, 0.95), 0.03)
    box(dark, (0.58, 0.48, 0.1), (0.58, 1.15, 0.7), 0.03)

    # Chart table fully inside the cabin (port), not overhanging the gunwale.
    box(wood, (0.9, 0.06, 1.1), (-0.7, 0.98, 1.35))
    for z in (0.95, 1.75):
        tube(steel, [(-0.7, 0.35, z), (-0.7, 0.95, z)], 0.03)

    # Controller case and accessories.
    box(dark, (0.7, 0.12, 0.42), (0.15, 1.28, 1.85))
    box(dark, (0.7, 0.42, 0.06), (0.15, 1.52, 2.08))
    for x in (-0.08, 0.38):
        tube(steel, [(x, 1.34, 1.82), (x, 1.45, 1.82)], 0.022)
        box(dark, (0.08, 0.035, 0.08), (x, 1.46, 1.82))
    box(dark, (0.11, 0.22, 0.06), (0.95, 1.35, 1.95))
    tube(dark, [(0.95, 1.45, 1.95), (0.95, 1.68, 1.95)], 0.007)
    tube(steel, [(1.08, 1.22, 1.75), (1.08, 1.45, 1.75)], 0.05)

    blank = kit.save_image(Path(output).with_suffix('.display.png'), np.ones((2, 2, 3)) * 0.8)

    def plane(name, center, width, height, vertical=True):
        mesh = bpy.data.meshes.new(name)
        x, y, z = center
        coords = [(x - width / 2, y - height / 2, z), (x + width / 2, y - height / 2, z),
                  (x + width / 2, y + height / 2, z), (x - width / 2, y + height / 2, z)]
        if not vertical:
            coords = [(x - width / 2, y, z - height / 2), (x + width / 2, y, z - height / 2),
                      (x + width / 2, y, z + height / 2), (x - width / 2, y, z + height / 2)]
        mesh.from_pydata([point(v) for v in coords], [], [(0, 1, 2, 3)])
        uv = mesh.uv_layers.new()
        for loop, xy in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            loop.uv = xy
        mesh.materials.append(kit.make_material(name, (.12, .24, .29), rough=.5, textures={'base': blank}))
        ob = bpy.data.objects.new(name, mesh)
        collection.objects.link(ob)
        ob.parent = root
        return ob

    plane('screen_main', (0.15, 1.52, 2.06), 0.6, 0.34)
    plane('screen_log', (-0.7, 1.03, 1.25), 0.4, 0.5, False)
    # Gallery on the forward cabin bulkhead facing aft — inside the beam.
    box(wood, (1.05, 0.7, 0.05), (-0.55, 1.45, 2.15))
    plane('frame_licence', (-0.85, 1.58, 2.12), 0.38, 0.34)
    for i in range(6):
        plane('photo_wall_' + str(i), (-0.4 + (i % 2) * 0.26, 1.68 - (i // 2) * 0.2, 2.12), 0.22, 0.16)
    for i in range(6):
        x = -1.05 + (i % 3) * 0.28
        z = -0.5 + (i // 3) * 0.35
        box(dark, (0.24, 0.11, 0.28), (x, 0.95, z))
        anchor('gear_slot_' + str(i), x, 1.02, z)

    # Diamond-plate sole panels (fewer, larger) so the pattern reads at menu distance.
    for i in range(6):
        box(grip, (1.05, 0.004, 0.55), (0.05, 0.412, -0.7 + i * 0.58), 0)
    box(grip, (0.55, 0.004, 1.5), (1.1, 0.412, -2.1), 0)

    glass.obj(collection, root)
    grip.obj(collection, root)
    rusty.obj(collection, root)
    antifoul.obj(collection, root)
    for part in (white, dark, steel, yellow, rope, wood):
        part.obj(collection, root)
    for name, position in {
        'anchor_cockpit': (-0.85, 2.05, 0.15), 'target_cockpit': (0.4, 1.25, 1.9),
        'anchor_platform': (0, 3.4, 0.15), 'target_platform': (0, 0.4, -2.15),
        'anchor_logbook': (0.2, 1.95, 0.45), 'target_logbook': (-0.7, 1.25, 1.55),
        'anchor_horizon': (0, 2.0, 3.2), 'target_horizon': (0, 5, 90),
        'rov_slot_0': (-0.75, 0.35, -2.2), 'rov_slot_1': (0.7, 0.35, -2.2),
        'menu_camera': (0, 3.15, 0.3), 'menu_target': (0, 0.35, -2.2),
        'TetherExit': (1.25, 0.38, -1.7), 'TetherDrum': (1.25, 0.38, -1.7),
        'hand_left': (-1.05, 1.05, -1.55), 'hand_right': (-0.4, 1.05, -1.55),
        'water_entry': (-0.75, 0, -3.55),
        'lifebuoy_slot': (1.48, 1.05, -0.7),
        # Far of the swim platform: ocean_buoy is a ~2.7 m nav mark, not a deck prop.
        'buoy_slot': (14.0, 0.0, -22.0),
    }.items():
        anchor(name, *position)
    triangles = kit.triangle_count(bpy.data.objects)
    assert triangles <= 60000, triangles
    kit.export_glb(output)
    print('Small boat triangles:', triangles)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    build(args[0])
