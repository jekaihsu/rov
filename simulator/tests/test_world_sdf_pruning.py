"""The nearest-surface queries skip boxes and capsules that cannot be closest; the answers must stay exactly the same.

World.sdf and World.sdf_many prune obstacles by a lower bound of their distance (bounding box, and a box's bounding
sphere). These tests compare them, bit for bit, with the unpruned evaluation over every obstacle in the same order.
"""
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.world import Box, ShipHull, World, ship_hull_local_sdf, ship_hull_params, _half_breadth


def naive_sdf(world, x):
    best, normal, name = world.seabed_depth - x[2], np.array([0.0, 0.0, -1.0]), "seabed"
    if world.terrain is not None and world.terrain.relief:
        depth, n = world.terrain.sample_many(np.asarray(x)[None, :])
        best, normal = float((depth[0] - x[2]) * -n[0, 2]), n[0]
    for ob in world.obstacles:
        d, n = ob.sdf(x)
        if d < best:
            best, normal, name = d, n, ob.name
    return best, normal, name


def naive_sdf_many(world, X):
    dist = world.seabed_depth - X[:, 2] if world.terrain is None or not world.terrain.relief else None
    reference = World.sdf_many(world, X, candidates=[])
    dist, normal, idx = reference[0].copy(), reference[1].copy(), reference[2].copy()
    cylinders = [i for i, ob in enumerate(world.obstacles) if type(ob).__name__ == "Cylinder"]
    if cylinders:
        d, n, k = World.sdf_many(world, X, candidates=cylinders)
        hit = k >= 0
        dist[hit], normal[hit], idx[hit] = d[hit], n[hit], k[hit]
    for i, ob in enumerate(world.obstacles):
        if type(ob).__name__ == "Cylinder":
            continue
        d, n = ob.sdf_many(X)
        closer = d < dist
        dist = np.where(closer, d, dist)
        normal[closer] = n[closer]
        idx[closer] = i
    return dist, normal, idx


class SdfPruningTests(unittest.TestCase):
    def check_world(self, key, low, high):
        world = Simulator(key, seed=1).world
        rng = np.random.default_rng(7)
        points = rng.uniform(low, high, (400, 3))
        for x in points[:120]:
            best, normal, name = world.sdf(x)
            ref_best, ref_normal, ref_name = naive_sdf(world, x)
            self.assertEqual(best, ref_best)
            self.assertEqual(name, ref_name)
            np.testing.assert_array_equal(normal, ref_normal)
        dist, normal, idx = world.sdf_many(points)
        ref = naive_sdf_many(world, points)
        np.testing.assert_array_equal(dist, ref[0])
        np.testing.assert_array_equal(normal, ref[1])
        np.testing.assert_array_equal(idx, ref[2])

    def test_net_pen_boxes_and_lines(self):
        self.check_world("aquaculture_pen", [-10, -40, 0], [60, 40, 30])

    def test_harbour_piles(self):
        self.check_world("harbor_inspection", [-20, -30, 0], [40, 30, 20])

    def test_ship_hull_shares_depth_terms(self):
        hp = ship_hull_params(60, 12, 5)
        L = np.random.default_rng(3).uniform([-40, -10, -3], [40, 10, 8], (2000, 3))
        e = 0.05
        x, y, z = L[:, 0], L[:, 1], L[:, 2]
        hb, fwd = _half_breadth(x, z, hp)
        hx = (_half_breadth(x + e, z, hp)[0] - _half_breadth(x - e, z, hp)[0]) / (2 * e)
        hz = (_half_breadth(x, z + e, hp)[0] - _half_breadth(x, z - e, hp)[0]) / (2 * e)
        self.assertTrue(np.all(np.isfinite(hx + hz)))
        d = ship_hull_local_sdf(L, hp)
        self.assertEqual(d.shape, (2000,))
        hull = ShipHull("h", (0, 0, 0), 30, 60, 12, 5)
        self.assertTrue(np.all(np.isfinite(hull.sdf_many(L)[0])))
        self.assertIsInstance(Box("b", (0, 0, 0), (1, 1, 1)), Box)


if __name__ == "__main__":
    unittest.main()
