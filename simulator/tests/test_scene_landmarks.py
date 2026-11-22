"""Authoring checks for navigable survey sites; the full scene manifest checks visible collision coverage."""
import unittest

import numpy as np

from qysim import scenarios
from qysim.aquaculture import layout
from qysim.scene_landmarks import MOORINGS


class LandmarkTests(unittest.TestCase):
    def test_landmarks_leave_launch_and_work_stations_clear(self):
        for key in (*scenarios.LIBRARY, "random"):
            site = scenarios.build(key, 42)
            source = scenarios.LIBRARY[key]() if key != "random" else scenarios.random_scenario(42)
            additions = site.obstacles[len(source.obstacles):]
            points = [site.start_pos, site.spool_pos] + [o.point for o in site.objectives if o.point is not None]
            for ob in additions:
                with self.subTest(key=key, obstacle=ob.name):
                    self.assertGreater(ob.sdf_many(np.array(points))[0].min(), .4)

    def test_generated_berth_keeps_random_inspection_stations_clear(self):
        for seed in (110, 348):
            site = scenarios.build("random", seed)
            berth = [o for o in site.obstacles if o.name.startswith("Berth ")]
            stations = np.array([o.point for o in site.objectives] + [site.start_pos, site.spool_pos])
            self.assertEqual(len(berth), 7)
            self.assertTrue(all(o.sdf_many(stations)[0].min() > 1.8 for o in berth))

    def test_buoyancy_is_on_the_riser_and_riser_meets_the_sinker(self):
        for key in (*MOORINGS, "open_water"):
            fixtures = {o.name: o for o in scenarios.build(key, 42).obstacles}
            for ob in fixtures.values():
                if ob.kind != "survey_float" or " float " not in ob.name:
                    continue
                label = ob.name.rsplit(" float ", 1)[0]
                riser = fixtures[f"{label} riser"]
                sinker = fixtures[f"{label} clump weight"]
                with self.subTest(key=key, float=ob.name):
                    self.assertLessEqual(sinker.sdf(np.array(riser.p0))[0], riser.radius)
                    self.assertLess(riser.sdf((np.asarray(ob.p0) + ob.p1) / 2)[0], 0)

    def test_numbered_tags_are_lashed_to_intact_pen_faces(self):
        obstacles, evidence = layout()
        tags = [ob for ob in obstacles if ob.kind == "pen_tag"]
        fixtures = {ob.name: ob for ob in obstacles}
        self.assertEqual(len(tags), len({tag.name for tag in tags}))
        self.assertTrue(tags)
        for tag in tags:
            panel_index = int(tag.name.split()[-1]) - 1
            panel = fixtures[f"pen-net-{panel_index}-0"]
            with self.subTest(tag=tag.name):
                self.assertNotIn(panel_index, [hole["panel"] for hole in evidence["holes"]])
                self.assertLess(panel.sdf(np.asarray(tag.center))[0] - tag.half[1], .015)

    def test_arch_has_an_open_notch_and_a_solid_lintel(self):
        rock = scenarios.build("coral_reef").obstacles
        self.assertTrue(all(ob.sdf(np.array([11.2, -2.65, 10.9]))[0] > .8 for ob in rock))
        self.assertLess(min(ob.sdf(np.array([11.2, -2.65, 6.7]))[0] for ob in rock), -.4)
