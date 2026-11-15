"""Reproducible multi-vehicle physics benchmark; excludes rendering/network."""
import argparse
import cProfile
import io
import hashlib
from dataclasses import asdict
import json
import os
from pathlib import Path
import pstats
import sys
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim.engine import Simulator
from qysim.room import Room


def update_digest(digest, value):
    """Hash numeric bytes and structure without depending on object aliasing."""
    if isinstance(value, np.ndarray):
        digest.update(str((value.dtype.str, value.shape)).encode())
        digest.update(value.tobytes())
    elif isinstance(value, (float, np.floating)):
        digest.update(np.float64(value).tobytes())
    elif isinstance(value, dict):
        for key, item in value.items():
            update_digest(digest, key)
            update_digest(digest, item)
    elif isinstance(value, (list, tuple)):
        digest.update(str(len(value)).encode())
        for item in value:
            update_digest(digest, item)
    else:
        digest.update(repr(value).encode())
    digest.update(b"\0")


def place_near_bed(sim, altitude):
    """Lower the vehicle (and its tether) to ``altitude`` above the bed and command a climb."""
    delta = sim.world.seabed_at(sim.vehicle.s.pos) - altitude - sim.vehicle.s.pos[2]
    sim.vehicle.s.pos[2] += delta
    sim.tether.x[:, 2] += delta * np.linspace(0, 1, len(sim.tether.x))
    sim.rc_physical.keep_depth = 0
    sim.rc_physical.left_wave = 1650


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--ticks', type=int, default=180)
    parser.add_argument('--warmup', type=int, default=120)
    parser.add_argument('--players', type=int, choices=(3, 6), default=3)
    parser.add_argument('--trace', help='per-tick byte-exact digests; use PYTHONHASHSEED=0 for replay')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--scenario', default='coral_reef')
    parser.add_argument('--near-bed', type=float, default=None,
                        help='start every vehicle this many metres above the bed with ascent thrust (silt worst case)')
    args = parser.parse_args()
    room = Room(Simulator(args.scenario, seed=42), 'benchmark')
    room.capacity = args.players  # benchmark-only stress load
    models = ('x1', 'bluerov2_heavy', 'falcon')
    for index in range(args.players):
        model = models[index % len(models)]
        player = room.join(model, model_id=model)
        sim = room.vehicles[player.vehicle_id]
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.keep_depth = 1
        sim.rc_physical.right_ud = 1580
        if args.near_bed is not None:
            place_near_bed(sim, args.near_bed)
    for _ in range(args.warmup):
        room.step(.01)
    durations, cpu_durations = [], []
    profiler = cProfile.Profile()
    if args.profile:
        profiler.enable()
    batches = 0
    trace = []
    for _ in range(args.ticks):
        start, cpu_start = time.perf_counter(), time.process_time()
        room.step(.01)
        durations.append((time.perf_counter() - start) * 1000)
        cpu_durations.append((time.process_time() - cpu_start) * 1000)
        batches += sum(sim.tether.last_batch_complete for sim in room.vehicles.values())
        if args.trace:
            state = [(asdict(sim.vehicle.s), sim.tether.x, sim.tether.v, sim.tether.l0,
                      sim.tether.force_on_rov, asdict(sim.sensors.frame), sim.sensors.state(sim))
                     for sim in room.vehicles.values()]
            digest = hashlib.sha256()
            update_digest(digest, state)
            trace.append(digest.hexdigest())
    if args.trace:
        Path(args.trace).write_text("\n".join(trace) + "\n", encoding='utf-8')
    if args.profile:
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(30)
        print(stream.getvalue())
    result = dict(scenario=args.scenario, near_bed=args.near_bed, seed=42, players=args.players, ticks=args.ticks,
        warmup=args.warmup, profiled=args.profile, python_hash_seed=os.environ.get("PYTHONHASHSEED"),
        wall_mean_ms=float(np.mean(durations)),
        wall_p95_ms=float(np.percentile(durations,95)), cpu_mean_ms=float(np.mean(cpu_durations)),
        cpu_p95_ms=float(np.percentile(cpu_durations, 95)),
        batch_fraction=batches/(args.players*args.ticks), real_time_factor=10.0/float(np.mean(durations)),
        positions={key:sim.vehicle.s.pos.tolist() for key,sim in room.vehicles.items()},
        tether_forces={key:sim.tether.force_on_rov.tolist() for key,sim in room.vehicles.items()},
        silt_puffs=room.primary.world.silt_field.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
