#!/usr/bin/env python3
"""沿結構物定距巡檢：用前向 ``Distance`` 保持距離，處理無回波與盲區。

無回波時 SDK 回報最大量程（50 m）；盲區內回報 0.3 m。本範例在這兩種情況下
暫停側移並後退／停等，避免把最大量程當成真實距離去追。

用法：

    cd simulator/sdk_mock
    PYTHONPATH=. python examples/standoff_inspect.py --host 127.0.0.1 --scenario hull_inspection
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    STRINGS,
    add_host_args,
    clamp_pwm,
    get_status,
    make_bridge,
    print_result,
    release_remote,
    take_remote,
)

FORWARD_MAX_M = 50.0
BLIND_M = 0.3
EPS = 0.05


def classify_range(distance: float) -> str:
    if distance >= FORWARD_MAX_M - EPS:
        return "no_echo"
    if abs(distance - BLIND_M) < EPS or distance <= BLIND_M + 0.02:
        # SDK reports 0.3 in the blind zone; treat near-blind as cautious.
        if distance <= BLIND_M + 0.05:
            return "blind"
    return "ok"


def run(bridge, seconds: float = 30.0, dt: float = 0.1, standoff_m: float | None = None) -> dict:
    take_remote(bridge)
    status = get_status(bridge)
    distance0 = float(status["Distance"])
    kind0 = classify_range(distance0)
    if standoff_m is None:
        standoff_m = distance0 if kind0 == "ok" else 2.0

    errors = []
    events = []
    last_kind = None
    t0 = bridge.sim_time()
    elapsed = 0.0

    while elapsed < seconds:
        status = get_status(bridge)
        distance = float(status["Distance"])
        kind = classify_range(distance)
        if kind != last_kind:
            note = {"ok": "測距正常", "no_echo": STRINGS["no_echo"], "blind": STRINGS["blind"]}[kind]
            events.append({"t": round(elapsed, 2), "kind": kind, "distance_m": round(distance, 2), "note": note})
            last_kind = kind

        # ROV_USA: surge=right_ud, sway=right_wave, yaw=left_lr, heave=left_wave.
        if kind == "ok":
            errors.append(abs(distance - standoff_m))
            # Surge closes range error; slight starboard crawl along the structure.
            surge = clamp_pwm(1500 + 120 * (distance - standoff_m), 1300, 1700)
            sway = 1570
            yaw = 1500
        elif kind == "no_echo":
            # Do not chase the max-range reading; hold and yaw slowly to reacquire.
            surge = 1500
            sway = 1500
            yaw = 1550
        else:  # blind: back away gently
            surge = 1400
            sway = 1500
            yaw = 1500

        bridge.sdk("QYRovControllerManage", "set_right_joystick_up_down", surge)
        bridge.sdk("QYRovControllerManage", "set_right_wave_left_right", sway)
        bridge.sdk("QYRovControllerManage", "set_left_joystick_left_right", yaw)
        bridge.sdk("QYRovControllerManage", "set_left_wave_left_right", 1500)
        bridge.sdk("QYRovControllerManage", "set_left_joystick_up_down", 1500)
        bridge.sdk("QYRovControllerManage", "set_right_joystick_left_right", 1500)

        bridge.sleep_or_advance(dt)
        elapsed = bridge.sim_time() - t0

    release_remote(bridge)
    final = get_status(bridge)
    mean_err = (sum(errors) / len(errors)) if errors else None
    return {
        "example": "standoff_inspect",
        "seconds": round(elapsed, 2),
        "standoff_m": round(standoff_m, 3),
        "final_distance_m": round(float(final["Distance"]), 3),
        "mean_error_m": None if mean_err is None else round(mean_err, 3),
        "events": events,
        "handled_no_echo": any(e["kind"] == "no_echo" for e in events),
        "handled_blind": any(e["kind"] == "blind" for e in events),
        "ok_samples": len(errors),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Forward-range standoff inspection")
    add_host_args(parser)
    parser.set_defaults(scenario="hull_inspection")
    parser.add_argument("--standoff", type=float, default=None, help="desired forward distance (m)")
    args = parser.parse_args(argv)
    bridge = make_bridge(args)
    try:
        result = run(bridge, seconds=args.seconds, standoff_m=args.standoff)
    finally:
        if hasattr(bridge, "close"):
            bridge.close()
    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
