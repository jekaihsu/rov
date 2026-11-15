"""Optional state.tether.events stream and pilot-log lines for snag / break / stall / twist."""
from __future__ import annotations

import unittest
import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_from_euler
from qysim.scenarios import build
from qysim.tether import TetherParams
from qysim.world import SnagFeature, World
from tests.test_tether_physics import PointBody, straight


class TestTetherEventStream(unittest.TestCase):
    def test_state_includes_events_and_hook_release_sequence(self):
        """Hook then back out: tether_snag → (optional tighten) → tether_snag_released, and state streams them."""
        world = World(20)
        world.obstacles.append(SnagFeature("rock", (12.0, 1.0, 20.0), 0.25, 0.4, hold_n=(150.0, 150.0)))
        params = TetherParams(density=1300.0, snag_hook_tension_n=1.0)
        tether = straight(world, (0, 0, 19.9), (15, 0, 19.6), 15.6, params)
        body = PointBody((15.0, 0.0, 19.6))
        t = body.go(tether, (15, 0, 19.6), 0.0, 3.0, 0.0)
        t = body.go(tether, (15, 4, 19.6), 0.3, 14.0, t)
        self.assertIn("tether_snag", [e["type"] for e in tether.state()["events"]])
        t = body.go(tether, (15, 7, 19.6), 0.3, 10.0, t)
        kinds = [e["type"] for e in tether.state()["events"]]
        self.assertIn("tether_snag_tightened", kinds)
        t = body.go(tether, (12.5, 3, 19.6), 0.3, 15.0, t)
        body.go(tether, (12.5, -1.5, 19.6), 0.3, 15.0, t)
        kinds = [e["type"] for e in tether.state()["events"]]
        self.assertEqual(kinds.count("tether_snag"), 1)
        self.assertIn("tether_snag_released", kinds)
        snag_i = kinds.index("tether_snag")
        released_i = kinds.index("tether_snag_released")
        self.assertLess(snag_i, released_i)

    def test_tether_untangle_debris_hook_and_release_events(self):
        """tether_untangle seabed debris: drag across → hook → back out → release, streamed in order."""
        sc = build("tether_untangle", 0)
        world = World(sc.seabed_depth)
        world.obstacles = list(sc.obstacles)
        debris = next(o for o in world.obstacles if isinstance(o, SnagFeature))
        n, e, d = debris.point
        # Negative tether lying on the bed, dragged sideways across the feature then backed out.
        params = TetherParams(density=1300.0, snag_hook_tension_n=1.0)
        start = (n - 4.0, e, d - 0.1)
        end = (n + 3.0, e, d - 0.4)
        tether = straight(world, start, end, 8.0, params)
        body = PointBody(end)
        t = body.go(tether, end, 0.0, 2.0, 0.0)
        t = body.go(tether, (n + 3.0, e + 3.5, d - 0.4), 0.35, 12.0, t)
        self.assertTrue(tether.snags.hooks, "debris should hook when dragged across")
        t = body.go(tether, (n + 0.5, e + 2.0, d - 0.4), 0.3, 12.0, t)
        body.go(tether, (n + 0.5, e - 2.5, d - 0.4), 0.3, 14.0, t)
        kinds = [e["type"] for e in tether.state()["events"]]
        self.assertIn("tether_snag", kinds)
        self.assertIn("tether_snag_released", kinds)
        self.assertLess(kinds.index("tether_snag"), kinds.index("tether_snag_released"))

    def test_twist_and_stall_events(self):
        world = World(20)
        tether = straight(world, (0, 0, 5), (10, 0, 5), 10.5, TetherParams())
        # Cross the ±2-turn console warning by yawing in place (restoring torque only; no extra force).
        pos = np.array([10.0, 0.0, 5.0])
        q = q_from_euler(0.0, 0.0, 0.0)
        for k in range(260):
            q = q_from_euler(0.0, 0.0, (k + 1) * (2 * np.pi / 100))
            tether.step(0.01, k * 0.01, pos, q, np.zeros(3))
        self.assertGreater(abs(tether.turns), 2.0)
        self.assertTrue(any(e["type"] == "tether_twist" for e in tether.state()["events"]))
        tether.reel.stalled = False
        tether.reel._stall_clock = tether.reel.p.stall_time
        tether.reel._set_speed = -0.1          # commanded haul-in; drum speed stays ~0 → stall
        tether.reel.finish(0.01, 2.0)
        tether.events.extend(tether.reel.events)
        tether.reel.events.clear()
        self.assertTrue(any(e["type"] == "reel_stall" for e in tether.state()["events"]))


class TestPilotLogTether(unittest.TestCase):
    def test_hook_release_and_power_silt_lines(self):
        sim = Simulator(scenario="harbor_inspection", seed=0)
        # Inject a snag then release into the solver event list the way the tracker does.
        sim.tether.events.append({"t": 1.0, "type": "tether_snag", "obstacle": "Harbor rubble", "hold_n": 200.0})
        sim.tether.events.append({"t": 2.0, "type": "tether_snag_released", "obstacle": "Harbor rubble"})
        sim.tether.events.append({"t": 3.0, "type": "tether_break", "where": "gland", "tension_n": 900.0})
        sim.tether.events.append({"t": 4.0, "type": "reel_stall", "tension_n": 100.0})
        sim.tether.events.append({"t": 5.0, "type": "tether_twist", "turns": 2.5})
        sim._log_tether_and_environment()
        texts = [row["text"] for row in sim.log]
        self.assertTrue(any(t.startswith("勾纏：") for t in texts))
        self.assertTrue(any(t.startswith("勾纏脫開：") for t in texts))
        self.assertTrue(any(t.startswith("斷纜") for t in texts))
        self.assertIn("絞車失速", texts)
        self.assertTrue(any(t.startswith("扭轉警示") for t in texts))
        self.assertTrue(all("stamp" in row for row in sim.log))
        sim.power.trip()
        sim._log_tether_and_environment()
        self.assertIn("電源跳脫", [row["text"] for row in sim.log])
        # Force a silt-out reading by stubbing camera turbidity.
        sim.camera_turbidity = lambda: {"mg_l": 50.0, "visibility_m": 0.2, "c": 24.0}
        sim._silt_out_logged = False
        sim._log_tether_and_environment()
        self.assertIn("揚沙全白", [row["text"] for row in sim.log])


if __name__ == "__main__":
    unittest.main()
