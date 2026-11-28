"""Keep the photographic launch within the original mission and tether envelope."""
import math
import unittest

from qysim.scenarios import aquaculture_pen, harbor_inspection, hull_inspection, tutorial_pool, wreck_survey


class LaunchLayoutTest(unittest.TestCase):
    def test_inspections_launch_from_the_original_tether_layout(self):
        for site, spool, length in ((hull_inspection(), (-5, 0, 0), 70), (wreck_survey(), (-4, 0, 0), 80)):
            with self.subTest(site=site.key):
                self.assertEqual(site.start_pos, (0, 0, 3))
                self.assertEqual(site.spool_pos, spool)
                self.assertEqual(site.tether_length, length)

    def test_shifted_sites_preserve_mission_and_cable(self):
        for site, original, spool, cable, points in (
            (aquaculture_pen(), (3, 0, 7), (-2, 0, 0), 150, [(3, 0, 7), (3, 0, 7), (9, 1, 15)]),
            (harbor_inspection(), (0, 0, 3), (-3, 0, 0), 75,
             [(18, -10, 8), (18, 10, 8), (39, 0, 10), (-2, 0, .5)]),
            (tutorial_pool(), (0, 0, 3), (-3, 0, 0), 35, []),
        ):
            with self.subTest(site=site.key):
                self.assertLessEqual(math.dist(site.start_pos, original), 3)
                self.assertEqual(site.tether_length, cable)
                self.assertEqual(site.spool_pos, spool)
                self.assertEqual([o.point for o in site.objectives], points)
