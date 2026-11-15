"""Headless integration tests for sdk_mock sandbox examples.

Each example runs about 30 s of simulation time through the in-process LocalBridge
(no wall-clock wait, no external network). Live TCP is covered by test_sdk_mock.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
EX_DIR = SIM_DIR / "sdk_mock" / "examples"
MOCK_DIR = SIM_DIR / "sdk_mock"


def load_example(name: str):
    """Load ``sdk_mock/examples/<name>.py`` without colliding with ``simulator/examples``."""
    # Ensure mock qysea and the examples directory (for ``_common``) are importable.
    for path in (str(MOCK_DIR), str(EX_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)
    path = EX_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"sdk_sandbox_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class SdkSandboxExamplesTest(unittest.TestCase):
    def test_depth_heading_cruise_hold_and_dvl_fallback(self):
        mod = load_example("depth_heading_cruise")
        from _common import LocalBridge
        # Realistic sensors required for instructor-style DVL fault injection.
        bridge = LocalBridge("open_water", seed=1, sensor_ideal=False)
        bridge.sim.vehicle.s.pos[2] = 5.0
        for _ in range(100):
            bridge.sim.step()
        result = mod.run(bridge, seconds=30.0, dt=0.1, target_depth=5.0, inject_dvl_loss_at=8.0)
        self.assertLess(result["depth_error_tail_m"], 0.1)
        self.assertTrue(result["switched_to_depth_only"])
        self.assertEqual(result["mode_final"], "depth_only")
        self.assertEqual(result["dvl_final"], "OffLine")

    def test_standoff_inspect_handles_range_and_runs(self):
        mod = load_example("standoff_inspect")
        from _common import LocalBridge
        bridge = LocalBridge("hull_inspection", seed=1, sensor_ideal=True)
        result = mod.run(bridge, seconds=30.0, dt=0.1)
        self.assertEqual(result["example"], "standoff_inspect")
        self.assertGreater(result["seconds"], 29.0)
        # With a hull ahead, we should get usable range samples or explicit handling events.
        self.assertTrue(result["ok_samples"] > 0 or result["handled_no_echo"] or result["handled_blind"])
        if result["mean_error_m"] is not None:
            self.assertLess(result["mean_error_m"], 5.0)

    def test_standoff_blind_and_no_echo_classification(self):
        mod = load_example("standoff_inspect")
        self.assertEqual(mod.classify_range(50.0), "no_echo")
        self.assertEqual(mod.classify_range(0.3), "blind")
        self.assertEqual(mod.classify_range(2.5), "ok")

    def test_vision_ai_detect_posts_and_releases(self):
        mod = load_example("vision_ai_detect")
        from _common import LocalBridge
        bridge = LocalBridge("open_water", seed=1, sensor_ideal=True)
        result = mod.run(bridge, seconds=30.0, dt=0.5)
        self.assertGreaterEqual(result["frames"], 50)
        self.assertGreater(result["vision_readbacks"], 0)
        self.assertTrue(result["remote_released"])
        # After release, remote_control must be off on the simulator.
        self.assertFalse(bridge.sim.remote_control)

    def test_detect_contours_returns_normalized_boxes(self):
        mod = load_example("vision_ai_detect")
        import numpy as np
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        frame[40:80, 100:160] = 220
        dets = mod.detect_contours(frame)
        self.assertIsInstance(dets, list)
        for det in dets:
            self.assertIn(det["cls"], ("blob",))
            self.assertTrue(0 <= det["score"] <= 1)
            self.assertEqual(len(det["box"]), 4)
            self.assertTrue(all(0 <= v <= 1 for v in det["box"]))


if __name__ == "__main__":
    unittest.main()
