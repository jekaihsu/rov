"""Instructor vehicle-system injections: video, link, comms loss, power trip, leak, overheat."""
import unittest

from qysim.engine import Simulator
from qysim.instructor import SYSTEM_KINDS
from qysim.room import Room


class InstructorFaultTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(Simulator())
        self.sim = self.room.primary
        self.instructor = self.room.instructor

    def tick(self, seconds):
        steps = int(round(seconds / self.sim.dt))
        for _ in range(steps):
            self.room.step(self.sim.dt)

    def test_each_kind_applies_and_restores(self):
        sim = self.sim
        checks = {
            'video_delay': lambda: sim.link.video_lag_s > 0,
            'video_freeze': lambda: sim.link.video_frozen,
            'link_degrade': lambda: sim.link.state()['state'] == 'degraded',
            'comms_loss': lambda: sim.link.state()['state'] == 'lost',
            'power_trip': lambda: sim.power.tripped and sim.link.state()['cause'] == 'power',
            'leak': lambda: sim.viewer_state()['leak']['detected'],
            'overheat': lambda: 'motor_hot' in sim.thermal.warnings(),
        }
        self.assertEqual(set(checks), set(SYSTEM_KINDS))
        for kind, active in checks.items():
            with self.subTest(kind=kind):
                self.instructor.inject({'kind': kind, 'duration': .05, 'strength': 1})
                self.assertTrue(active())
                self.instructor.update(.06)
                if kind in ('comms_loss', 'power_trip'):
                    # Restoring the link starts the modem's reconnect; it is not instantly healthy.
                    self.assertEqual(sim.link.state()['phase'], 'reconnecting')
                    self.assertFalse(sim.power.tripped)
                else:
                    self.assertFalse(active())
                self.assertIn('restored_at', self.instructor.events[-1])
                sim.link = type(sim.link)()

    def test_comms_loss_options_and_reconnect(self):
        sim = self.sim
        sim.rc_physical.rc_lock = 0
        self.instructor.inject({'kind': 'comms_loss', 'duration': 1.5, 'failsafe': 'depth_hold',
                                'failsafe_delay': .5, 'reconnect': 1})
        self.tick(1)
        self.assertEqual(sim.link.failsafe, 'depth_hold')
        self.tick(.6)
        self.assertEqual(sim.link.state()['phase'], 'reconnecting')
        self.assertEqual(sim.link.config['failsafe_action'], 'disarm', 'per-injection options are restored')
        self.tick(1.1)
        self.assertEqual(sim.link.state()['phase'], 'connected')
        self.assertTrue(sim.link.rearm_required)

    def test_invalid_options_are_rejected(self):
        with self.assertRaises(ValueError):
            self.instructor.inject({'kind': 'comms_loss', 'failsafe': 'explode'})
        with self.assertRaises(ValueError):
            self.instructor.inject({'kind': 'comms_loss', 'reconnect': -1})
        self.assertEqual(self.instructor.active, [])

    def test_power_trip_stops_thrust_and_lights(self):
        sim = self.sim
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000
        sim.rc_physical.right_switch = 2
        self.instructor.inject({'kind': 'power_trip', 'duration': 1})
        self.tick(.5)
        state = sim.viewer_state()
        self.assertTrue(state['power']['tripped'])
        self.assertFalse(state['power']['lights_on'])
        self.assertLess(abs(sim.vehicle.s.thrust).max(), 1.0)
        self.assertEqual(state['link']['failsafe'], 'disarm')

    def test_battery_injection_on_tether_vehicle_sags_supply(self):
        sim = self.sim
        before = sim.power.available_w(sim)
        self.instructor.inject({'kind': 'battery', 'strength': .5, 'duration': 1})
        self.assertLess(sim.power.available_w(sim), before)
        self.assertEqual(sim.viewer_state()['battery'], 100.0)


if __name__ == '__main__':
    unittest.main()
