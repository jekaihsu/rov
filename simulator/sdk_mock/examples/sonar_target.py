"""Subscribe as an observer and locate the strongest first return inside the sonar range."""
import argparse
import json
import time

from websockets.sync.client import connect

from _common import print_result


def strongest(frame):
    distances = frame["distance_m"]
    hits = [i for i, d in enumerate(distances) if 0 < d < frame["range_m"] and frame["intensity"][i] > 0]
    if not hits:
        return None
    beam = max(hits, key=frame["intensity"].__getitem__)
    bearing = frame["fov_deg"] * (beam / (frame["beams"] - 1) - 0.5)
    return {"bearing_deg": bearing, "range_m": distances[beam], "intensity": frame["intensity"][beam]}


def search(url, timeout):
    with connect(url, max_size=None) as ws:
        ws.send(json.dumps({"type": "operation", "action": "sonar_subscribe", "enabled": True}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            packet = json.loads(ws.recv(timeout=max(0, deadline - time.monotonic())))
            if packet.get("type") == "error":
                raise RuntimeError(packet)
            if packet.get("sonar"):
                return strongest(packet["sonar"])
    raise TimeoutError("No sonar frame received")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:8765")
    args = parser.parse_args()
    print_result({"target": search(args.url, 30)})
