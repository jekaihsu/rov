"""Cross-model dynamics and exported asset contract regressions."""
import json
import math
from pathlib import Path
import struct
import unittest

import numpy as np

from rov01sim.controller import FlightController
from rov01sim.physics import Vehicle
from rov01sim.vehicles import VEHICLE_DEFINITIONS, get_vehicle_definition


class TestVehicleFleet(unittest.TestCase):
    def test_topology_and_locked_motor_count(self):
        for model, count, rank in [('rov01', 6, 6), ('rov02_heavy', 8, 6), ('rov01_pro', 5, 4)]:
            with self.subTest(model=model):
                v = Vehicle(model_id=model)
                self.assertEqual(v.B.shape, (6, count))
                self.assertEqual(np.linalg.matrix_rank(v.B), rank)
                output = FlightController(v).update(.01, {}, 'S', True, False)
                self.assertEqual(output.shape, (count,))
                self.assertTrue(np.isfinite(v.authority).all())

    def test_rov01_pro_does_not_invent_pitch_roll_actuators(self):
        v = Vehicle(model_id='rov01_pro')
        np.testing.assert_allclose(v.authority[3:5], 0., atol=1e-8)
        c = FlightController(v)
        np.testing.assert_allclose(c.update(.01, {'roll': 1, 'pitch': 1}, 'S', False, False), 0., atol=1e-8)

    def test_all_allocations_bounded_and_finite(self):
        rng = np.random.default_rng(120)
        for model in VEHICLE_DEFINITIONS:
            v = Vehicle(model_id=model)
            v.s.pos[2] = 10
            v.current_ned[:] = [.3, -.2, .02]
            for _ in range(500):
                command = v.allocate(rng.uniform(-1, 1, 6))
                self.assertLessEqual(np.max(np.abs(command)), 1.000001)
                v.step(.01, command)
            self.assertTrue(np.isfinite(v.s.pos).all())
            self.assertTrue(np.isfinite(v.s.thrust).all())
            self.assertAlmostEqual(np.linalg.norm(v.s.q), 1., places=6)

    def test_heavy_vertical_thrusters_supply_roll_pitch(self):
        v = Vehicle(model_id='rov02_heavy')
        for axis in (2, 3, 4):
            wrench = np.eye(6)[axis]
            motor = v.allocate(wrench)
            actual = v.B @ motor
            self.assertGreater(actual[axis], .1)
            np.testing.assert_allclose(np.delete(actual, axis), 0., atol=1e-8)

    def test_definition_json_and_unknown_model(self):
        for d in VEHICLE_DEFINITIONS.values():
            public = json.loads(json.dumps(d.public()))
            self.assertEqual(public['id'], d.id)
            self.assertEqual(len(public['thrusters']), len(d.thrusters))
            self.assertGreater(d.hull_radius, 0)
        with self.assertRaises(ValueError):
            get_vehicle_definition('missing')

    def test_exported_models_have_exact_thruster_ids_and_anchors(self):
        folder = Path(__file__).resolve().parents[1] / 'viewer' / 'models'
        for model, count in [('rov02_heavy', 8), ('rov01_pro', 5)]:
            glb_path = folder / f'{model}.glb'
            if not glb_path.exists():
                continue
            raw = glb_path.read_bytes()
            self.assertEqual(raw[:4], b'glTF')
            size = struct.unpack_from('<I', raw, 12)[0]
            doc = json.loads(raw[20:20+size])
            nodes = doc['nodes']
            ids = [n['extras']['thruster_index'] for n in nodes if n.get('extras', {}).get('role') == 'rotor']
            self.assertEqual(sorted(ids), list(range(count)))
            names = {n['name'] for n in nodes}
            self.assertTrue({'anchor_camera', 'anchor_lamp_0', 'anchor_lamp_1', 'anchor_tether', 'anchor_arm_mount'} <= names)
            self.assertGreater(len(doc['meshes']), 60)


if __name__ == '__main__':
    unittest.main()
