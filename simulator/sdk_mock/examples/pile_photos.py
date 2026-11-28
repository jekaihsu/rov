"""Inspect the two entrance dolphin piles from the south on a fresh harbor_inspection dive."""
import argparse
import math

from _common import (add_host_args, angle_error_deg, clamp_pwm, get_status, make_bridge,
                     print_result, release_remote, reply_ok, take_remote)

# Survey plan (name, north, east), metres from the scenario origin.
PILES = (("Outer dolphin", 3.6, -0.45), ("Outer dolphin twin", 4.4, 1.15))


def checked(bridge, cls, method, *args):
    reply = bridge.sdk(cls, method, *args)
    if not reply_ok(reply):
        raise RuntimeError(f"{method}: {reply}")
    return reply


def run(bridge, timeout):
    nav = "QYRovNavigationManage"
    control = "QYRovControllerManage"
    photos = []
    if get_status(bridge)["RC_Switch_Status"]["Rov_Operation_Mode"] != "ROV_USA":
        raise ValueError("Select ROV_USA for this survey")
    checked(bridge, nav, "init_dr")
    try:
        if not reply_ok(take_remote(bridge)):
            raise RuntimeError("Remote control unavailable")
        for name, north, east in PILES:
            deadline = bridge.sim_time() + timeout
            while bridge.sim_time() < deadline:
                data = checked(bridge, nav, "get_rov_data", ["rov", "dvl"])["data"]
                dvl = data["dvl"]
                if not dvl["position_valid"]:
                    raise RuntimeError("DVL position unavailable")
                # Approach a point 2 m south of the charted pile, camera facing north.
                dn = north - 2 - dvl["x"]
                de = east - dvl["y"]
                yaw = math.radians(data["rov"]["yaw"])
                heading_error = angle_error_deg(0, data["rov"]["yaw"])
                if math.hypot(dn, de) < 0.45 and abs(heading_error) < 8:
                    checked(bridge, "QYCameraActionManage", "take_photo_normal", "MAIN_CAMERA")
                    photos.append({"pile": name, "north_m": dvl["x"], "east_m": dvl["y"]})
                    break
                n = 260 * dn - 140 * dvl["vx"]
                e = 500 * de - 140 * dvl["vy"]
                surge = n * math.cos(yaw) + e * math.sin(yaw)
                sway = -n * math.sin(yaw) + e * math.cos(yaw)
                bridge.sdk(control, "set_right_joystick_up_down", clamp_pwm(1500 + surge))
                bridge.sdk(control, "set_right_wave_left_right", clamp_pwm(1500 + sway))
                bridge.sdk(control, "set_left_joystick_left_right", clamp_pwm(1500 + 10 * heading_error))
                bridge.sleep_or_advance(0.2)
            else:
                raise TimeoutError(f"Did not reach {name}")
    finally:
        release_remote(bridge)
    return photos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    add_host_args(parser)
    parser.set_defaults(scenario="harbor_inspection", seconds=60)
    args = parser.parse_args()
    bridge = make_bridge(args)
    try:
        print_result({"photos": run(bridge, args.seconds)})
    finally:
        if hasattr(bridge, "close"):
            bridge.close()
