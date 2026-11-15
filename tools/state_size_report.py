"""Measure actual host state payloads at 30 Hz, with one deflate context per recipient.

Run from any directory. --source can point at a baseline checkout's simulator.
CSV records every message; JSON reports mean/max bytes, B/s and the ten largest
non-overlapping top-level fields plus fleet-expanded paths (vehicles[].field).
Four recipients means three supported pilot seats plus an instructor observer.
"""
import argparse
import csv
import json
from pathlib import Path
import sys
import zlib
from collections import defaultdict


def field_sizes(state, dumps):
    """Attribute UTF-8 key/value bytes, excluding enclosing commas/braces."""
    sizes = defaultdict(int)
    for key, value in state.items():
        if key == 'vehicles':
            for vehicle in value:
                for name, item in vehicle.items():
                    sizes[f'vehicles[].{name}'] += len(dumps({name: item}).encode()) - 2
        else:
            sizes[key] += len(dumps({key: value}).encode()) - 2
    return sizes


def measure(args):
    sys.path.insert(0, str(args.source.resolve()))
    from qysim.engine import Simulator
    from qysim.scenarios import LIBRARY
    from qysim.server import SimHost, dumps

    keys = args.scenario or [*LIBRARY, 'random']
    summaries = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['scenario', 'recipients', 'frame', 'recipient', 'sim_s', 'raw_bytes', 'deflate_bytes'])
        for key in keys:
            for count in (1, 4):
                host = SimHost(Simulator(key, args.seed))
                room = host.room
                players = [room.join(f'Pilot {i}') for i in range(min(count, room.capacity))]
                # Stable public IDs make before/after compression reproducible. Tokens never enter state.
                room.players.clear()
                for i, player in enumerate(players):
                    player.id = f'{i + 1:012x}'
                    room.players[player.id] = player
                room.host_id = players[0].id
                recipients = players + ([None] if count == 4 else [])
                sonar_frames = {}
                compressors = [zlib.compressobj(wbits=-12, memLevel=5) for _ in recipients]
                totals = [0, 0]
                maxima = [0, 0]
                fields = defaultdict(int)
                frames = round(args.seconds * 30)
                steps = 0
                for frame in range(frames):
                    target = round(frame * 100 / 30)
                    while steps < target:
                        for sim in room.vehicles.values():
                            sim.apply_viewer_rc({'rc_lock': 0, 'right_ud': 1600}, partial=True)
                        room.step(.01)
                        steps += 1
                    for index, (player, compressor) in enumerate(zip(recipients, compressors)):
                        payload = host.viewer_payload(room, player)
                        if args.sonar:
                            from qysim.sonar import scan, snapshot
                            if frame % 6 == 0:
                                sim = room.vehicles[player.vehicle_id] if player else room.primary
                                sonar = scan(*snapshot(room, sim), seed=args.seed + frame)
                                sonar['timestamp'] = 1700000000 + frame / 30
                                sonar_frames[index] = sonar
                            state = json.loads(payload)
                            state['sonar'] = sonar_frames[index]
                            payload = dumps(state)
                        raw = payload.encode('utf-8')
                        compressed = compressor.compress(raw) + compressor.flush(zlib.Z_SYNC_FLUSH)
                        # RFC 7692 removes the four-byte sync-flush trailer; context takeover stays on.
                        sizes = [len(raw), len(compressed) - 4]
                        writer.writerow([key, count, frame, index, room.primary.t, *sizes])
                        for i, size in enumerate(sizes):
                            totals[i] += size
                            maxima[i] = max(maxima[i], size)
                        for path, size in field_sizes(json.loads(payload), dumps).items():
                            fields[path] += size
                messages = frames * count
                duration = frames / 30
                summaries.append({
                    'scenario': key, 'recipients': count, 'messages': messages,
                    'mean_bytes': [round(n / messages, 1) for n in totals], 'max_bytes': maxima,
                    'room_bytes_s': [round(n / duration, 1) for n in totals],
                    'per_recipient_bytes_s': [round(n / duration / count, 1) for n in totals],
                    'top10': [(k, round(v / messages, 1)) for k, v in
                              sorted(fields.items(), key=lambda pair: pair[1], reverse=True)[:10]],
                })
                print(f'{key} / {count}: {summaries[-1]["mean_bytes"]}', flush=True)
    report = {'seed': args.seed, 'seconds': args.seconds, 'hz': 30,
              'compression': 'RFC7692 raw deflate, window=12, memLevel=5, context takeover per connection',
              'scope': 'state payload only; no WS/TCP/TLS headers, world, RC or video; sonar only with --sonar',
              'sonar': args.sonar,
              'four_recipients': '3 pilots + instructor (same primary snapshot as observer)',
              'results': summaries}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'simulator')
    parser.add_argument('--scenario', action='append')
    parser.add_argument('--seconds', type=float, default=3)
    parser.add_argument('--sonar', action='store_true', help='Subscribe every recipient at 5 Hz')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=Path('state-size.json'))
    args = parser.parse_args()
    if args.seconds < 1 or not args.seconds < float('inf'):
        parser.error('--seconds must be finite and >= 1')
    measure(args)


if __name__ == '__main__':
    main()
