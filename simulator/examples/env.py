"""Deterministic simulator extension; six raw PWM channels, no wall clock pacing."""
import csv
import json

import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_rot
from qysim.rc import CHANNELS


class Env:
    """One action lasts ticks * 0.01 s. Observations are independent snapshots."""

    def __init__(self, scenario="open_water", seed=1, ticks=10):
        if not isinstance(ticks, int) or ticks < 1:
            raise ValueError("ticks must be a positive integer")
        self.scenario = scenario
        self.ticks = ticks
        self.reset(seed)

    def reset(self, seed=1):
        self.sim = Simulator(self.scenario, seed=seed)
        self.sim.apply_viewer_rc({"rc_lock": 0})
        self.rows = []
        return self.observe()

    def observe(self):
        sim = self.sim
        state = sim.viewer_state()
        ranges = {}
        for name, axis in (("forward", [1, 0, 0]), ("right", [0, 1, 0]), ("down", [0, 0, 1])):
            ranges[name] = sim.world.raycast(sim.vehicle.s.pos, q_rot(sim.vehicle.s.q, np.array(axis)))
        return {"t": sim.t, "position": sim.vehicle.s.pos.tolist(), "quaternion": sim.vehicle.s.q.tolist(),
                "velocity": sim.vehicle.s.vel.tolist(), "depth": sim.depth, "ranges": ranges,
                "tether": state["tether"]}

    def step(self, action):
        values = np.asarray(action, dtype=float)
        if values.shape != (6,) or not np.all(np.isfinite(values)) or np.any((values < 1000) | (values > 2000)):
            raise ValueError("action must contain six finite PWM values in [1000, 2000]")
        self.sim.apply_viewer_rc(dict(zip(CHANNELS, values)))
        return self.advance(values.tolist())

    def advance(self, action=None):
        for _ in range(self.ticks):
            self.sim.step()
        obs = self.observe()
        self.rows.append({"t": obs["t"], "action": json.dumps(action), "observation": json.dumps(obs, sort_keys=True)})
        return obs

    def save_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["t", "action", "observation"])
            writer.writeheader()
            writer.writerows(self.rows)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as stream:
        return [{"t": float(row["t"]), "action": json.loads(row["action"]),
                 "observation": json.loads(row["observation"])} for row in csv.DictReader(stream)]
