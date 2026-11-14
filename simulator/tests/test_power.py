"""Tether power budget, battery cutoff and backward-compatible SDK power telemetry."""
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.power import POWER_PROFILES, PowerSystem
from qysim.rc import RCState


class Stub:
    def __init__(self, battery=100.0):
        self.battery = battery


def run(sim, seconds):
    for _ in range(int(round(seconds / sim.dt))):
        sim.step()


class PowerModelTests(unittest.TestCase):
    def test_every_value_carries_a_source(self):
        for model, profile in POWER_PROFILES.items():
            for key, item in profile.items():
                with self.subTest(model=model, key=key):
                    self.assertIn("value", item)
                    self.assertTrue(item["source"])

    def test_budget_scales_thrust_only_when_demand_exceeds_it(self):
        power = PowerSystem("x1")
        rc = RCState(right_switch=2)
        light = np.array([0.5, 0.5, 0, 0, 0, 0])
        np.testing.assert_array_equal(power.apply(Stub(), light, rc), light)
        self.assertFalse(power.limited)
        full = np.ones(6)
        scaled = power.apply(Stub(), full, rc)
        self.assertTrue(power.limited)
        self.assertTrue(np.all(scaled < 1))
        self.assertAlmostEqual(float(scaled[0]), float(scaled[5]))
        self.assertLessEqual(power.demand_w, power.values["available_w"] + 1e-6)
        sign = power.apply(Stub(), -full, rc)
        self.assertTrue(np.all(sign < 0))

    def test_lights_share_the_budget(self):
        power = PowerSystem("x1")
        dark = power.apply(Stub(), np.ones(6), RCState(right_switch=0))
        lit = power.apply(Stub(), np.ones(6), RCState(right_switch=2))
        self.assertGreater(dark[0], lit[0])

    def test_supply_sag_reduces_the_budget(self):
        power = PowerSystem("x1")
        full = power.apply(Stub(100), np.ones(6), RCState())[0]
        sag = power.apply(Stub(50), np.ones(6), RCState())[0]
        self.assertLess(sag, full)

    def test_trip_removes_thrust_and_lights(self):
        power = PowerSystem("x1")
        power.trip()
        out = power.apply(Stub(), np.ones(6), RCState(right_switch=2))
        self.assertFalse(np.any(out))
        self.assertFalse(power.lights_on)
        self.assertEqual(power.demand_w, 0)
        power.reset()
        self.assertTrue(np.any(power.apply(Stub(), np.ones(6), RCState())))

    def test_battery_cutoff_with_hysteresis(self):
        power = PowerSystem("bluerov2_heavy")
        self.assertFalse(power.tether)
        self.assertTrue(np.any(power.apply(Stub(0.5), np.ones(8), RCState())))
        self.assertFalse(np.any(power.apply(Stub(0.0), np.ones(8), RCState(right_switch=2))))
        self.assertTrue(power.cutoff)
        self.assertFalse(power.lights_on)
        self.assertFalse(np.any(power.apply(Stub(1.0), np.ones(8), RCState())))
        self.assertTrue(np.any(power.apply(Stub(5.0), np.ones(8), RCState())))
        self.assertIsNotNone(power.voltage(Stub(50)))


class SimulatorPowerTests(unittest.TestCase):
    def test_x1_is_tether_powered_and_does_not_drain(self):
        sim = Simulator()
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000
        run(sim, 2)
        self.assertEqual(sim.battery, 100.0)
        state = sim.viewer_state()
        self.assertEqual(state["battery"], 100.0)
        self.assertEqual(state["power"]["type"], "tether")
        self.assertIsNone(state["power"]["soc"])
        self.assertGreater(state["power"]["demand_w"], 0)

    def test_full_demand_is_power_limited(self):
        sim = Simulator()
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000          # full surge and full heave with the lights on
        sim.rc_physical.left_wave = 2000
        sim.rc_physical.right_switch = 2
        limited = []
        for _ in range(100):
            sim.step()
            limited.append(sim.viewer_state()["power"]["limited"])
        self.assertTrue(any(limited))
        state = sim.viewer_state()["power"]
        self.assertLessEqual(state["demand_w"], state["available_w"] + 1)

    def test_sdk_telemetry_is_backward_compatible(self):
        sim = Simulator()
        rov = sim.sdk_call("QYRovNavigationManage", "get_rov_data", [["rov"]], {})["data"]["rov"]
        self.assertEqual(rov["power"]["type"], "tether")
        self.assertEqual(rov["power"]["battery_cap_1"], 100)
        self.assertEqual(rov["power"]["battery_cap_2"], 100)
        self.assertIn("available_w", rov["power"])
        self.assertEqual(rov["endurance"], 5000)
        status = sim.sdk_call("QYRovRealTimeStatusManage", "get_rov_status", [], {})
        self.assertEqual(status["Battery"], "Left: 100, Right: 100")

    def test_battery_models_keep_battery_telemetry_and_cut_off(self):
        sim = Simulator(model_id="bluerov2_heavy")
        rov = sim.sdk_call("QYRovNavigationManage", "get_rov_data", [["rov"]], {})["data"]["rov"]
        self.assertEqual(set(rov["power"]), {"type", "battery_cap_1", "battery_cap_2"})
        self.assertEqual(rov["power"]["type"], "battery")
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000
        sim.battery = 0.0
        run(sim, 0.5)
        self.assertLess(np.abs(sim.vehicle.s.thrust).max(), 1e-6)
        self.assertTrue(sim.viewer_state()["power"]["cutoff"])

    def test_battery_drain_formula_is_unchanged_for_battery_models(self):
        sim = Simulator(model_id="bluerov2_heavy")
        run(sim, 1)
        self.assertAlmostEqual(sim.battery, 100.0 - 0.004, places=6)


if __name__ == "__main__":
    unittest.main()
