"""Player-facing YX fleet and site names (docs/design/game-plan.md §10); internal keys stay unchanged."""
import json
import re
import unittest
from pathlib import Path

from qysim import scenarios
from qysim.engine import Simulator
from qysim.expedition import ensure_expedition
from qysim.fleet_names import VEHICLE_NAMES, WRECK_NAME, vehicle_name
from qysim.vehicles import VEHICLE_DEFINITIONS

VIEWER = Path(__file__).resolve().parents[1] / 'viewer'
VENDOR = re.compile(r'\bX1\b|BlueROV|Falcon|Korean Castle|QYSEA|FIFISH', re.IGNORECASE)


class TestFleetNames(unittest.TestCase):
    def test_every_vehicle_definition_has_a_display_name(self):
        self.assertEqual(set(VEHICLE_NAMES), set(VEHICLE_DEFINITIONS))
        self.assertEqual(vehicle_name('x1'), 'YX Model R')
        self.assertEqual(vehicle_name('bluerov2_heavy'), 'YX Model O')
        self.assertEqual(vehicle_name('falcon'), 'YX Model V')
        self.assertEqual(vehicle_name('unknown'), 'unknown')

    def test_internal_keys_are_unchanged(self):
        self.assertEqual(VEHICLE_DEFINITIONS['x1'].id, 'x1')
        self.assertIn('korean_castle', scenarios.LIBRARY)
        self.assertEqual(scenarios.build('korean_castle').key, 'korean_castle')

    def test_wreck_site_text_uses_the_fictional_name(self):
        scenario = scenarios.build('korean_castle')
        self.assertEqual(WRECK_NAME, '碧海號')
        self.assertIn(WRECK_NAME, scenario.name)
        texts = [scenario.name, scenario.brief] + [objective.label for objective in scenario.objectives]
        for text in texts:
            self.assertIsNone(VENDOR.search(text), text)

    def test_contract_reason_names_the_work_vehicle(self):
        sim = Simulator('coral_reef', 42)
        offered = ensure_expedition(sim).available(sim)
        reasons = [item['reason'] for item in offered if item['kind'] != 'inspect']
        self.assertTrue(reasons)
        for reason in reasons:
            self.assertIn(vehicle_name('falcon'), reason)
            self.assertIsNone(VENDOR.search(reason), reason)

    def test_menu_catalogue_export_uses_display_names(self):
        catalogue = json.loads((VIEWER / 'menu_catalogue.json').read_text(encoding='utf8'))
        names = {vehicle['id']: vehicle['name'] for vehicle in catalogue['vehicles']}
        self.assertEqual(names, VEHICLE_NAMES)
        scenes = json.loads((VIEWER / 'scene_previews.json').read_text(encoding='utf8'))
        wreck = next(scene for scene in scenes if scene['key'] == 'korean_castle')
        self.assertIn(WRECK_NAME, wreck['name'])


if __name__ == '__main__':
    unittest.main()
