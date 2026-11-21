"""The SDK camera must see the same mooring and box surfaces as the simulator."""

import sys
import unittest
from pathlib import Path

import numpy as np

from qysim.world import Box, Cylinder

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk_mock"))
from qysea.sdk._render import Scene


class SDKCameraGeometryTests(unittest.TestCase):
    def assert_world_distances(self, obstacle, points):
        scene = Scene({"seabed_depth": 100, "obstacles": [obstacle.as_dict()]})
        expected, _ = obstacle.sdf_many(points)
        np.testing.assert_allclose(scene.sdf(points), expected, rtol=1e-13, atol=1e-13)

    def test_mooring_lines_and_float_caps(self):
        start = np.array([3., -1., 6.])
        endpoints = [(3., -1., 8.), (3., -1., 4.), (2.1, .5, 4.), tuple(start), (3., -1., 6.00000001)]
        for end in endpoints:
            with self.subTest(end=end):
                axis = np.array(end) - start
                # Beyond both ends, directly on the axis, on the cap and outside the sidewall.
                centers = start + np.array([-.5, 0., .5, 1., 1.5])[:, None] * axis
                points = np.vstack([centers, centers + [.3, 0., 0.], centers + [.8, -.2, .1]])
                self.assert_world_distances(Cylinder('rope', tuple(start), end, .3), points)

    def test_yawed_box_faces_and_edges(self):
        box = Box('weight', (3., -1., 6.), (2., 1., .4), 37.)
        local = np.array([[0., 0., 0.], [0., 0., .4], [2., 1., .4], [-2., -1., -.4],
                          [1., .2, -.15], [2.3, 1.4, .7], [-2.4, 0., 0.]])
        self.assert_world_distances(box, local @ box._rot().T + box.center)
