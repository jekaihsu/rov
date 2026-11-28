"""Short bake smoke: storyboard drive → replay clip without a browser."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.trailer.bake import bake_shot, write_clip


class BakeSmokeTests(unittest.TestCase):
    def test_bake_half_second_harbor(self):
        shot = {
            'id': 'bake-smoke',
            'duration': 0.5,
            'scenario': 'harbor_inspection',
            'seed': 1,
            'camera': {'mode': 'onboard'},
            'drive': [{'t': 0.0, 'surge': 0.4, 'keep_depth': True, 'led': 2, 'locked': False}],
            'hud': True,
        }
        doc = bake_shot(shot, fps=60)
        clip = doc['clips'][0]
        self.assertGreaterEqual(len(clip['frames']), 25)
        self.assertLessEqual(len(clip['frames']), 40)
        self.assertEqual(clip['trailer']['camera']['mode'], 'onboard')
        self.assertAlmostEqual(clip['frames'][0]['t'], 0.0, places=3)
        self.assertAlmostEqual(clip['frames'][-1]['t'], 0.5, places=3)

    def test_write_clip_roundtrip(self):
        shot = {
            'id': 'bake-file',
            'duration': 0.25,
            'scenario': 'tutorial_pool',
            'seed': 2,
            'camera': {'mode': 'onboard'},
            'drive': [{'t': 0.0, 'heave': -0.2}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = write_clip(shot, Path(tmp) / 'clip.json', fps=60)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)


if __name__ == '__main__':
    unittest.main()
