"""Measure total warmed water-query cost per 100 Hz tick, including periodic ecology and viewer samples."""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim.engine import Simulator


def measure(site):
    sim = Simulator(site, seed=42)
    sample = sim.world.current_at_many
    elapsed_ns = np.zeros(2)

    def timed(points, *args, **kwargs):
        wall_start = time.perf_counter_ns()
        cpu_start = time.thread_time_ns()
        value = sample(points, *args, **kwargs)
        elapsed_ns[1] += time.thread_time_ns() - cpu_start
        elapsed_ns[0] += time.perf_counter_ns() - wall_start
        return value

    sim.world.current_at_many = timed
    durations = []
    for tick in range(600):
        elapsed_ns.fill(0)
        sim.step(0.01)
        if tick % 3 == 0:
            sim.flow_field_state()
        if tick >= 100:
            durations.append(elapsed_ns / 1e6)
    for clock, times in zip(("wall", "cpu"), np.array(durations).T):
        print(f"{site:20s} {clock:4s} {np.mean(times):7.3f} {np.percentile(times, 95):7.3f} {max(times):7.3f}")


if __name__ == "__main__":
    print("site                 clock mean_ms  p95_ms  max_ms")
    for scenario in sys.argv[1:] or ("jacket_inspection", "hull_inspection", "aquaculture_pen", "cold_open_jacket"):
        measure(scenario)
