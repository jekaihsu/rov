"""Probe the new harbor bents using the live hull and tether contact paths."""
import unittest

import numpy as np

from qysim.scenarios import harbor_inspection
from qysim.tether_contact import build
from qysim.world import World


class HarborBentsTest(unittest.TestCase):
    def setUp(self):
        scenario = harbor_inspection()
        self.world = World(scenario.seabed_depth)
        self.world.obstacles = scenario.obstacles

    def test_hull_meets_inner_pile(self):
        wrench = self.world.vehicle_contact(0, np.array([26., -6.65, 8.]), np.array([1., 0., 0., 0.]),
                                            np.zeros(3), np.zeros(3))
        self.assertLess(wrench[1], 0)
        self.assertIn("Harbor pile A2 inner", [event.obstacle for event in self.world.events])

    def test_long_tether_span_hits_pile_between_nodes(self):
        nodes = np.array([[24., -6., 8.], [28., -6., 8.]])
        candidates = self.world.near(nodes.min(axis=0), nodes.max(axis=0), .1)
        contacts = build(self.world, nodes, candidates, False, .005, .1, .05)
        hits = {self.world.obstacles[i].name for i in contacts.obstacle[contacts.dist0 < 0]}
        self.assertEqual(hits, {"Harbor pile A2 inner"})

    def test_tyre_has_a_clear_bore_and_snaggable_tread(self):
        tyre = [ob for ob in self.world.obstacles if ob.kind == "tyre_tread"]
        self.assertTrue(tyre)
        hole = np.array([38.8, 6.5, 17.9])
        self.assertGreater(min(ob.sdf(hole)[0] for ob in tyre), .14)
        self.assertLess(tyre[0].sdf(np.array(tyre[0].p0))[0], 0)
        self.assertTrue(all(ob.snag_hold for ob in tyre))
