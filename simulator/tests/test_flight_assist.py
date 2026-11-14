"""Flight-assist acceptance tests using the unchanged vehicle dynamics and allocator."""
import unittest

import numpy as np

from qysim.controller import FlightController, PROFILES
from qysim.physics import Vehicle, q_from_euler

MODELS = ('x1', 'bluerov2_heavy', 'falcon')


class TestFlightAssist(unittest.TestCase):
    def test_manual_bitwise_main_regression(self):
        from tests.legacy_controller_reference import FlightController as LegacyController

        for model in MODELS:
            for explicit in (False, True):
                v = Vehicle(model_id=model)
                c = FlightController(v)
                legacy = LegacyController(v)
                for i in range(90):
                    v.s.pos = np.array([1., 2., 10. + i * .01])
                    v.s.q = q_from_euler(.2, .4, i * .03)
                    v.s.vel = np.array([.1, -.2, .3])
                    v.s.omega = np.array([.03, .02, -.01])
                    cmd = dict(surge=.7, sway=-.2, heave=.15, roll=.3, pitch=-.2, yaw=.1 if i % 2 else 0)
                    kwargs = {'assist': 0} if explicit else {}
                    motors = c.update(.01, cmd, ('A', 'S', 'C')[i % 3], i % 19 == 0, i % 2 == 0, **kwargs)
                    expected = legacy.update(.01, cmd, ('A', 'S', 'C')[i % 3], i % 19 == 0, i % 2 == 0)
                    np.testing.assert_array_equal(motors, expected)
                    self.assertEqual(motors.tobytes(), expected.tobytes())
                    self.assertEqual(c.last_wrench.tobytes(), legacy.last_wrench.tobytes())

    def test_step_and_brake_all_models_profiles(self):
        for model in MODELS:
            for profile, reach_limit in (('cine', 2.0), ('normal', 1.2), ('sport', .9)):
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
                        amax = v.authority[:3] / v.M * fraction
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
                    self.assertLessEqual(max(speeds), limit * (1.05 if profile == 'normal' else 1.1))
                    reach = np.flatnonzero(speeds[:1500] >= .9 * limit)
                    self.assertTrue(len(reach))
                    self.assertLess(reach[0] * .01, reach_limit)
                    stop = np.flatnonzero(np.abs(speeds[1500:]) < .05)
                    self.assertTrue(len(stop))
                    self.assertLessEqual(stop[0] * .01, {'cine': 2.0, 'normal': 1.2, 'sport': 1.0}[profile])
                    if profile == 'normal':
                        self.assertLessEqual(positions[1500 + stop[0]] - positions[1499], .6)
                        self.assertLess(max(positions) - min(positions[1500 + stop[0]:]), .03)

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

    def test_integral_and_reference_remain_in_world_frame(self):
        from qysim.physics import q_rot

        for mode in ('A', 'S'):
            v = Vehicle()
            v.s.pos[2] = 20
            c = FlightController(v)
            c.update(.01, {}, mode, False, False, assist=2)
            bias = np.array([.03, -.02, .01])
            c.velocity_integral = bias.copy()
            c.velocity_target = bias.copy()
            c.acceleration = bias.copy()
            # Reorient without translating: the learned world force must not turn.
            v.s.q = q_from_euler(.4 if mode == 'S' else 0, .3 if mode == 'S' else 0, np.pi / 2)
            c.q_hold = v.s.q.copy()
            c.update(0, {}, mode, False, False, assist=2)
            frame = v.s.q if mode == 'S' else q_from_euler(0, 0, np.pi / 2)
            np.testing.assert_allclose(q_rot(frame, c.velocity_integral), bias, atol=1e-14)
            np.testing.assert_allclose(q_rot(frame, c.velocity_target), bias, atol=1e-14)
            np.testing.assert_allclose(q_rot(frame, c.acceleration), bias, atol=1e-14)
            self.assertTrue(c.assist_state()['holding'])

    def test_manual_profile_dvl_loss_and_manual_force_ceiling(self):
        from qysim.engine import Simulator

        for model in MODELS:
            v = Vehicle(model_id=model)
            v.s.pos[2] = 20
            c = FlightController(v)
            c.update(.01, {}, 'A', False, False, assist=0, profile='sport')
            self.assertEqual(c.assist_state()['profile'], 'sport')
            c.update(.01, {}, 'A', True, False, assist=0, profile='cine')
            self.assertEqual(c.assist_state()['profile'], 'cine')
            c.update(.01, {}, 'A', False, False, assist=2)
            self.assertTrue(c.assist_state()['holding'])
            motors = c.update(.01, {}, 'A', False, False, assist=2, dvl_valid=False)
            manual = FlightController(v).update(.01, {}, 'A', False, False)
            np.testing.assert_array_equal(motors, manual)
            self.assertEqual(c.assist_state()['level'], 0)
            self.assertFalse(c.assist_state()['holding'])
            np.testing.assert_array_equal(c.velocity_integral, 0)
            for i in range(100):
                c.update(.01, {'surge': 1, 'sway': -1, 'heave': 1}, 'A', False, False,
                         assist=1, profile='sport')
                self.assertLessEqual(np.max(np.abs(c.last_wrench[:3])), 1)
        sim = Simulator()
        sim.apply_viewer_rc({'assist': 2, 'rc_lock': 0})
        sim.vehicle.s.pos[2] = sim.world.depth_at(sim.vehicle.s.pos) - .05
        sim.step()
        self.assertEqual(sim.controller.assist_state()['level'], 0)

    def test_internal_usb_and_bridge_keep_settings(self):
        import asyncio
        from qysim.engine import Simulator
        from qysim.server import SimHost

        host = SimHost(Simulator(), qirc=True)
        host.sim.apply_viewer_rc({'assist': 2, 'profile': 'sport'})
        asyncio.run(host.controller_sample({'right_ud': 1600}, ()))
        self.assertEqual(host.sim.rc_physical.assist, 2)
        self.assertEqual(host.sim.rc_physical.profile, 'sport')
        host.handle_viewer({'type': 'rc', 'rc': {'right_ud': 1700}}, controller_bridge=True)
        self.assertEqual(host.sim.rc_physical.assist, 2)
        self.assertEqual(host.sim.rc_physical.profile, 'sport')
        # A complete legacy client packet still selects the documented defaults.
        host.qirc_enabled = False
        host.handle_viewer({'type': 'rc', 'rc': {'right_ud': 1500}})
        self.assertEqual(host.sim.rc_physical.assist, 0)
        self.assertEqual(host.sim.rc_physical.profile, 'normal')

    def test_profile_order_and_ten_second_step(self):
        from tests.flight_assist_metrics import measure

        for model in MODELS:
            rows = [measure(model, profile) for profile in ('cine', 'normal', 'sport')]
            self.assertGreater(rows[0]['rise_s'], rows[1]['rise_s'])
            self.assertGreater(rows[1]['rise_s'], rows[2]['rise_s'])
            self.assertGreater(rows[0]['stop_s'], rows[1]['stop_s'])
            self.assertGreater(rows[1]['stop_s'], rows[2]['stop_s'])
            for row in rows:
                self.assertLessEqual(row['max_force'], 1)
            normal = rows[1]
            self.assertLessEqual(normal['rise_s'], 1.2)
            self.assertLessEqual(normal['stop_s'], 1.2)
            self.assertLessEqual(normal['stop_m'], .6)
            self.assertLess(normal['reverse_m'], .03)
            self.assertLessEqual(normal['peak'], normal['limit'] * 1.05)

    def test_current_hold_while_yawing(self):
        v = Vehicle()
        v.s.pos[2] = 20
        origin = v.s.pos.copy()
        v.current_ned = np.array([0, .5 * .514444, 0])
        c = FlightController(v)
        for i in range(3000):
            motors = c.update(.01, {'yaw': .15 if i >= 1500 else 0}, 'A', False, False, assist=2)
            v.step(.01, motors)
        self.assertLess(np.linalg.norm(v.s.pos - origin), .15)
        self.assertTrue(c.assist_state()['holding'])
