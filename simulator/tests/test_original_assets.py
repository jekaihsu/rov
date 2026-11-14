"""Shipping geometry must retain physical motor anchors and asset budgets."""
import json
from pathlib import Path
import struct
import unittest
from qysim.vehicles import VEHICLE_DEFINITIONS

MODELS = Path(__file__).resolve().parents[1] / 'viewer/models'


class OriginalAssetsTests(unittest.TestCase):
    def test_fleet(self):
        for identifier, slug in [('x1', 'observation'), ('falcon', 'work'),
                                 ('bluerov2_heavy', 'openframe')]:
            definition = VEHICLE_DEFINITIONS[identifier]
            counts = []
            for lod in range(3):
                data = (MODELS / f'{slug}-lod{lod}.glb').read_bytes()
                length = struct.unpack_from('<I', data, 12)[0]
                doc = json.loads(data[20:20 + length])
                self.assertLessEqual(len(data), 8 * 1024 * 1024)
                for extension in ['EXT_meshopt_compression', 'KHR_texture_basisu']:
                    self.assertIn(extension, doc['extensionsRequired'])
                count = sum(doc['accessors'][p['indices']]['count'] // 3
                            for mesh in doc['meshes'] for p in mesh['primitives'])
                self.assertLessEqual(count, 80000)
                counts.append(count)
                nodes = doc['nodes']
                rotors = [n for n in nodes if n.get('extras', {}).get('role') == 'rotor']
                self.assertEqual(len(rotors), len(definition.thrusters))
                for rotor in rotors:
                    index = rotor['extras']['thruster_index']
                    parent = next(n for n in nodes if nodes.index(rotor) in n.get('children', []))
                    p = definition.thrusters[index][1]
                    for actual, target in zip(parent.get('translation', [0, 0, 0]), [-p[1], -p[2], p[0]]):
                        self.assertAlmostEqual(actual, target, places=5)
                names = {n.get('name') for n in nodes}
                self.assertIn('camera_gimbal', names)
                if identifier == 'falcon':
                    for name in ['arm_yaw', 'arm_shoulder', 'arm_elbow', 'arm_wrist', 'arm_tip']:
                        self.assertIn(name, names)
            self.assertGreater(counts[0], counts[1])
            self.assertGreater(counts[1], counts[2])
            proxy = json.loads((MODELS / f'{slug}-collision.json').read_text())
            self.assertEqual(proxy['spheres'], json.loads(json.dumps(definition.hull_spheres)))
        self.assertLessEqual(sum(p.stat().st_size for p in MODELS.glob('*.glb')), 120 * 1024 * 1024)
