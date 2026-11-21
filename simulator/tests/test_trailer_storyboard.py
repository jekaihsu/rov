"""Unit tests for trailer storyboard parsing and drive sampling."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.trailer.storyboard import drive_at, load_storyboard, validate_shot, validate_storyboard

BOARDS = Path(__file__).resolve().parents[1] / 'tools' / 'trailer' / 'storyboards'


class StoryboardParseTests(unittest.TestCase):
    def test_load_test_5s(self):
        board = load_storyboard(BOARDS / 'test_5s.json')
        self.assertEqual(board['fps'], 60)
        self.assertEqual(board['width'], 1920)
        self.assertEqual(len(board['shots']), 1)
        self.assertEqual(board['shots'][0]['scenario'], 'harbor_inspection')

    def test_load_store_80s(self):
        board = load_storyboard(BOARDS / 'store_80s.json')
        total = sum(shot['duration'] for shot in board['shots'])
        self.assertGreaterEqual(total, 79.0)
        self.assertLessEqual(total, 81.0)
        ids = [shot['id'] for shot in board['shots']]
        self.assertIn('01-harbor-fpv-drift', ids)
        self.assertIn('05b-cold-open-establish', ids)
        self.assertIn('11-harbor-cta', ids)

    def test_load_demo(self):
        board = load_storyboard(BOARDS / 'demo.json')
        self.assertGreaterEqual(len(board['shots']), 4)
        self.assertEqual(board['shots'][0]['scenario'], 'cold_open_jacket')

    def test_rejects_unknown_scenario(self):
        with self.assertRaises(ValueError):
            validate_shot({
                'id': 'bad', 'duration': 1, 'scenario': 'not_a_place',
                'camera': {'mode': 'onboard'},
            })

    def test_rejects_bad_camera_mode(self):
        with self.assertRaises(ValueError):
            validate_shot({
                'id': 'bad', 'duration': 1, 'scenario': 'harbor_inspection',
                'camera': {'mode': 'drone'},
            })

    def test_cold_open_alias(self):
        shot = validate_shot({
            'id': 'open', 'duration': 2, 'source': 'cold_open',
            'camera': {'mode': 'onboard'},
        })
        self.assertEqual(shot['scenario'], 'cold_open_jacket')

    def test_drive_requires_keyframes_for_orbit(self):
        with self.assertRaises(ValueError):
            validate_shot({
                'id': 'bad', 'duration': 1, 'scenario': 'harbor_inspection',
                'camera': {'mode': 'orbit', 'keyframes': []},
            })

    def test_duplicate_ids(self):
        with self.assertRaises(ValueError):
            validate_storyboard({
                'shots': [
                    {'id': 'a', 'duration': 1, 'scenario': 'harbor_inspection', 'camera': {'mode': 'onboard'}},
                    {'id': 'a', 'duration': 1, 'scenario': 'harbor_inspection', 'camera': {'mode': 'onboard'}},
                ],
            })


class DriveSampleTests(unittest.TestCase):
    def test_piecewise_hold(self):
        drive = [
            {'t': 0.0, 'surge': 0.2, 'yaw': -0.1},
            {'t': 2.0, 'surge': 0.5},
        ]
        early = drive_at(drive, 1.0)
        self.assertAlmostEqual(early['surge'], 0.2)
        self.assertAlmostEqual(early['yaw'], -0.1)
        late = drive_at(drive, 3.0)
        self.assertAlmostEqual(late['surge'], 0.5)
        self.assertAlmostEqual(late['yaw'], -0.1)

    def test_storyboards_are_valid_json(self):
        for path in sorted(BOARDS.glob('*.json')):
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding='utf-8'))
                board = validate_storyboard(data, source=path.name)
                self.assertTrue(board['shots'])


if __name__ == '__main__':
    unittest.main()
