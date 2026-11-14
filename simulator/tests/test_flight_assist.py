"""Flight-assist acceptance tests using the unchanged vehicle dynamics and allocator."""
import hashlib
import unittest

import numpy as np

from qysim.controller import FlightController, PROFILES
from qysim.physics import Vehicle, q_from_euler

MODELS = ('x1', 'bluerov2_heavy', 'falcon')


class TestFlightAssist(unittest.TestCase):
    def test_manual_bitwise_main_regression(self):
        # SHA256 of motor outputs + requested wrenches from main f2b2207.
        golden = (
            '85dc24ff82a0674e8034769df5555636103b48097741aa6b745dd764800b67a3',
            '77071f61b4ebfe0250aa6ecc2ec558f34216722dc78917efffe7f28173298e6b',
            '694b459f115e494f15d5cbda08587424f382145111478c0bc902dcb18ea01525',
        )
        for model, expected in zip(MODELS, golden):
            for explicit in (False, True):
                v = Vehicle(model_id=model)
                c = FlightController(v)
                digest = hashlib.sha256()
                for i in range(90):
                    v.s.pos = np.array([1., 2., 10. + i * .01])
                    v.s.q = q_from_euler(.2, .4, i * .03)
                    v.s.vel = np.array([.1, -.2, .3])
                    v.s.omega = np.array([.03, .02, -.01])
                    cmd = dict(surge=.7, sway=-.2, heave=.15, roll=.3, pitch=-.2, yaw=.1 if i % 2 else 0)
                    kwargs = {'assist': 0} if explicit else {}
                    motors = c.update(.01, cmd, ('A', 'S', 'C')[i % 3], i % 19 == 0, i % 2 == 0, **kwargs)
                    digest.update(motors.tobytes())
                    digest.update(c.last_wrench.tobytes())
                self.assertEqual(digest.hexdigest(), expected)

    def test_step_and_brake_all_models_profiles(self):
        for model in MODELS:
            for profile, reach_limit in (('cine', 8), ('normal', 10), ('sport', 12)):
                with self.subTest(model=model, profile=profile):
                    v = Vehicle(model_id=model)
                    v.s.pos[2] = 20
                    c = FlightController(v)
                    speeds = []
                    positions = []
                    previous_a = np.zeros(3)
                    actual_accelerations = []
                    previous_velocity = v.world_velocity().copy()
                    for i in range(3000):
                        motors = c.update(.01, {'surge': 1 if i < 1500 else 0}, 'A', False, False,
                                          assist=1, profile=profile)
                        _, fraction, jerk, _, _ = PROFILES[profile]
                        amax = np.minimum(v.authority[:3] / v.M * fraction,
                                          np.asarray(v.p.vmax) * PROFILES[profile][0] * 1.5)
                        self.assertTrue(np.all(np.abs(c.acceleration - previous_a) <= amax * jerk * .01 + 1e-12))
                        previous_a = c.acceleration.copy()
                        v.step(.01, motors)
                        velocity = v.world_velocity().copy()
                        actual_accelerations.append((velocity - previous_velocity) / .01)
                        previous_velocity = velocity
                        speeds.append(velocity[0])
                        positions.append(v.s.pos[0])
                    # Motor lag and real dynamics remain unchanged; no acceleration jump.
                    self.assertLess(np.max(np.abs(np.diff(actual_accelerations, axis=0))), .5)
                    limit = c.assist_state()['speed_limit'][0]
                    speeds = np.asarray(speeds)
                    self.assertLessEqual(max(speeds), limit * 1.1)
                    reach = np.flatnonzero(speeds[:1500] >= .9 * limit)
                    self.assertTrue(len(reach))
                    self.assertLess(reach[0] * .01, reach_limit)
                    if profile == 'normal':
                        stop = np.flatnonzero(np.abs(speeds[1500:]) < .05)
                        self.assertTrue(len(stop))
                        self.assertLess(stop[0] * .01, 8)
                        self.assertLess(positions[1500 + stop[0]] - positions[1499], 4)
                        self.assertLess(max(positions) - positions[-1], .05)

    def test_current_hold_and_saturation(self):
        for model in MODELS:
            for knots in (.5, 2.5):
                with self.subTest(model=model, knots=knots):
                    v = Vehicle(model_id=model)
                    v.s.pos[2] = 20
                    origin = v.s.pos.copy()
                    v.current_ned = np.array([0., knots * .514444, 0.])
                    c = FlightController(v)
                    saturated = False
                    for i in range(3000):
                        v.step(.01, c.update(.01, {}, 'A', False, False, assist=2))
                        saturated |= c.limited
                    error = np.linalg.norm(v.s.pos - origin)
                    if knots == .5:
                        self.assertLess(error, .15)
                        self.assertTrue(c.assist_state()['holding'])
                    else:
                        self.assertTrue(saturated)
                        self.assertLess(error, 40)
                        self.assertLess(np.linalg.norm(v.world_velocity()), 1.3)
                        self.assertTrue(np.all(np.abs(c.velocity_integral) <= v.authority[:3] / v.M + 1e-9))

    def test_release_reset_and_depth_priority(self):
        for model in MODELS:
            v = Vehicle(model_id=model)
            v.s.pos[2] = 20
            c = FlightController(v)
            c.update(.01, {}, 'A', False, False, assist=2)
            self.assertTrue(c.assist_state()['holding'])
            c.update(.01, {'surge': .5}, 'A', False, False, assist=2)
            self.assertFalse(c.assist_state()['holding'])
            c.update(.01, {}, 'A', True, False, assist=2)
            self.assertEqual(c.assist_state()['level'], 0)
            np.testing.assert_array_equal(c.velocity_integral, 0)
            v.s.q = q_from_euler(0, .6, .4)
            c.update(.01, {'surge': .5}, 'A', False, True, assist=2)
            self.assertEqual(c.depth_hold, 20)

    def test_heading_frame_yaw_limits_and_priority(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from qysim.engine import Simulator
        from qysim.physics import q_rot
        from qysim.room import Room

        for mode in ('A', 'C'):
            v = Vehicle()
            v.s.q = q_from_euler(0, .6, .4)
            c = FlightController(v)
            c.update(.01, {'surge': 1}, mode, False, False, assist=1)
            world = q_rot(v.s.q, c.last_wrench[:3] * v.authority[:3])
            self.assertAlmostEqual(world[2], 0)
            self.assertGreater(world[0], 0)
            for i in range(100):
                previous = c.yaw_rate
                c.update(.01, {'yaw': 1}, mode, False, False, assist=1)
                bound = np.radians(c.assist_state()['yaw_rate_limit'])
                self.assertLessEqual(abs(c.yaw_rate - previous), bound * .01 + 1e-12)
                self.assertLessEqual(abs(c.yaw_rate), bound)

        sim = Simulator()
        sim.apply_viewer_rc({'assist': 2, 'profile': 'cine', 'rc_lock': 0})
        sim.step()
        self.assertEqual(sim.controller.assist_state()['level'], 2)
        sim._sdk_QYRovControllerManage__set_remote_control_status('ON')
        self.assertEqual(sim.controller.assist_state()['level'], 0)
        sim.step()
        self.assertEqual(sim.controller.assist_state()['level'], 0)
        sim._sdk_QYRovControllerManage__set_remote_control_status('OFF')
        sim.nav.mode = 'H_NAVI'
        out = SimpleNamespace(cmd={'surge': .2}, heading=0., depth=None)
        with patch.object(sim.nav, 'step', return_value=out):
            sim.step()
        self.assertEqual(sim.controller.assist_state()['level'], 0)
        Room.lock(sim)
        self.assertEqual(sim.rc_physical.assist, 0)
        self.assertEqual(sim.controller.assist_state()['level'], 0)
        sim.apply_viewer_rc({'right_ud': 1600})
        self.assertEqual(sim.rc_physical.assist, 0)
        self.assertEqual(sim.rc_physical.profile, 'normal')

    def test_protocol_profile_transport(self):
        from qysim.engine import Simulator
        from qysim.server import SimHost

        host = SimHost(Simulator())
        host.handle_viewer({'type': 'rc', 'rc': {'assist': 2, 'profile': 'cine', 'rc_lock': 0}})
        self.assertEqual(host.sim.rc_physical.assist, 2)
        self.assertEqual(host.sim.rc_physical.profile, 'cine')
        with self.assertRaises(ValueError):
            host.handle_viewer({'type': 'rc', 'rc': {'right_ud': float('nan'), 'profile': 'normal'}})
        host.handle_viewer({'type': 'rc', 'rc': {'assist': 99, 'profile': 'unknown'}})
        self.assertEqual(host.sim.rc_physical.assist, 0)
        self.assertEqual(host.sim.rc_physical.profile, 'normal')
        # Repeated metadata must survive the USB/button edge filtering path.
        host.qirc_enabled = True
        previous = {}
        packet = {'type': 'rc', 'rc': {'assist': 2, 'profile': 'cine'}}
        host.handle_viewer(packet, button_values=previous)
        host.handle_viewer(packet, button_values=previous)
        self.assertEqual(host.sim.rc_physical.assist, 2)
        self.assertEqual(host.sim.rc_physical.profile, 'cine')
