"""Authored wreck budgets, feature alignment and reachable survey checkpoints."""

import json
import struct
import unittest
from pathlib import Path

import numpy as np

from qysim.scenarios import wreck_survey
from qysim.world import FieldMesh, SnagFeature

ROOT = Path(__file__).resolve().parents[2]


class ChenjiaoTests(unittest.TestCase):
    def test_survey_clearance_and_unique_features(self):
        scenario = wreck_survey()
        wreck = scenario.obstacles[0]
        self.assertIsInstance(wreck, FieldMesh)
        names = [o.name for o in scenario.obstacles]
        self.assertEqual(len(names), len(set(names)))
        legacy = [o for o in scenario.obstacles if isinstance(o, SnagFeature) and not o.embedded]
        self.assertEqual(len(legacy), 4)
        for objective in scenario.objectives:
            for obstacle in scenario.obstacles:
                self.assertGreater(obstacle.sdf(np.asarray(objective.point))[0], 0.4)
        for feature in scenario.obstacles[1:]:
            if isinstance(feature, SnagFeature) and feature.embedded:
                self.assertLess(wreck.sdf(np.asarray(feature.point))[0], 0.25)
                self.assertTrue(feature.as_dict()["embedded"])
                self.assertEqual(feature.snag_hold, (150, 400))

    def test_field_contract(self):
        path = ROOT / "simulator/qysim/assets/wreck_chenjiao_field.npz"
        with np.load(path) as field:
            self.assertEqual(set(field.files), {"field", "origin", "spacing", "quant"})
            self.assertEqual(field["field"].dtype, np.uint8)
            self.assertEqual(float(field["spacing"]), 0.3)
            self.assertEqual(float(field["quant"]), 0.05)

    def test_asset_budget(self):
        report = json.loads((ROOT / "docs/design/scenes/chenjiao/asset-report.json").read_text())
        for lod, budget in zip(report, (150000, 50000, 10000)):
            suffix = f"_lod{lod['lod']}" if lod["lod"] else ""
            raw = (ROOT / f"simulator/viewer/models/wreck_chenjiao{suffix}.glb").read_bytes()
            length = struct.unpack_from("<I", raw, 12)[0]
            gltf = json.loads(raw[20 : 20 + length])
            count = sum(
                gltf["accessors"][p["indices"]]["count"] // 3
                for n in gltf["nodes"]
                if "mesh" in n
                for p in gltf["meshes"][n["mesh"]]["primitives"]
            )
            self.assertEqual(count, lod["triangles"])
            self.assertEqual(len(raw), lod["bytes"])
            self.assertLessEqual(lod["triangles"], budget)
            self.assertLessEqual(lod["texture_bytes_with_mips"], 32 * 1024**2)
            self.assertIn("EXT_meshopt_compression", lod["extensions"])
            self.assertIn("EXT_texture_webp", lod["extensions"])
