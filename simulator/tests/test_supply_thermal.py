"""Electrical operating points, accessory loads and thermal feedback regression tests."""
import math
import unittest
from types import SimpleNamespace

import numpy as np

from qysim.engine import Simulator
from qysim.power import PowerSystem
from qysim.rc import RCState
from qysim.thermal import ThermalModel, water_temperature


class SupplyTests(unittest.TestCase):
    def test_conductor_drop_and_power_balance(self):
        power = PowerSystem("x1")
        sim = SimpleNamespace(battery=100, tether=SimpleNamespace(length=10))
        previous = math.inf
        for length, fraction in ((10, .3), (100, .3), (100, .6)):
            sim.tether.length = length
            power.apply(sim, np.full(6, fraction), RCState())
            resistance = length * power.values["loop_ohm_m"]
            self.assertAlmostEqual(power.bus_v, power.values["source_v"] - resistance * power.current_a)
            self.assertAlmostEqual(power.demand_w, power.bus_v * power.current_a)
            self.assertLess(power.bus_v, previous)
            previous = power.bus_v

    def test_shared_and_single_motor_current(self):
        power = PowerSystem("bluerov2_heavy")
        sim = SimpleNamespace(battery=100)
        rc = RCState(right_switch=2)
        commands = np.array([1, -.7, .5, -1, .3, .8, 1, -1])
        out = power.apply(sim, commands, rc)
        np.testing.assert_allclose(out / commands, power.scale)
        self.assertAlmostEqual(power.current_a, power.values["total_limit_a"])
        power.values["branch_limit_a"] = 12
        out = power.apply(sim, commands[:1], rc)
        self.assertAlmostEqual(power.values["thruster_full_w"] * out[0] ** 1.5 / power.bus_v, 12)
        self.assertAlmostEqual(power.bus_v, power.voltage(sim) - power.values["internal_ohm"] * power.current_a)

    def test_loaded_cutoff_and_recovery(self):
        power = PowerSystem("bluerov2_heavy")
        sim = SimpleNamespace(battery=.5)
        full = np.ones(8)
        self.assertGreater(power.apply(sim, full, RCState())[0], 0)
        self.assertTrue(power.voltage_limited)
        self.assertFalse(power.apply(sim, full, RCState(right_switch=2)).any())
        self.assertTrue(power.cutoff)
        self.assertFalse(power.apply(sim, full, RCState()).any())
        sim.battery = 5
        self.assertGreater(power.apply(sim, full, RCState())[0], 0)

    def test_accessory_demand(self):
        sim = Simulator(model_id="bluerov2_heavy")
        sim.step()
        idle = sim.power.demand_w
        sim.camera.recording_since = 0
        sim.rc_physical.right_switch = 2
        sim.step()
        self.assertAlmostEqual(sim.power.demand_w, idle + sim.power.values["record_w"] + sim.power.lights_w)
        self.assertGreater(min(sim.power.aux_w.values()), 0)


class ThermalTests(unittest.TestCase):
    def test_one_time_constant_heating_and_cooling(self):
        model = ThermalModel(1)
        sim = SimpleNamespace(depth=0, vehicle=SimpleNamespace(s=SimpleNamespace(thrust=np.ones(1)),
                                                               p=SimpleNamespace(thruster_max=1)))
        tau = model.p["motor_tau_water_s"]
        model.step(sim, tau)
        ambient = water_temperature(0)
        rise = model.p["motor_rise_water_c"] * (1 - math.exp(-1))
        self.assertAlmostEqual(model.motor_c[0], ambient + rise)
        sim.vehicle.s.thrust[:] = 0
        model.step(sim, tau)
        self.assertAlmostEqual(model.motor_c[0], ambient + rise * math.exp(-1))

    def test_overheat_reduces_physical_thrust(self):
        sim = Simulator()
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 1900
        sim.step()
        self.assertGreater(sim.power.thruster_w, 0)
        sim.thermal.injected_c = 90
        before = np.linalg.norm(sim.vehicle.s.thrust)
        sim.step()
        self.assertLess(np.linalg.norm(sim.vehicle.s.thrust), before)
        self.assertTrue(sim.viewer_state()["thermal"]["derated"])
        self.assertEqual(sim.power.thruster_w, 0)
