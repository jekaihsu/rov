"""Simulated vehicle link: degradation, loss, failsafe actions, reconnect and re-arm."""
import unittest
from unittest import mock

from qysim import scenarios as sc_mod

from qysim.comms import CommsLink, LINK_PARAMETERS
from qysim.engine import Simulator
from qysim.room import Room


def run(sim, seconds):
    for _ in range(int(round(seconds / sim.dt))):
        sim.step()


def armed(sim, **channels):
    sim.rc_physical.rc_lock = 0
    for key, value in channels.items():
        setattr(sim.rc_physical, key, value)


def rearm(sim):
    """What the server's latch accepts: a locked packet first, then an unlocked one."""
    sim.input_latched = False
    sim.rc_physical.rc_lock = 1
    sim.step()
    sim.rc_physical.rc_lock = 0
    sim.step()


class LinkStateTests(unittest.TestCase):
    def test_parameters_carry_sources(self):
        for key, item in LINK_PARAMETERS.items():
            with self.subTest(key=key):
                self.assertIn("value", item)
                self.assertTrue(item["source"])

    def test_default_link_is_healthy_and_inert(self):
        sim = Simulator()
        state = sim.viewer_state()["link"]
        self.assertEqual(state["state"], "healthy")
        self.assertEqual(state["video_lag_s"], 0)
        self.assertFalse(state["video_frozen"])
        self.assertIsNone(state["telemetry_hz"])
        armed(sim, right_ud=2000)
        run(sim, 2)
        self.assertEqual(sim.link.state()["state"], "healthy")
        self.assertIs(sim.link.command_rc(sim.rc), sim.rc)

    def test_degraded_lag_grows_to_cap_then_jumps_back(self):
        link = CommsLink()
        link.degrade(1.0)

        class Stub:
            pass
        lags = []
        for _ in range(300):
            link.step(Stub(), 0.01)
            lags.append(link.video_lag_s)
        self.assertTrue(all(b >= a for a, b in zip(lags, lags[1:])))
        self.assertAlmostEqual(lags[-1], LINK_PARAMETERS["max_video_lag_s"]["value"])
        self.assertEqual(link.state()["state"], "degraded")
        self.assertEqual(link.telemetry_hz, LINK_PARAMETERS["degraded_telemetry_hz"]["value"])
        link.clear_degrade()
        self.assertEqual(link.video_lag_s, 0)
        self.assertEqual(link.state()["state"], "healthy")

    def test_degraded_freeze_episodes_follow_the_period(self):
        link = CommsLink()
        link.degrade(1.0)
        frozen = []
        for _ in range(4000):
            link.clock += 0.01
            frozen.append(link.video_frozen)
        fraction = sum(frozen) / len(frozen)
        period = LINK_PARAMETERS["freeze_period_s"]["value"]
        length = LINK_PARAMETERS["freeze_s"]["value"]
        self.assertAlmostEqual(fraction, length / period, delta=0.02)
        mild = CommsLink()
        mild.degrade(0.2)
        mild.clock = 19.9
        self.assertFalse(mild.video_frozen)

    def test_degraded_link_still_delivers_commands(self):
        sim = Simulator()
        armed(sim, right_ud=2000)
        sim.link.degrade(1.0)
        run(sim, 3)
        self.assertGreater(sim.vehicle.s.vel[0], 0.3)
        self.assertEqual(sim.link.state()["state"], "degraded")

    def test_configuration_is_validated(self):
        with self.assertRaises(ValueError):
            CommsLink({"failsafe_action": "explode"})
        with self.assertRaises(ValueError):
            CommsLink({"reconnect_s": -1})
        with self.assertRaises(ValueError):
            CommsLink({"bogus": 1})
        link = CommsLink({"state": "degraded", "severity": 0.4, "reconnect_s": 5})
        self.assertEqual(link.severity, 0.4)
        self.assertEqual(link.config["reconnect_s"], 5)


class LinkLossTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator()
        self.room = Room(self.sim)

    def test_loss_keeps_last_command_then_disarms_and_latches(self):
        sim = self.sim
        armed(sim, right_ud=2000)
        run(sim, 1)
        sim.link.lose(rc=sim.rc)
        sim.rc_physical.right_ud = 1000        # never reaches the vehicle
        run(sim, 1)
        self.assertGreater(sim.vehicle.s.vel[0], 0.1, "the vehicle keeps its last received command")
        self.assertIsNone(sim.link.failsafe)
        generation = sim.control_generation
        run(sim, LINK_PARAMETERS["failsafe_delay_s"]["value"])
        self.assertEqual(sim.link.failsafe, "disarm")
        self.assertTrue(sim.input_latched)
        self.assertEqual(sim.rc.rc_lock, 1)
        self.assertGreater(sim.control_generation, generation)
        state = sim.viewer_state()["link"]
        self.assertTrue(state["video_frozen"])
        self.assertEqual(state["telemetry_hz"], 0)
        self.assertTrue(state["rearm_required"])

    def test_packets_during_loss_and_reconnect_cannot_rearm(self):
        sim = self.sim
        sim.link.configure({"reconnect_s": 2.0})
        armed(sim, right_ud=2000)
        sim.link.lose()
        run(sim, 4)
        rearm(sim)                              # pilot tries while the link is down
        sim.rc_physical.right_ud = 2000
        run(sim, 1)
        self.assertLess(abs(sim.vehicle.s.thrust).max(), 1e-3)
        sim.link.restore()
        run(sim, 1)
        self.assertEqual(sim.link.state()["phase"], "reconnecting")
        self.assertGreater(sim.link.state()["reconnect_in"], 0)
        run(sim, 1.1)
        self.assertEqual(sim.link.state()["state"], "healthy")
        self.assertTrue(sim.link.rearm_required)
        self.assertEqual(sim.rc.rc_lock, 1, "reconnecting re-latches the lock")
        self.assertTrue(sim.input_latched)
        rearm(sim)
        self.assertFalse(sim.link.rearm_required)
        self.assertIsNone(sim.link.failsafe)
        sim.rc_physical.right_ud = 2000
        run(sim, 1)
        self.assertGreater(abs(sim.vehicle.s.thrust).max(), 1.0)

    def test_depth_hold_failsafe_holds_depth_until_rearm(self):
        sim = self.sim
        sim.link.configure({"failsafe_action": "depth_hold", "reconnect_s": 1.0})
        armed(sim, left_wave=1000)              # ascending command in ROV_USA
        run(sim, 0.5)
        sim.link.lose()
        run(sim, LINK_PARAMETERS["failsafe_delay_s"]["value"] + 0.1)
        held = sim.depth
        self.assertEqual(sim.link.failsafe, "depth_hold")
        run(sim, 4)
        self.assertAlmostEqual(sim.depth, held, delta=0.25)
        sim.link.restore()
        run(sim, 2)
        self.assertEqual(sim.link.failsafe, "depth_hold", "the failsafe persists until the pilot re-arms")
        rearm(sim)
        self.assertIsNone(sim.link.failsafe)

    def test_surface_failsafe_ascends(self):
        sim = self.sim
        start = sim.depth
        sim.link.configure({"failsafe_action": "surface", "failsafe_delay_s": 0.5})
        armed(sim)
        sim.link.lose()
        run(sim, 6)
        self.assertEqual(sim.link.failsafe, "surface")
        self.assertGreater(start, 1.0)
        self.assertLess(sim.depth, 0.5)

    def test_power_loss_disarms_immediately(self):
        sim = self.sim
        sim.link.configure({"failsafe_action": "depth_hold"})
        armed(sim)
        sim.link.lose(cause="power", immediate=True)
        sim.step()
        self.assertEqual(sim.link.failsafe, "disarm")

    def test_scenario_can_start_degraded(self):
        original = sc_mod.build

        def degraded(key, seed=None):
            scenario = original(key, seed)
            scenario.link = {"state": "degraded", "severity": 0.6, "failsafe_action": "surface"}
            return scenario
        with mock.patch.object(sc_mod, "build", degraded):
            sim = Simulator()
        state = sim.viewer_state()["link"]
        self.assertEqual(state["state"], "degraded")
        self.assertEqual(state["failsafe_action"], "surface")


if __name__ == "__main__":
    unittest.main()
