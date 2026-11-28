"""右端為最新樣本的終端機深度曲線，每 0.2 秒更新，不需要 GUI。"""
import argparse
from collections import deque

from _common import add_host_args, get_status, make_bridge


def plot(bridge, seconds):
    history = deque(maxlen=60)
    levels = "▁▂▃▄▅▆▇█"
    start = bridge.sim_time()
    while bridge.sim_time() - start < seconds:
        history.append(float(get_status(bridge)["Depth"]))
        low, high = min(history), max(history)
        scale = (len(levels) - 1) / (high - low) if high > low else 0
        curve = "".join(levels[round((sample - low) * scale)] for sample in history)
        print(f"\r{low:6.2f}–{high:6.2f} m  {curve:<60} {history[-1]:6.2f} m", end="", flush=True)
        bridge.sleep_or_advance(0.2)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    add_host_args(parser)
    args = parser.parse_args()
    plot(make_bridge(args), args.seconds)
