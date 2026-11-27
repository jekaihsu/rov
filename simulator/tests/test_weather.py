"""Optional site weather survives world description serialization."""
import unittest

from qysim.scenarios import Scenario, build


class WeatherTests(unittest.TestCase):
    def test_legacy_summary(self):
        self.assertNotIn("weather", Scenario("custom", "", "").summary())

    def test_presets_are_per_instance(self):
        site = build("aquaculture_pen")
        site.weather["rain"] = 1
        self.assertEqual(build("aquaculture_pen").summary()["weather"]["rain"], 0)

    def test_main_sites_have_valid_weather(self):
        from qysim.scenarios import LIBRARY
        for key in LIBRARY:
            with self.subTest(site=key):
                weather = build(key).summary()["weather"]
                self.assertIn(weather["time_of_day"], ("dawn", "morning", "day", "dusk", "night"))
                self.assertIn(weather["sea_state"], range(10))
                for name in ("cloud_cover", "rain"):
                    self.assertTrue(0 <= weather[name] <= 1)
