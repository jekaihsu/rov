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
from qysim import scenarios as sc_mod          # noqa: E402
from qysim.server import _json_default       # noqa: E402

CTRL = "QYRovControllerManage"
NAV = "QYRovNavigationManage"


_KEEP = ("t", "pos", "q", "euler", "vel", "speed_kn", "thrust", "health", "rc", "remote_control",
         "operation_mode", "ctrl_mode", "locked", "keep_depth", "depth_hold", "battery", "recording",
         "photos", "current_here", "current_kn", "tether", "events", "damage", "silt", "nav", "score", "log")


def _round(x):
    if isinstance(x, float):
        return round(x, 3)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v) for v in x]
    if isinstance(x, np.generic):
        return _round(x.item())
    return x


class _Slimmer:
    """Keeps only what the viewer draws; the autopilot route is stored once per change.

    While an autopilot flies, the recorded sticks would sit at neutral; the pilot picture in
    the replay shows the equivalent stick positions of the autopilot command instead (ROV_USA)."""

    def __init__(self):
        self.last_route = None
        self.sim = None
        self.disp = {}

    def _display_rc(self, rc: dict) -> dict:
        sim = self.sim
        cmd = getattr(sim, "last_pilot", None) or {}
        auto = sim.nav.mode != "IDLE" or sim.nav.hold is not None
        if not auto:
            return rc
        yaw_rate = float(sim.vehicle.s.omega[2])
        want = {"right_ud": cmd.get("surge", 0.0), "right_wave": cmd.get("sway", 0.0),
                "left_wave": cmd.get("heave", 0.0), "left_lr": float(np.clip(yaw_rate / 0.6, -1, 1)),
                "left_ud": -cmd.get("pitch", 0.0), "right_lr": cmd.get("roll", 0.0)}
        out = dict(rc)
        for ch, x in want.items():
            prev = self.disp.get(ch, 0.0)
            self.disp[ch] = prev + (float(np.clip(x, -1, 1)) - prev) * 0.5
            out[ch] = int(round(1500 + 500 * self.disp[ch]))
        return out

    def __call__(self, state: dict) -> dict:
        out = {k: state[k] for k in _KEEP if k in state}
        if self.sim is not None and "rc" in out:
            out["rc"] = self._display_rc(out["rc"])
        out["tether"] = {**state["tether"], "nodes": [[round(float(c), 2) for c in n] for n in state["tether"]["nodes"]]}
        nav = dict(state["nav"])
        route = nav.pop("route", None)
        if route != self.last_route:
            nav["route"] = route
            self.last_route = route
        out["nav"] = nav
        out["log"] = state.get("log", [])[-6:]
        return _round(out)


_slim = None


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
    t_end = 32.0
    freed = False
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
            if not freed and sim.t - t_rev >= 6:
                freed = True
                script.append({"t": round(sim.t, 1), "text": f"已脫離斜撐，纜線張力 {sim.tether.tension_max:.0f} N → 重新規劃航線"})
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            _slim.sim = sim; frames.append(_slim(sim.viewer_state()))
    return sim, frames, script


def clip_untangle(sim_hz: float, rec_hz: float):
    sim = Simulator("tether_untangle", seed=2)
    _take_control(sim)
    frames, script = [], []
    pile = next(o for o in sim.world.obstacles if o.name == "Pile P1")
    c = np.asarray(pile.p0[:2], float)
    for _ in range(int(2 * sim_hz)):           # let the cable settle, record the start state
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            _slim.sim = sim; frames.append(_slim(sim.viewer_state()))
    w0 = sim.tether.wraps.get("Pile P1", 0.0)
    script.append({"t": round(sim.t, 1), "text": f"開局：纜線繞樁 {w0:+.2f} 圈，張力 {sim.tether.tension_max:.0f} N"})
    # orbit the pile the opposite way at a safe radius, facing it
    p = sim.vehicle.s.pos
    a0 = math.atan2(p[1] - c[1], p[0] - c[0])
    direction = -1.0 if w0 > 0 else 1.0
    R = pile.radius + 1.6
    # pure pursuit: a single waypoint kept 40 degrees ahead on the circle, so the vehicle orbits
    # continuously instead of braking at every point of a dense route
    lead = math.radians(30)

    def carrot(a, r_now):
        rr = R + float(np.clip(1.5 * (R - r_now), -0.8, 1.2))      # push back out when cutting inside
        pt = c + rr * np.array([math.cos(a), math.sin(a)])
        face = math.atan2(c[1] - pt[1], c[0] - pt[0])
        return Waypoint(float(pt[0]), float(pt[1]), 10.0, face)

    sim.nav.mode, sim.nav.nav_status, sim.nav.speed = "V_NAVI", 1, 0.8
    script.append({"t": round(sim.t, 1), "text": "判斷纏繞方向 → 反方向繞樁解纜（面向樁、保持 1.6 m）"})
    swept, prev = 0.0, a0
    t_end = sim.t + 150
    done_logged = False
    while sim.t < t_end:
        p = sim.vehicle.s.pos
        ang = math.atan2(p[1] - c[1], p[0] - c[0])
        swept += wrap_pi(ang - prev) * direction
        prev = ang
        if not done_logged:
            sim.nav.route, sim.nav.route_i = [carrot(ang + direction * lead, math.hypot(p[0] - c[0], p[1] - c[1]))], 0
            sim.nav.mode, sim.nav.nav_status = "V_NAVI", 1
        sim.step(1 / sim_hz)
        if len(frames) < sim.t * rec_hz:
            _slim.sim = sim; frames.append(_slim(sim.viewer_state()))
        if not done_logged and sim.scenario.objectives[0].done:
            script.append({"t": round(sim.t, 1), "text": f"纏繞解除（剩 {sim.tether.wraps.get('Pile P1', 0.0):+.2f} 圈）→ 懸停"})
            done_logged = True
            sim.nav.route, sim.nav.mode = [], "IDLE"
            sim.nav.hold = Waypoint(float(p[0]), float(p[1]), 10.0, sim.yaw)
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
            _slim.sim = sim; frames.append(_slim(sim.viewer_state()))
    script.append({"t": round(sim.t, 1), "text": f"懸停進度 {ob.progress * 100:.0f}%、纜線張力 {sim.tether.tension_max:.0f} N"})
    return sim, frames, script


def clip_wreck(sim_hz: float, rec_hz: float):
    """Korean Castle: descend, lights on, then the four inspection points; climb over the
    gunwale between them instead of cutting through the hull."""
    sim = Simulator("korean_castle", seed=2)
    _take_control(sim)
    wreck = sim.world.obstacles[0]
    W = lambda x, y, z: wreck.world_point((x, y, z))
    frames, script = [], []

    def face(p, q):
        return math.atan2(q[1] - p[1], q[0] - p[0])

    obs = sim.scenario.objectives
    legs = [  # (waypoints in local coords, facing point in local coords or None, hold objective index)
        ([(45.5, -26.0, 8.0), (45.5, -14.8, 6.0)], (45.5, -10.4, 6.0), 0),
        ([(45.5, -18.0, 16.5), (61.0, 1.5, 15.0)], (61.0, 12.0, 15.0), 1),
        ([(88.0, 19.0, 16.0), (108.5, 21.0, 9.0), (108.5, 16.8, 7.0)], (108.5, 12.8, 7.0), 2),
        ([(122.0, 18.0, 12.0), (137.0, 14.0, 12.0)], (137.0, 10.2, 12.0), 3),
    ]
    texts = ["往 X1-BOW-C05：左舷艏段斷裂面", "爬升越過舷牆 → X1-MID-C07 二號貨艙（艙外俯視）",
             "繞到右舷 → X1-STERN-C11 艉段斷裂面", "X1-STERN-C14 艉樓窗框"]
    sim.nav.speed = 1.1
    leg, stage, lights = 0, "go", False

    def start_leg(i):
        pts, fp, _ = legs[i]
        route = []
        for k, lp in enumerate(pts):
            p = W(*lp)
            nxt = W(*pts[k + 1]) if k + 1 < len(pts) else W(*fp)
            route.append(Waypoint(float(p[0]), float(p[1]), float(p[2]), face(p, nxt)))
        sim.nav.route, sim.nav.route_i, sim.nav.mode, sim.nav.nav_status, sim.nav.hold = route, 0, "V_NAVI", 1, None
        script.append({"t": round(sim.t, 1), "text": texts[i]})

    start_leg(0)
    t_end = 400.0
    while sim.t < t_end:
        if not lights and sim.vehicle.s.pos[2] > 14.0:
            sim.rc_physical.right_switch = 2
            lights = True
            script.append({"t": round(sim.t, 1), "text": f"水深 {sim.vehicle.s.pos[2]:.0f} m，自然光不足 → 開啟 LED（2 檔）"})
        if stage == "go" and sim.nav.mode == "IDLE":
            stage, t_hold = "hold", sim.t
        if stage == "hold":
            ob = obs[legs[leg][2]]
            if ob.done or sim.t - t_hold > 25:
                script.append({"t": round(sim.t, 1), "text": f"{ob.label} ✓" if ob.done else f"{ob.label}（未完成）"})
                leg += 1
                if leg >= len(legs):
                    t_end = min(t_end, sim.t + 6)
                    stage = "done"
                else:
                    start_leg(leg)
                    stage = "go"
        sim.step(1 / sim_hz)
        _slim.sim = sim
        if len(frames) < sim.t * rec_hz:
            frames.append(_slim(sim.viewer_state()))
    return sim, frames, script


CLIPS = {
    "jacket": ("導管架碰撞與纜線勾掛", clip_jacket),
    "untangle": ("纜線纏繞脫困", clip_untangle),
    "monopile": ("強流中樁前懸停", clip_monopile),
    "wreck": ("Korean Castle 沉船調查", clip_wreck),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "viewer" / "demo_recording.json"))
    ap.add_argument("--hz", type=float, default=6.0)
    ap.add_argument("--clips", default=",".join(CLIPS))
    args = ap.parse_args()
    out = {"format": "qysim-replay-2", "hz": args.hz, "clips": []}
    for key in args.clips.split(","):
        title, fn = CLIPS[key]
        global _slim
        _slim = _Slimmer()
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
