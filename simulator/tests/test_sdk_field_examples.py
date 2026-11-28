"""End-to-end SDK tutorials using a headless sonar-search server and a seeded survey dive."""
import json
import math
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.test_sdk_sandbox_examples import EX_DIR, SIM_DIR, free_port, load_example


class SurveyTest(unittest.TestCase):
    def test_each_pile_has_a_distinct_nearby_photo(self):
        survey = load_example("pile_photos")
        from _common import LocalBridge
        bridge = LocalBridge("harbor_inspection")
        report = survey.run(bridge, timeout=60)
        self.assertEqual([row["pile"] for row in report], [name for name, _, _ in survey.PILES])
        files = bridge.sim.camera.files
        self.assertEqual(len(files), len(survey.PILES))
        self.assertFalse(bridge.sim.remote_control)
        for photo, (_, n, e) in zip(files, survey.PILES):
            self.assertTrue(photo["name"].endswith(".JPG"))
            pose = photo["pose"]
            self.assertLess(math.hypot(n - 2 - pose["n"], e - pose["e"]), 0.8)
            self.assertLess(abs((pose["yaw"] + 180) % 360 - 180), 12)


class FieldClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.ws_port = free_port()
        while cls.ws_port == cls.port:
            cls.ws_port = free_port()
        server = subprocess.Popen([
            sys.executable, "-m", "qysim.server", "--scenario", "sonar_search",
            "--seed", "1", "--no-http", "--rpc-port", str(cls.port), "--ws-port", str(cls.ws_port)
        ], cwd=SIM_DIR, stdout=subprocess.DEVNULL)
        cls.addClassCleanup(server.wait, 10)
        if os.name == "posix":
            # Let asyncio and the sonar process pool exit normally.
            cls.addClassCleanup(server.send_signal, signal.SIGINT)
        else:
            cls.addClassCleanup(server.terminate)
        deadline = time.monotonic() + 60
        while server.poll() is None and time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Test server did not start")

    def example(self, name, *args):
        return subprocess.check_output([sys.executable, str(EX_DIR / (name + ".py")), *args],
                                       text=True, timeout=65)

    def test_terminal_plot(self):
        out = self.example("telemetry_plot", "--port", str(self.port), "--seconds", "1")
        curves = [line.split()[-3] for line in out.splitlines() if line.strip()]
        self.assertGreaterEqual(len(curves), 2)
        self.assertEqual(len(curves[-1]), len(curves))
        self.assertLessEqual(set(curves[-1]), set("▁▂▃▄▅▆▇█"))

    def test_replay_reproduces_recorded_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dive.jsonl"
            self.example("dive_log", "record", str(path), "--seconds", "1", "--port", str(self.port))
            samples = [json.loads(s) for s in path.read_text().splitlines()]
            played = self.example("dive_log", "replay", str(path), "--speed", "100")
        self.assertGreaterEqual(len(samples), 2)
        self.assertEqual([json.loads(s) for s in played.splitlines()], samples)
        self.assertGreater(samples[-1]["time_s"], samples[0]["time_s"])
        self.assertTrue(all(row["status"]["Depth"] > 0 for row in samples))

    def test_sonar_finds_charted_target(self):
        out = self.example("sonar_target", "--url", f"ws://127.0.0.1:{self.ws_port}")
        hit = json.loads(out)["target"]
        # The 2 m wide box is centred at N=18, E=5, level with the transducer.
        self.assertAlmostEqual(hit["range_m"], 18, delta=1.5)
        self.assertAlmostEqual(hit["bearing_deg"], 15.5, delta=4)

    def test_image_adapter_reads_camera_frames(self):
        out = self.example("ai_frames", "--port", str(self.port), "--seconds", "1")
        frames = [json.loads(line) for line in out.splitlines()]
        self.assertTrue(frames)
        self.assertEqual(frames[0], {"shape": [360, 640, 3], "detections": []})
