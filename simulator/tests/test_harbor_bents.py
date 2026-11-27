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

    def test_survey_targets_resolve_to_their_rendered_sites(self):
        from qysim.engine import Simulator
        from qysim.expedition import Expedition

        sim = Simulator("harbor_inspection", seed=42)
        sites = [entity for entity in sim.world.habitat_entities if entity["id"].startswith("harbor-")]
        self.assertEqual(len(sites), 22)
        self.assertEqual(len({site["id"] for site in sites}), len(sites))
        self.assertEqual(len(sim.world.fish_schools), 4)
        tools = [site for site in sites if site["kind"] == "harbor_tool"]
        self.assertEqual({site["variant"] for site in tools}, {0, 1, 2})
        expedition = Expedition(sim)
        for site in tools:
            category, point, radius = Expedition._entity(sim, site["id"])
            self.assertEqual(category, site["kind"])
            np.testing.assert_allclose(point[:2], site["pos"][:2])
            self.assertLess(abs(point[2] - sim.world.depth_at(point)), radius)
            camera = point - np.array([1.2, 0, .4])
            sim.vehicle.s.pos[:] = camera - sim.vehicle.definition.camera_body
            sim.vehicle.s.q[:] = [1, 0, 0, 0]
            reply = expedition.observe(sim, dict(photo_id=site["id"], entity_id=site["id"],
                                       view="onboard", visible=True, coverage=.03,
                                       camera=dict(pos=camera.tolist(), q=[1, 0, 0, 0], fov=70, aspect=1.6)))
            self.assertTrue(reply["observation"]["accepted"], reply)
