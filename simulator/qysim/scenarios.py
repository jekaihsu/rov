"""Training scenarios, random scenario generator, objectives and scoring.

A scenario defines the site (obstacles, seabed, current profile, visibility), the
start state (ROV pose, spool position, tether length, optional pre-wrapped cable)
and an ordered list of objectives. ``Scorer`` tracks objectives and penalties
(impacts, tether over-tension, tether break) during the run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .world import Box, Cylinder, CurrentProfile, Wall


@dataclass
class Objective:
    kind: str                      # checkpoint / inspect / station_keep / untangle / surface
    label: str
    point: tuple = (0.0, 0.0, 0.0)  # NED
    radius: float = 1.5
    hold_s: float = 0.0
    face_point: tuple | None = None   # inspect: the ROV must face this point
    standoff: tuple = (0.8, 2.5)      # inspect: allowed distance to the target surface
    target: str = ""                  # untangle: obstacle name
    done: bool = False
    progress: float = 0.0

    def as_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label, "point": list(self.point), "radius": self.radius,
                "hold_s": self.hold_s, "done": self.done, "progress": round(self.progress, 2),
                "target": self.target}


@dataclass
class Scenario:
    key: str
    name: str
    brief: str
    seabed_depth: float = 30.0
    obstacles: list = field(default_factory=list)
    current: CurrentProfile = field(default_factory=CurrentProfile)
    visibility_m: float = 12.0
    start_pos: tuple = (0.0, 0.0, 3.0)
    start_heading_deg: float = 0.0
    spool_pos: tuple = (-3.0, 0.0, 0.0)
    tether_length: float = 40.0
    prewrap: dict | None = None          # {"pile": name, "turns": 1.25, "depth": 10}
    objectives: list = field(default_factory=list)
    time_limit_s: float = 900.0
    seed: int | None = None

    def summary(self) -> dict:
        return {"key": self.key, "name": self.name, "brief": self.brief, "seed": self.seed,
                "visibility_m": self.visibility_m, "time_limit_s": self.time_limit_s,
                "tether_length": self.tether_length}


# ── site builders ──────────────────────────────────────────────────────────
def jacket(cx: float, cy: float, seabed: float, half: float = 6.0, leg_r: float = 0.6,
           prefix: str = "J") -> list:
    """Four-legged jacket with horizontal and X braces."""
    top, bot = -3.0, seabed + 1.0
    legs = []
    obs = []
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, -1), (-1, 1))):
        p_top = (cx + sx * half * 0.8, cy + sy * half * 0.8, top)
        p_bot = (cx + sx * half, cy + sy * half, bot)
        legs.append((p_top, p_bot))
        obs.append(Cylinder(f"{prefix} leg {'ABCD'[i]}", p_top, p_bot, leg_r, "jacket_leg"))

    def on_leg(i, z):
        (a, b) = legs[i]
        t = (z - a[2]) / (b[2] - a[2])
        return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))

    levels = [z for z in (8.0, 18.0, 28.0) if z < seabed - 1.5]
    for z in levels:
        for i in range(4):
            obs.append(Cylinder(f"{prefix} brace {z:.0f}m {'ABCD'[i]}{'ABCD'[(i + 1) % 4]}",
                                on_leg(i, z), on_leg((i + 1) % 4, z), 0.25, "brace"))
    for z0, z1 in zip(levels[:-1], levels[1:]):
        for i in range(4):
            j = (i + 1) % 4
            obs.append(Cylinder(f"{prefix} X {z0:.0f}-{z1:.0f} {'ABCD'[i]}", on_leg(i, z0), on_leg(j, z1), 0.2, "brace"))
    return obs


def _leg_point(ob: Cylinder, depth: float) -> tuple:
    a, b = np.asarray(ob.p0), np.asarray(ob.p1)
    t = (depth - a[2]) / (b[2] - a[2])
    return tuple(float(v) for v in a + (b - a) * t)


def _inspect_leg(ob: Cylinder, depth: float, cx: float, cy: float, label: str) -> Objective:
    c = np.asarray(_leg_point(ob, depth))
    out = c[:2] - np.array([cx, cy])
    out = out / np.linalg.norm(out)
    stand = c.copy()
    stand[:2] += out * (ob.radius + 1.5)
    return Objective("inspect", label, tuple(stand), radius=1.2, hold_s=5.0, face_point=tuple(c),
                     standoff=(0.8, 2.5))


# ── scenario library ───────────────────────────────────────────────────────
def open_water() -> Scenario:
    pts = [(10, 0, 6), (10, 10, 10), (0, 10, 14), (0, 0, 8)]
    return Scenario(
        "open_water", "開放水域熟悉", "無結構物，微弱洋流。依序通過 4 個檢查點，熟悉搖桿、A/S 模式和定深。",
        seabed_depth=25.0, current=CurrentProfile(0.3, 45, 0.3, 45, 0.1, 45, 0.2),
        start_pos=(0, 0, 2), tether_length=30.0,
        objectives=[Objective("checkpoint", f"檢查點 {i + 1}", p, radius=1.5) for i, p in enumerate(pts)]
                   + [Objective("surface", "回到投放點上浮", (-2, 0, 0.5), radius=3.0)])


def jacket_inspection() -> Scenario:
    sea = 32.0
    obs = jacket(20.0, 0.0, sea)
    legs = [o for o in obs if o.kind == "jacket_leg"]
    objs = [_inspect_leg(l, d, 20.0, 0.0, f"{l.name} 陽極塊 @{d:.0f}m") for l, d in zip(legs, (6, 12, 16, 10))]
    return Scenario(
        "jacket_inspection", "導管架樁腿巡檢", "四腳導管架＋水平/X 斜撐，表層 1.5 kn 洋流。逐一在 0.8–2.5 m 距離內面向樁腿陽極塊停留 5 秒。注意斜撐會卡纜。",
        seabed_depth=sea, obstacles=obs, current=CurrentProfile(1.5, 80, 1.0, 95, 0.4, 110, 0.25),
        visibility_m=8.0, start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=60.0,
        objectives=objs + [Objective("surface", "回收上浮", (-3, 0, 0.5), radius=3.0)], time_limit_s=1200)


def monopile_current() -> Scenario:
    sea = 28.0
    pile = Cylinder("Monopile M1", (15.0, 0.0, -3.0), (15.0, 0.0, sea + 1.0), 3.0, "monopile")
    stand = (15.0 - 3.0 - 1.5, 0.0, 12.0)
    return Scenario(
        "monopile_current", "單樁抗流懸停", "直徑 6 m 單樁，2.5 kn 強流。在樁前 1.5 m、深 12 m 處抗流懸停 30 秒，不可碰樁。",
        seabed_depth=sea, obstacles=[pile], current=CurrentProfile(2.5, 180, 2.2, 185, 1.0, 190, 0.3),
        visibility_m=10.0, start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=40.0,
        objectives=[Objective("station_keep", "樁前 12 m 懸停 30 秒", stand, radius=1.0, hold_s=30.0,
                              face_point=(15.0, 0.0, 12.0))])


def tether_untangle() -> Scenario:
    sea = 25.0
    pile = Cylinder("Pile P1", (8.0, 0.0, -3.0), (8.0, 0.0, sea + 1.0), 0.9, "pile")
    return Scenario(
        "tether_untangle", "纜線纏繞脫困", "纜線已在 P1 樁繞了一圈多，張力持續上升。判斷纏繞方向，反向繞樁把纜線解開（剩不到 0.25 圈），再回投放點。",
        seabed_depth=sea, obstacles=[pile], current=CurrentProfile(0.8, 90, 0.8, 90, 0.3, 90, 0.2),
        visibility_m=9.0, start_pos=(8.0, 2.8, 10.0), start_heading_deg=180, spool_pos=(-3, 0, 0),
        tether_length=35.0, prewrap={"pile": "Pile P1", "turns": 1.25, "depth": 10.0},
        objectives=[Objective("untangle", "解開 P1 纏繞", target="Pile P1"),
                    Objective("surface", "回投放點上浮", (-2, 0, 0.5), radius=3.0)])


def hull_inspection() -> Scenario:
    sea = 20.0
    hull = Box("Hull 貨輪船殼", (50.0, 0.0, 4.0), (40.0, 9.0, 4.0), 0.0, "hull")
    pts = [(18, 0, 9.5), (45, 0, 9.5), (70, -6, 9.5), (70, 6, 9.5), (50, 12, 5)]
    return Scenario(
        "hull_inspection", "船殼底部檢查", "80 m 貨輪吃水 8 m。從船底下穿過沿龍骨檢查，再繞到右舷。纜線可能卡在船底邊緣。",
        seabed_depth=sea, obstacles=[hull], current=CurrentProfile(0.6, 0, 0.5, 10, 0.2, 20, 0.2),
        visibility_m=7.0, start_pos=(0, 0, 3), spool_pos=(-5, 0, 0), tether_length=70.0,
        objectives=[Objective("checkpoint", f"船底 {i + 1}", p, radius=1.8) for i, p in enumerate(pts)])


def wreck_survey() -> Scenario:
    sea = 30.0
    wreck = Box("Wreck 沉船", (25.0, 5.0, sea - 3.0), (18.0, 4.0, 3.0), 35.0, "wreck")
    mast = Cylinder("Wreck mast", (22.0, 3.0, sea - 6.0), (22.5, 3.5, sea - 14.0), 0.25, "mast")
    c, s = math.cos(math.radians(35)), math.sin(math.radians(35))
    pts = []
    for lx, ly in ((20, 0), (0, 6.5), (-20, 0), (0, -6.5)):
        pts.append((25 + c * lx - s * ly, 5 + s * lx + c * ly, sea - 4.0))
    return Scenario(
        "wreck_survey", "沉船調查", "水深 30 m、能見度 4 m，繞沉船一圈拍攝四個面。碰到海床會揚起泥沙；注意桅桿。",
        seabed_depth=sea, obstacles=[wreck, mast], current=CurrentProfile(0.8, 200, 0.6, 210, 0.3, 220, 0.25),
        visibility_m=4.0, start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=80.0,
        objectives=[Objective("checkpoint", n, p, radius=2.0) for n, p in zip(("艏", "左舷", "艉", "右舷"), pts)])


def random_scenario(seed: int | None = None) -> Scenario:
    rng = np.random.default_rng(seed)
    seed = int(seed if seed is not None else rng.integers(0, 10 ** 6))
    rng = np.random.default_rng(seed)
    sea = float(rng.uniform(18, 40))
    kind = rng.choice(["jacket", "piles", "hull", "wall"])
    obs: list = []
    objs: list = []
    if kind == "jacket":
        cx, cy = float(rng.uniform(15, 30)), float(rng.uniform(-8, 8))
        obs = jacket(cx, cy, sea)
        legs = [o for o in obs if o.kind == "jacket_leg"]
        for l in rng.permutation(len(legs))[:3]:
            d = float(rng.uniform(5, sea - 5))
            objs.append(_inspect_leg(legs[int(l)], d, cx, cy, f"{legs[int(l)].name} @{d:.0f}m"))
    elif kind == "piles":
        for i in range(int(rng.integers(3, 7))):
            p = (float(rng.uniform(8, 35)), float(rng.uniform(-15, 15)))
            r = float(rng.uniform(0.5, 2.0))
            obs.append(Cylinder(f"Pile R{i + 1}", (p[0], p[1], -3.0), (p[0], p[1], sea + 1), r, "pile"))
        for i in range(3):
            objs.append(Objective("checkpoint", f"檢查點 {i + 1}",
                                  (float(rng.uniform(5, 38)), float(rng.uniform(-14, 14)), float(rng.uniform(4, sea - 4))), 1.8))
    elif kind == "hull":
        L, B, T = float(rng.uniform(40, 120)), float(rng.uniform(10, 24)), float(rng.uniform(4, 10))
        cx = L / 2 + 8
        obs.append(Box("Hull 船殼", (cx, 0.0, T / 2), (L / 2, B / 2, T / 2), float(rng.uniform(-20, 20)), "hull"))
        for i in range(3):
            objs.append(Objective("checkpoint", f"船底 {i + 1}", (float(rng.uniform(10, L)), float(rng.uniform(-B / 3, B / 3)), T + 1.5), 1.8))
    else:
        obs.append(Wall("Quay 岸壁", (float(rng.uniform(12, 25)), 0.0, 0.0), 180.0, 120.0, -2.0, "wall"))
        for i in range(3):
            objs.append(Objective("checkpoint", f"岸壁 {i + 1}", (obs[0].point[0] - 1.8, float(rng.uniform(-20, 20)), float(rng.uniform(3, sea - 3))), 1.5))
    dirs = rng.uniform(0, 360, 3)
    base = float(rng.uniform(0.0, 3.0))
    current = CurrentProfile(base, float(dirs[0]), base * float(rng.uniform(0.5, 1.0)), float(dirs[0] + rng.uniform(-40, 40)),
                             base * float(rng.uniform(0.1, 0.5)), float(dirs[0] + rng.uniform(-60, 60)), float(rng.uniform(0.1, 0.4)))
    return Scenario(
        "random", f"隨機情境 #{seed}", f"隨機生成（{kind}），水深 {sea:.0f} m、表層流 {base:.1f} kn。完成所有檢查點，避免碰撞與纜線過載。",
        seabed_depth=sea, obstacles=obs, current=current, visibility_m=float(rng.uniform(3, 14)),
        start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=float(rng.uniform(40, 120)),
        objectives=objs, time_limit_s=1200, seed=seed)


LIBRARY = {
    "open_water": open_water,
    "jacket_inspection": jacket_inspection,
    "monopile_current": monopile_current,
    "tether_untangle": tether_untangle,
    "hull_inspection": hull_inspection,
    "wreck_survey": wreck_survey,
}


def build(key: str, seed: int | None = None) -> Scenario:
    if key == "random":
        return random_scenario(seed)
    if key not in LIBRARY:
        raise KeyError(f"unknown scenario {key!r}; choose from {sorted(LIBRARY)} or 'random'")
    return LIBRARY[key]()


def catalogue() -> list[dict]:
    out = [{"key": k, "name": f().name, "brief": f().brief} for k, f in LIBRARY.items()]
    out.append({"key": "random", "name": "隨機模式", "brief": "隨機結構物、洋流、能見度與纜長；可指定種子重現同一題。"})
    return out


# ── scoring ────────────────────────────────────────────────────────────────
PENALTY = {"touch": 5, "hard": 15, "severe": 30}


class Scorer:
    def __init__(self, sc: Scenario):
        self.sc = sc
        self.penalties: list[dict] = []
        self.seen_events = 0
        self.seen_tether_events = 0
        self._over_tension = False
        self.failed = ""
        self.finished = False
        self.elapsed = 0.0
        self.current_index = 0

    def update(self, dt: float, sim) -> None:
        if self.finished or self.failed:
            return
        self.elapsed += dt
        # impacts
        for ev in sim.world.events[self.seen_events:]:
            self.penalties.append({"t": ev.t, "reason": f"碰撞 {ev.obstacle}（{ev.severity} {ev.speed} m/s）",
                                   "points": PENALTY[ev.severity]})
        self.seen_events = len(sim.world.events)
        if sum(1 for e in sim.world.events if e.severity == "severe") >= 3:
            self.failed = "嚴重碰撞 3 次"
        # tether
        tt = sim.tether
        over = tt.tension_max > tt.p.warn_n
        if over and not self._over_tension:
            self.penalties.append({"t": round(sim.t, 2), "reason": f"纜線張力過高 {tt.tension_max:.0f} N", "points": 10})
        self._over_tension = over
        if tt.broken:
            self.failed = "臍帶纜斷裂"
        if self.elapsed > self.sc.time_limit_s:
            self.failed = "超過時間限制"
        # objectives (in order)
        objs = self.sc.objectives
        while self.current_index < len(objs) and objs[self.current_index].done:
            self.current_index += 1
        if self.current_index >= len(objs):
            self.finished = True
            return
        ob = objs[self.current_index]
        pos = sim.vehicle.s.pos
        if ob.kind in ("checkpoint", "surface"):
            if np.linalg.norm(pos - np.asarray(ob.point)) < ob.radius:
                ob.done, ob.progress = True, 1.0
        elif ob.kind in ("inspect", "station_keep"):
            ok = np.linalg.norm(pos - np.asarray(ob.point)) < ob.radius
            if ok and ob.face_point is not None:
                to = np.asarray(ob.face_point) - pos
                heading_to = math.atan2(to[1], to[0])
                ok = abs((heading_to - sim.yaw + math.pi) % (2 * math.pi) - math.pi) < math.radians(35)
            ob.progress = min(1.0, ob.progress + dt / ob.hold_s) if ok else max(0.0, ob.progress - dt / ob.hold_s * 0.5)
            if ob.progress >= 1.0:
                ob.done = True
        elif ob.kind == "untangle":
            if abs(sim.tether.wraps.get(ob.target, 0.0)) < 0.25:
                ob.progress += dt / 3.0
                if ob.progress >= 1.0:
                    ob.done = True
            else:
                ob.progress = 0.0

    @property
    def score(self) -> int:
        done = sum(1 for o in self.sc.objectives if o.done)
        total = max(1, len(self.sc.objectives))
        base = 100 * done / total
        return int(max(0, round(base - sum(p["points"] for p in self.penalties))))

    def as_dict(self) -> dict:
        return {"score": self.score, "elapsed": round(self.elapsed, 1), "failed": self.failed,
                "finished": self.finished, "current_index": self.current_index,
                "objectives": [o.as_dict() for o in self.sc.objectives],
                "penalties": self.penalties[-20:], "penalty_total": sum(p["points"] for p in self.penalties)}
