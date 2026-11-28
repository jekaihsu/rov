#!/usr/bin/env python3
"""定深＋定向巡航：DVL 在線時慢速前進並保航向；失鎖時退回只定深。

用法（先啟動 ``python -m qysim.server``）：

    cd simulator/sdk_mock
    PYTHONPATH=. python examples/depth_heading_cruise.py --host 127.0.0.1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Script-style import: ``python examples/xxx.py`` puts this directory on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    STRINGS,
    LocalBridge,
    add_host_args,
    angle_error_deg,
    clamp_pwm,
    get_status,
    make_bridge,
    print_result,
    release_remote,
    take_remote,
)


def run(bridge, seconds: float = 30.0, dt: float = 0.1, target_depth: float | None = None,
        inject_dvl_loss_at: float | None = None) -> dict:
    """Closed-loop depth + heading cruise with DVL-aware mode switch.

    Returns a summary dict for tests and CLI output.
    """
    try:
        take_remote(bridge)
        return cruise(bridge, seconds, dt, target_depth, inject_dvl_loss_at)
    finally:
        release_remote(bridge)


def cruise(bridge, seconds, dt, target_depth, inject_dvl_loss_at):
    status = get_status(bridge)
    if target_depth is None:
        target_depth = float(status["Depth"])
    target_heading = float(status["Compass"])
    mode = "cruise"
    mode_events = []
    depth_errors = []
    t0 = bridge.sim_time()
    elapsed = 0.0

    while elapsed < seconds:
        if (
            inject_dvl_loss_at is not None
            and isinstance(bridge, LocalBridge)
            and elapsed >= inject_dvl_loss_at
            and "dvl" not in bridge.sim.sensors.faults
        ):
            bridge.sim.sensors.set_fault("dvl", 1.0)

        status = get_status(bridge)
        depth = float(status["Depth"])
        heading = float(status["Compass"])
        dvl = status["Accessories_Status"]["DVL_Status"]
        depth_errors.append(abs(depth - target_depth))

        if dvl == "OffLine" and mode == "cruise":
            mode = "depth_only"
            mode_events.append({"t": round(elapsed, 2), "mode": mode, "note": STRINGS["dvl_offline"]})
        elif dvl == "OnLine" and mode == "depth_only":
            mode = "cruise"
            mode_events.append({"t": round(elapsed, 2), "mode": mode, "note": STRINGS["dvl_online"]})

        # ROV_USA: heave=left_wave, yaw=left_lr, surge=right_ud, sway=right_wave.
        # keep_depth latches a hold depth; non-neutral heave *slews* that target.
        # Nudge only while far, then centre so the loop holds steady.
        depth_err = target_depth - depth
        if abs(depth_err) > 0.08:
            # heave(+up): positive stick raises; we need +down when too shallow → stick < 1500.
            heave = clamp_pwm(1500 - 350 * depth_err, 1200, 1800)
        else:
            heave = 1500

        yaw_err = angle_error_deg(target_heading, heading)
        yaw = clamp_pwm(1500 + 6.0 * yaw_err, 1200, 1800) if abs(yaw_err) > 2.0 else 1500

        if mode == "cruise":
            surge = 1600  # gentle forward while DVL reports velocity
        else:
            # Depth-only fallback: centre horizontal thrust; keep depth + heading.
            surge = 1500

        bridge.sdk("QYRovControllerManage", "set_left_wave_left_right", heave)
        bridge.sdk("QYRovControllerManage", "set_left_joystick_left_right", yaw)
        bridge.sdk("QYRovControllerManage", "set_right_joystick_up_down", surge)
        bridge.sdk("QYRovControllerManage", "set_left_joystick_up_down", 1500)
        bridge.sdk("QYRovControllerManage", "set_right_joystick_left_right", 1500)
        bridge.sdk("QYRovControllerManage", "set_right_wave_left_right", 1500)

        bridge.sleep_or_advance(dt)
        elapsed = bridge.sim_time() - t0

    final = get_status(bridge)
    mean_err = sum(depth_errors) / max(1, len(depth_errors))
    # Steady-state window: last 5 s of samples.
    tail = depth_errors[-max(1, int(5.0 / dt)):]
    return {
        "example": "depth_heading_cruise",
        "seconds": round(elapsed, 2),
        "mode_final": mode,
        "mode_events": mode_events,
        "heading_error_final_deg": round(abs(angle_error_deg(target_heading, float(final["Compass"]))), 2),
        "target_depth_m": round(target_depth, 3),
        "final_depth_m": round(float(final["Depth"]), 3),
        "depth_error_mean_m": round(mean_err, 4),
        "depth_error_tail_m": round(sum(tail) / len(tail), 4),
        "dvl_final": final["Accessories_Status"]["DVL_Status"],
        "switched_to_depth_only": any(e["mode"] == "depth_only" for e in mode_events),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Depth + heading cruise with DVL fallback")
    add_host_args(parser)
    parser.add_argument("--target-depth", type=float, default=None)
    parser.add_argument("--inject-dvl-loss-at", type=float, default=None,
                        help="local only: inject DVL fault after this many sim seconds")
    args = parser.parse_args(argv)
    bridge = make_bridge(args)
    try:
        result = run(
            bridge,
            seconds=args.seconds,
            target_depth=args.target_depth,
            inject_dvl_loss_at=args.inject_dvl_loss_at,
        )
    finally:
        if hasattr(bridge, "close"):
            bridge.close()
    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
