"""Sensor noise, filtered feedback, geometry rejection and imaging fan regressions."""
import math
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_from_euler
from qysim.sensors import SensorConfig
from qysim.sonar import scan
from qysim.world import Box, World


class FeedbackTests(unittest.TestCase):
    def test_temperature_offset_and_pressure_statistics(self):
        cfg = SensorConfig(depth_reference_c=10, depth_zero_sigma_m=0)
        sim = Simulator("open_water", 31, sensor_config=cfg)
        sim.vehicle.s.pos[2] = 20
        samples = [sim.sensors._depth_reading(sim) for _ in range(4096)]
        self.assertAlmostEqual(np.mean(samples), 20 + (23 - 10) * cfg.depth_temp_m_per_c, delta=0.0003)
        self.assertAlmostEqual(np.std(samples), cfg.depth_noise_m, delta=0.0003)

    def test_gyro_walk_increment_statistics(self):
        sim = Simulator("open_water", 17)
        cfg = sim.sensor_config
        bias = [sim.sensors.gyro_bias]
        for _ in range(1600):
            sim.sensors.step(sim.dt, sim)
            bias.append(sim.sensors.gyro_bias)
        increments = np.diff(bias)
        sigma = math.radians(cfg.gyro_walk_deg_min) / 60 * math.sqrt(sim.dt / 60)
        self.assertAlmostEqual(np.mean(increments), 0, delta=sigma * .1)
        self.assertAlmostEqual(np.std(increments), sigma, delta=sigma * .08)

    def test_pressure_rate_and_apparent_tilt(self):
        sim = Simulator("open_water", 33)
        sim.vehicle.s.q = q_from_euler(0, 0, 0)
        sim.sensors.reset(sim)
        sim.vehicle.s.accel[0] = 1
        for _ in range(200):
            sim.vehicle.s.pos[2] += .002
            sim.sensors.step(.01, sim)
        roll, pitch, _ = sim.sensors.attitude(sim)
        self.assertAlmostEqual(math.degrees(pitch), math.degrees(math.atan(1 / 9.81)), delta=.5)
        self.assertAlmostEqual(roll, 0)
        self.assertAlmostEqual(sim.sensors.frame.vz, .2, delta=.06)
        self.assertAlmostEqual(sim.sensors.frame.omega[2], sim.sensors.gyro_bias)
        self.assertEqual(sim.viewer_state()["sensors"]["pitch"], round(math.degrees(pitch), 2))

    def test_net_and_tilt_disable_assist(self):
        for reason in ("net", "tilt"):
            with self.subTest(reason=reason):
                sim = Simulator("open_water", 34)
                sim.vehicle.s.pos[:] = (0, 0, 10)
                if reason == "net":
                    sim.world.obstacles = [Box("pen floor", (0, 0, 12), (6, 6, .025), kind="pen_net")]
                else:
                    sim.vehicle.s.q = q_from_euler(0, math.radians(50), 0)
                sim.rc_physical.assist = 2
                sim.rc_physical.rc_lock = 0
                sim.step()
                self.assertEqual(sim.sensors.frame.dvl_reason, reason)
                self.assertFalse(sim.sensors.frame.dvl_valid)
                self.assertEqual(sim.controller.assist_level, 0)

    def test_sidelobe_next_to_narrow_target(self):
        world = World(50)
        world.obstacles = [Box("target", (10.13, 0, 5), (.1, .1, 1))]
        args = world, np.array([0., 0., 5.]), q_from_euler(0, 0, 0)
        frame = scan(*args, noise=0, multipath=0)
        distance = frame["distance_m"][128]
        self.assertAlmostEqual(distance / .05, round(distance / .05))
        self.assertEqual(frame["distance_m"][132], 30)
        self.assertEqual(frame["sidelobe_m"][132], distance)
        self.assertGreater(frame["sidelobe_intensity"][132], 0)
        self.assertNotIn("sidelobe_m", scan(*args, ideal=True))
