"""Reproducible three-vehicle physics benchmark; excludes rendering/network."""
import argparse
import cProfile
import io
import json
from pathlib import Path
import pstats
import sys
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim.engine import Simulator
from qysim.room import Room


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--ticks', type=int, default=180)
    parser.add_argument('--warmup', type=int, default=120)
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    room = Room(Simulator('coral_reef', seed=42), 'benchmark')
    for model in ('x1', 'bluerov2_heavy', 'falcon'):
        player = room.join(model, model_id=model)
        sim = room.vehicles[player.vehicle_id]
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.keep_depth = 1
        sim.rc_physical.right_ud = 1580
    for _ in range(args.warmup):
        room.step(.01)
    durations, cpu_durations = [], []
    profiler = cProfile.Profile()
    if args.profile:
        profiler.enable()
    batches = 0
    for _ in range(args.ticks):
        start, cpu_start = time.perf_counter(), time.process_time()
        room.step(.01)
        durations.append((time.perf_counter() - start) * 1000)
        cpu_durations.append((time.process_time() - cpu_start) * 1000)
        batches += sum(sim.tether.last_batch_complete for sim in room.vehicles.values())
    if args.profile:
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(30)
        print(stream.getvalue())
    result = dict(scenario='coral_reef', seed=42, players=3, ticks=args.ticks,
        warmup=args.warmup, profiled=args.profile, wall_mean_ms=float(np.mean(durations)),
        wall_p95_ms=float(np.percentile(durations,95)), cpu_mean_ms=float(np.mean(cpu_durations)),
        batch_fraction=batches/(3*args.ticks),
        positions={key:sim.vehicle.s.pos.tolist() for key,sim in room.vehicles.items()},
        tether_forces={key:sim.tether.force_on_rov.tolist() for key,sim in room.vehicles.items()})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
