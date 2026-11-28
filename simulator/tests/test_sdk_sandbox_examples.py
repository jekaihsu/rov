"""Headless integration tests for sdk_mock sandbox examples.

Each example runs about 30 s of simulation time through the in-process LocalBridge
(no wall-clock wait, no external network). ``LiveExamplesTest`` runs the examples for a few wall-clock
seconds through the real mock-SDK TCP client against a local server subprocess (loopback only).
"""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
import time
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
        self.assertLess(result["heading_error_final_deg"], 8)
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
        # The hull is ahead at the start: range readings are usable and the vehicle closes on the stand-off.
        self.assertGreater(result["ok_samples"], 0)
        initial_error = abs(result["initial_distance_m"] - result["standoff_m"])
        final_error = abs(result["final_distance_m"] - result["standoff_m"])
        self.assertLess(final_error, 0.5 * initial_error)

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
        self.assertTrue(result["remote_taken"])
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LiveExamplesTest(unittest.TestCase):
    """The path users run: examples -> mock qysea TCP client -> qysim.server."""

    @classmethod
    def setUpClass(cls):
        cls.rpc_port = free_port()
        cls.ws_port = free_port()
        cls._env_backup = {k: os.environ.get(k) for k in ("QYSIM_HOST", "QYSIM_RPC_PORT")}
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "qysim.server", "--rpc-port", str(cls.rpc_port), "--ws-port", str(cls.ws_port),
             "--no-http", "--scenario", "open_water", "--seed", "1"],
            cwd=str(SIM_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        load_example("depth_heading_cruise")
        from _common import configure_rpc
        configure_rpc("127.0.0.1", cls.rpc_port)
        from qysea.sdk import _client
        deadline = time.time() + 60.0
        while time.time() < deadline and not _client.get_client().ping():
            time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        from qysea.sdk import _client
        _client.get_client().close()
        cls.server.terminate()
        try:
            cls.server.wait(5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
        for key, value in cls._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def bridge(self):
        from _common import LiveBridge
        return LiveBridge("127.0.0.1", self.rpc_port, ws_port=self.ws_port)

    def test_live_depth_cruise(self):
        mod = load_example("depth_heading_cruise")
        bridge = self.bridge()
        try:
            result = mod.run(bridge, seconds=3.0, dt=0.1)
        finally:
            bridge.close()
        self.assertEqual(result["dvl_final"], "OnLine")
        self.assertLess(result["depth_error_mean_m"], 0.3)

    def test_live_vision_round_trip(self):
        mod = load_example("vision_ai_detect")
        bridge = self.bridge()
        try:
            result = mod.run(bridge, seconds=3.0, dt=0.2)
        finally:
            bridge.close()
        self.assertGreater(result["frames"], 0)
        self.assertGreater(result["vision_readbacks"], 0, "vision_results must come back through the server")
        self.assertTrue(result["remote_taken"])
        self.assertTrue(result["remote_released"])


if __name__ == "__main__":
    unittest.main()
