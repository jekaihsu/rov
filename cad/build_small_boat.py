"""Original swim-platform stern, metres, Blender Z up; no reference image input.

blender -b --python cad/build_small_boat.py -- /tmp/small_boat.glb
python -c "from simulator.tools.build_support_assets import compress; from pathlib import Path; \
compress(Path('/tmp/small_boat.glb'), Path('simulator/viewer/models/small_boat.glb'), ())"
No .blend is saved. Geometry/texture copyright dedicated to CC0 by this contribution.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import support_assets_lib as kit


def build(output):
    collection = kit.reset_scene()
    root = bpy.data.objects.new('SmallBoat', None)
    collection.objects.link(root)
    for key, value in dict(length=5.8, deckY=0.28, sternZ=-2.9, transomY=0.28).items():
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

    def box(part, size, center, bevel=0.03):
        part.add_bmesh(kit.box((size[0], size[2], size[1]), point(center), bevel=bevel, segments=3))

    def tube(part, points, radius=0.02):
        part.add_bmesh(kit.sweep([point(p) for p in points], radius=radius, seg=10))

    white = kit.Part('Fibreglass', kit.make_material('Gelcoat', (0.88, 0.9, 0.89), rough=0.23))
    dark = kit.Part('SeamsAndRubber', kit.make_material('Rubber', (0.018, 0.024, 0.028), rough=0.8))
    steel = kit.Part('Stainless', kit.make_material('Stainless', (0.55, 0.61, 0.65), metal=0.65, rough=0.22))
    yellow = kit.Part('CoiledUmbilical', kit.make_material('FluorescentLime', (0.65, 0.95, 0.005), rough=0.45))
    rope = kit.Part('SafetyLanyard', kit.make_material('WovenSafetyLine', (0.14, 0.19, 0.24), rough=0.9))
    tex = Path(output).with_suffix('.teak.png')
    rng = np.random.default_rng(3)
    grain = rng.random((512, 64))
    grain = np.repeat(grain, 8, axis=1)
    rgb = np.stack([0.67 + grain * 0.1, 0.38 + grain * 0.08, 0.17 + grain * 0.05], axis=-1)
    kit.save_image(tex, rgb)
    wood = kit.Part('TeakPlanks', kit.make_material('Teak', (1, 1, 1), rough=0.65, textures={'base': tex}), uv_tile=1)
    box(white, (3.55, 0.65, 4.3), (0, -0.18, 0.65), 0.22)
    box(white, (3.4, 0.18, 2.0), (0, 0.17, -1.9), 0.15)
    box(dark, (3.28, 0.025, 1.84), (0, 0.265, -1.9), 0.07)
    for i in range(25):
        box(wood, (0.122, 0.025, 1.77), (-1.56 + i * 0.13, 0.282, -1.9), 0.012)
    for side in (-1, 1):
        box(white, (0.62, 0.95, 3.1), (side * 1.47, 0.62, 0.65), 0.16)
        box(white, (0.78, 0.43, 1.45), (side * 1.1, 0.53, -0.28), 0.1)
        box(dark, (0.74, 0.02, 1.38), (side * 1.1, 0.755, -0.28), 0.06)
        box(white, (0.74, 0.09, 1.38), (side * 1.1, 0.8, -0.28), 0.08)
        tube(steel, [(side * 1.6, 1.1, 1.9), (side * 1.6, 1.25, 0.4),
                     (side * 1.6, 1.05, -0.9)], 0.023)
        box(steel, (0.14, 0.025, 0.045), (side * 1.1, 0.86, -0.65), 0.008)
    # Ladder aft, between the two parking spots.
    for x in (-0.26, 0.26):
        tube(steel, [(x, 0.29, -2.45), (x, 0.9, -2.55), (x, 1.0, -2.72),
                     (x, 0.9, -2.96), (x, -0.65, -3.03)], 0.025)
    for y in (-0.55, -0.25, 0.05):
        box(steel, (0.55, 0.045, 0.18), (0, y, -3.03), 0.015)
        box(dark, (0.45, 0.012, 0.13), (0, y + 0.028, -3.03), 0.008)
    points = []
    for i in range(401):
        a = i / 400 * math.pi * 12
        r = 0.28 + i / 400 * 0.12
        points.append((1.15 + r * math.cos(a), 0.32 + i / 400 * 0.07, -1.25 + r * math.sin(a)))
    tube(yellow, points, 0.008)
    tube(yellow, [points[-1], (1.25, 0.31, -1.7), (0.7, 0.31, -2.5)], 0.008)
    tube(dark, [(0.7, 0.32, -2.5), (0.7, 0.32, -2.88)], 0.02)
    tube(rope, [(-1.55, 0.35, -1.1), (-1.35, 0.31, -1.6), (-0.9, 0.31, -1.8)], 0.012)
    for part in (white, dark, steel, yellow, rope, wood):
        part.obj(collection, root)
    for name, position in {
        'rov_slot_0': (-0.78, 0.3, -2.02), 'rov_slot_1': (0.72, 0.3, -2.02),
        'menu_camera': (0, 3.25, 0.4), 'menu_target': (0, 0.3, -2.05),
        'TetherExit': (1.3, 0.35, -1.55), 'TetherDrum': (1.3, 0.35, -1.55),
        'hand_left': (-1.1, 1.1, -1.4), 'hand_right': (-0.45, 1.1, -1.4),
        'water_entry': (-0.78, 0, -3.45),
    }.items():
        anchor(name, *position)
    triangles = kit.triangle_count(bpy.data.objects)
    assert triangles <= 60000, triangles
    kit.export_glb(output)
    print('Small boat triangles:', triangles)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    build(args[0])
