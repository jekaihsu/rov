"""Pure helpers from browser_gpu_bench (no browser)."""
import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / 'tools'
BENCH = TOOLS_DIR / 'browser_gpu_bench.py'


def load():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location('browser_gpu_bench', BENCH)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as error:
        raise unittest.SkipTest(str(error)) from error
    return module


class GpuBenchStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load()

    def test_percentile_and_summary(self):
        values = [10, 12, 14, 16, 20, 30, 40]
        summary = self.mod.summarise_intervals(values)
        self.assertEqual(summary['frames'], 7)
        self.assertAlmostEqual(summary['mean_ms'], sum(values) / 7, places=3)
        self.assertGreaterEqual(summary['p95_ms'], summary['mean_ms'])
        self.assertGreaterEqual(summary['p99_ms'], summary['p95_ms'])
        self.assertEqual(summary['min_ms'], 10)
        self.assertEqual(summary['max_ms'], 40)

    def test_machine_id_sanitises(self):
        self.assertEqual(self.mod.ensure_machine_id('My PC / GPU'), 'My-PC-GPU')

    def test_empty_intervals(self):
        summary = self.mod.summarise_intervals([])
        self.assertIsNone(summary['mean_ms'])


if __name__ == '__main__':
    unittest.main()
