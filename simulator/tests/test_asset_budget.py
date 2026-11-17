"""The asset budget tool runs against the shipped models and rejects an over-budget file."""
import importlib.util
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / 'tools' / 'asset_budget.py'
spec = importlib.util.spec_from_file_location('asset_budget', TOOL)
asset_budget = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asset_budget)


class AssetBudgetTest(unittest.TestCase):
    def test_repository_is_within_budget(self):
        self.assertEqual(asset_budget.check(), [])

    def test_over_budget_file_is_reported(self):
        report = {
            'files': [{
                'path': 'models/example.glb',
                'bytes': 100,
                'triangles': 10,
                'gpu_bytes': 10,
                'meshopt': True,
                'textures': [],
                'loaded_by': ['viewer'],
            }],
            'unreferenced': ['models/orphan.glb'],
            'total_bytes': 100,
        }
        limits = {
            'defaults': {'max_bytes': 50, 'max_triangles': 100, 'max_gpu_bytes': 100},
            'files': {},
            'totals': {'max_bytes': 1000},
            'retained_unloaded': {},
        }
        found = asset_budget.violations(report, limits)
        self.assertTrue(any('example.glb' in line and 'bytes' in line for line in found))
        self.assertTrue(any('orphan.glb' in line for line in found))

    def test_distance_lods_are_shipped(self):
        models = asset_budget.MODELS
        for name in (
            'falcon_lod1.glb', 'falcon_lod2.glb',
            'bluerov2_heavy_lod1.glb', 'bluerov2_heavy_lod2.glb',
            'worker_lod2.glb',
        ):
            self.assertTrue((models / name).is_file(), name)


if __name__ == '__main__':
    unittest.main()
