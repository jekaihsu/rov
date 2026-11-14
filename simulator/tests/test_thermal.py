"""Thermal model: modelled self-test temperatures, dry-run and in-water overheating warnings."""
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.thermal import THERMAL_PARAMETERS, ThermalModel


class Vehicle:
    def __init__(self, load):
        self.s = type("S", (), {"thrust": np.full(6, 100.0 * load)})()
        self.p = type("P", (), {"thruster_max": 100.0})()


class Stub:
    def __init__(self, load, on_deck=False, depth=5.0):
        self.vehicle = Vehicle(load)
        self.on_deck = on_deck
        self.depth = depth


def advance(model, sim, seconds, dt=0.1):
    for _ in range(int(round(seconds / dt))):
        model.step(sim, dt)


class ThermalModelTests(unittest.TestCase):
    def test_parameters_carry_sources(self):
        for key, item in THERMAL_PARAMETERS.items():
            with self.subTest(key=key):
                self.assertTrue(item["source"])

    def test_idle_in_water_matches_the_former_constant_self_test(self):
        model = ThermalModel(6, depth=0.0)
        self.assertAlmostEqual(model.housing_c, 31.0)
        self.assertAlmostEqual(model.mos_c, 38.0)
        self.assertEqual(model.warnings(), [])

    def test_dry_run_warns_after_thirty_seconds(self):
        model = ThermalModel(6)
        deck = Stub(0.3, on_deck=True)
        advance(model, deck, 29)
        self.assertNotIn("dry_run", model.warnings())
        advance(model, deck, 2)
        self.assertIn("dry_run", model.warnings())
        self.assertFalse(model.state()["in_water"])
        advance(model, Stub(0.3), 0.1)
        self.assertNotIn("dry_run", model.warnings())

    def test_idle_motors_on_deck_do_not_count(self):
        model = ThermalModel(6)
        advance(model, Stub(0.0, on_deck=True), 60)
        self.assertEqual(model.dry_run_s, 0)

    def test_sustained_full_thrust_in_water_overheats(self):
        model = ThermalModel(6)
        advance(model, Stub(0.5), 600)
        self.assertNotIn("motor_hot", model.warnings())
        model = ThermalModel(6)
        advance(model, Stub(1.0), 600)
        self.assertIn("motor_hot", model.warnings())

    def test_injected_overheat_raises_readings(self):
        model = ThermalModel(6)
        model.injected_c = 50
        self.assertIn("motor_hot", model.warnings())
        self.assertIn("electronics_hot", model.warnings())


class SimulatorThermalTests(unittest.TestCase):
    def test_state_and_self_test_use_the_model(self):
        sim = Simulator()
        state = sim.viewer_state()
        self.assertIn("thermal", state)
        self.assertEqual(state["leak"], {"detected": False})
        test = sim.sdk_call("QYRovCheckManage", "ego_self_test", [], {})["text"]
        self.assertEqual(test["leak"], 1)
        self.assertEqual(test["temp"], round(sim.thermal.housing_c))
        self.assertEqual(test["mos_temp"], round(sim.thermal.mos_reading_c))
        sim.leak = True
        sim.thermal.injected_c = 30
        test = sim.sdk_call("QYRovCheckManage", "ego_self_test", [], {})["text"]
        self.assertEqual(test["leak"], 0)
        self.assertGreater(test["mos_temp"], 60)

    def test_running_on_deck_logs_a_warning(self):
        sim = Simulator()
        sim.on_deck = True
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 1800
        for _ in range(3100):
            sim.step()
        self.assertIn("dry_run", sim.viewer_state()["thermal"]["warnings"])
        self.assertTrue(any(line["kind"] == "thermal" for line in sim.log))


if __name__ == "__main__":
    unittest.main()
