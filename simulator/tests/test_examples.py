"""Integration and repeatability checks for the standalone automation examples."""
import tempfile
import unittest
from pathlib import Path

from examples.env import Env, read_csv
from examples import missions


class ExamplesTest(unittest.TestCase):
    def test_deterministic_reset_and_input(self):
        env = Env("random", seed=42, ticks=2)
        actions = [[1500, 1500, 1600, 1500, 1500, 1520]] * 12
        first = [env.step(action) for action in actions]
        env.reset(42)
        self.assertEqual(first, [env.step(action) for action in actions])
        other = Env("random", seed=43, ticks=2)
        self.assertNotEqual(first, [other.step(action) for action in actions])

    def test_action_validation_and_csv(self):
        env = Env(ticks=2)
        for bad in ([1500], [float("nan")] * 6, [999] * 6):
            with self.assertRaises(ValueError):
                env.step(bad)
        obs = env.step([1500] * 6)
        self.assertAlmostEqual(obs["t"], .02)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.csv"
            env.save_csv(path)
            self.assertEqual(read_csv(path)[0]["observation"], obs)
        obs["position"][0] = 999
        self.assertNotEqual(env.observe()["position"][0], 999)

    def test_cruise(self):
        _, result = missions.cruise(side=1)
        self.assertEqual(result["reached"], 4)

    def test_wall_and_tether(self):
        _, wall = missions.wall(steps=10)
        self.assertLess(wall["mean_error_m"], 1)
        self.assertLess(wall["standoff_m"], 50)
        _, tether = missions.tether(steps=10)
        self.assertGreaterEqual(tether["peak_tension_n"], 0)
        self.assertLess(missions.retreat_action(10)[2], 1500)
        self.assertGreater(missions.retreat_action(0)[2], 1500)

    def test_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.ppm"
            missions.camera(output=path)
            first = path.read_bytes()
            missions.camera(output=path)
            self.assertEqual(first, path.read_bytes())
            self.assertEqual(len(first), len(b"P6\n320 180\n255\n") + 320 * 180 * 3)

    def test_inspection(self):
        _, result = missions.inspection()
        self.assertEqual(result, {"status": "completed", "photos": 3, "completed": 3})

    def test_batch(self):
        first = missions.batch(count=2)
        self.assertEqual(first, missions.batch(count=2))
        self.assertEqual(first["success_rate"], 1)
