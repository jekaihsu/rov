"""Runnable integration examples using the unchanged engine and SDK manage classes."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

from examples.env import Env, read_csv
from qysim.mission_modes import MissionRun

# Select the mock only for these standalone simulator examples.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk_mock"))
from qysea.sdk.manage.QY_Rov_Manage import QYRovNavigationManage
from qysea.sdk.manage.QY_RovController_Manage import QYRovControllerManage


def local_manage(env, cls):
    """Simulator-only transport binding, scoped to this object; SDK calls stay unchanged."""
    obj = cls()

    def call(method, *args, on_fail=None, **kwargs):
        return env.sim.sdk_call(obj._CLS, method, list(args), kwargs)

    obj._call = call
    return obj


def navigation(env):
    controller = local_manage(env, QYRovControllerManage)
    controller.set_remote_control_status("ON")
    controller.set_rc_lock_button(0)
    nav = local_manage(env, QYRovNavigationManage)
    result = nav.init_dr(*env.sim.latlng())
    if result["status"] != "ok":
        raise RuntimeError(result)
    nav.set_h_navi_settings(accuracy=0.3, speed=0.5)
    return nav


def go(env, nav, point, limit=1500):
    lat, lng = env.sim.geo.to_geo(*point[:2])
    result = nav.start_h_navi("DVL", lat, lng, float(point[2]))
    if result["status"] != "ok":
        raise RuntimeError(result)
    for _ in range(limit):
        env.advance(env.sim.rc.as_dict())
        if np.linalg.norm(env.sim.vehicle.s.pos - point) < 0.65:
            nav.stop_h_navi()
            return True
    nav.stop_h_navi()
    return False


def cruise(seed=1, side=2.0):
    env = Env(seed=seed)
    nav = navigation(env)
    start = env.sim.vehicle.s.pos.copy()
    reached = 0
    for offset in ([side, 0, 0], [side, side, 0], [0, side, 0], [0, 0, 0]):
        reached += go(env, nav, start + offset)
    return env, {"reached": reached, "waypoints": 4, "depth": round(env.sim.depth, 3)}


def wall(seed=1, steps=100):
    env = Env("hull_inspection", seed=seed)
    initial = env.observe()["ranges"]["forward"]
    errors = []
    for _ in range(steps):
        distance = env.observe()["ranges"]["forward"]
        # Maintain initial standoff while moving starboard along the surface.
        surge = int(np.clip(1500 + 100 * (distance - initial), 1300, 1700))
        env.step([1500, 1500, surge, 1500, 1500, 1570])
        errors.append(abs(distance - initial))
    return env, {"standoff_m": round(initial, 3), "mean_error_m": round(float(np.mean(errors)), 3)}


def camera(seed=1, output="frame.ppm"):
    from qysea.sdk._render import render
    env = Env(seed=seed)
    sim = env.sim
    view = {"pos": sim.vehicle.s.pos.tolist(), "q": sim.vehicle.s.q.tolist(),
            "visibility_m": sim.scenario.visibility_m, "seabed_depth": sim.world.seabed_depth,
            "obstacles": [o.as_dict() for o in sim.world.obstacles]}
    frame = render(view, width=320, height=180, osd=False, t_now=1.0 + sim.t)
    # Standard-library PPM writer: no image codec dependency required.
    with open(output, "wb") as stream:
        stream.write(b"P6\n320 180\n255\n")
        stream.write(frame[:, :, ::-1].tobytes())
    return env, {"image": str(output), "shape": list(frame.shape)}


def retreat_action(tension, threshold=2.0):
    return [1500, 1500, 1350 if tension > threshold else 1570, 1500, 1500, 1500]


def tether(seed=1, steps=100):
    env = Env(seed=seed)
    peak = 0.0
    retreats = 0
    for _ in range(steps):
        tension = env.observe()["tether"]["tension_rov"]
        action = retreat_action(tension)
        retreats += action[2] < 1500
        peak = max(peak, tension)
        env.step(action)
    return env, {"peak_tension_n": round(peak, 3), "retreat_steps": retreats}


def inspection(seed=1):
    env = Env(seed=seed)
    sim = env.sim
    mission = MissionRun(sim, "inspection_coop")
    sim.world.mission_run = mission
    nav = navigation(env)
    for target in mission.targets:
        if not go(env, nav, np.asarray(target["point"])):
            break
        # Navigation keeps station while the mission verifies speed and dwell.
        point = np.asarray(target["point"])
        lat, lng = sim.geo.to_geo(*point[:2])
        nav.start_h_navi("DVL", lat, lng, float(point[2]))
        for _ in range(600):
            env.advance(sim.rc.as_dict())
            state = mission.state(sim)
            if any(t["id"] == target["id"] and t["ready"] for t in state["targets"]):
                sim.sdk_call("QYCameraActionManage", "take_photo_normal", [], {})
                break
    return env, {"status": mission.status, "photos": len(sim.camera.files),
                 "completed": sum(t["completed"] for t in mission.targets)}


def batch(count=20):
    results = []
    for seed in np.random.default_rng(18).integers(0, 1000000, size=count):
        env, result = cruise(seed=int(seed), side=1.0)
        results.append((result["reached"] == 4, env.sim.t))
    return {"seeds": count, "success_rate": sum(r[0] for r in results) / count,
            "mean_sim_seconds": round(float(np.mean([r[1] for r in results])), 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("example", choices=["cruise", "wall", "camera", "tether", "inspection", "batch", "read_csv"])
    parser.add_argument("--csv", default="run.csv")
    args = parser.parse_args()
    if args.example == "batch":
        result = batch()
    elif args.example == "read_csv":
        rows = read_csv(args.csv)
        result = {"rows": len(rows), "last_time": rows[-1]["t"] if rows else None}
    else:
        env, result = globals()[args.example]()
        env.save_csv(args.csv)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
