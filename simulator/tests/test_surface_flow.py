"""Scenario flow extensions sampled at the same NED points and clock as physics."""
import math
import unittest

import numpy as np

from qysim.aquaculture import CENTER, RADIUS
from qysim.flow import AiryWave, Tide
from qysim.scenarios import aquaculture_pen, jacket_inspection
from qysim.world import CurrentProfile, World


class SurfaceFlowTests(unittest.TestCase):
    def test_regular_wave_depth_direction_and_phase(self):
        wave = AiryWave(0.4, 4, 90)
        k = (math.tau / 4) ** 2 / 9.81
        points = np.array([[0, 0, 0], [0, 0, 1 / k], [0, math.pi / k, 0]])
        amplitude = 0.2 * math.tau / 4
        np.testing.assert_allclose(wave.velocity(points, 0)[:, 1], amplitude * np.array([1, 1 / math.e, -1]))
        np.testing.assert_allclose(wave.velocity(points, 1)[0], [0, 0, amplitude], atol=1e-12)

    def test_scenario_period_slack_and_reversal(self):
        tide = Tide.from_dict({"period_s": 80})
        profile = CurrentProfile(surface_kn=1, tide=tide)
        initial = profile.at(0, 30)
        profile.step_gust(20)
        np.testing.assert_allclose(profile.at(0, 30), 0, atol=1e-12)
        profile.step_gust(20)
        np.testing.assert_allclose(profile.mean_at(0, 30)[1], -0.514444, atol=1e-5)
        self.assertGreater(initial[1], 0)
        for invalid in (True, 0, float("inf")):
            with self.assertRaises(ValueError):
                Tide.from_dict({"period_s": invalid})

    def test_seeded_shared_queries_are_order_independent(self):
        points = np.array([[0, 1, 2], [1, 2, 8], [2, 3, 18]])
        a, b = (jacket_inspection().current for _ in range(2))
        for profile in (a, b):
            profile.reseed(723)
            profile.step_gust(0.01)
        np.testing.assert_array_equal(a.sample_many(points, 32), b.sample_many(points[::-1], 32)[::-1])

    def test_net_shelters_and_accelerates_flanks(self):
        world = World()
        scene = aquaculture_pen()
        world.obstacles = scene.obstacles
        world.current = CurrentProfile(1, 0, 1, 0, 1, 0, 0, bypass_flow=True)
        n, e = CENTER
        speeds = world.current_at_many([[n, e, 6], [n, e + 1.05 * RADIUS, 6], [n + 4 * RADIUS, e, 6]])[:, 0]
        self.assertLess(speeds[0], speeds[2])
        self.assertGreater(speeds[1], speeds[2])

    def test_hull_shelter_and_shoulder_match_reference(self):
        from qysim.world import ShipHull
        world = World()
        world.obstacles = [ShipHull("test hull", (0., 0., 0.), 0., 40., 10., 5.)]
        world.current = CurrentProfile(1, 0, 1, 0, 1, 0, 0, bypass_flow=True)
        points = [[21, 0, 3], [0, 7, 3], [0, 7, 15]]
        fast = world.current_at_many(points)
        self.assertLess(fast[0, 0], fast[2, 0])
        self.assertGreater(fast[1, 0], fast[2, 0])
        world.structure_flow().use_compiled = False
        np.testing.assert_allclose(fast, world.current_at_many(points), atol=1e-12)

    def test_wave_reaches_viewer_grid(self):
        from qysim.engine import Simulator
        sim = Simulator("jacket_inspection", seed=12)
        sim.world.current = CurrentProfile(wave=AiryWave(0.45, 4, 90))
        sim.world.current.step_gust(1)
        grid = sim.flow_field_state()
        origin = grid["origin"]
        expected = sim.world.current_at(origin)
        self.assertGreater(np.linalg.norm(expected), 0.1)
        np.testing.assert_allclose(np.array(grid["cm_s"][:3]) / 100, expected, atol=0.0051)

    def test_surface_wave_drives_vehicle_and_tether_in_still_water(self):
        from qysim.engine import Simulator
        calm, swell = (Simulator("open_water", seed=9) for _ in range(2))
        calm.world.current = CurrentProfile()
        swell.world.current = CurrentProfile(wave=AiryWave(0.4, 4., 90.))
        for _ in range(25):
            calm.step(.01)
            swell.step(.01)
        self.assertGreater(np.linalg.norm(swell.vehicle.s.vel - calm.vehicle.s.vel), 0.01)
        self.assertGreater(np.linalg.norm(swell.tether.v - calm.tether.v), 0.01)
        self.assertGreater(np.ptp(swell.tether._cur[:, 1]), 0.01)
