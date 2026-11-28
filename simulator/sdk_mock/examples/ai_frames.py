"""Pass SDK camera frames to a detector function. The default adapter returns no detections."""
import argparse
from importlib import import_module

from _common import add_host_args, make_bridge, print_result


def detect(frame_bgr):
    """Accept H×W×3 BGR uint8. Return [{cls, score, box: normalized top-left xywh}, ...]."""
    return []


def run(bridge, detector, seconds):
    start = bridge.sim_time()
    while bridge.sim_time() - start < seconds:
        frame = bridge.get_frame_bgr()
        print_result({"shape": list(frame.shape), "detections": detector(frame)})
        bridge.sleep_or_advance(0.2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    add_host_args(parser)
    parser.add_argument("--detector", metavar="MODULE:FUNCTION")
    args = parser.parse_args()
    detector = detect
    if args.detector:
        module, function = args.detector.split(":", 1)
        detector = getattr(import_module(module), function)
    bridge = make_bridge(args)
    try:
        run(bridge, detector, args.seconds)
    finally:
        if hasattr(bridge, "close"):
            bridge.close()
