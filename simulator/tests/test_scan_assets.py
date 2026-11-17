"""Scanned seabed, steel and rock assets (viewer/models/scan/, built by tools/build_scan_materials.py).

Checks the shipped files against their budgets and credits, and the rock levels against the containment the
viewer relies on: rock armour scales each scan from the unit sphere inside its collision capsule, so every vertex
must lie inside the unit sphere; habitat rocks fit the scan round the collision sphere from its inner radius.
"""
import json
import re
import struct
import subprocess
import unittest
from pathlib import Path

import numpy as np

VIEWER = Path(__file__).resolve().parents[1] / 'viewer'
SCAN = VIEWER / 'models/scan'
MAX_FILE_BYTES = 600 * 1024
LOD_TRIANGLES = (1200, 320, 96)
TEXTURES = ('sand', 'shell', 'gravel', 'mud', 'rockbed', 'coating', 'rust', 'concrete', 'plate', 'grating', 'rocks')


def read_glb(path):
    data = path.read_bytes()
    if b'EXT_meshopt_compression' in data:
        script = Path(__file__).resolve().parents[1] / 'tools' / 'decode_meshopt.mjs'
        data = subprocess.check_output(['node', str(script), str(path)])
    magic, version, _ = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67 and version == 2
    length, _ = struct.unpack_from('<II', data, 12)
    document = json.loads(data[20:20 + length])
    offset = 20 + length
    bin_length, _ = struct.unpack_from('<II', data, offset)
    return document, data[offset + 8:offset + 8 + bin_length]


def accessor(document, binary, index):
    item = document['accessors'][index]
    view = document['bufferViews'][item['bufferView']]
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[item['type']]
    dtype = {5126: np.float32, 5123: np.uint16}[item['componentType']]
    start = view.get('byteOffset', 0) + item.get('byteOffset', 0)
    return np.frombuffer(binary, dtype=dtype, count=item['count'] * width, offset=start).reshape(-1, width)


class ScanAssetTest(unittest.TestCase):
    def test_files_are_small_and_credited(self):
        credits = (VIEWER / 'models/CREDITS.md').read_text(encoding='utf-8')
        files = sorted(SCAN.iterdir())
        self.assertTrue(files)
        for path in files:
            self.assertLessEqual(path.stat().st_size, MAX_FILE_BYTES, path.name)
            self.assertIn(f'`{path.name}`', credits, f'{path.name} is not listed in CREDITS.md')
        names = {path.name for path in files}
        for texture in TEXTURES:
            self.assertIn(f'{texture}_c.webp', names)
            self.assertIn(f'{texture}_n.webp', names)
        self.assertIn('ripple_n.webp', names)
        self.assertIn('macro_c.webp', names)

    def test_viewer_requests_only_shipped_textures(self):
        names = {path.stem for path in SCAN.glob('*.webp')}
        sources = ''.join(path.read_text(encoding='utf-8') for path in VIEWER.glob('*.js'))
        literal = set(re.findall(r"scan(?:Texture|Uniform)\('([a-z_]+)'", sources))
        self.assertTrue(literal)
        self.assertLessEqual(literal, names)

    def test_rock_levels_stay_inside_the_unit_sphere(self):
        document, binary = read_glb(SCAN / 'rocks.glb')
        rocks = {}
        for node in document['nodes']:
            extras = node['extras']
            primitive = document['meshes'][node['mesh']]['primitives'][0]
            position = accessor(document, binary, primitive['attributes']['POSITION'])
            uv = accessor(document, binary, primitive['attributes']['TEXCOORD_0'])
            index = accessor(document, binary, primitive['indices'])
            radius = np.linalg.norm(position, axis=1)
            self.assertLessEqual(radius.max(), 1.0 + 1e-5, node['name'])
            self.assertGreater(radius.max(), 0.9, node['name'])    # bounding radius is over all levels
            self.assertLessEqual(len(index) // 3, LOD_TRIANGLES[extras['lod']] * 1.05, node['name'])
            self.assertTrue(((uv >= 0) & (uv <= 1)).all(), node['name'])
            self.assertLess(index.max(), len(position))
            rocks.setdefault(extras['rock'], []).append(extras)
        # the viewer's habitat (rock_07, rock_09, stone_01) and armour (boulder_01, rock_09) scans, three levels
        self.assertEqual(sorted(rocks), ['boulder_01', 'rock_07', 'rock_09', 'stone_01'])
        for rock, levels in rocks.items():
            self.assertEqual(sorted(level['lod'] for level in levels), [0, 1, 2], rock)
            self.assertTrue(0.35 < levels[0]['inner'] < 1, rock)

    def test_habitat_fit_keeps_the_rock_close_to_its_collider(self):
        # scale 1.2 / (1 + inner) about a sphere of radius 0.6: visual and collision differ by at most this much
        document, _ = read_glb(SCAN / 'rocks.glb')
        for node in document['nodes']:
            if node['extras']['rock'] == 'boulder_01':
                continue
            inner = node['extras']['inner']
            excess = 0.6 * (1 - inner) / (1 + inner)
            self.assertLess(excess, 0.2, node['name'])


if __name__ == '__main__':
    unittest.main()
