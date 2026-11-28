"""Check every physical observable and replay all deterministic traces."""
import json
import unittest

import numpy as np


class PhysicsBench(unittest.TestCase):
    def test_manoeuvres(self):
        from tools.physics_bench.cases import cases
        from tools.physics_bench.report import HERE, check

        seen = []
        for first, replay in zip(cases(), cases(), strict=True):
            seen.append(first.name)
            with self.subTest(case=first.name):
                self.assertEqual(first.name, replay.name)
                self.assertEqual(check(first), [])
                if first.name != "timing":
                    np.testing.assert_array_equal(first.rows, replay.rows)
                    self.assertEqual(first.metrics, replay.metrics)
        self.assertCountEqual(seen, json.loads((HERE / "bands.json").read_text(encoding="utf8"))["cases"])
