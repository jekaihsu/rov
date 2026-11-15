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

import json
from pathlib import Path

from . import site_dressing as dressing
from .flow import Tide
from .silt import seabed_type_for as silt_seabed_type
from .world import Box, Cylinder, CurrentProfile, FieldMesh, SnagFeature, Wall

ASSETS = Path(__file__).resolve().parent / "assets"
STRINGS = {
    "pool_name": "室內測試水池",
    "pool_brief": "潮間帶工作隊的首次操控練習。",
    "pool_walls": ("池北壁", "池南壁", "池東壁", "池西壁"),
}


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
    tether: dict | None = None           # optional TetherParams overrides, e.g. {"density": 1150}
    objectives: list = field(default_factory=list)
    time_limit_s: float = 900.0
    seed: int | None = None
    biome: str = "temperate"
    # Optional simulated vehicle-link setup (see comms.CommsLink); None keeps a healthy link.
    link: dict | None = None
    # Sediment and near-bed turbid layer (silt.py). Provisional site values, not measurements.
    seabed_type: str | None = None      # fluff / mud / silt / sand / gravel / rock; None: from biome
    bnl_height_m: float = 0.0           # e-folding height of the near-bed turbid layer
    bnl_mg_l: float = 0.0               # extra suspended sediment at the bed, mg/L
    water: str = "salt"                  # "salt" or "fresh": pressure-to-depth density of the site
    enclosed: bool = False               # walled pool or tank: DVL beams reverberate off the walls
    # Optical water type for the viewer's colour (oceanic / coastal / shelf / harbour / fresh_clear);
    # None: from the biome (water_type_for). Presentation only; it does not change physics or visibility_m.
    water_type: str | None = None

    def summary(self) -> dict:
        from .aquaculture import layout
        return {"key": self.key, "name": self.name, "brief": self.brief, "seed": self.seed,
                "visibility_m": self.visibility_m, "time_limit_s": self.time_limit_s,
                "tether_length": self.tether_length, "biome": self.biome,
                "seabed_type": silt_seabed_type(self.biome, self.seabed_type),
                "bnl_height_m": self.bnl_height_m, "bnl_mg_l": self.bnl_mg_l,
                "water_type": water_type_for(self.biome, self.water_type, self.water),
                **({"aquaculture": layout()[1]}
                   if self.key == "aquaculture_pen" else {})}


WATER_TYPES = ("oceanic", "coastal", "shelf", "harbour", "fresh_clear")


def water_type_for(biome: str, explicit: str | None = None, water: str = "salt") -> str:
    """Optical water type of a site, loosely after Jerlov's classes (assumed per biome, not measured):
    clear tropical reef water is oceanic (Jerlov I-III), seagrass flats clear coastal (1-3), temperate shelf
    sites such as offshore wind, jackets and wrecks coastal 3-7 ("shelf"), harbours coastal 7-9; a pool is
    clear fresh water."""
    if explicit in WATER_TYPES:
        return explicit
    if water == "fresh":
        return "fresh_clear"
    return {"reef": "oceanic", "seagrass": "coastal", "harbor": "harbour"}.get(biome, "shelf")


# Scenario currents are provisional assumptions, not site measurements (AGENTS.md: replace with
# X1 / site data when available). Streamwise turbulence intensity per setting: tidal channels about
# 10-15 % (Islay 12-13 %), open shelf ~10 %, sheltered harbours ~5-8 % (assumed).
TI_TIDAL = 0.12
TI_OFFSHORE = 0.10
TI_SHELTERED = 0.08
# Random scenarios draw a sea type: (surface knots range, turbulence range, tide kind or None).
RANDOM_SEAS = {
    "harbour": ((0.2, 1.0), (0.05, 0.10), "rectilinear"),
    "tidal_channel": ((1.0, 3.0), (0.10, 0.15), "rectilinear"),
    "offshore": ((0.3, 1.5), (0.08, 0.12), "rotary"),
}


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
        seabed_depth=25.0, current=CurrentProfile(0.3, 45, 0.3, 45, 0.1, 45, TI_SHELTERED),
        start_pos=(0, 0, 2), tether_length=30.0,
        objectives=[Objective("checkpoint", f"檢查點 {i + 1}", p, radius=1.5) for i, p in enumerate(pts)]
                   + [Objective("surface", "回到投放點上浮", (-2, 0, 0.5), radius=3.0)])


def jacket_inspection() -> Scenario:
    sea = 32.0
    obs = jacket(20.0, 0.0, sea)
    legs = [o for o in obs if o.kind == "jacket_leg"]
    objs = [_inspect_leg(l, d, 20.0, 0.0, f"{l.name} 陽極塊 @{d:.0f}m") for l, d in zip(legs, (6, 12, 16, 10))]
    obs += dressing.dress_jacket(obs, 20.0, 0.0, sea, {l.name: (d, 24.0) for l, d in zip(legs, (6, 12, 16, 10))})
    return Scenario(
        "jacket_inspection", "導管架樁腿巡檢", "四腳導管架＋水平/X 斜撐，表層 1.5 kn 洋流。逐一在 0.8–2.5 m 距離內面向樁腿陽極塊停留 5 秒。注意斜撐會卡纜。",
        seabed_depth=sea, obstacles=obs, current=CurrentProfile(1.5, 80, 1.0, 95, 0.4, 110, TI_OFFSHORE,
                                                              tide=Tide(kind="rotary", minor_ratio=0.3)),
        visibility_m=8.0, start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=60.0,
        objectives=objs + [Objective("surface", "回收上浮", (-3, 0, 0.5), radius=3.0)], time_limit_s=1200)


def monopile_current() -> Scenario:
    sea = 28.0
    pile = Cylinder("Monopile M1", (15.0, 0.0, -3.0), (15.0, 0.0, sea + 1.0), 3.0, "monopile")
    stand = (15.0 - 3.0 - 1.5, 0.0, 12.0)
    return Scenario(
        "monopile_current", "單樁抗流懸停", "直徑 6 m 單樁，1.8 kn 橫流（纜線拖曳會吃掉大半推力）。在樁前 1.5 m、深 12 m 處抗流懸停 30 秒，不可碰樁。",
        seabed_depth=sea, obstacles=[pile] + dressing.dress_monopile(pile, sea),
        current=CurrentProfile(1.8, 180, 1.6, 185, 0.8, 190, TI_TIDAL, tide=Tide()),
        visibility_m=10.0, start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=30.0,
        objectives=[Objective("station_keep", "樁前 12 m 懸停 30 秒", stand, radius=1.0, hold_s=30.0,
                              face_point=(15.0, 0.0, 12.0))])


def tether_untangle() -> Scenario:
    sea = 25.0
    pile = Cylinder("Pile P1", (8.0, 0.0, -3.0), (8.0, 0.0, sea + 1.0), 0.9, "pile")
    return Scenario(
        "tether_untangle", "纜線纏繞脫困", "纜線已在 P1 樁繞了一圈多，張力持續上升。判斷纏繞方向，反向繞樁把纜線解開（剩不到 0.25 圈），再回投放點。",
        seabed_depth=sea, obstacles=[pile, SnagFeature("P1 base debris", (9.6, -1.4, sea), 0.3, 0.5, item="debris")],
        current=CurrentProfile(0.8, 90, 0.8, 90, 0.3, 90, TI_OFFSHORE),
        visibility_m=9.0, start_pos=(8.0, 2.8, 10.0), start_heading_deg=180, spool_pos=(-3, 0, 0),
        tether_length=35.0, prewrap={"pile": "Pile P1", "turns": 1.25, "depth": 10.0},
        objectives=[Objective("untangle", "解開 P1 纏繞", target="Pile P1"),
                    Objective("surface", "回投放點上浮", (-2, 0, 0.5), radius=3.0)])


def hull_inspection() -> Scenario:
    sea = 20.0
    hull = dressing.ship_hull("Hull 貨輪船殼", (50.0, 0.0), 0.0, 80.0, 18.0, 8.0)
    pts = [(18, 0, 9.5), (45, 0, 9.5), (70, -6, 9.5), (70, 6, 9.5), (50, 12, 5)]
    return Scenario(
        "hull_inspection", "船殼底部檢查", "80 m 貨輪吃水 8 m。從船底下穿過沿龍骨檢查，再繞到右舷。纜線可能卡在船底邊緣。",
        seabed_depth=sea, obstacles=hull, current=CurrentProfile(0.6, 0, 0.5, 10, 0.2, 20, TI_SHELTERED),
        visibility_m=7.0, start_pos=(0, 0, 3), spool_pos=(-5, 0, 0), tether_length=70.0,
        objectives=[Objective("checkpoint", f"船底 {i + 1}", p, radius=1.8) for i, p in enumerate(pts)])


def wreck_debris(cx: float, cy: float, seabed: float, prefix: str = "Wreck", yaw_deg: float = 0.0) -> list:
    """Snaggable debris round a wreck (offsets in the wreck frame): plates, a rope tangle and rocks.

    Holding forces use the SnagFeature default range, a provisional training setting."""
    items = (((-10.0, -6.5), 0.35, 0.6, "debris"), ((6.0, -6.0), 0.25, 0.3, "rope"),
             ((12.0, 6.5), 0.45, 0.7, "boulder"), ((-15.0, 6.0), 0.3, 0.4, "rock"))
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return [SnagFeature(f"{prefix} {item} {i + 1}", (cx + c * dx - s * dy, cy + s * dx + c * dy, seabed), r, h,
                        item=item)
            for i, ((dx, dy), r, h, item) in enumerate(items)]


def wreck_survey() -> Scenario:
    sea = 30.0
    from .wreck_chenjiao import snag_features
    wreck = FieldMesh("Chenjiao", ASSETS / "wreck_chenjiao_field.npz", origin=(25.0, 5.0, sea + 1.2),
                      heading_deg=35.0, kind="wreck", model="models/wreck_chenjiao.glb")
    c, s = math.cos(math.radians(35)), math.sin(math.radians(35))
    pts = []
    for lx, ly in ((27, 0), (0, 8), (-27, 0), (0, -8)):
        pts.append((25 + c * lx - s * ly, 5 + s * lx + c * ly, sea - 4.0))
    return Scenario(
        "wreck_survey", "沉船調查", "水深 30 m、能見度 4 m，繞沉船一圈拍攝四個面。碰到海床會揚起泥沙；注意桅桿。",
        seabed_depth=sea, obstacles=[wreck] + snag_features(wreck) + wreck_debris(25.0, 5.0, sea, yaw_deg=35.0),
        current=CurrentProfile(0.8, 200, 0.6, 210, 0.3, 220, TI_OFFSHORE),
        visibility_m=4.0, start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=80.0,
        seabed_type="silt", bnl_height_m=1.5, bnl_mg_l=1.0,      # provisional silted wreck site
        objectives=[Objective("checkpoint", n, p, radius=2.0) for n, p in zip(("艏", "左舷", "艉", "右舷"), pts)])


def korean_castle() -> Scenario:
    """Korean Castle wreck (illustrative poster reconstruction, not a survey): 150 m cargo ship
    broken in three on a 32 m seabed. Inspection targets use the model's X1 grid cells
    (C01-C15 every 10 m bow to stern, R01-R04 across)."""
    sea = 32.0
    # local frame: X bow->stern, Y across, Z up from the seabed; bow to the west, stern to the east
    wreck = FieldMesh("Korean Castle", ASSETS / "korean_castle_field.npz", origin=(28.0, -70.0, sea),
                      heading_deg=90.0, kind="wreck", model="models/korean_castle.glb", snag_hold=(250.0, 700.0))
    W = lambda x, y, z: tuple(float(v) for v in wreck.world_point((x, y, z)).round(2))
    objs = [
        Objective("inspect", "X1-BOW-C05 艏段斷裂面（左舷）", W(45.5, -14.8, 6.0), radius=1.6, hold_s=5.0,
                  face_point=W(45.5, -10.4, 6.0)),
        Objective("checkpoint", "X1-MID-C07 二號貨艙開口（艙外俯視，勿入艙）", W(61.0, 1.5, 15.0), radius=2.5, hold_s=5.0),
        Objective("inspect", "X1-STERN-C11 艉段斷裂面（右舷）", W(108.5, 16.8, 7.0), radius=1.6, hold_s=5.0,
                  face_point=W(108.5, 12.8, 7.0)),
        Objective("inspect", "X1-STERN-C14 艉樓窗框", W(137.0, 14.0, 12.0), radius=1.6, hold_s=5.0,
                  face_point=W(137.0, 10.2, 12.0)),
        Objective("surface", "回投放點上浮", (-2.0, 0.0, 0.5), radius=3.0),
    ]
    return Scenario(
        "korean_castle", "Korean Castle 沉船調查",
        "150 m 貨輪斷成三截躺在 32 m 海床，船身長滿附著物、貨艙開口朝上。依 X1 格網編號檢查兩處斷裂面、"
        "二號貨艙與艉樓窗框。不要進入貨艙：纜線很容易卡在艙口圍板。模型為海報推估的示意，非實測。",
        seabed_depth=sea, obstacles=[wreck], current=CurrentProfile(0.9, 250, 0.6, 260, 0.3, 270, TI_OFFSHORE),
        visibility_m=10.0, start_pos=(0.0, 0.0, 4.0), start_heading_deg=90.0, spool_pos=(-4.0, 0.0, 0.0),
        tether_length=90.0, objectives=objs, time_limit_s=1500.0,
        seabed_type="silt")                      # silted wreck site, as wreck_survey (assumed)


def korean_castle_route() -> list:
    """The model's preview ROV route (a lap round the wreck) as world NED waypoints."""
    meta = json.loads((ASSETS / "korean_castle.json").read_text(encoding="utf-8"))
    wreck = korean_castle().obstacles[0]
    return [tuple(float(v) for v in wreck.world_point(p).round(2)) for p in meta["route"]]


def random_current(seed: int, flood_dir: float) -> tuple[CurrentProfile, float]:
    """Current for a random scenario from a sea type (assumed ranges, see RANDOM_SEAS)."""
    rng = np.random.default_rng([int(seed), 0xC0FFEE])
    sea_type = list(RANDOM_SEAS)[int(rng.integers(len(RANDOM_SEAS)))]
    (lo, hi), (ti_lo, ti_hi), tide_kind = RANDOM_SEAS[sea_type]
    base = float(rng.uniform(lo, hi))
    veer = float(rng.uniform(-15, 15))
    tide = Tide(kind=tide_kind, minor_ratio=float(rng.uniform(0.2, 0.5)) if tide_kind == "rotary" else 0.0,
                start=float(rng.uniform(-6.2, 6.2)))
    current = CurrentProfile(base, flood_dir, base * float(rng.uniform(0.6, 0.9)), flood_dir + veer,
                             base * float(rng.uniform(0.3, 0.6)), flood_dir + 2 * veer,
                             float(rng.uniform(ti_lo, ti_hi)), tide=tide)
    return current, base


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
        anodes: dict = {}
        for l in rng.permutation(len(legs))[:3]:
            d = float(rng.uniform(5, sea - 5))
            objs.append(_inspect_leg(legs[int(l)], d, cx, cy, f"{legs[int(l)].name} @{d:.0f}m"))
            anodes[legs[int(l)].name] = (d,)
        obs += dressing.dress_jacket(obs, cx, cy, sea, anodes)
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
        obs += dressing.ship_hull("Hull 船殼", (cx, 0.0), float(rng.uniform(-20, 20)), L, B, T)
        for i in range(3):
            objs.append(Objective("checkpoint", f"船底 {i + 1}", (float(rng.uniform(10, L)), float(rng.uniform(-B / 3, B / 3)), T + 1.5), 1.8))
    else:
        obs.append(Wall("Quay 岸壁", (float(rng.uniform(12, 25)), 0.0, 0.0), 180.0, 120.0, -2.0, "quay"))
        for i in range(3):
            objs.append(Objective("checkpoint", f"岸壁 {i + 1}", (obs[0].point[0] - 1.8, float(rng.uniform(-20, 20)), float(rng.uniform(3, sea - 3))), 1.5))
        lane = tuple(-o.point[1] for o in objs)
        obs += dressing.dress_quay(obs[0], sea, keep_clear=lane)
        obs += dressing.quay_debris(obs[0], sea)
    # Legacy draws keep every seed's layout, visibility and tether length unchanged.
    dirs = rng.uniform(0, 360, 3)
    rng.uniform(0.0, 3.0, 6)
    current, base = random_current(seed, float(dirs[0]))
    return Scenario(
        "random", f"隨機情境 #{seed}", f"隨機生成（{kind}），水深 {sea:.0f} m、表層流 {base:.1f} kn。完成所有檢查點，避免碰撞與纜線過載。",
        seabed_depth=sea, obstacles=obs, current=current, visibility_m=float(rng.uniform(3, 14)),
        start_pos=(0, 0, 3), spool_pos=(-4, 0, 0), tether_length=float(rng.uniform(40, 120)),
        objectives=objs, time_limit_s=1200, seed=seed,
        seabed_type="mud" if kind == "wall" else None)          # harbour quay: muddy bed (assumed)


def coral_reef() -> Scenario:
    return Scenario("coral_reef", "珊瑚礁生態觀察", "沿珊瑚礁觀測帶拍攝珊瑚與魚群，保持離底距離，避免接觸生物。",
                    seabed_depth=14, biome="reef", visibility_m=18,
                    current=CurrentProfile(.55, 60, .35, 75, .12, 90, TI_OFFSHORE),
                    start_pos=(0, 0, 3), tether_length=70,
                    objectives=[Objective("inspect", "礁區西側觀測", (16, -12, 9), 2.5, hold_s=8),
                                Objective("inspect", "礁區東側魚群調查", (35, 12, 9), 2.5, hold_s=8),
                                Objective("surface", "回到投放區", (-2, 0, .5), 3)])


def seagrass_meadow() -> Scenario:
    return Scenario("seagrass_meadow", "海草床低干擾調查", "淺水海草床與沙地，緩速離底航行；近底推進器會揚起局部泥沙。",
                    seabed_depth=9, biome="seagrass", visibility_m=12,
                    current=CurrentProfile(.4, 110, .3, 100, .10, 95, TI_SHELTERED),
                    start_pos=(0, 0, 2), tether_length=60,
                    objectives=[Objective("inspect", "海草床樣區 A", (14, -9, 6), 2, hold_s=8),
                                Objective("inspect", "海星與沙地樣區 B", (32, 8, 6), 2, hold_s=8),
                                Objective("surface", "返回投放區", (-2, 0, .5), 3)])


def harbor_obstacles(sea: float) -> list:
    """Quay wall with its fittings, two rows of jetty piles under a deck, and debris off the quay toe."""
    quay = Wall("Quay", (42, 0, 0), 180, 70, -2, "quay")
    obs = [quay,
           Cylinder("Harbor pile A", (21, -10, -2), (21, -10, sea), .65),
           Cylinder("Harbor pile B", (21, 10, -2), (21, 10, sea), .65)]
    for row, y in (("A", -10), ("B", 10)):
        for k, x in ((2, 27), (3, 33)):
            obs.append(Cylinder(f"Harbor pile {row}{k}", (x, y, -2), (x, y, sea), .65))
        obs.append(Box(f"Jetty deck {row}", (30.5, y, -2.4), (11.5, 2.2, .4), 0, "deck"))
    obs += dressing.dress_quay(quay, sea, keep_clear=(0.0,))
    # snaggable debris off the quay (mooring block, rope, rubble), placed on main with the tether snag model
    obs += [SnagFeature("Harbor mooring block", (24, -6, sea), .5, .6, item="debris"),
            SnagFeature("Harbor rope tangle", (30, 4, sea), .25, .3, item="rope"),
            SnagFeature("Harbor rubble", (36, -2, sea), .4, .5, item="rock")]
    return obs


def harbor_inspection() -> Scenario:
    sea = 18.
    return Scenario("harbor_inspection", "港灣協作巡檢", "在港樁與碼頭邊分工巡檢，留意橫流、纜線與低能見度。",
                    seabed_depth=sea, biome="harbor", visibility_m=7, seabed_type="mud",
                    # Provisional near-bed turbid layer: about half the mid-water visibility at 0.5 m altitude.
                    bnl_height_m=2.0, bnl_mg_l=2.0,
                    obstacles=harbor_obstacles(sea),
                    current=CurrentProfile(.8, 90, .55, 95, .15, 110, TI_SHELTERED, tide=Tide()),
                    start_pos=(0, 0, 3), tether_length=75,
                    objectives=[Objective("inspect", "港樁 A", (18, -10, 8), 1.5, hold_s=6, face_point=(21,-10,8)),
                                Objective("inspect", "港樁 B", (18, 10, 8), 1.5, hold_s=6, face_point=(21,10,8)),
                                Objective("inspect", "碼頭壁面", (39, 0, 10), 1.5, hold_s=6, face_point=(42,0,10)),
                                Objective("surface", "返回投放區", (-2, 0, .5), 3)])


def sonar_search() -> Scenario:
    """Low visibility acoustic approach training; parameters are illustrative."""
    return Scenario("sonar_search", "聲納搜尋", "坐底掃描、讀方位、轉向零度，再接近回波並以攝影機確認。",
                    seabed_depth=15, visibility_m=0.8, start_pos=(0, 0, 13), spool_pos=(-3, 0, 0),
                    tether_length=60,
                    obstacles=[Box("搜尋目標", (18, 5, 13), (1, 1, 2))],
                    objectives=[Objective("checkpoint", "接近並確認目標", (16, 5, 13), radius=1.5)])


def tutorial_pool() -> Scenario:
    """Calm indoor commissioning pool, using the unchanged vehicle dynamics."""
    return Scenario("tutorial_pool", STRINGS["pool_name"], STRINGS["pool_brief"],
                    seabed_depth=8, visibility_m=20, start_pos=(0, 0, 3), tether_length=35, seabed_type="rock",
                    water="fresh", enclosed=True,
                    current=CurrentProfile(0, 0, 0, 0, 0, 0, 0),
                    obstacles=[Wall(STRINGS["pool_walls"][0], (12, 0, 0), 180, 24, 0),
                               Wall(STRINGS["pool_walls"][1], (-12, 0, 0), 0, 24, 0),
                               Wall(STRINGS["pool_walls"][2], (0, 12, 0), 270, 24, 0),
                               Wall(STRINGS["pool_walls"][3], (0, -12, 0), 90, 24, 0)])


# Incident exercises use existing contacts, cable wrapping and scoring only.
INCIDENT_STRINGS = {
    "incident_jacket": ("事故演練｜導管架內受困", "強潮流中止巡檢，沿西側出口撤離；人手與信標壓力見講評腳本。"),
    "incident_wreck": ("事故演練｜沉船勾纏", "不要硬拉；沿纜線回卡點，反向解纏再回收。繞樁代替殘骸細線。"),
    "incident_silt": ("險情演練｜揚沙迷航",
                      "貼近鬆軟泥底懸停；起飛的推進水流會揚起泥沙，畫面可能全黑。沿纜線回出發點，考慮先調暗燈光。"),
    "incident_compass": ("險情演練｜鋼構羅盤失準", "演練通報：航向讀數不可信，退出定向，依目視與纜線撤離。未改寫羅盤讀數。"),
    "incident_current": ("險情演練｜流速超限", "無法維持站位時中止，沿回收路線撤離；流速為演練設定，非機型能力值。"),
    "exit": "沿纜線離開危險區",
    "return": "回投放點回收",
    "untangle": "反向繞卡點解纏",
}


def _dressed_jacket(cx: float, cy: float, sea: float, prefix: str) -> list:
    obs = jacket(cx, cy, sea, prefix=prefix)
    legs = [o for o in obs if o.kind == "jacket_leg"]
    return obs + dressing.dress_jacket(obs, cx, cy, sea, {l.name: (10.0, 24.0) for l in legs})


def incident_jacket() -> Scenario:
    name, brief = INCIDENT_STRINGS["incident_jacket"]
    return Scenario(
        "incident_jacket", name, brief, seabed_depth=32,
        obstacles=_dressed_jacket(0, 0, 32, "Training"),
        current=CurrentProfile(2, 90, 1.8, 90, 1, 90, TI_TIDAL, tide=Tide()),
        start_pos=(0, 0, 12), spool_pos=(-12, 0, 0), tether_length=40,
        objectives=[Objective("checkpoint", INCIDENT_STRINGS["exit"], (-8, 0, 12)),
                    Objective("surface", INCIDENT_STRINGS["return"], (-12, 0, .5), radius=3)],
        time_limit_s=240)


def incident_wreck() -> Scenario:
    name, brief = INCIDENT_STRINGS["incident_wreck"]
    snag = Cylinder("Training snag", (8, 0, 118), (8, 0, 135), .6, "pile")
    return Scenario(
        "incident_wreck", name, brief, seabed_depth=138, visibility_m=4,
        current=CurrentProfile(0.5, 200, 0.4, 210, 0.3, 220, TI_SHELTERED),     # weak deep-water current
        obstacles=[Box("Training wreck", (20, 0, 134), (6, 3, 3), 0, "wreck"), snag]
                  + wreck_debris(20.0, 0.0, 138.0, "Training"),
        start_pos=(8, 2.8, 128), spool_pos=(0, 0, 0), tether_length=160, seabed_type="silt",
        prewrap={"pile": "Training snag", "turns": 1.25, "depth": 128},
        objectives=[Objective("untangle", INCIDENT_STRINGS["untangle"], target="Training snag"),
                    Objective("surface", INCIDENT_STRINGS["return"], (0, 0, .5), radius=3)],
        time_limit_s=600)


def incident_silt() -> Scenario:
    name, brief = INCIDENT_STRINGS["incident_silt"]
    return Scenario(
        # The vehicle hovers 0.45 m over a soft fluff bed: the silt-out comes from the pilot's own thrust.
        "incident_silt", name, brief, seabed_depth=12, visibility_m=3,
        seabed_type="fluff", bnl_height_m=1.0, bnl_mg_l=2.0,
        start_pos=(8, 0, 11.55), spool_pos=(0, 0, 0), tether_length=20,
        objectives=[Objective("checkpoint", INCIDENT_STRINGS["exit"], (4, 0, 6)),
                    Objective("surface", INCIDENT_STRINGS["return"], (0, 0, .5), radius=2)],
        time_limit_s=240)


def incident_compass() -> Scenario:
    name, brief = INCIDENT_STRINGS["incident_compass"]
    return Scenario(
        "incident_compass", name, brief, seabed_depth=20, visibility_m=6,
        obstacles=[Box("Training steel", (12, 0, 10), (2, 6, 8), 0, "hull")],
        start_pos=(7, 0, 10), spool_pos=(0, 0, 0), tether_length=25,
        objectives=[Objective("checkpoint", INCIDENT_STRINGS["exit"], (3, 0, 10)),
                    Objective("surface", INCIDENT_STRINGS["return"], (0, 0, .5), radius=2)],
        time_limit_s=240)


def incident_current() -> Scenario:
    name, brief = INCIDENT_STRINGS["incident_current"]
    return Scenario(
        "incident_current", name, brief, seabed_depth=20, visibility_m=8,
        current=CurrentProfile(3, 90, 3, 90, 2, 90, TI_TIDAL),
        start_pos=(6, 0, 8), spool_pos=(0, 0, 0), tether_length=25,
        objectives=[Objective("checkpoint", INCIDENT_STRINGS["exit"], (2, 0, 8)),
                    Objective("surface", INCIDENT_STRINGS["return"], (0, 0, .5), radius=3)],
        time_limit_s=180)


def aquaculture_pen() -> Scenario:
    from .aquaculture import layout, STRINGS as pen_strings
    obstacles, _ = layout()
    return Scenario(
        "aquaculture_pen", pen_strings["name"], pen_strings["brief"],
        seabed_depth=25., obstacles=obstacles, visibility_m=8., biome="aquaculture",
        seabed_type="mud", water_type="coastal", start_pos=(3., 0., 7.),
        spool_pos=(-2., 0., 0.), tether_length=150., time_limit_s=2400.,
        current=CurrentProfile(.8, 90, .5, 95, .3, 100, TI_SHELTERED),
        objectives=[Objective("pen_lap", pen_strings["lap"], (3., 0., 7.)),
                    Objective("pen_photo", pen_strings["photo"], (3., 0., 7.), target="hole-0"),
                    Objective("pen_recover", pen_strings["recover"], (9., 1., 15.), target="mort-0")])


LIBRARY = {
    "incident_jacket": incident_jacket,
    "incident_wreck": incident_wreck,
    "incident_silt": incident_silt,
    "incident_compass": incident_compass,
    "incident_current": incident_current,

    "tutorial_pool": tutorial_pool,
    "sonar_search": sonar_search,
    "open_water": open_water,
    "jacket_inspection": jacket_inspection,
    "monopile_current": monopile_current,
    "tether_untangle": tether_untangle,
    "hull_inspection": hull_inspection,
    "wreck_survey": wreck_survey,
    "korean_castle": korean_castle,
    "coral_reef": coral_reef,
    "seagrass_meadow": seagrass_meadow,
    "harbor_inspection": harbor_inspection,
    "aquaculture_pen": aquaculture_pen,
}


def build(key: str, seed: int | None = None) -> Scenario:
    if key == "random":
        return random_scenario(seed)
    if key not in LIBRARY:
        raise KeyError(f"unknown scenario {key!r}; choose from {sorted(LIBRARY)} or 'random'")
    scenario = LIBRARY[key]()
    scenario.seed = int(seed) if seed is not None else 0
    return scenario


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
        self.pen_sectors = set()

    def update(self, dt: float, sim) -> None:
        if self.finished or self.failed:
            return
        self.elapsed += dt
        # impacts
        for ev in sim.world.events[self.seen_events:]:
            if ev.vehicle_id not in (getattr(sim, "vehicle_id", "default"), "default"):
                continue
            self.penalties.append({"t": ev.t, "reason": f"碰撞 {ev.obstacle}（{ev.severity} {ev.speed} m/s）",
                                   "points": PENALTY[ev.severity]})
        self.seen_events = len(sim.world.events)
        if sum(1 for e in sim.world.events if e.severity == "severe" and
               e.vehicle_id in (getattr(sim, "vehicle_id", "default"), "default")) >= 3:
            self.failed = "嚴重碰撞 3 次"
        # tether
        tt = sim.tether
        # Rated working load (cable or termination), formerly a fixed 250 N; same penalty per episode.
        over = tt.over_working_load
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
        if ob.kind.startswith("pen_"):
            from .aquaculture import update_objective
            update_objective(self, ob, sim)
        elif ob.kind in ("checkpoint", "surface"):
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
