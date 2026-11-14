"""Sonar geometric accuracy, occlusion and bounds regression tests."""
import unittest
import numpy as np
from qysim.world import World, Box
from qysim.sonar import scan


class SonarTests(unittest.TestCase):
    def test_wall_and_shadow(self):
        world = World(50)
        wall = Box('wall', (10, 0, 5), (0.5, 20, 10))
        world.obstacles = [wall]
        args = (world, np.array([0., 0., 5.]), np.array([1., 0., 0., 0.]))
        first = scan(*args, noise=0, multipath=0)
        self.assertAlmostEqual(first['distance_m'][128], 9.5, delta=0.04)
        world.obstacles.append(Box('hidden', (15, 0, 5), (1, 1, 1)))
        second = scan(*args, noise=0, multipath=0)
        self.assertEqual(first['distance_m'], second['distance_m'])
        self.assertEqual(first['intensity'], second['intensity'])
        self.assertTrue(all(isinstance(i, int) and 0 <= i <= 255 for i in first['intensity']))

    def test_range_and_validation(self):
        world = World(50)
        args = (world, np.array([0., 0., 5.]), np.array([1., 0., 0., 0.]))
        self.assertEqual(scan(*args, range_m=2, noise=0)['distance_m'], [2.] * 256)
        for value in (1, 51, float('nan')):
            with self.assertRaises(ValueError):
                scan(*args, range_m=value)


class SonarSubscriptionTests(unittest.TestCase):
    def setUp(self):
        from qysim.engine import Simulator
        from qysim.server import SimHost
        self.host = SimHost(Simulator('sonar_search', 42))

    def test_subscribe_validates_and_unsubscribes(self):
        socket = object()
        reply = self.host.sonar_subscribe(socket, {'enabled': True, 'range_m': 20})
        self.assertTrue(reply['ok'])
        self.assertEqual(self.host.sonar_subscriptions[socket]['range_m'], 20.0)
        for bad in ({'range_m': 1}, {'range_m': 'nan'}, {'noise': 2}):
            with self.assertRaises(ValueError):
                self.host.sonar_subscribe(socket, bad)
        self.host.sonar_subscribe(socket, {'enabled': False})
        self.assertNotIn(socket, self.host.sonar_subscriptions)

    def test_sdk_reads_null_before_any_scan_and_state_has_no_sonar(self):
        self.assertIsNone(self.host.handle_rpc({'type': 'sonar_latest'}))
        self.assertNotIn('sonar', self.host.viewer_state(self.host.room, None))

    def test_search_target_returns_an_echo(self):
        from qysim.sonar import snapshot
        world, pos, q = snapshot(self.host.room, self.host.sim)
        frame = scan(world, pos, q, range_m=30, noise=0, multipath=0)
        self.assertLess(min(frame['distance_m']), 30)
