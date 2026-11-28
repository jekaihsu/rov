"""Free-dive propeller colliders and separation from the existing wreck mission."""
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.scenarios import build
from qysim.tether import TetherParams


class WreckVisit(unittest.TestCase):
    def test_launch_tether_remains_intact(self):
        sim = Simulator("free_dive_wreck", 42)
        for _ in range(700):
            sim.step()
        self.assertFalse(sim.tether.broken)

    def test_route_and_propeller_collisions(self):
        visit = build("free_dive_wreck", 42)
        mission = build("korean_castle", 42)
        self.assertTrue(mission.objectives)
        self.assertFalse(visit.objectives)
        self.assertEqual(mission.obstacles[0].as_dict(), visit.obstacles[0].as_dict())
        blades = visit.obstacles[1:]
        self.assertEqual(len(blades), 9)
        for blade in blades:
            centre = (np.array(blade.p0) + blade.p1) / 2
            self.assertLess(blade.sdf(centre)[0], 0)
            self.assertGreater(blade.sdf(centre + 5)[0], 0)
            self.assertLess(np.linalg.norm(centre - visit.spool_pos), TetherParams().max_length)
        self.assertGreater(visit.obstacles[0].sdf(np.array(visit.start_pos))[0], 1)
