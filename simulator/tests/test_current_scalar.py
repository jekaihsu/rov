"""Compare scalar current queries with the independent batch implementation."""
import unittest
import numpy as np
from qysim.world import CurrentProfile


class ScalarCurrentTests(unittest.TestCase):
    def test_scalar_matches_batch(self):
        rng = np.random.default_rng(1942)
        current = CurrentProfile(.8, 200, .6, 210, .3, 220, .25)
        for _ in range(100):
            current.step_gust(.01, rng)
            point = rng.uniform([-100, -100, -5], [100, 100, 40])
            t = rng.uniform(0, 30)
            np.testing.assert_allclose(current.sample(point, 30, t),
                                       current.sample_many(point[None, :], 30, t)[0],
                                       rtol=1e-14, atol=1e-14)
        for depth in (0, 15, 29, 30, 35, -1):
            point = np.array([2., 3., depth])
            np.testing.assert_allclose(current.sample(point, 30),
                                       current.sample_many(point[None, :], 30)[0],
                                       rtol=1e-14, atol=1e-14)
