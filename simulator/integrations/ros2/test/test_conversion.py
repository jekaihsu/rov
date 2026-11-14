"""Coordinate, command and watchdog tests without a ROS installation."""
import math
import unittest

from rov_sim_bridge.conversion import CommandGate, frd_to_flu, ned_to_enu, quaternion, velocity_rc


class ConversionTests(unittest.TestCase):
    def test_vectors(self):
        self.assertEqual(ned_to_enu([1, 2, 3]), (2, 1, -3))
        self.assertEqual(frd_to_flu([1, 2, 3]), (1, -2, -3))

    def test_quaternion_north_and_east(self):
        north = quaternion([1, 0, 0, 0])
        for actual, expected in zip(north, [0, 0, math.sqrt(.5), math.sqrt(.5)]):
            self.assertAlmostEqual(actual, expected)
        east = quaternion([math.sqrt(.5), 0, 0, math.sqrt(.5)])
        for actual, expected in zip(east, [0, 0, 0, 1]):
            self.assertAlmostEqual(actual, expected)

    def test_quaternion_rotation_agrees_with_basis_change(self):
        # Compare rotations on all three body basis vectors for a nontrivial pose.
        def rotate(q, v):
            w, x, y, z = q
            return ((1-2*y*y-2*z*z)*v[0] + (2*x*y-2*w*z)*v[1] + (2*x*z+2*w*y)*v[2],
                    (2*x*y+2*w*z)*v[0] + (1-2*x*x-2*z*z)*v[1] + (2*y*z-2*w*x)*v[2],
                    (2*x*z-2*w*y)*v[0] + (2*y*z+2*w*x)*v[1] + (1-2*x*x-2*y*y)*v[2])
        q = [.5, .5, -.5, .5]
        x, y, z, w = quaternion(q)
        for vector in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            expected = ned_to_enu(rotate(q, frd_to_flu(vector)))
            for actual, target in zip(rotate([w, x, y, z], vector), expected):
                self.assertAlmostEqual(actual, target)

    def test_velocity_axes_and_saturation(self):
        rc = velocity_rc([100, 100, 100, 100, 100, 100], [1, 1, 1])
        self.assertEqual(rc, dict(left_ud=2000, left_lr=1000, right_ud=2000,
                                  right_lr=2000, left_wave=2000, right_wave=1000))
        rc = velocity_rc([.125, 0, 0, 0, 0, 0], [1, 1, 1])
        self.assertEqual(rc['right_ud'], 1625)

    def test_invalid_numeric_inputs(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                velocity_rc([value, 0, 0, 0, 0, 0], [1, 1, 1])
        with self.assertRaises(ValueError):
            quaternion([0, 0, 0, 0])
        with self.assertRaises(ValueError):
            velocity_rc([0]*6, [0, 1, 1])


class GateTests(unittest.TestCase):
    def setUp(self):
        self.gate = CommandGate(.4)
        self.state = {'assist': {'speed_limit': [1, 1, 1]}, 'pos': [0, 0, 2], 'depth_hold': None}

    def test_explicit_arm_and_fresh_command_required(self):
        self.gate.arm(True, 1)
        self.assertFalse(self.gate.armed)
        self.gate.velocity([.1, 0, 0, 0, 0, 0], 1)
        self.assertEqual(self.gate.packet(self.state, 1, 2)['rc_lock'], 1)
        self.gate.arm(True, 1.1)
        self.assertEqual(self.gate.packet(self.state, 1.2, 2)['rc_lock'], 0)
        rc = self.gate.packet(self.state, 1.5, 2)
        self.assertEqual(rc['rc_lock'], 1)
        self.assertEqual(rc['right_ud'], 1500)
        self.gate.velocity([.1, 0, 0, 0, 0, 0], 1.6)
        self.assertEqual(self.gate.packet(self.state, 1.6, 2)['rc_lock'], 1)

    def test_reset_discards_command_and_depth(self):
        self.gate.set_depth(3, 1)
        self.gate.arm(True, 1)
        rc = self.gate.packet(self.state, 1, 0)
        self.assertEqual(rc['keep_depth'], 1)
        self.assertEqual(rc['left_wave'], 1000)
        self.gate.reset()
        self.gate.arm(True, 1.1)
        self.assertFalse(self.gate.armed)
        self.assertIsNone(self.gate.depth)

    def test_command_modes_do_not_refresh_stale_axes(self):
        self.gate.velocity([1]*6, 1)
        self.gate.set_depth(3, 1.1)
        self.assertEqual(self.gate.twist, (0,)*6)
        self.gate.velocity([0]*6, 1.2)
        self.assertIsNone(self.gate.depth)

    def test_legacy_host_omits_assistance(self):
        self.assertNotIn('assist', self.gate.packet({}, 1, 0))
        self.assertNotIn('profile', self.gate.packet({}, 1, 0))


if __name__ == '__main__':
    unittest.main()
