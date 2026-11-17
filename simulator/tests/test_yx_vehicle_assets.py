"""YX fleet visual contract: three LODs, budgets, rotor axes, and the nodes the viewer moves."""
import json
import re
import struct
import unittest
from pathlib import Path

import numpy as np

from qysim.vehicles import get_vehicle_definition

MODELS = Path(__file__).resolve().parents[1] / 'viewer' / 'models'
FLEET = (
    ('x1', 'rov', 6),
    ('bluerov2_heavy', 'bluerov2_heavy', 8),
    ('falcon', 'falcon', 5),
)
BUDGETS = (40_000, 12_000, 3_000)
BYTE_BUDGET = int(1.5 * 1024 * 1024)
BRANDS = re.compile(
    r'qysea|fifish|blue ?robotics|bluerov|saab|seaeye|chasing|deep ?trekker',
    re.I,
)
ANCHORS = {'anchor_camera', 'anchor_lamp_0', 'anchor_lamp_1', 'anchor_tether', 'anchor_arm_mount'}
ARM = ('arm_yaw', 'arm_shoulder', 'arm_elbow', 'arm_wrist', 'arm_jaw_left', 'arm_jaw_right', 'arm_tip')


def files_for(stem):
    return (f'{stem}.glb', f'{stem}_lod1.glb', f'{stem}_lod2.glb')


def read_glb(name):
    raw = (MODELS / name).read_bytes()
    length = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20 + length]), raw


def node_matrix(node):
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    rotation = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
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
    accessors = doc['accessors']
    total = 0
    for node in doc['nodes']:
        if 'mesh' not in node:
            continue
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            if 'indices' in primitive:
                total += accessors[primitive['indices']]['count'] // 3
            else:
                total += accessors[primitive['attributes']['POSITION']]['count'] // 3
    return total


class TestYxVehicleAssets(unittest.TestCase):
    def test_budgets_extensions_and_monotonic_lods(self):
        for model_id, stem, _count in FLEET:
            previous = None
            for level, name in enumerate(files_for(stem)):
                with self.subTest(file=name):
                    doc, raw = read_glb(name)
                    triangles = drawn_triangles(doc)
                    self.assertLessEqual(triangles, BUDGETS[level])
                    self.assertLessEqual(len(raw), BYTE_BUDGET)
                    self.assertIn('EXT_meshopt_compression', doc.get('extensionsRequired', []))
                    self.assertIn('EXT_texture_webp', doc.get('extensionsUsed', []))
                    if previous is not None:
                        self.assertLess(triangles, previous)
                    previous = triangles

    def test_rotors_match_thruster_axes(self):
        for model_id, stem, count in FLEET:
            definition = get_vehicle_definition(model_id)
            for name in files_for(stem):
                with self.subTest(file=name):
                    doc, _raw = read_glb(name)
                    worlds = world_matrices(doc)
                    rotors = {}
                    for index, node in enumerate(doc['nodes']):
                        extras = node.get('extras', {})
                        if extras.get('role') != 'rotor':
                            continue
                        rotors[extras['thruster_index']] = (node, worlds[index])
                    self.assertEqual(sorted(rotors), list(range(count)))
                    for index, (_thruster_name, position, axis) in enumerate(definition.thrusters):
                        node, matrix = rotors[index]
                        self.assertIn('mesh', node)
                        if model_id == 'x1':
                            self.assertTrue(node.get('name', '').startswith('ROTOR'))
                            self.assertIn('axis', node['extras'])
                        np.testing.assert_allclose(matrix[:3, 3], three(position), atol=1e-5)
                        spin = matrix[:3, :3] @ np.array([0.0, 1.0, 0.0])
                        expected = three(axis) / np.linalg.norm(axis)
                        self.assertGreater(abs(float(spin @ expected)), 0.999)

    def test_pivots_anchors_and_arm(self):
        for model_id, stem, _count in FLEET:
            doc, _raw = read_glb(f'{stem}.glb')
            names = {node.get('name') for node in doc['nodes']}
            with self.subTest(model=model_id):
                self.assertTrue({'camera_gimbal', 'lamp_pivot_0', 'lamp_pivot_1', 'yx_frame'} <= names)
                self.assertTrue(ANCHORS <= names)
                frame = next(node for node in doc['nodes'] if node.get('name') == 'yx_frame')
                self.assertEqual(frame.get('extras', {}).get('frame'), 'cg')
            if model_id != 'falcon':
                continue
            by_name = {node['name']: node for node in doc['nodes']}
            self.assertTrue(set(ARM) <= names)
            np.testing.assert_allclose(by_name['arm_yaw']['translation'], [0.12, -0.40, 0.30], atol=1e-6)
            for joint, length in (('arm_elbow', 0.32), ('arm_wrist', 0.30), ('arm_tip', 0.12)):
                np.testing.assert_allclose(by_name[joint]['translation'], [0, 0, length], atol=1e-6)
            for name in files_for('falcon'):
                with self.subTest(file=name):
                    lodged, _raw = read_glb(name)
                    lodged_by_name = {node.get('name'): node for node in lodged['nodes']}
                    for label in ('arm_jaw_left', 'arm_jaw_right'):
                        children = lodged_by_name[label].get('children', [])
                        self.assertTrue(children, label)
                        for child in children:
                            finger = lodged['nodes'][child]
                            self.assertIn('mesh', finger)
                            offset = finger.get('translation', [0, 0, 0])
                            self.assertLess(float(np.linalg.norm(offset)), 0.05)

    def test_mesh_count_and_no_brand_strings(self):
        for model_id, stem, _count in FLEET:
            for name in files_for(stem):
                doc, _raw = read_glb(name)
                labels = [item.get('name', '') for key in ('nodes', 'meshes', 'materials', 'images')
                          for item in doc.get(key, [])]
                labels.append(json.dumps([node.get('extras', {}) for node in doc['nodes']]))
                for label in labels:
                    self.assertIsNone(BRANDS.search(label), label)
            doc, _raw = read_glb(f'{stem}.glb')
            if model_id != 'x1':
                self.assertGreater(len(doc['meshes']), 60)


if __name__ == '__main__':
    unittest.main()
