"""Shipping geometry must retain physical motor anchors and asset budgets."""
import json
import math
from pathlib import Path
import struct
import unittest
from qysim.vehicles import VEHICLE_DEFINITIONS

MODELS = Path(__file__).resolve().parents[1] / 'viewer/models'


class OriginalAssetsTests(unittest.TestCase):
    def test_fleet(self):
        for identifier, slug in [('x1', 'observation')]:
            definition = VEHICLE_DEFINITIONS[identifier]
            counts = []
            for lod in range(3):
                data = (MODELS / f'{slug}-lod{lod}.glb').read_bytes()
                length = struct.unpack_from('<I', data, 12)[0]
                doc = json.loads(data[20:20 + length])
                self.assertLessEqual(len(data), 8 * 1024 * 1024)
                for extension in ['EXT_meshopt_compression', 'KHR_texture_basisu']:
                    self.assertIn(extension, doc['extensionsRequired'])
                for material in doc['materials']:
                    pbr = material['pbrMetallicRoughness']
                    self.assertEqual(pbr['baseColorFactor'], material['extras']['original_base_color'])
                    self.assertIn('baseColorTexture', pbr)
                    self.assertIn('metallicRoughnessTexture', pbr)
                    self.assertIn('normalTexture', material)
                    self.assertIn('occlusionTexture', material)
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
                    x, y, z, w = parent.get('rotation', [0, 0, 0, 1])
                    axis = [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)]
                    a = definition.thrusters[index][2]
                    magnitude = math.sqrt(sum(v * v for v in a))
                    expected_axis = [-a[1] / magnitude, -a[2] / magnitude, a[0] / magnitude]
                    for actual, target in zip(axis, expected_axis):
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

    def test_static_bundle_includes_runtime_assets(self):
        import importlib.util
        import sys
        import tempfile
        tools = MODELS.parents[1] / 'tools'
        sys.path.insert(0, str(tools))
        spec = importlib.util.spec_from_file_location('asset_showcase', tools / 'build_showcase.py')
        showcase = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(showcase)
        with tempfile.TemporaryDirectory() as temporary:
            for artifact in [False, True]:
                output = Path(temporary) / str(artifact)
                showcase.build(output, glb_json=artifact)
                for name in ['asset_config.js', 'asset_inspector.js', 'glb.js']:
                    self.assertTrue((output / name).is_file(), name)
                for name in ['basis_transcoder.js', 'basis_transcoder.wasm']:
                    path = output / 'vendor/three/examples/jsm/libs/basis' / name
                    self.assertTrue(path.is_file(), name)
                for name in ['observation-collision.json', 'assets-report.json']:
                    self.assertTrue((output / 'models' / name).is_file(), name)
                for lod in range(3):
                    name = f'observation-lod{lod}.glb' + ('.json' if artifact else '')
                    self.assertTrue((output / 'models' / name).is_file(), name)
