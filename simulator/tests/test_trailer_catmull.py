"""Unit tests for trailer Catmull-Rom interpolation."""

from __future__ import annotations

import math
import unittest

from tools.trailer.catmull import catmull_rom, evaluate_camera_path, interpolate_scalar, interpolate_vector


class CatmullRomTests(unittest.TestCase):
    def test_midpoint_of_colinear_points(self):
        p0, p1, p2, p3 = [0.0], [1.0], [2.0], [3.0]
        mid = catmull_rom(p0, p1, p2, p3, 0.5)[0]
        self.assertAlmostEqual(mid, 1.5, places=6)

    def test_endpoints(self):
        p0, p1, p2, p3 = [0.0, 0.0], [1.0, 2.0], [3.0, 4.0], [5.0, 6.0]
        self.assertEqual(catmull_rom(p0, p1, p2, p3, 0.0), [1.0, 2.0])
        end = catmull_rom(p0, p1, p2, p3, 1.0)
        self.assertAlmostEqual(end[0], 3.0, places=6)
        self.assertAlmostEqual(end[1], 4.0, places=6)

    def test_interpolate_vector_holds_single_keyframe(self):
        frames = [{'t': 0.0, 'position': [1.0, 2.0, 3.0]}]
        self.assertEqual(interpolate_vector(frames, 'position', 1.5), [1.0, 2.0, 3.0])

    def test_interpolate_vector_missing_attr_returns_none(self):
        frames = [{'t': 0.0, 'position': [1.0, 2.0, 3.0]}, {'t': 1.0, 'position': [2.0, 2.0, 3.0]}]
        self.assertIsNone(interpolate_vector(frames, 'lookAt', 0.5))
        self.assertIsNone(interpolate_vector([{'t': 0.0}], 'offset', 0.0))

    def test_interpolate_scalar_between_two(self):
        frames = [{'t': 0.0, 'fov': 40.0}, {'t': 2.0, 'fov': 60.0}]
        self.assertAlmostEqual(interpolate_scalar(frames, 'fov', 1.0, 50.0), 50.0, places=5)


class CameraPathTests(unittest.TestCase):
    def test_onboard(self):
        sample = evaluate_camera_path({'mode': 'onboard'}, 0.0, {'position': [0, 0, 0]})
        self.assertEqual(sample['mode'], 'onboard')
        self.assertIsNone(sample['position'])

    def test_fixed_path(self):
        path = {
            'mode': 'fixed',
            'keyframes': [
                {'t': 0.0, 'position': [0.0, 1.0, 0.0], 'lookAt': [0.0, 0.0, 5.0], 'fov': 50},
                {'t': 2.0, 'position': [4.0, 1.0, 0.0], 'lookAt': [0.0, 0.0, 5.0], 'fov': 50},
            ],
        }
        sample = evaluate_camera_path(path, 1.0, {'position': [0, 0, 0]})
        self.assertAlmostEqual(sample['position'][0], 2.0, places=5)

    def test_fixed_without_look_at_falls_back_to_rov(self):
        path = {
            'mode': 'fixed',
            'keyframes': [{'t': 0.0, 'position': [1.0, 2.0, 3.0]}],
        }
        sample = evaluate_camera_path(path, 0.0, {'position': [9.0, 8.0, 7.0]})
        self.assertEqual(sample['lookAt'], [9.0, 8.0, 7.0])

    def test_follow_without_look_offset_uses_default(self):
        path = {
            'mode': 'follow',
            'keyframes': [{'t': 0.0, 'offset': [0.0, 1.0, -2.0]}],
        }
        sample = evaluate_camera_path(path, 0.0, {'position': [0.0, 0.0, 0.0], 'heading': 0.0})
        self.assertEqual(sample['lookAt'], [0.0, 0.2, 1.5])

    def test_follow_offset_rotates_with_heading(self):
        path = {
            'mode': 'follow',
            'keyframes': [{'t': 0.0, 'offset': [0.0, 1.0, -2.0], 'lookOffset': [0.0, 0.0, 1.0]}],
        }
        rov = {'position': [10.0, -5.0, 20.0], 'heading': math.pi / 2}
        sample = evaluate_camera_path(path, 0.0, rov)
        # heading π/2: back (-z local) maps toward -x world in the follow convention.
        self.assertAlmostEqual(sample['position'][1], -4.0, places=5)

    def test_orbit_radius(self):
        path = {
            'mode': 'orbit',
            'keyframes': [
                {'t': 0.0, 'azimuth': 0.0, 'radius': 4.0, 'height': 1.0},
                {'t': 1.0, 'azimuth': 0.0, 'radius': 6.0, 'height': 1.0},
            ],
        }
        sample = evaluate_camera_path(path, 0.5, {'position': [0.0, 0.0, 0.0]})
        self.assertAlmostEqual(sample['position'][0], 5.0, places=5)


if __name__ == '__main__':
    unittest.main()
