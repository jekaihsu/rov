"""Original swim-platform stern, metres, Blender Z up; no reference image input.

Materials: CC0 Poly Haven / ambientCG scans from simulator/viewer/models/boat/ (teak, gelcoat paint,
diamond plate) plus rust/coating copies; rebuild those with simulator/tools/build_boat_scan_materials.py.
Hull and deck geometry remain original procedural work. Lifebuoy prop is appended from the CC0 Poly Haven
model (stencil text scrubbed at build time).

blender -b --python cad/build_small_boat.py -- /tmp/small_boat.glb
python -c "from simulator.tools.build_support_assets import compress; from pathlib import Path; \
compress(Path('/tmp/small_boat.glb'), Path('simulator/viewer/models/small_boat.glb'), ())"
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
def scan_textures(stem):
    """Load boat/ WebP maps (base + normal; roughness lives in the normal map's alpha)."""
    from PIL import Image

    base = BOAT_MATS / f'{stem}_c.webp'
    normal = BOAT_MATS / f'{stem}_n.webp'
    if not base.is_file():
        raise FileNotFoundError(f'Missing {base}; run simulator/tools/build_boat_scan_materials.py first')
    work = Path(bpy.app.tempdir)
    # Blender's image loader is happier with PNG paths for the ORM split.
    base_png = work / f'{stem}_c.png'
    normal_png = work / f'{stem}_n.png'
    orm_png = work / f'{stem}_orm.png'
    Image.open(base).convert('RGB').save(base_png)
    n_img = Image.open(normal).convert('RGBA')
    n_img.save(normal_png)
    alpha = np.asarray(n_img.split()[-1], dtype=np.uint8)
    orm = np.zeros((alpha.shape[0], alpha.shape[1], 3), dtype=np.uint8)
    orm[..., 1] = alpha
    Image.fromarray(orm, 'RGB').save(orm_png)
    return {'base': base_png, 'normal': normal_png, 'orm': orm_png}


def build(output):
    collection = kit.reset_scene()
    root = bpy.data.objects.new('SmallBoat', None)
    collection.objects.link(root)
    for key, value in dict(length=8.8, deckY=0.28, sternZ=-2.9, transomY=0.28).items():
        root[key] = value

    def anchor(name, x, y, z):
        node = bpy.data.objects.new(name, None)
        collection.objects.link(node)
        node.parent = root
        node.location = (x, -z, y)
        return node

    # Coordinate adapter: all modelling below uses the viewer's Y-up frame.
    def point(p):
        return (p[0], -p[2], p[1])

    def box(part, size, center, bevel=0.012):
        part.add_bmesh(kit.box((size[0], size[2], size[1]), point(center), bevel=bevel, segments=2))

    def tube(part, points, radius=0.02):
        part.add_bmesh(kit.sweep([point(p) for p in points], radius=radius, seg=10))

    paint = scan_textures('paint')
    plate = scan_textures('plate')
    teak = scan_textures('teak')
    rust = scan_textures('rust')
    white = kit.Part('Fibreglass', kit.make_material('Gelcoat', (0.92, 0.93, 0.91),
                     rough=0.34, textures=paint), uv_tile=1.6)
    dark = kit.Part('SeamsAndRubber', kit.make_material('Rubber', (0.018, 0.024, 0.028), rough=0.8))
    steel = kit.Part('Stainless', kit.make_material('Stainless', (0.55, 0.61, 0.65), metal=0.65, rough=0.22))
    rusty = kit.Part('RustAccents', kit.make_material('Rust', (1, 1, 1), rough=0.85, textures=rust), uv_tile=0.7)
    yellow = kit.Part('CoiledUmbilical', kit.make_material('FluorescentLime', (0.65, 0.95, 0.005), rough=0.45))
    rope = kit.Part('SafetyLanyard', kit.make_material('WovenSafetyLine', (0.14, 0.19, 0.24), rough=0.9))
    wood = kit.Part('TeakPlanks', kit.make_material('Teak', (1, 1, 1), rough=0.62, textures=teak), uv_tile=1.2)
    grip = kit.Part('NonSlip', kit.make_material('NonSlipPlate', (1, 1, 1), rough=0.9, metal=0.35,
                    textures=plate), uv_tile=0.55)
    # Hard-chine hull: fine bow entry, flared topsides and a closed transom.
    sections = [(-1.05, 1.65), (0, 1.67), (1.8, 1.6), (3.2, 1.38), (4.5, 0.85), (5.6, 0.025)]
    hull = bmesh.new()
    rings = []
    for z, width in sections:
        rings.append([hull.verts.new(point(v)) for v in [
            (-width, 0.95, z), (-width * .92, -.15, z), (-width * .62, -.65, z),
            (0, -.85, z), (width * .62, -.65, z), (width * .92, -.15, z), (width, .95, z)]])
    for a, b in zip(rings, rings[1:]):
        for i in range(6):
            hull.faces.new([a[i], b[i], b[i + 1], a[i + 1]])
    hull.faces.new(rings[0][::-1])
    hull.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(hull, faces=list(hull.faces))
    white.add_bmesh(hull)
    box(white, (3.12, .12, 4.2), (0, .24, 1.05))
    for side in (-1, 1):
        tube(dark, [(side * w, .87, z) for z, w in sections], .045)
        tube(steel, [(side * w, 1.28, z) for z, w in sections[1:]], .022)
        for z, w in sections[1:-1]:
            tube(steel, [(side * w, .94, z), (side * w, 1.28, z)], .018)
        # Light rust weep under the gunwale and on the transom corners.
        box(rusty, (0.08, 0.02, 0.35), (side * 1.55, 0.88, -1.7), 0.01)
    # Foredeck tapers with the bow rather than extending as a rectangular platform.
    deck = bmesh.new()
    ring = [deck.verts.new(point((side * w, .96, z)))
            for side, seq in [(1, sections[3:]), (-1, sections[3:][::-1])] for z, w in seq]
    deck.faces.new(ring)
    white.add_bmesh(deck)
    box(white, (3.4, 0.18, 2.0), (0, 0.17, -1.9), 0.15)
    box(dark, (3.28, 0.025, 1.84), (0, 0.265, -1.9), 0.07)
    for i in range(25):
        box(wood, (0.122, 0.025, 1.77), (-1.56 + i * 0.13, 0.282, -1.9), 0.012)
    for side in (-1, 1):
        box(white, (0.62, 0.95, 3.1), (side * 1.47, 0.62, 0.65), 0.025)
        box(white, (0.78, 0.43, 1.45), (side * 1.1, 0.53, -0.28), 0.025)
        box(dark, (0.74, 0.02, 1.38), (side * 1.1, 0.755, -0.28), 0.06)
        box(white, (0.74, 0.09, 1.38), (side * 1.1, 0.8, -0.28), 0.025)
        tube(steel, [(side * 1.6, 1.1, 1.9), (side * 1.6, 1.25, 0.4),
                     (side * 1.6, 1.05, -0.9)], 0.023)
        box(steel, (0.14, 0.025, 0.045), (side * 1.1, 0.86, -0.65), 0.008)
    # Ladder aft, between the two parking spots.
    for x in (1.05, 1.57):
        tube(steel, [(x, 0.29, -2.83), (x, 0.9, -2.86), (x, 1.0, -2.96),
                     (x, 0.9, -2.96), (x, -0.65, -3.03)], 0.025)
    for y in (-0.55, -0.25, 0.05):
        box(steel, (0.55, 0.045, 0.18), (1.31, y, -3.03), 0.015)
        box(dark, (0.45, 0.012, 0.13), (1.31, y + 0.028, -3.03), 0.008)
    points = []
    for i in range(401):
        a = i / 400 * math.pi * 12
        r = 0.28 + i / 400 * 0.12
        points.append((1.15 + r * math.cos(a), 0.32 + i / 400 * 0.07, -1.25 + r * math.sin(a)))
    tube(yellow, points, 0.008)
    tube(yellow, [points[-1], (1.25, 0.31, -1.7), (0.7, 0.31, -2.5)], 0.008)
    tube(dark, [(0.7, 0.32, -2.5), (0.7, 0.32, -2.88)], 0.02)
    tube(rope, [(-1.55, .37, -1.1), (-1.35, .31, -1.6), (-1.1, .31, -1.7),
                (-1.22, .31, -1.3), (-1.55, .37, -1.1)], .012)
    tube(steel, [(-1.6, .32, -1.1), (-1.6, .39, -1.1), (-1.5, .39, -1.1),
                 (-1.5, .32, -1.1)], .016)
    # Engine well and transom wings leave the central manual launch lane clear.
    box(white, (.62, .75, .18), (1.31, .62, -1.04))
    box(dark, (.48, .65, .57), (1.95, .39, -1.05), .045)
    box(steel, (.16, .9, .22), (1.95, -.32, -1.05))
    tube(steel, [(1.95, -.68, -1.05), (1.95, -.68, -1.4)], .075)
    for i in range(3):
        a = i * math.tau / 3
        tube(dark, [(1.95, -.68, -1.4), (1.95 + .2 * math.cos(a), -.68 + .2 * math.sin(a), -1.4)], .045)
    # Console, sloping windshield, helm, seat and the port chart table.
    box(white, (1.22, .85, .6), (.65, .72, 2.1))
    box(dark, (1.18, .08, .64), (.65, 1.17, 2.1))
    glass = kit.Part('Windshield', kit.make_material('SmokedGlass', (.065, .16, .19), rough=.19, metal=.25))
    box(glass, (2.8, .67, .035), (0, 1.58, 2.5))
    for x in (-1.4, 0, 1.4):
        tube(steel, [(x, 1.22, 2.5), (x, 1.95, 2.5)], .025)
    tube(steel, [(-1.4, 1.95, 2.5), (1.4, 1.95, 2.5)], .025)
    steel.add_bmesh(kit.torus(.22, .018, center=point((.72, 1.13, 1.72)), axis=(0, 1, .4)))
    for i in range(3):
        a = i * math.tau / 3
        tube(steel, [(.72, 1.13, 1.72), (.72 + .21 * math.cos(a), 1.13 + .21 * math.sin(a), 1.72)], .012)
    box(steel, (.13, .58, .13), (.7, .56, .95))
    box(dark, (.65, .13, .62), (.7, .87, .95), .025)
    box(dark, (.65, .53, .1), (.7, 1.15, .65), .025)
    box(wood, (1.02, .07, 1.3), (-.85, .96, 1.48))
    for z in (1, 1.95):
        tube(steel, [(-.85, .3, z), (-.85, .94, z)], .035)
    # Open rugged controller case and portable accessories; no baked language or logos.
    box(dark, (.75, .13, .45), (.15, 1.25, 2.05))
    box(dark, (.75, .48, .07), (.15, 1.51, 2.29))
    for x in (-.1, .4):
        tube(steel, [(x, 1.32, 2), (x, 1.43, 2)], .025)
        box(dark, (.09, .04, .09), (x, 1.44, 2))
    box(dark, (.12, .24, .065), (1.04, 1.33, 2.12))
    tube(dark, [(1.04, 1.44, 2.12), (1.04, 1.69, 2.12)], .008)
    tube(steel, [(1.18, 1.21, 1.93), (1.18, 1.47, 1.93)], .055)
    box(dark, (.5, .035, .65), (-.85, 1.02, 1.35))
    box(white, (.46, .018, .61), (-.85, 1.045, 1.35))
    tube(steel, [(-.5, 1.02, 1.2), (-.5, 1.02, 1.5)], .008)
    box(white, (.06, 1.15, 1.5), (-1.39, 1.48, 1.45))
    # UV 0-1 replaceable display surfaces, kept as separate named meshes.
    blank = kit.save_image(Path(output).with_suffix('.display.png'), np.ones((2, 2, 3)) * .8)

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

    plane('screen_main', (.15, 1.51, 2.245), .65, .37)
    plane('screen_log', (-.85, 1.058, 1.35), .43, .57, False)
    # Gallery mounted on forward bulkhead, facing aft.
    box(wood, (1.2, .75, .06), (-.78, 1.55, 2.44))
    plane('frame_licence', (-1.02, 1.68, 2.4), .42, .37)
    for i in range(6):
        plane('photo_wall_' + str(i), (-.6 + (i % 2) * .27, 1.78 - (i // 2) * .21, 2.4), .23, .17)
    # Rack pockets with individual equipment attachment nodes.
    for i in range(6):
        x = -1.12 + (i % 3) * .28
        z = -.4 + (i // 3) * .35
        box(dark, (.25, .12, .3), (x, .91, z))
        anchor('gear_slot_' + str(i), x, .98, z)
    # Diamond-plate anti-slip on the cockpit sole and traffic lanes.
    for i in range(12):
        box(grip, (.95, .004, .28), (.05, .308, -.95 + i * .29), 0)
    box(grip, (0.55, 0.004, 1.6), (1.15, 0.308, -1.9), 0)
    glass.obj(collection, root)
    grip.obj(collection, root)
    rusty.obj(collection, root)
    for part in (white, dark, steel, yellow, rope, wood):
        part.obj(collection, root)
    for name, position in {
        'anchor_cockpit': (-.9, 2.15, .2), 'target_cockpit': (.45, 1.3, 2.05),
        'anchor_platform': (0, 3.5, .25), 'target_platform': (0, .35, -1.9),
        'anchor_logbook': (.25, 2.05, .5), 'target_logbook': (-.85, 1.3, 1.75),
        'anchor_horizon': (0, 2.1, 3.5), 'target_horizon': (0, 6, 100),
        'rov_slot_0': (-0.78, 0.3, -2.02), 'rov_slot_1': (0.72, 0.3, -2.02),
        'menu_camera': (0, 3.25, 0.4), 'menu_target': (0, 0.3, -2.05),
        'TetherExit': (1.3, 0.35, -1.55), 'TetherDrum': (1.3, 0.35, -1.55),
        'hand_left': (-1.1, 1.1, -1.4), 'hand_right': (-0.45, 1.1, -1.4),
        'water_entry': (-0.78, 0, -3.45),
        # Runtime props (CC0 Poly Haven) attach here — see menu/boat_stage.js.
        'lifebuoy_slot': (1.55, 1.15, -0.55),
        'buoy_slot': (3.2, 0.0, -1.0),
    }.items():
        anchor(name, *position)
    triangles = kit.triangle_count(bpy.data.objects)
    assert triangles <= 60000, triangles
    kit.export_glb(output)
    print('Small boat triangles:', triangles)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    build(args[0])
