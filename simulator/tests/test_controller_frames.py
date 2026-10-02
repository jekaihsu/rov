"""Force-frame regressions measured after real thruster allocation."""
import math
import unittest

import numpy as np

from qysim.controller import FlightController
from qysim.physics import Vehicle, q_from_euler, q_rot


class TestVerticalControlFrames(unittest.TestCase):
    def assert_vertical(self, v, ctrl, motors, direction):
        requested = q_rot(v.s.q, ctrl.last_wrench[:3] * v.authority[:3])
        np.testing.assert_allclose(requested[:2], 0., atol=1e-8)
        actual = q_rot(v.s.q, (v.B @ motors * v.p.thruster_max)[:3])
        # Falcon is underactuated. Its current six-row least-squares allocator
        # trades a small force residual against its coupled roll/pitch moments.
        tolerance = abs(actual[2]) * .005 if v.model_id == 'falcon' else 1e-8
        np.testing.assert_allclose(actual[:2], 0., atol=tolerance)
        self.assertGreater(actual[2] * direction, 0.)

    def vehicle(self, model):
        v = Vehicle(model_id=model)
        v.s.pos[2] = 10.
        v.s.q = q_from_euler(0., math.radians(40), math.radians(35))
        return v

    def test_depth_feedback_produces_world_vertical_force_in_all_modes(self):
        for model in ('x1', 'bluerov2_heavy', 'falcon'):
            for mode in ('A', 'S', 'C'):
                with self.subTest(model=model, mode=mode):
                    v = self.vehicle(model)
                    ctrl = FlightController(v)
                    ctrl.depth_hold = 10.05
                    motors = ctrl.update(.01, {}, mode, False, True)
                    self.assert_vertical(v, ctrl, motors, 1)

    def test_stabilized_manual_heave_is_world_vertical(self):
        for model in ('x1', 'bluerov2_heavy', 'falcon'):
            with self.subTest(model=model):
                v = self.vehicle(model)
                ctrl = FlightController(v)
                motors = ctrl.update(.01, {'heave': .1}, 'A', False, False)
                self.assert_vertical(v, ctrl, motors, -1)

    def test_sport_without_depth_hold_retains_body_heave(self):
        v = self.vehicle('bluerov2_heavy')
        motors = FlightController(v).update(.01, {'heave': .1}, 'S', False, False)
        actual_body = (v.B @ motors * v.p.thruster_max)[:3]
        np.testing.assert_allclose(actual_body[:2], 0., atol=1e-8)
        self.assertLess(actual_body[2], 0.)
        self.assertGreater(abs(q_rot(v.s.q, actual_body)[0]), .1)

    def test_depth_target_changes_upwards_and_stops_on_release(self):
        v = self.vehicle('bluerov2_heavy')
        ctrl = FlightController(v)
        ctrl.update(.1, {'heave': .5}, 'S', False, True)
        self.assertAlmostEqual(ctrl.depth_hold, 9.97)
        ctrl.update(.1, {}, 'S', False, True)
        self.assertAlmostEqual(ctrl.depth_hold, 9.97)


if __name__ == '__main__':
    unittest.main()
