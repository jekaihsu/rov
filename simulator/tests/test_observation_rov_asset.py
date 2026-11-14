"""Contract checks for the original observation ROV visual (generic asset set) against the x1 physics."""
import json
import re
import struct
import unittest
from pathlib import Path

import numpy as np

from qysim.vehicles import get_vehicle_definition

MODELS = Path(__file__).resolve().parents[1] / 'viewer' / 'models'
LODS = ('observation_rov.glb', 'observation_rov_lod1.glb', 'observation_rov_lod2.glb')
# Manufacturer or model names that must not appear in the generic asset (AGENTS.md brand rule).
BRANDS = re.compile(r'qysea|fifish|blue ?robotics|bluerov|saab|seaeye|falcon|chasing|deep ?trekker|\bx1\b', re.I)


def read_glb(name):
    raw = (MODELS / name).read_bytes()
    length = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20 + length]), raw


def node_matrix(node):
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    rotation = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation @ np.diag(node.get('scale', [1, 1, 1]))
    matrix[:3, 3] = node.get('translation', [0, 0, 0])
    return matrix


def world_matrices(doc):
    result = {}

    def visit(index, parent):
        node = doc['nodes'][index]
        matrix = parent @ node_matrix(node)
        result[index] = matrix
        for child in node.get('children', []):
            visit(child, matrix)

    for index in doc['scenes'][doc.get('scene', 0)]['nodes']:
        visit(index, np.eye(4))
    return result


def three(frd):
    return np.array([-frd[1], -frd[2], frd[0]])


def drawn_triangles(doc):
    per_mesh = []
    for mesh in doc['meshes']:
        count = 0
        for primitive in mesh['primitives']:
            count += doc['accessors'][primitive['indices']]['count'] // 3
        per_mesh.append(count)
    return sum(per_mesh[node['mesh']] for node in doc['nodes'] if 'mesh' in node)


class TestObservationRovAsset(unittest.TestCase):
    definition = get_vehicle_definition('x1')

    def test_rotors_match_x1_thrusters_in_every_lod(self):
        for name in LODS:
            with self.subTest(lod=name):
                doc, _ = read_glb(name)
                worlds = world_matrices(doc)
                rotors = {}
                for index, node in enumerate(doc['nodes']):
                    if node.get('extras', {}).get('role') == 'rotor':
                        rotors[node['extras']['thruster_index']] = worlds[index]
                self.assertEqual(sorted(rotors), list(range(len(self.definition.thrusters))))
                for index, (_, position, axis) in enumerate(self.definition.thrusters):
                    matrix = rotors[index]
                    np.testing.assert_allclose(matrix[:3, 3], three(position), atol=1e-5)
                    # Blender's local +Z spin axis becomes glTF local +Y in the exporter's axis conversion.
                    spin = matrix[:3, :3] @ np.array([0.0, 1.0, 0.0])
                    expected = three(axis) / np.linalg.norm(axis)
                    self.assertGreater(abs(float(spin @ expected)), 0.999)

    def test_named_pivots_and_anchors(self):
        doc, _ = read_glb(LODS[0])
        worlds = world_matrices(doc)
        by_name = {node.get('name'): index for index, node in enumerate(doc['nodes'])}
        for key in ('camera_gimbal', 'lamp_pivot_0', 'lamp_pivot_1', 'anchor_camera', 'anchor_tether',
                    'anchor_lamp_0', 'anchor_lamp_1'):
            self.assertIn(key, by_name)
        np.testing.assert_allclose(worlds[by_name['anchor_tether']][:3, 3], three(self.definition.gland_body),
                                   atol=1e-5)
        for index, lamp in enumerate(self.definition.lamp_body):
            pivot = worlds[by_name[f'lamp_pivot_{index}']][:3, 3]
            self.assertLess(np.linalg.norm(pivot - three(lamp)), 0.02)
        gimbal = worlds[by_name['camera_gimbal']][:3, 3]
        self.assertLess(np.linalg.norm(gimbal - three(self.definition.camera_body)), 0.1)

    def test_t11_budgets(self):
        doc, raw = read_glb(LODS[0])
        self.assertLessEqual(drawn_triangles(doc), 80_000)
        self.assertLessEqual(len(raw), 8 * 1024 * 1024)
        self.assertIn('EXT_meshopt_compression', doc.get('extensionsRequired', []))
        material = next(m for m in doc['materials'] if m['name'] == 'body_atlas')
        for key in ('normalTexture', 'occlusionTexture'):
            self.assertIn(key, material)
        for slot in ('baseColorTexture', 'metallicRoughnessTexture'):
            self.assertIn(slot, material['pbrMetallicRoughness'])
        previous = drawn_triangles(doc)
        for name in LODS[1:]:
            lod, _ = read_glb(name)
            self.assertLess(drawn_triangles(lod), previous)
            previous = drawn_triangles(lod)

    def test_no_manufacturer_names(self):
        for name in LODS:
            doc, _ = read_glb(name)
            labels = [item.get('name', '') for key in ('nodes', 'meshes', 'materials', 'images')
                      for item in doc.get(key, [])]
            labels.append(json.dumps([node.get('extras', {}) for node in doc['nodes']]))
            for label in labels:
                self.assertIsNone(BRANDS.search(label), label)


if __name__ == '__main__':
    unittest.main()
