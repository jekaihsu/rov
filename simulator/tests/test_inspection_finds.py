"""Inspection route subjects have stable photo identities and do not add collision bodies."""
import unittest
from types import SimpleNamespace
from qysim.aquaculture import layout
from qysim.expedition import Expedition
from qysim.inspection_finds import populate
from qysim.world import World


class InspectionFindsTest(unittest.TestCase):
    def test_subjects_resolve_in_the_photo_service(self):
        total = 0
        for site in ("hull_inspection", "aquaculture_pen"):
            world = World(20 if site == "hull_inspection" else 25)
            if site == "aquaculture_pen":
                world.obstacles, _ = layout()
            original = list(world.obstacles)
            populate(world, site)
            self.assertEqual(world.obstacles, original)
            subjects = world.habitat_entities + world.fish_schools
            ids = [item["id"] for item in subjects]
            self.assertEqual(len(ids), len(set(ids)))
            for key in ids:
                category, pos, radius = Expedition._entity(SimpleNamespace(world=world), key)
                self.assertTrue(category)
                self.assertEqual(len(pos), 3)
                self.assertGreater(radius, 0)
            total += len(ids)
        self.assertLessEqual(total, 30)
        self.assertGreaterEqual(total, 15)
