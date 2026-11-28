"""Record timestamped SDK status to JSONL or replay the samples offline at the recorded cadence."""
import argparse
import json
import time

from _common import add_host_args, get_status, make_bridge


def record(bridge, output, seconds):
    start = bridge.sim_time()
    while bridge.sim_time() - start < seconds:
        status = get_status(bridge)
        row = {"time_s": bridge.sim_time() - start, "status": status}
        print(json.dumps(row, ensure_ascii=False), file=output, flush=True)
        bridge.sleep_or_advance(0.2)


def replay(source, speed):
    if speed <= 0:
        raise ValueError("speed must be positive")
    start = time.monotonic()
    for line in source:
        row = json.loads(line)
        time.sleep(max(0, start + row["time_s"] / speed - time.monotonic()))
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("record")
    add_host_args(capture)
    capture.add_argument("file")
    playback = commands.add_parser("replay")
    playback.add_argument("file")
    playback.add_argument("--speed", type=float, default=1)
    args = parser.parse_args()
    if args.command == "record":
        with open(args.file, "x", encoding="utf-8") as output:
            record(make_bridge(args), output, args.seconds)
    else:
        with open(args.file, encoding="utf-8") as source:
            replay(source, args.speed)
