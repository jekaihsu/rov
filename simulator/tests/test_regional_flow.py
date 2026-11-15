"""Regional flow is bounded, compact, and shared by world current consumers."""
import unittest
import numpy as np
from qysim.regional_flow import RegionalFlow
from qysim.world import World, CurrentProfile, Box


class RegionalFlowTests(unittest.TestCase):
    def test_profile_and_boundary(self):
        r = RegionalFlow((0, 0, 4), (4, 2, 2), (1, 0, 0))
        points = [[0, 0, 4], [2, 0, 4], [4, 0, 4], [0, 3, 4]]
        np.testing.assert_allclose(r.sample_many(points), [[1, 0, 0], [.5, 0, 0], [0, 0, 0], [0, 0, 0]])
        self.assertEqual(r.as_dict()['velocity'], [1, 0, 0])

    def test_validation(self):
        for radii in [(0, 1, 1), (-1, 1, 1), (1, 2), (float('nan'), 1, 1)]:
            with self.assertRaises(ValueError):
                RegionalFlow((0, 0, 0), radii, (1, 0, 0))
        with self.assertRaises(ValueError):
            RegionalFlow((0, 0, 0), (1, 1, 1), (float('inf'), 0, 0))

    def test_world_and_solids(self):
        w = World(20)
        w.current = CurrentProfile(0, 0, 0, 0, 0, 0, 0)
        points = np.array([[0, 0, 4], [1, 0, 4], [20, 0, 4]])
        np.testing.assert_array_equal(w.current_at_many(points), np.zeros((3, 3)))
        w.regional_flows = [RegionalFlow((0, 0, 4), (4, 2, 2), (1, 0, 0))]
        actual = w.current_at_many(points)
        for p, v in zip(points, actual):
            np.testing.assert_allclose(w.current_at(p), v)
        self.assertGreater(actual[1, 0], 0)
        w.obstacles = [Box('solid', (0, 0, 4), (.5, .5, .5))]
        np.testing.assert_allclose(w.current_at((0, 0, 4)), 0)

    def test_empty_metadata_and_additive_fields(self):
        from qysim.scenarios import build
        self.assertNotIn('regional_flows', build('tutorial_pool').summary())
        source = [1, 0, 0]
        r = RegionalFlow((0, 0, 4), (4, 2, 2), source)
        source[0] = 20
        self.assertEqual(r.velocity, (1, 0, 0))
        w = World(20)
        w.current = CurrentProfile(0, 0, 0, 0, 0, 0, 0)
        w.regional_flows = [r, r]
        np.testing.assert_allclose(w.current_at((0, 0, 4)), [2, 0, 0])
