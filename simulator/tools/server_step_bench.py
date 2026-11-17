"""Server cost per dive site: physics step time (the host runs 100 steps per second) and viewer state size.

Usage (from the simulator directory):
  python tools/server_step_bench.py                       # every site in browser_gpu_bench.SITES
  python tools/server_step_bench.py --sites hull_inspection --steps 2000 --json out.json

One vehicle (x1), unlocked, holding depth and driving forward, after a 2 s settle. Reports the median / p95 / p99
step time, the share of the 10 ms budget used on average, the longest step, the full state message and the
static_once delta message (what a current viewer receives 30 times a second) in bytes, and the encode time.
Rendering and networking are not included.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim.engine import Simulator  # noqa: E402
from qysim.server import SimHost, _json_default  # noqa: E402
from qysim.state_wire import StaticOnceTracker  # noqa: E402

SITES = (
    'jacket_inspection', 'monopile_current', 'tether_untangle', 'hull_inspection', 'wreck_survey',
    'korean_castle', 'harbor_inspection', 'tutorial_pool', 'coral_reef', 'seagrass_meadow', 'open_water',
    'aquaculture_pen',
)


def percentile(ordered, fraction):
    return ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))]


def bench_site(site, steps):
    host = SimHost(Simulator(site, 1))
    room = host.room
    player = room.join('bench', model_id='x1')
    sim = room.vehicles[player.vehicle_id]
    sim.rc_physical.rc_lock = 0
    sim.rc_physical.keep_depth = 1
    sim.rc_physical.right_ud = 1600
    sim.rc_physical.left_ud = 1580
    for _ in range(200):
        room.step(.01)
    durations = []
    for _ in range(steps):
        started = time.perf_counter()
        room.step(.01)
        durations.append((time.perf_counter() - started) * 1000)
    tracker = StaticOnceTracker()
    full = host.viewer_payload(room, player)
    encode, delta = [], []
    for _ in range(60):
        for _ in range(3):
            room.step(.01)
        started = time.perf_counter()
        host.viewer_payload(room, player)
        encode.append((time.perf_counter() - started) * 1000)
        stripped = tracker.strip(host.viewer_state(room, player))
        message = json.dumps({'type': 'state', **stripped}, default=_json_default, ensure_ascii=False)
        delta.append(len(message.encode()))
    ordered = sorted(durations)
    return {
        'site': site,
        'step_ms_median': round(statistics.median(ordered), 3),
        'step_ms_p95': round(percentile(ordered, .95), 3),
        'step_ms_p99': round(percentile(ordered, .99), 3),
        'step_ms_max': round(ordered[-1], 3),
        'budget_used_pct': round(statistics.mean(ordered) / 10 * 100, 1),
        'state_bytes_full': len(full.encode()),
        'state_bytes_delta': int(statistics.median(delta[2:])),
        'encode_ms': round(statistics.median(encode), 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sites', default=','.join(SITES))
    parser.add_argument('--steps', type=int, default=1000)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    rows = []
    for site in args.sites.split(','):
        row = bench_site(site, args.steps)
        rows.append(row)
        print(json.dumps(row), flush=True)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
