"""Reservoir scenario wiring and photographic mission evidence."""
import unittest
import numpy as np
from qysim.engine import Simulator
from qysim.scenarios import build
from qysim.physics import q_from_euler


class ReservoirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = Simulator('reservoir_intake')

    def test_configuration(self):
        sc = build('reservoir_intake')
        self.assertEqual((sc.water, sc.visibility_m, sc.seabed_type), ('fresh', 3, 'mud'))
        self.assertEqual(sc.summary()['water_type'], 'fresh_green')
        self.assertEqual(len(sc.objectives), 3)
        self.assertIsNone(sc.current.tide)
        sim = self.sim
        self.assertLess(sim.tether.tension_max, 1.)
        self.assertFalse(sim.tether.broken)
        self.assertGreater(sim.world.sdf(np.asarray(sc.start_pos))[0], .4)
        np.testing.assert_allclose(sim.world.current_at(sc.start_pos), 0)
        self.assertGreater(sim.world.current_at((18, 0, 10))[0], 0)
        self.assertEqual(len(sim.world.habitat_entities), 0)
        self.assertTrue(any(getattr(o, 'snag_hold', None) for o in sc.obstacles))

    def test_photo_requires_order_range_and_orientation(self):
        sim = self.sim
        sim.vehicle.s.pos[:] = (18, 0, 10)
        sim._take_photo()
        self.assertFalse(sim.scenario.objectives[1].done)
        sim.scenario.objectives[0].done = True
        sim.scorer.current_index = 1
        sim.vehicle.s.q[:] = q_from_euler(0, 0, np.pi)
        sim._take_photo()
        self.assertFalse(sim.scenario.objectives[1].done)
        sim.vehicle.s.q[:] = q_from_euler(0, 0, 0)
        sim.vehicle.s.pos[:] = (10, 0, 10)
        sim._take_photo()
        self.assertFalse(sim.scenario.objectives[1].done)
        sim.vehicle.s.pos[:] = (18, 0, 10)
        sim._take_photo()
        self.assertTrue(sim.scenario.objectives[1].done)
        from qysim.world import Box
        sim.scenario.objectives[1].done = False
        sim.world.obstacles.append(Box('occluder', (19, 0, 10), (.2, 1, 1)))
        sim._take_photo()
        self.assertFalse(sim.scenario.objectives[1].done)
