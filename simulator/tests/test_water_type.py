"""Optical water type in the scenario summary (presentation only; PROTOCOL.md world.scenario.water_type)."""
import unittest

from qysim import scenarios


class WaterTypeTests(unittest.TestCase):
    def test_biome_defaults(self):
        expected = {"coral_reef": "oceanic", "seagrass_meadow": "coastal", "harbor_inspection": "harbour",
                    "monopile_current": "shelf", "jacket_inspection": "shelf", "korean_castle": "shelf",
                    "open_water": "oceanic", "tutorial_pool": "fresh_clear"}
        for key, water_type in expected.items():
            self.assertEqual(scenarios.build(key).summary()["water_type"], water_type, key)

    def test_explicit_type_wins_and_unknown_falls_back(self):
        self.assertEqual(scenarios.water_type_for("reef", "harbour"), "harbour")
        self.assertEqual(scenarios.water_type_for("reef", "murky"), "oceanic")
        self.assertEqual(scenarios.water_type_for("temperate", None, "fresh"), "fresh_clear")

    def test_every_catalogue_scenario_has_a_known_type(self):
        for item in scenarios.catalogue():
            summary = scenarios.build(item["key"], seed=1).summary()
            self.assertIn(summary["water_type"], scenarios.WATER_TYPES, item["key"])


if __name__ == "__main__":
    unittest.main()
