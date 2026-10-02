"""Cross-model dynamics and exported asset contract regressions."""
import json
import math
from pathlib import Path
import struct
import unittest

import numpy as np

from qysim.controller import FlightController
from qysim.physics import Vehicle
from qysim.vehicles import VEHICLE_DEFINITIONS, get_vehicle_definition


class TestVehicleFleet(unittest.TestCase):
    def test_topology_and_locked_motor_count(self):
        for model, count, rank in [('x1', 6, 6), ('bluerov2_heavy', 8, 6), ('falcon', 5, 4)]:
            with self.subTest(model=model):
                v = Vehicle(model_id=model)
                self.assertEqual(v.B.shape, (6, count))
                self.assertEqual(np.linalg.matrix_rank(v.B), rank)
                output = FlightController(v).update(.01, {}, 'S', True, False)
                self.assertEqual(output.shape, (count,))
                self.assertTrue(np.isfinite(v.authority).all())

    def test_falcon_does_not_invent_pitch_roll_actuators(self):
        v = Vehicle(model_id='falcon')
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
        v = Vehicle(model_id='bluerov2_heavy')
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
        for model, count in [('bluerov2_heavy', 8), ('falcon', 5)]:
            raw = (folder / f'{model}.glb').read_bytes()
            self.assertEqual(raw[:4], b'glTF')
            size = struct.unpack_from('<I', raw, 12)[0]
            doc = json.loads(raw[20:20+size])
            nodes = doc['nodes']
            ids = [n['extras']['thruster_index'] for n in nodes if n.get('extras', {}).get('role') == 'rotor']
            self.assertEqual(sorted(ids), list(range(count)))
            names = {n['name'] for n in nodes}
            self.assertTrue({'anchor_camera', 'anchor_lamp_0', 'anchor_lamp_1', 'anchor_tether', 'anchor_arm_mount'} <= names)
            self.assertGreater(len(doc['meshes']), 60)
            if model == 'falcon':
                by_name={n['name']:n for n in nodes}
                self.assertTrue({'arm_yaw','arm_shoulder','arm_elbow','arm_wrist','arm_jaw_left','arm_jaw_right','arm_tip'} <= names)
                np.testing.assert_allclose(by_name['arm_yaw']['translation'], [.12,-.40,.30], atol=1e-6)
                for name,length in [('arm_elbow',.32),('arm_wrist',.30),('arm_tip',.12)]:
                    np.testing.assert_allclose(by_name[name]['translation'],[0,0,length],atol=1e-6)
            def transform(node):
                if 'matrix' in node:
                    return np.asarray(node['matrix']).reshape(4,4).T
                x,y,z,w = node.get('rotation', [0,0,0,1])
                r = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                              [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                              [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
                m = np.eye(4); m[:3,:3] = r @ np.diag(node.get('scale',[1,1,1])); m[:3,3] = node.get('translation',[0,0,0])
                return m
            def visit(index, parent):
                node=nodes[index]; matrix=parent @ transform(node)
                if node.get('extras',{}).get('role') == 'rotor':
                    idx=node['extras']['thruster_index']; pos=VEHICLE_DEFINITIONS[model].thrusters[idx][1]
                    np.testing.assert_allclose(matrix[:3,3],[-pos[1],-pos[2],pos[0]],atol=1e-6)
                for child in node.get('children',[]):
                    visit(child,matrix)
            for index in doc['scenes'][doc.get('scene',0)]['nodes']:
                visit(index,np.eye(4))


if __name__ == '__main__':
    unittest.main()
