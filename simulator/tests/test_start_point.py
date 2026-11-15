"""Optional assisted start point: only the spawn point moves; locked, procedure-free vehicles only."""
import math
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.server import SimHost
from qysim.start_point import SCENARIOS, apply_near_target_start, near_target_pose


def loaded(key):
    sim = Simulator()
    sim.load_scenario(key, 42)
    return sim


class NearTargetStartTest(unittest.TestCase):
    def test_every_listed_scenario_offers_a_clear_point_in_front_of_its_work(self):
        for key in SCENARIOS:
            with self.subTest(key=key):
                sim = loaded(key)
                pose = near_target_pose(sim)
                self.assertIsNotNone(pose)
                point = np.asarray(pose["pos"])
                self.assertGreaterEqual(sim.world.depth_at(point) - point[2], 2.5 - 1e-6)
                self.assertGreater(sim.world.sdf(point)[0], 1.5)
                start = np.asarray(sim.scenario.start_pos, float)
                goal = np.asarray(next(o.point for o in sim.scenario.objectives if o.point is not None), float)
                self.assertLess(np.linalg.norm(goal - point), np.linalg.norm(goal - start))

    def test_surface_starts_stay_where_the_scenario_puts_them(self):
        for key in ("tutorial_pool", "sonar_search", "incident_silt", "tether_untangle"):
            with self.subTest(key=key):
                self.assertIsNone(near_target_pose(loaded(key)))
                self.assertNotIn("near_start", loaded(key).world_description())

    def test_applying_moves_only_the_spawn_and_rebuilds_tether_and_sensors(self):
        sim = loaded("coral_reef")
        objectives = [o.as_dict() for o in sim.scenario.objectives]
        result = apply_near_target_start(sim)
        self.assertTrue(result["ok"])
        np.testing.assert_allclose(sim.vehicle.s.pos, result["start"]["pos"])
        self.assertAlmostEqual(math.degrees(sim.vehicle.euler[2]) % 360, result["start"]["heading"], places=3)
        self.assertEqual([o.as_dict() for o in sim.scenario.objectives], objectives)
        gland = sim.tether.x[-1]
        self.assertLess(np.linalg.norm(gland - sim.vehicle.s.pos), 1.0)
        self.assertAlmostEqual(sim.sensors.frame.depth, sim.vehicle.s.pos[2], delta=0.3)
        for _ in range(200):
            sim.step()
        self.assertLess(np.linalg.norm(sim.vehicle.s.pos - result["start"]["pos"]), 1.0)

    def test_refused_once_unlocked_or_inside_the_procedure(self):
        sim = loaded("coral_reef")
        sim.rc_physical.rc_lock = 0
        with self.assertRaises(ValueError):
            apply_near_target_start(sim)
        sim = loaded("coral_reef")
        sim.procedure.action({"action": "begin"})
        with self.assertRaises(ValueError):
            apply_near_target_start(sim)

    def test_server_message_and_world_field(self):
        server = SimHost(loaded("coral_reef"))
        world = server.sim.world_description()
        self.assertEqual(world["near_start"], near_target_pose(server.sim))
        reply = server.handle_viewer({"type": "start", "point": "near_target"})
        self.assertEqual(reply["type"], "start_result")
        self.assertTrue(reply["ok"])
        with self.assertRaises(ValueError):
            server.handle_viewer({"type": "start", "point": "seabed"})


if __name__ == "__main__":
    unittest.main()
