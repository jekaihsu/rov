"""Measure three-vehicle snapshots and scans without modifying physics."""
import sys
import time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim.engine import Simulator
from qysim.room import Room
from qysim.sonar import scan, snapshot, submit_scan

room = Room(Simulator('sonar_search', seed=42))
for i in range(3):
    room.join(str(i))
durations = []
for _ in range(30):
    start = time.perf_counter()
    for sim in room.vehicles.values():
        world, pos, q = snapshot(room, sim)
        scan(world, pos, q)
    durations.append((time.perf_counter() - start) * 1000)
print('3 vehicles, 30 batches, snapshot + scan total ms:',
      'mean', round(np.mean(durations), 3), 'p95', round(np.percentile(durations, 95), 3))

import asyncio


async def cadence(enabled):
    timings = []
    jobs = []
    start = time.perf_counter()
    for tick in range(120):
        if enabled and tick % 20 == 0:
            if all(job.done() for job in jobs):
                jobs = []
                for sim in room.vehicles.values():
                    frozen = snapshot(room, sim)
                    jobs.append(submit_scan(*frozen, {}))
        begin = time.perf_counter()
        room.step(.01)
        timings.append((time.perf_counter() - begin) * 1000)
        await asyncio.sleep(max(0, start + (tick + 1) * .01 - time.perf_counter()))
    await asyncio.gather(*jobs)
    print('physics sonar=', enabled, 'mean ms', round(np.mean(timings), 3),
          'p95 ms', round(np.percentile(timings, 95), 3), 'wall seconds', round(time.perf_counter() - start, 3))


asyncio.run(cadence(False))
asyncio.run(cadence(True))
