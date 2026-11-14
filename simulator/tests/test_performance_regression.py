"""Thirty-second seeded trajectories captured before T19 optimizations."""
import json
from pathlib import Path
import unittest

import numpy as np
from qysim.engine import Simulator
from qysim.room import Room

FIXTURE = Path(__file__).parent / 'fixtures' / 'performance_trajectories.json'


def trajectory(scenario):
    room = Room(Simulator(scenario, seed=42), 'regression')
    for model in ('x1', 'bluerov2_heavy', 'falcon'):
        player = room.join(model, model_id=model)
        sim = room.vehicles[player.vehicle_id]
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.keep_depth = 1
        sim.rc_physical.right_ud = 1580
    samples = []
    for tick in range(3000):
        room.step(.01)
        if (tick + 1) % 100 == 0:
            samples.append([
                dict(pos=sim.vehicle.s.pos.tolist(), q=sim.vehicle.s.q.tolist(),
                     tension=float(sim.tether.tension_max))
                for sim in room.vehicles.values()
            ])
    return samples


class PerformanceRegression(unittest.TestCase):
    def test_seeded_trajectories(self):
        for scenario, expected in json.loads(FIXTURE.read_text()).items():
            with self.subTest(scenario=scenario):
                actual = trajectory(scenario)
                for observed_tick, reference_tick in zip(actual, expected, strict=True):
                    for observed, reference in zip(observed_tick, reference_tick, strict=True):
                        self.assertLessEqual(np.linalg.norm(np.subtract(observed['pos'], reference['pos'])), .001)
                        # Quaternions q and -q encode the same attitude. Bound chord distance.
                        q, r = np.array(observed['q']), np.array(reference['q'])
                        self.assertLessEqual(min(np.linalg.norm(q-r), np.linalg.norm(q+r)), 1e-6)
                        self.assertLessEqual(abs(observed['tension']-reference['tension']),
                                             max(1e-9, abs(reference['tension'])*.005))
