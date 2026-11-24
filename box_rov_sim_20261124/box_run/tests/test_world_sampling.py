"""Scalar query parity: preserve terrain, current and collision behavior."""
import unittest

import numpy as np

from rov01sim.ecology import SeabedTerrain
from rov01sim.world import Box, CurrentProfile, Cylinder, World


class TestWorldSampling(unittest.TestCase):
    def test_terrain_random_points_and_outside_edges_match_batch(self):
        rng = np.random.default_rng(627)
        edges = [-1000., -100.000001, -100., -95., 0., 95., 99.999995, 100., 100.000001, 1000.]
        boundary = np.array([[x, y, 12.] for x in edges for y in edges])
        positions = np.vstack([rng.uniform(-160., 160., (300, 3)), boundary])
        for seed in (0, 17, 800):
            for relief in (0., .5, 1.4):
                with self.subTest(seed=seed, relief=relief):
                    terrain = SeabedTerrain(30., seed, relief)
                    expected_depth, expected_normal = terrain.sample_many(positions)
                    actual = [terrain.sample_one(position) for position in positions]
                    np.testing.assert_allclose([a[0] for a in actual], expected_depth, rtol=0., atol=1e-13)
                    np.testing.assert_allclose([a[1] for a in actual], expected_normal, rtol=0., atol=3e-16)

    def test_terrain_mutations_take_effect_without_stale_cache(self):
        terrain = SeabedTerrain(30., 8, 1.)
        terrain.origin[:] = [-30., -70.]
        terrain.spacing = 3.5
        terrain.depths[10:16, 12:18] += .37
        positions = np.array([[11., -15., 7.], [900., -900., -3.]])
        depths, normals = terrain.sample_many(positions)
        for index, point in enumerate(positions):
            depth, normal = terrain.sample_one(point.tolist())
            self.assertAlmostEqual(depth, depths[index], places=13)
            np.testing.assert_allclose(normal, normals[index], atol=1e-15)

    def test_scalar_current_matches_batch_across_layers_and_boundaries(self):
        rng = np.random.default_rng(809)
        for seabed in (0., .3, 1., 30., 250.):
            current = CurrentProfile(surface_kn=2.3, surface_dir=355., mid_kn=.8,
                                     mid_dir=83., bottom_kn=.2, bottom_dir=196., turbulence=.32)
            current._gust[:] = [.4, -.7, .2]
            positions = rng.uniform(-200., 200., (120, 3))
            boundaries = [-2., 0., seabed/2-1e-8, seabed/2, seabed/2+1e-8,
                          seabed-1.00001, seabed-.99999, seabed-.01, seabed, seabed+3.]
            positions[:len(boundaries), 2] = boundaries
            for time in (0., 19.73, 86400.):
                expected = current.sample_many(positions, seabed, time)
                actual = np.array([current.sample(point, seabed, time) for point in positions])
                np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=2e-14)

    def test_current_parameter_edits_and_zero_flow_match_batch(self):
        current = CurrentProfile()
        point = [12.7, -18.6, 5.]
        for speed, direction, turbulence, gust in ((0., 0., 0., [0., 0., 0.]),
                                                   (0., 83., .3, [.8, -.4, .1]),
                                                   (-.7, -460., .2, [1., .5, -.2]),
                                                   (3.8, 720., 0., [0., 0., 0.])):
            current.surface_kn = current.mid_kn = current.bottom_kn = speed
            current.surface_dir = current.mid_dir = current.bottom_dir = direction
            current.turbulence = turbulence
            current._gust[:] = gust
            np.testing.assert_allclose(current.sample(point, 30., 17.),
                                       current.sample_many([point], 30., 17.)[0], atol=1e-14)

    def test_local_horizontal_shear_is_preserved(self):
        current = CurrentProfile(surface_kn=1.3, mid_kn=1.3, bottom_kn=1.3, turbulence=0.)
        positions = np.array([[0., 0., 5.], [40., -15., 5.]])
        result = np.array([current.sample(p, 30., 0.) for p in positions])
        np.testing.assert_allclose(result, current.sample_many(positions, 30.), atol=1e-14)
        self.assertGreater(np.linalg.norm(result[0]-result[1]), .01)

    def test_world_depth_and_empty_scene_sdf_match_batch(self):
        rng = np.random.default_rng(54)
        positions = rng.uniform([-180., -180., -2.], [180., 180., 35.], (100, 3))
        for terrain in (None, SeabedTerrain(30., 7, 0.), SeabedTerrain(30., 7, 1.4)):
            world = World(30.)
            world.terrain = terrain
            dist, normal, ids = world.sdf_many(positions)
            depth = np.full(len(positions), 30.) if terrain is None else terrain.sample_many(positions)[0]
            for index, point in enumerate(positions):
                actual_dist, actual_normal, name = world.sdf(point)
                self.assertAlmostEqual(world.depth_at(point), depth[index], places=12)
                self.assertAlmostEqual(actual_dist, dist[index], places=12)
                np.testing.assert_allclose(actual_normal, normal[index], atol=1e-14)
                self.assertEqual(name, "seabed")
                self.assertEqual(ids[index], -1)

    def test_world_obstacle_queries_retain_nearest_surface(self):
        world = World(30.)
        world.terrain = SeabedTerrain(30., 7, 1.4)
        world.obstacles = [Cylinder("pile", (6., 2., 0.), (6., 2., 30.), 1.),
                           Box("hull", (-5., 1., 24.), (3., 1., 1.), 32.)]
        positions = np.random.default_rng(560).uniform([-12., -8., 0.], [12., 8., 31.], (100, 3))
        dist, normal, ids = world.sdf_many(positions)
        for index, point in enumerate(positions):
            actual_dist, actual_normal, name = world.sdf(point)
            self.assertAlmostEqual(actual_dist, dist[index], places=10)
            np.testing.assert_allclose(actual_normal, normal[index], atol=1e-10)
            self.assertEqual(name, "seabed" if ids[index] < 0 else world.obstacles[ids[index]].name)


if __name__ == "__main__":
    unittest.main()
