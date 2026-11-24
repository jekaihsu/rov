"""Inspection route subjects have stable photo identities and do not add collision bodies."""
import unittest
from types import SimpleNamespace

from qysim.aquaculture import layout
from qysim.expedition import Expedition
from qysim.inspection_finds import populate
from qysim.scenarios import build
from qysim.world import World


OWNED = (
    "open_water", "jacket_inspection", "wreck_survey", "coral_reef", "seagrass_meadow",
    "monopile_current", "sonar_search", "incident_silt",
)


class InspectionFindsTest(unittest.TestCase):
    def test_subjects_resolve_in_the_photo_service(self):
        total = 0
        for site in ("hull_inspection", "aquaculture_pen", *OWNED):
            if site.startswith("aquaculture") or site == "hull_inspection":
                world = World(20 if site == "hull_inspection" else 25)
                if site == "aquaculture_pen":
                    world.obstacles, _ = layout()
                original = list(world.obstacles)
                populate(world, site)
                self.assertEqual(world.obstacles, original)
                subjects = world.habitat_entities + world.fish_schools
            else:
                sim_world = build(site, 42)
                world = World(sim_world.seabed_depth)
                world.obstacles = list(sim_world.obstacles)
                world.configure_habitat(getattr(sim_world, "biome", "temperate"), 42,
                                        keep_clear=[sim_world.start_pos], site=site)
                before = len(world.obstacles)
                populate(world, site)
                self.assertEqual(len(world.obstacles), before)
                subjects = [e for e in world.habitat_entities if e["id"].startswith("inspection-")]
                self.assertLessEqual(len(subjects), 8)
                self.assertGreaterEqual(len(subjects), 4)
            ids = [item["id"] for item in subjects]
            self.assertEqual(len(ids), len(set(ids)))
            for key in ids:
                category, pos, radius = Expedition._entity(SimpleNamespace(world=world), key)
                self.assertTrue(category)
                self.assertEqual(len(pos), 3)
                self.assertGreater(radius, 0)
            total += len(ids)
        self.assertGreaterEqual(total, 40)

    def test_landmarks_skip_r5_r6_sites(self):
        for key in ("harbor_inspection", "hull_inspection", "aquaculture_pen"):
            site = build(key, 42)
            from qysim import scenarios
            source = scenarios.LIBRARY[key]()
            self.assertEqual(len(site.obstacles), len(source.obstacles))
