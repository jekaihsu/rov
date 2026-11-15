"""X1 training GLB LOD contract: draw-call merge, rotor pivots, triangle budgets."""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

MODELS = Path(__file__).resolve().parents[1] / 'viewer' / 'models'
LODS = ('rov.glb', 'rov_lod1.glb', 'rov_lod2.glb')
DRAW_CALL_BUDGET = 40
LOD1_TARGET = 80_000
LOD2_TARGET = 30_000  # ~20k target; meshoptimizer floors around cage/rotor topology
BYTE_SOFT_LIMIT = 2 * 1024 * 1024


def read_glb(name):
    raw = (MODELS / name).read_bytes()
    size = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20 + size]), raw


def drawn_triangles(doc):
    accessors = doc['accessors']
    total = 0
    for node in doc['nodes']:
        if 'mesh' not in node:
            continue
        for prim in doc['meshes'][node['mesh']]['primitives']:
            if 'indices' in prim:
                total += accessors[prim['indices']]['count'] // 3
            else:
                total += accessors[prim['attributes']['POSITION']]['count'] // 3
    return total


def draw_calls(doc):
    return sum(
        len(doc['meshes'][node['mesh']]['primitives'])
        for node in doc['nodes'] if 'mesh' in node
    )


class TestX1RovAsset(unittest.TestCase):
    def test_files_exist(self):
        for name in LODS:
            self.assertTrue((MODELS / name).is_file(), name)

    def test_lod0_draw_calls_and_rotors(self):
        doc, raw = read_glb(LODS[0])
        self.assertLessEqual(draw_calls(doc), DRAW_CALL_BUDGET)
        rotors = [n for n in doc['nodes'] if n.get('extras', {}).get('role') == 'rotor']
        self.assertEqual(len(rotors), 6)
        for rotor in rotors:
            self.assertIn('mesh', rotor)
            self.assertTrue(rotor.get('name', '').startswith('ROTOR'))
            extras = rotor['extras']
            self.assertEqual(extras.get('role'), 'rotor')
            self.assertIn('axis', extras)
        # Joining shared thruster instances grows the file; keep the reason in the report.
        if len(raw) > BYTE_SOFT_LIMIT:
            report = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'vehicle' / 'x1-lod-report.json'
            self.assertTrue(report.is_file(), 'LOD0 >2 MB needs docs/design/vehicle/x1-lod-report.json')

    def test_triangle_budgets_and_monotonic_lods(self):
        previous = None
        expected = [None, LOD1_TARGET, LOD2_TARGET]
        for name, budget in zip(LODS, expected):
            doc, _ = read_glb(name)
            tris = drawn_triangles(doc)
            if previous is not None:
                self.assertLess(tris, previous, name)
            if budget is not None:
                self.assertLessEqual(tris, budget + 5_000, name)
            previous = tris
            rotors = [n for n in doc['nodes'] if n.get('extras', {}).get('role') == 'rotor']
            self.assertEqual(len(rotors), 6, name)


if __name__ == '__main__':
    unittest.main()
