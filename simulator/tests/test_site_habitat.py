"""Host samples and visual terrain coincide at the two shoals; station work stays clear."""
import unittest

import numpy as np

from qysim.ecology import SeabedTerrain
from qysim.scenarios import build
from qysim.site_habitat import school_refuges, shape_bed


class SiteHabitatTests(unittest.TestCase):
    def test_shoal_profile_is_planar_across_each_drawn_cell(self):
        site = build("open_water")
        terrain = SeabedTerrain(site.seabed_depth, 0)
        shape_bed(terrain, site.key, [], [site.start_pos])
        points = [[3, 25, 0], [7, -20, 0], [0, 0, 0]]
        depths, _ = terrain.sample_many(points)
        self.assertLess(depths[0], 11)
        self.assertLess(depths[1], 15)
        self.assertEqual(depths[2], 25)
        self.assertTrue(np.all(terrain.depths == terrain.depths[:1, :]))
        track = [[n, e, 0] for n in range(0, 40, 2) for e in (-8, 0, 8, 14)]
        np.testing.assert_equal(terrain.sample_many(track)[0], np.full(len(track), 25.0))
        for anchor in (ob for ob in site.obstacles if ob.name.endswith("clump weight")):
            floor, _ = terrain.sample_many([anchor.center])
            self.assertAlmostEqual(anchor.center[2] + .19, floor[0])

    def test_incident_workstation_retains_clearance_and_open_water_beyond_has_relief(self):
        site = build("incident_silt")
        terrain = SeabedTerrain(site.seabed_depth, 4)
        shape_bed(terrain, site.key, site.obstacles, [site.start_pos])
        depth, _ = terrain.sample_many([site.start_pos])
        self.assertAlmostEqual(float(depth[0]) - site.start_pos[2], .45)
        self.assertGreater(terrain.relief, .4)

    def test_default_sites_and_seeded_random_use_existing_school_contract(self):
        for key in ("harbor_inspection", "monopile_current", "wreck_survey", "random"):
            sc = build(key, 4)
            schools = school_refuges(sc)
            self.assertEqual(len(schools), 4)
            self.assertTrue(all(0 < s["home"][2] < sc.seabed_depth for s in schools))
        cold_open = build("cold_open_jacket")
        self.assertIs(school_refuges(cold_open), cold_open.fish_schools)
        self.assertIsNone(school_refuges(build("tutorial_pool")))
