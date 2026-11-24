"""Autopilots behind the SDK navigation APIs: DR, H_NAVI, V_NAVI and VCCM.

Each autopilot turns the mission into the same pilot intent the flight controller
receives from the sticks (surge/sway/heave/yaw) plus a heading and depth
set-point, so automatic and manual flight share one control path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

EARTH_R = 6378137.0


class GeoFrame:
    """Flat-earth local tangent plane around a reference point (NED metres)."""

    def __init__(self, lat0: float = 24.35, lng0: float = 120.45):
        self.lat0, self.lng0 = lat0, lng0

    def to_ned(self, lat: float, lng: float) -> tuple[float, float]:
        n = math.radians(lat - self.lat0) * EARTH_R
        e = math.radians(lng - self.lng0) * EARTH_R * math.cos(math.radians(self.lat0))
        return n, e

    def to_geo(self, n: float, e: float) -> tuple[float, float]:
        lat = self.lat0 + math.degrees(n / EARTH_R)
        lng = self.lng0 + math.degrees(e / (EARTH_R * math.cos(math.radians(self.lat0))))
        return lat, lng


def wrap_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Waypoint:
    n: float
    e: float
    depth: float
    heading: float           # rad, NED yaw
    record: bool = True


@dataclass
class AutopilotOutput:
    cmd: dict = field(default_factory=dict)       # surge/sway/heave/yaw in [-1, 1]
    heading: float | None = None
    depth: float | None = None                    # depth set-point (m); None = no depth control


def goto(pos: np.ndarray, yaw: float, wp: Waypoint, speed_frac: float,
         v_world: np.ndarray) -> tuple[AutopilotOutput, float]:
    """Position/heading servo toward ``wp``. Returns (output, horizontal distance)."""
    en, ee = wp.n - pos[0], wp.e - pos[1]
    dist = math.hypot(en, ee)
    # world error -> body frame (yaw only)
    c, s = math.cos(yaw), math.sin(yaw)
    ex_b = c * en + s * ee
    ey_b = -s * en + c * ee
    vx_b = c * v_world[0] + s * v_world[1]
    vy_b = -s * v_world[0] + c * v_world[1]
    k_p, k_d = 0.6, 0.9
    surge = max(-speed_frac, min(speed_frac, k_p * ex_b - k_d * vx_b * 0.5))
    sway = max(-speed_frac, min(speed_frac, k_p * ex_b * 0 + k_p * ey_b - k_d * vy_b * 0.5))
    return AutopilotOutput({"surge": surge, "sway": sway}, wp.heading, wp.depth), dist


class Navigator:
    """Holds DR state and runs whichever autopilot is active."""

    def __init__(self, geo: GeoFrame):
        self.geo = geo
        self.dr_initialized = False
        self.mode = "IDLE"                # IDLE / H_NAVI / V_NAVI / VCCM
        self.paused = False
        self.speed = 0.5                  # m/s (set_h_navi_settings)
        self.accuracy = 0.0
        self.idnum = 0
        self.target: Waypoint | None = None
        self.nav_status = 0               # 0 idle, 1 running, 2 arrived, 3 stopped
        self.route: list[Waypoint] = []
        self.route_i = 0
        self.v_params: dict = {}
        self.vccm_status = "IDLE"
        self.vccm_error = ""
        self.vccm_connected = False
        self.cruise_speed_dm = 0
        self.cruise_distance_m = 0.0
        self.track: list[tuple[float, float, float]] = []   # recorded (n, e, depth)
        self.hold: Waypoint | None = None   # post-arrival station keeping until the pilot takes over

    # ── DR ─────────────────────────────────────────────────────────────────
    def init_dr(self, pos: np.ndarray, lat: float | None, lng: float | None) -> None:
        if lat is not None and lng is not None:
            # re-anchor the frame so the vehicle's current position maps to (lat, lng)
            lat_c, lng_c = self.geo.to_geo(-pos[0], -pos[1])
            dlat, dlng = lat - self.geo.lat0, lng - self.geo.lng0
            self.geo.lat0, self.geo.lng0 = lat_c + dlat, lng_c + dlng
            # (to_geo of an offset around the new origin keeps consistent scale)
            self.geo.lat0 = lat - math.degrees(pos[0] / EARTH_R)
            self.geo.lng0 = lng - math.degrees(pos[1] / (EARTH_R * math.cos(math.radians(lat))))
        self.dr_initialized = True

    # ── H_NAVI ─────────────────────────────────────────────────────────────
    def start_h(self, lat: float, lng: float, depth: float, seabed: float, idnum=None) -> Waypoint:
        n, e = self.geo.to_ned(lat, lng)
        d = depth if depth >= 0 else max(0.0, seabed + depth)      # negative = altitude
        self.idnum = self.idnum + 1 if idnum is None else int(idnum)
        self.target = Waypoint(n, e, d, 0.0)
        self.mode, self.nav_status, self.paused = "H_NAVI", 1, False
        return self.target

    # ── V_NAVI ─────────────────────────────────────────────────────────────
    def start_v(self, pos: np.ndarray, yaw: float, scene: str, route_type: str, direction: str,
                length: float, start_depth: float, end_depth: float, interval: float,
                distance: float, diameter: float = 0.0) -> None:
        self.v_params = dict(scene=scene, route_type=route_type, direction=direction, length=length,
                             start_depth=start_depth, end_depth=end_depth, interval=interval,
                             distance=distance, diameter=diameter)
        self.route = build_facade_route(pos, yaw, **self.v_params)
        self.route_i = 0
        self.mode, self.nav_status, self.paused = "V_NAVI", 1, False

    def stop(self) -> None:
        self.hold = None
        if self.mode in ("H_NAVI", "V_NAVI"):
            self.nav_status = 3
        self.mode = "IDLE" if self.mode != "VCCM" else self.mode
        self.target, self.route = None, []

    # ── per-step autopilot ─────────────────────────────────────────────────
    def step(self, dt: float, pos: np.ndarray, yaw: float, v_world: np.ndarray,
             pilot: dict, vmax_surge: float) -> AutopilotOutput | None:
        if self.mode == "IDLE":
            if self.hold is None or any(abs(float(v)) > 0.05 for v in pilot.values()):
                self.hold = None
                return None
            out, _ = goto(pos, yaw, self.hold, 0.4, v_world)
            return out
        if self.paused:
            return AutopilotOutput({}, yaw, float(pos[2]))
        speed_frac = min(1.0, self.speed / vmax_surge)
        if self.mode == "H_NAVI" and self.target is not None:
            tgt = self.target
            dn, de = tgt.n - pos[0], tgt.e - pos[1]
            dist = math.hypot(dn, de)
            heading = math.atan2(de, dn) if dist > 0.5 else yaw
            wp = Waypoint(tgt.n, tgt.e, tgt.depth, heading)
            out, dist = goto(pos, yaw, wp, speed_frac, v_world)
            # face the target first when far off-heading
            if abs(wrap_pi(heading - yaw)) > math.radians(35):
                out.cmd["surge"] *= 0.2
            if dist < 0.3 and abs(tgt.depth - pos[2]) < 0.25:
                self.hold = Waypoint(tgt.n, tgt.e, tgt.depth, yaw)
                self.mode, self.nav_status, self.target = "IDLE", 2, None
                return None
            return out
        if self.mode == "V_NAVI" and self.route:
            wp = self.route[self.route_i]
            out, dist = goto(pos, yaw, wp, speed_frac, v_world)
            if dist < 0.2 and abs(wp.depth - pos[2]) < 0.15:
                if wp.record:
                    self.track.append((float(pos[0]), float(pos[1]), float(pos[2])))
                self.route_i += 1
                if self.route_i >= len(self.route):
                    self.hold = Waypoint(wp.n, wp.e, wp.depth, wp.heading)
                    self.mode, self.nav_status, self.route = "IDLE", 2, []
                    return None
            return out
        if self.mode == "VCCM" and self.vccm_status == "running":
            # vertical cruise: pilot heave sets cruise speed, horizontal station keeping
            heave = float(pilot.get("heave", 0.0))
            self.cruise_speed_dm = int(round(heave * 5))           # up to 0.5 m/s
            self.cruise_distance_m += abs(v_world[2]) * dt
            return AutopilotOutput({"surge": 0.0, "sway": 0.0, "heave": heave}, yaw, None)
        return None


def build_facade_route(pos, yaw, scene, route_type, direction, length, start_depth,
                       end_depth, interval, distance, diameter=0.0) -> list[Waypoint]:
    """Serpentine scan of a vertical face in front of the vehicle (SDK 8 route variants)."""
    interval = max(0.1, float(interval))
    sgn = 1.0 if str(direction).upper() == "RIGHT" else -1.0
    down = end_depth >= start_depth
    depths = []
    d = start_depth
    while (d <= end_depth + 1e-6) if down else (d >= end_depth - 1e-6):
        depths.append(d)
        d = d + interval if down else d - interval
    if not depths or abs(depths[-1] - end_depth) > 1e-6:
        depths.append(end_depth)

    fwd = np.array([math.cos(yaw), math.sin(yaw)])
    right = np.array([-math.sin(yaw), math.cos(yaw)])
    origin = np.array(pos[:2], float)
    scene = str(scene).upper()
    pts: list[Waypoint] = []

    if scene in ("BRIDGE", "TANK") and abs(diameter) > 1:
        r_obj = abs(diameter) / 2
        inside = scene == "TANK" or diameter < 0
        centre = origin + fwd * ((r_obj + distance) if not inside else (r_obj - distance))
        r_path = r_obj + distance if not inside else max(0.3, r_obj - distance)
        a0 = math.atan2(origin[1] - centre[1], origin[0] - centre[0])
        arc = sgn * float(length) / r_path

        def at(frac, depth):
            a = a0 + arc * frac
            p = centre + r_path * np.array([math.cos(a), math.sin(a)])
            face = math.atan2(centre[1] - p[1], centre[0] - p[0])
            if inside:
                face = wrap_pi(face + math.pi)
            return Waypoint(float(p[0]), float(p[1]), depth, face)
    else:
        def at(frac, depth):
            p = origin + right * (sgn * float(length) * frac)
            return Waypoint(float(p[0]), float(p[1]), depth, yaw)

    n_cols = max(1, int(round(float(length) / interval)))
    if str(route_type).upper() == "LONGITUDINAL":
        cols = [i / n_cols for i in range(n_cols + 1)]
        for k, f in enumerate(cols):
            seq = depths if k % 2 == 0 else depths[::-1]
            pts += [at(f, d) for d in seq]
    else:  # LATERAL: sweep horizontally, step in depth
        for k, d in enumerate(depths):
            seq = (0.0, 1.0) if k % 2 == 0 else (1.0, 0.0)
            steps = max(2, n_cols + 1)
            fr = np.linspace(seq[0], seq[1], steps)
            pts += [at(float(f), d) for f in fr]
    return pts
