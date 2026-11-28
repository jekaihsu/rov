"""Annual wind-farm watches flown through the same RC and tether solver as the cold open."""
import math
import unittest

from qysim.engine import Simulator
from qysim import cold_open
from test_cold_open import fly_to, sticks


class WindWatchTests(unittest.TestCase):
    def test_live_set_moves_vehicle_even_at_held_depth(self):
        for seed in (7, 42):
            with self.subTest(seed=seed):
                sim = Simulator('wind_set', seed)
                east = sim.vehicle.s.pos[1]
                sticks(sim, 9)
                self.assertGreater(sim.vehicle.s.pos[1] - east, 1)

    def test_b_anode_enters_visual_range_on_approach(self):
        sim = Simulator('wind_shadow', 42)
        target = sim.scenario.objectives[0]
        self.assertGreater(math.dist(sim.vehicle.s.pos, target.face_point), sim.camera_turbidity()['visibility_m'])
        fly_to(sim, target.point[:2], 18, yaw=math.radians(135))
        self.assertLess(math.dist(sim.vehicle.s.pos, target.face_point), sim.camera_turbidity()['visibility_m'])

    def arrive_at_hook(self, seed):
        sim = Simulator('wind_return', seed)
        sticks(sim, 13)
        c, b = sim.scenario.objectives[:2]
        fly_to(sim, c.point[:2], 16, yaw=math.radians(45))
        self.assertFalse(sim.tether.broken)
        self.assertFalse(sim.tether.snags.hooks)
        speed = .6 if seed == 7 else .32
        self.assertTrue(fly_to(sim, b.point[:2], 35, speed=speed, until=lambda: bool(sim.tether.snags.hooks)))
        self.assertEqual(sim.tether.snags.hooks[0].name, cold_open.SNAG_ANODE)
        return sim

    def test_reverse_frees_line_intact(self):
        for seed in (7, 42):
            with self.subTest(seed=seed):
                sim = self.arrive_at_hook(seed)
                sticks(sim, 2)
                self.assertTrue(fly_to(sim, cold_open.START[:2], 30, yaw=sim.yaw,
                                       until=lambda: not sim.tether.snags.hooks))
                self.assertFalse(sim.tether.broken)

    def test_full_thrust_parts_the_loaded_termination(self):
        for seed in (7, 42):
            with self.subTest(seed=seed):
                sim = self.arrive_at_hook(seed)
                self.assertTrue(sticks(sim, 75, surge=1, until=lambda: sim.tether.broken))
                self.assertEqual(sim.tether.break_reason, 'gland')
