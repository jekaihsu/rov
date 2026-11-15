"""Route arclength, projection, collision clearance and explicit survey evidence contracts."""
import math
import unittest
from types import SimpleNamespace
import numpy as np
from qysim.cable_route import layout, project, at, CableTerrain, update, photo
from qysim.scenarios import build, Scorer
from qysim.world import World
from qysim.physics import q_from_euler
from qysim.sensors import raycast_many


class CableTests(unittest.TestCase):
    def test_route_and_seed(self):
        obs, data = layout(51)
        self.assertEqual(data, layout(51)[1])
        self.assertNotEqual(data['anomalies'], layout(52)[1]['anomalies'])
        points = data['centerline']
        length = np.linalg.norm(np.diff([p['pos'] for p in points], axis=0), axis=1).sum()
        self.assertAlmostEqual(length, 300, places=7)
        self.assertEqual(points[-1]['kp_km'], .3)
        self.assertEqual([m['chainage_m'] for m in data['markers']], list(range(0, 301, 50)))
        for p in points:
            s, error = project(points, p['pos'])
            self.assertAlmostEqual(s, p['chainage_m'])
            self.assertAlmostEqual(error, 0)
        self.assertFalse(any(o.name == 'route-0' for o in obs))
        self.assertEqual(len(build('cable_survey').objectives), 3)

    def test_span_gap(self):
        obs, data = layout()
        world = World(33)
        world.obstacles = obs
        world.terrain = CableTerrain()
        p = np.array(data['anomalies'][-1]['pos'])
        gap = world.seabed_at(p) - p[2] - .1
        self.assertGreater(gap, .4)
        self.assertGreater(world.sdf(p + [0, 0, gap / 2 + .1])[0], .05)
        self.assertLess(world.sdf(p)[0], 0)
        down = np.array([0., 0., 1.])
        self.assertAlmostEqual(world.raycast(p - down, down), .9, delta=.04)
        ranges, hits, _, indices = raycast_many(world, np.array([p - down, p + down * .25]),
                                               np.array([down, down]), 5.)
        self.assertTrue(hits.all())
        self.assertGreaterEqual(indices[0], 0)
        self.assertEqual(indices[1], -1)
        self.assertAlmostEqual(ranges[0], .9, delta=.04)
        under = p + down * .25
        self.assertAlmostEqual(world.raycast(under, down), world.seabed_at(under) - under[2], delta=.05)
        self.assertGreater(data['free_span']['length_m'], data['free_span']['allowable_m'])

    def test_no_remote_coverage_or_photo(self):
        sc = build('cable_survey')
        scorer = Scorer(sc)
        world = World(33)
        world.obstacles = sc.obstacles
        world.terrain = CableTerrain()
        state = SimpleNamespace(pos=np.array([0., 0., 1.]), q=np.array([1., 0., 0., 0.]))
        sim = SimpleNamespace(scenario=sc, scorer=scorer, world=world, vehicle=SimpleNamespace(s=state), t=0.)
        update(scorer, sim)
        photo(sim)
        self.assertEqual(len(scorer.cable_coverage), 0)
        self.assertEqual(scorer.cable_records, {})
        for s in np.arange(.5, 300, 1):
            state.pos = at(sc.cable_route['centerline'], s) - [0, 0, 1.5]
            update(scorer, sim)
        self.assertTrue(sc.objectives[0].done)
        self.assertFalse(sc.objectives[1].done)
        self.assertFalse(sc.objectives[2].done)

    def test_photo_records_endpoints_and_measured_length(self):
        sc = build('cable_survey')
        scorer = Scorer(sc)
        state = SimpleNamespace(pos=np.zeros(3), q=np.array([1., 0., 0., 0.]))
        world = World(33)
        world.obstacles = sc.obstacles
        world.terrain = CableTerrain()
        sim = SimpleNamespace(scenario=sc, scorer=scorer, world=world, vehicle=SimpleNamespace(s=state), t=12.)
        for key in ('start', 'end'):
            target = np.array(sc.cable_route['free_span'][key]['pos'])
            state.pos = target - [2., .5, 1.5]
            state.q = q_from_euler(0., -math.atan2(1.5, math.hypot(2., .5)), math.atan2(.5, 2.))
            photo(sim)
        self.assertTrue(sc.objectives[2].done)
        for anomaly in sc.cable_route['anomalies']:
            state.pos = np.array(anomaly['pos']) - [2., .5, 1.5]
            photo(sim)
        self.assertTrue(sc.objectives[1].done)
        self.assertAlmostEqual(scorer.cable_span_m, sc.cable_route['free_span']['length_m'])
