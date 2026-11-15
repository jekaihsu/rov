"""Regional flow compatibility, actual environment wiring and reservoir evidence rules."""
import unittest
import numpy as np
from qysim.local_current import sample_regions
from qysim.engine import Simulator
from qysim.world import World, CurrentProfile
from qysim.reservoir import photo


class ReservoirTests(unittest.TestCase):
    def test_region_support_direction_addition_and_validation(self):
        region = dict(center=[0,0,5],radius_m=2,velocity=[.4,0,0])
        points = [[0,0,5],[1,0,5],[2,0,5],[3,0,5]]
        values = sample_regions(points,[region])
        np.testing.assert_allclose(values[:,0],[.4,.225,0,0])
        np.testing.assert_array_equal(values[:,1:],0)
        np.testing.assert_allclose(sample_regions(points,[region,region]),values*2)
        for radius in (0,-1,float('nan')):
            with self.assertRaises(ValueError):
                sample_regions(points,[dict(region,radius_m=radius)])

    def test_legacy_world_and_scalar_batch(self):
        world = World()
        world.current = CurrentProfile(0,0,0,0,0,0,0)
        np.testing.assert_array_equal(world.current_at([0,0,5]),[0,0,0])
        world.local_currents = [dict(center=[0,0,5],radius_m=2,velocity=[.4,0,0])]
        np.testing.assert_allclose(world.current_at([0,0,5]),[.4,0,0])
        np.testing.assert_allclose(world.current_at_many([[0,0,5]])[0],world.current_at([0,0,5]))

    def test_scene_and_photo(self):
        sim = Simulator('reservoir_intake',71)
        self.assertLess(sim.tether.tension_max, 5.)
        self.assertFalse(sim.tether.broken)
        self.assertEqual(sim.scenario.water,'fresh')
        self.assertEqual(sim.scenario.visibility_m,3)
        self.assertEqual(sim.scenario.summary()['water_type'],'fresh_green')
        self.assertEqual(sim.world.habitat_entities,[])
        self.assertGreater(sim.world.current_at([18,0,10])[0],0)
        np.testing.assert_array_equal(sim.world.current_at([22.5,0,10]),[0,0,0])
        np.testing.assert_array_equal(sim.world.current_at([3,0,1.5]),[0,0,0])
        for point in [sim.scenario.start_pos]+[o.point for o in sim.scenario.objectives]:
            self.assertGreater(sim.world.sdf(np.array(point,float))[0],.3,point)
        sim.vehicle.s.pos[:] = [18,0,10]
        sim.vehicle.s.q[:] = [1,0,0,0]
        photo(sim)
        self.assertFalse(sim.scenario.objectives[1].done)
        sim.scorer.current_index = 1
        sim.vehicle.s.q[:] = [0,0,0,1]
        photo(sim)
        self.assertFalse(sim.scenario.objectives[1].done)
        sim.vehicle.s.q[:] = [1,0,0,0]
        photo(sim)
        self.assertTrue(sim.scenario.objectives[1].done)
        self.assertTrue(any(getattr(o,'snag_hold',None) for o in sim.world.obstacles))
