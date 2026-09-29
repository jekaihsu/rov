"""Record scripted demo flights for the offline replay page.

    python tools/record_demo.py --out viewer/demo_recording.json

Each clip runs the real simulator headless with a scripted pilot (SDK calls /
autopilot waypoints) and stores the world description plus viewer states at
``--hz``. The viewer plays the file back when opened with ``?replay=<file>``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qysim.engine import Simulator          # noqa: E402
from qysim.navigation import Waypoint, wrap_pi  # noqa: E402
from qysim.server import _json_default       # noqa: E402

CTRL = "QYRovControllerManage"
NAV = "QYRovNavigationManage"


def _slim(state: dict) -> dict:
    state = dict(state)
    state["tether"] = dict(state["tether"])
    state["tether"]["nodes"] = [[round(c, 2) for c in n] for n in state["tether"]["nodes"]]
    state["nav"] = {**state["nav"], "route": state["nav"]["route"][:120]}
    return state


def _take_control(sim: Simulator) -> None:
    sim.sdk_call(CTRL, "set_remote_control_status", ["ON"], {})
    sim.sdk_call(CTRL, "set_rc_lock_button", [0], {})
    # recorded demos should look like a pilot flew them, not "SDK REMOTE"
    sim.remote_control = False
    sim.rc_physical = sim.rc_sdk


def clip_jacket(sim_hz: float, rec_hz: float):
    sim = Simulator("jacket_inspection", seed=3)
    # demo: weak current so the straight run really crosses the jacket (1.5 kn would carry it past)
    cur = sim.world.current
    cur.surface_kn, cur.mid_kn, cur.bottom_kn = 0.3, 0.3, 0.1
    _take_control(sim)
    sim.sdk_call(NAV, "init_dr", [24.35, 120.45], {})
    frames, script = [], []
    # dive, then auto-navigate straight through the jacket at brace depth -> collision
    lat, lng = sim.geo.to_geo(34.0, 0.0)
    started = False
    t_end = 70.0
    reversed_ = False
    while sim.t < t_end:
        if not started and sim.t > 1.0:
            sim.sdk_call(NAV, "set_h_navi_settings", [], {"speed": 1.0})
            sim.sdk_call(NAV, "start_h_navi", ["DVL", lat, lng, 8.0], {})
            script.append({"t": round(sim.t, 1), "text": "H_NAVI 直線穿越導管架（深 8 m，正好在斜撐高度）"})
            started = True
        hits = [e for e in sim.world.events if e.severity in ("hard", "severe")]
        if hits and not reversed_:
            sim.sdk_call(NAV, "stop_h_navi", [], {})
            reversed_ = True
            t_rev = sim.t
            script.append({"t": round(sim.t, 1), "text": f"撞上 {hits[0].obstacle}（{hits[0].speed} m/s）→ 停止導航、倒退脫離"})
        if reversed_:
            sim.rc_physical.right_ud = 1200 if sim.t - t_rev < 6 else 1500
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            frames.append(_slim(sim.viewer_state()))
    return sim, frames, script


def clip_untangle(sim_hz: float, rec_hz: float):
    sim = Simulator("tether_untangle")
    _take_control(sim)
    frames, script = [], []
    pile = next(o for o in sim.world.obstacles if o.name == "Pile P1")
    c = np.asarray(pile.p0[:2], float)
    for _ in range(int(2 * sim_hz)):           # let the cable settle, record the start state
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            frames.append(_slim(sim.viewer_state()))
    w0 = sim.tether.wraps.get("Pile P1", 0.0)
    script.append({"t": round(sim.t, 1), "text": f"開局：纜線繞樁 {w0:+.2f} 圈，張力 {sim.tether.tension_max:.0f} N"})
    # orbit the pile the opposite way at a safe radius, facing it
    p = sim.vehicle.s.pos
    a0 = math.atan2(p[1] - c[1], p[0] - c[0])
    turns = abs(w0) + 0.35
    direction = -1.0 if w0 > 0 else 1.0
    R = pile.radius + 1.6
    route = []
    for k in range(1, 73 + int(turns * 24)):
        a = a0 + direction * 2 * math.pi * turns * k / (72 + int(turns * 24))
        pt = c + R * np.array([math.cos(a), math.sin(a)])
        face = math.atan2(c[1] - pt[1], c[0] - pt[0])
        route.append(Waypoint(float(pt[0]), float(pt[1]), 10.0, face))
    sim.nav.route, sim.nav.route_i, sim.nav.mode, sim.nav.nav_status = route, 0, "V_NAVI", 1
    sim.nav.speed = 0.5
    script.append({"t": round(sim.t, 1), "text": "判斷纏繞方向 → 反方向繞樁解纜（面向樁、保持 1.6 m）"})
    t_end = sim.t + 110
    done_logged = False
    while sim.t < t_end:
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            frames.append(_slim(sim.viewer_state()))
        if not done_logged and sim.scenario.objectives[0].done:
            script.append({"t": round(sim.t, 1), "text": f"纏繞解除（剩 {sim.tether.wraps.get('Pile P1', 0.0):+.2f} 圈）"})
            done_logged = True
            t_end = min(t_end, sim.t + 8)
    return sim, frames, script


def clip_monopile(sim_hz: float, rec_hz: float):
    sim = Simulator("monopile_current", seed=1)
    _take_control(sim)
    sim.sdk_call(NAV, "init_dr", [24.35, 120.45], {})
    frames, script = [], []
    ob = sim.scenario.objectives[0]
    lat, lng = sim.geo.to_geo(ob.point[0], ob.point[1])
    started = False
    while sim.t < 75:
        if not started and sim.t > 1.0:
            sim.sdk_call(NAV, "set_h_navi_settings", [], {"speed": 1.0})
            sim.sdk_call(NAV, "start_h_navi", ["DVL", lat, lng, ob.point[2]], {})
            script.append({"t": round(sim.t, 1), "text": "2.5 kn 橫流，導航到樁前 1.5 m 懸停點"})
            started = True
        if sim.nav.hold is not None and sim.nav.mode == "IDLE":
            # keep facing the pile while station keeping
            sim.nav.hold.heading = math.atan2(0 - sim.vehicle.s.pos[1], 15 - sim.vehicle.s.pos[0])
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            frames.append(_slim(sim.viewer_state()))
    script.append({"t": round(sim.t, 1), "text": f"懸停進度 {ob.progress * 100:.0f}%、纜線張力 {sim.tether.tension_max:.0f} N"})
    return sim, frames, script


CLIPS = {
    "jacket": ("導管架碰撞與纜線勾掛", clip_jacket),
    "untangle": ("纜線纏繞脫困", clip_untangle),
    "monopile": ("強流中樁前懸停", clip_monopile),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "viewer" / "demo_recording.json"))
    ap.add_argument("--hz", type=float, default=10.0)
    ap.add_argument("--clips", default=",".join(CLIPS))
    args = ap.parse_args()
    out = {"format": "qysim-replay-1", "hz": args.hz, "clips": []}
    for key in args.clips.split(","):
        title, fn = CLIPS[key]
        sim, frames, script = fn(100.0, args.hz)
        out["clips"].append({"key": key, "title": title, "world": sim.world_description(),
                             "frames": frames, "script": script})
        s = sim.scorer.as_dict()
        print(f"{key:9s} {len(frames):4d} frames  impacts={len(sim.world.events)} "
              f"wraps={sim.tether.wraps} score={s['score']} failed={s['failed']!r}")
        for line in script:
            print(f"   {line['t']:6.1f}s  {line['text']}")
    Path(args.out).write_text(json.dumps(out, default=_json_default, ensure_ascii=False, separators=(",", ":")))
    print("wrote", args.out, f"{Path(args.out).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
