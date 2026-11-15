"""Shared sensor and estimation layer between physics truth and every consumer of measurements.

Physics truth (vehicle state, world geometry) -> ``SensorSuite.step`` -> ``SensorFrame``. The frame is read by
the flight controller (heading, depth and position hold), the SDK autopilots and dead reckoning, the SDK
telemetry and the viewer state. Nothing downstream reads truth for a quantity a real vehicle has to measure.

``SensorConfig(ideal=True)`` restores the pre-layer behaviour exactly: the suite then produces no frame for
control (the controller and navigator receive ``None`` and read truth as before) and every telemetry helper
evaluates the same expressions the engine used before this module existed. Tests compare that path
byte-for-byte against a frozen copy of the old engine.

Sensor models (realistic path, the default):
  heading   gyro bias drift fused with a magnetometer through a complementary filter; magnetometer deviation
            from steel in the scene (cube-law dipoles derived from obstacle definitions and the wreck distance
            field); occasional EKF-style "yaw re-aligned" jumps when the anomaly is strong
  depth     surface zero offset, fresh/salt density setting, quantisation and noise, 50 Hz sample-and-hold
  echo      altimeter and forward range as 25 degree cones with a 0.3 m blind zone against terrain and
            obstacles, false returns from fish schools and vegetation
  DVL       four-beam bottom lock with altitude window, slope limit, vegetation, soft mud, aeration, silt,
            pool reverberation, coast/re-acquire hysteresis, scale error and noise; dead reckoning integrates
            DVL velocity with the estimated heading and freezes when the lock is lost

Every number is provisional. Tags: [datasheet] primary spec of a comparable sensor (not X1), [vendor] QYSEA
claim, [forum] field report, [assumption] chosen here. Sources are listed in
``research_notes/感測器_揚沙_通訊/sensors_and_navigation.md``; X1 values await
``docs/reference/x1-measurement-checklist.md``. All randomness comes from a generator seeded by the scenario
seed and the vehicle id, and is drawn only inside ``step``.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field

import numpy as np

from .navigation import wrap_pi
from .silt import seabed_type_for
from .physics import KNOT, q_from_axis_angle, q_mul, q_rot

STRINGS = {
    "realigned": "航向估計重新對準（磁場異常）",
    "dvl_lost": "DVL 失去底鎖",
    "dvl_locked": "DVL 底鎖恢復",
}

# Kinematic water density used to convert pressure to depth [datasheet: Blue Robotics MS5837 examples].
WATER_DENSITY = {"fresh": 997.0, "salt": 1029.0}

# Steel tube wall thickness per cylinder kind, metres [assumption: typical offshore tubulars].
STEEL_WALL_M = {"jacket_leg": 0.04, "brace": 0.02, "monopile": 0.06, "pile": 0.02, "mast": 0.01,
                # inspection-site steel fittings (site_dressing.py) [assumption]; solid bars use radius / 2
                # (same mass per metre as a tube of that wall); anodes count only their steel insert core
                "transition_piece": 0.06, "j_tube": 0.015, "boat_landing": 0.012, "anode": 0.004,
                "anode_strap": 0.0175, "shaft": 0.125, "bilge_keel": 0.01}
# Steel per square metre of a box hull or wreck shell, tonnes [assumption: 15 mm plate plus framing].
STEEL_SHELL_T_PER_M2 = {"hull": 0.24, "wreck": 0.24, "rudder": 0.24}
# Geometrics rule of thumb: 1 t of steel gives about 1 nT at 100 ft, cubic in distance [snippet].
STEEL_REFERENCE_M = 30.48

# Seabed material by biome when a scenario does not name one [assumption].
# The silt model's seabed types (silt.SEABED_TYPES) grouped by how they return DVL beams.
DVL_SEABED = {"fluff": "mud", "mud": "mud", "silt": "mud", "sand": "sand", "gravel": "sand", "rock": "rock"}
# Per-beam dropout probability by seabed material [assumption, causes from Nortek and Cerulean docs].
SEABED_DROPOUT = {"sand": 0.0, "rock": 0.0, "mud": 0.12, "pool": 0.10}
# Vegetation footprint radius (m), canopy height per unit scale (m), DVL dropout, echo false return.
VEGETATION = {"kelp": (0.6, 2.3, 0.6, 0.3), "seagrass": (0.4, 0.55, 0.25, 0.1)}


@dataclass
class SensorConfig:
    """Sensor parameters. ``ideal`` turns every imperfection off and restores the pre-layer behaviour."""

    ideal: bool = False
    # Heading
    gyro_drift_deg_min: tuple = (0.1, 0.3)     # [snippet] Water Linked AHRS after per-boot gyro calibration
    gyro_walk_deg_min: float = 0.02            # bias random walk per sqrt(minute) [assumption]
    mag_rate_hz: float = 10.0                  # [assumption]
    mag_noise_deg: float = 0.5                 # [snippet] Xsens MTi 0.5 deg RMS with good calibration
    fusion_tau_s: float = 20.0                 # [snippet] Xsens converges to new local north in 10-30 s
    deviation: bool = True                     # steel deviation of the magnetometer
    earth_horizontal_nt: float = 35000.0       # [assumption] order of magnitude at the low-latitude site
    earth_vertical_nt: float = 25000.0         # [assumption]
    steel_nt_per_tonne: float = 1.0            # at STEEL_REFERENCE_M [snippet] Geometrics
    remanence: float = 0.5                     # permanent / induced magnetisation ratio [assumption]
    near_field_m: float = 1.0                  # dipole distance floor [assumption]
    erratic_deg: float = 8.0                   # extra near-field noise at anomaly ratio 1 [assumption]
    realign_ratio: float = 0.3                 # anomaly |dB_h| / B_h counted as strong [assumption]
    realign_innovation_deg: float = 15.0       # [assumption] EKF yaw reset symptom, BR forum case [forum]
    realign_mean_s: float = 6.0                # mean time to a reset while both thresholds hold [assumption]
    # Depth
    depth_rate_hz: float = 50.0                # [inference] MS5837 conversion time about 16 ms
    depth_noise_m: float = 0.003               # [assumption] 2-5 mm
    depth_quantum_m: float = 0.002             # [datasheet] Bar30 resolution 0.2 mbar
    depth_zero_sigma_m: float = 0.03           # surface zero error [assumption]; FIFISH FAQ: >1 m possible
    water_setting: str | None = None           # "fresh"/"salt"; None = the site's own water
    # Echo sounders (altimeter and forward range)
    echo_rate_hz: float = 5.0                  # [assumption] not on the Ping2 page; bounds server cost
    echo_cone_deg: float = 25.0                # [datasheet] Ping2 beamwidth
    echo_blind_m: float = 0.3                  # [datasheet] Ping2 minimum range
    echo_resolution: float = 0.005             # [datasheet] Ping2 0.5 % of range
    altimeter_max_m: float = 100.0             # as the pre-layer telemetry
    forward_max_m: float = 50.0                # as the pre-layer telemetry
    fish_false_p: float = 0.3                  # [assumption] Ping2 footnote names fish and vegetation
    # DVL
    dvl_min_alt_m: float = 0.1                 # [vendor] Q-DVL 0.1-100 m; listings conflict (5/10/15 cm)
    dvl_max_alt_m: float = 100.0               # [vendor] Q-DVL; A50 datasheet 50 m, >35 m seabed-dependent
    dvl_beam_deg: float = 22.5                 # [datasheet] A50; Q-DVL geometry unpublished
    dvl_rate_hz: tuple = (4.0, 15.0)           # [datasheet] A50, adaptive to altitude
    dvl_scale_error: float = 0.01              # [datasheet] A50 long-term accuracy +-1.01 %
    dvl_noise_mps: tuple = (0.003, 0.001)      # sigma = a + b * altitude [assumption] no sigma published
    dvl_slope_deg: tuple = (45.0, 75.0)        # at (2 m, 10 m) [snippet] Sonardyne Syrinx
    dvl_coast_s: float = 1.0                   # lock kept through brief gaps [assumption]
    dvl_reacquire_pings: int = 3               # [assumption]
    dvl_reacquire_low_m: float = 0.5           # [assumption] Cerulean advises 2 m for its DVL-75
    dvl_range_fade: float = 0.6                # dropout rises above this fraction of max range [assumption]
    aeration_depth_m: float = 0.6              # thruster wash draws air near the surface [assumption]


@dataclass
class SensorFrame:
    """Latest measurements and estimates. Angles in radians, distances in metres, NED."""

    q: np.ndarray
    yaw: float
    depth: float
    vz: float
    vel_world: np.ndarray
    pos: np.ndarray
    altitude: float | None = None
    altitude_blind: bool = False
    range: float | None = None
    range_blind: bool = False
    dvl_status: str = "locked"
    dvl_reason: str | None = None
    dvl_vel: np.ndarray | None = None
    dvl_altitude: float | None = None
    beams: list = field(default_factory=lambda: [None] * 4)

    @property
    def dvl_valid(self) -> bool:
        return self.dvl_status != "lost"


def stable_seed(seed, vehicle_id: str) -> list:
    return [int(seed or 0), 0x5E45, zlib.crc32(str(vehicle_id).encode())]


def raycast_many(world, origins: np.ndarray, directions: np.ndarray, max_range):
    """Sphere-trace many rays at once against terrain and obstacles. Returns (range, hit, normal, index).

    ``max_range`` is one distance or one per ray.
    """
    d = directions / np.linalg.norm(directions, axis=1)[:, None]
    n = len(origins)
    max_range = np.broadcast_to(np.asarray(max_range, float), (n,))
    t = np.zeros(n)
    hit = np.zeros(n, bool)
    done = np.zeros(n, bool)
    for _ in range(128):
        active = np.flatnonzero(~done)
        if not len(active):
            break
        dist, _, _ = world.sdf_many(origins[active] + d[active] * t[active, None])
        close = dist < 0.02
        hit[active[close]] = True
        done[active[close]] = True
        far = active[~close]
        # The step floor grows with range: grazing rays stay cheap at the sonar's 0.5 % resolution.
        t[far] += np.maximum(np.maximum(0.05, 0.03 * t[far]), dist[~close])
        done[far[t[far] >= max_range[far]]] = True
    t = np.minimum(t, max_range)
    _, normal, index = world.sdf_many(origins + d * t[:, None])
    return t, hit, normal, index


def cone_directions(axis: np.ndarray, cone_deg: float, count: int = 4) -> np.ndarray:
    """Axis plus ``count`` rays on the half-power edge of a cone around it."""
    axis = axis / np.linalg.norm(axis)
    helper = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    w = np.cross(axis, u)
    half = math.radians(cone_deg / 2)
    rays = [axis]
    for k in range(count):
        a = 2 * math.pi * k / count
        rays.append(math.cos(half) * axis + math.sin(half) * (math.cos(a) * u + math.sin(a) * w))
    return np.array(rays)


class SteelField:
    """Magnetic anomaly of the scene's steel, as point dipoles derived from obstacle definitions."""

    def __init__(self, obstacles, config: SensorConfig, seed: int):
        rng = np.random.default_rng([int(seed or 0), 0x3A6])
        earth = np.array([config.earth_horizontal_nt, 0.0, config.earth_vertical_nt])
        induced = earth / np.linalg.norm(earth)
        points, masses, moments = [], [], []
        for ob in obstacles:
            pts, mass = steel_points(ob)
            if not len(pts):
                continue
            permanent = rng.normal(size=3)
            permanent /= np.linalg.norm(permanent)
            moment = induced + config.remanence * permanent
            points.append(pts)
            masses.append(mass)
            moments.append(np.tile(moment / np.linalg.norm(moment), (len(pts), 1)))
        self.points = np.concatenate(points) if points else np.zeros((0, 3))
        self.masses = np.concatenate(masses) if masses else np.zeros(0)
        self.moments = np.concatenate(moments) if moments else np.zeros((0, 3))
        self.scale = self.masses * config.steel_nt_per_tonne * STEEL_REFERENCE_M ** 3
        self.config = config

    def anomaly(self, position: np.ndarray) -> np.ndarray:
        """Anomaly field (nT, NED) at ``position``."""
        if not len(self.points):
            return np.zeros(3)
        r = position - self.points
        d = np.maximum(np.linalg.norm(r, axis=1), self.config.near_field_m)
        rhat = r / d[:, None]
        along = np.einsum("ij,ij->i", self.moments, rhat)
        b = (3 * along[:, None] * rhat - self.moments) * (self.scale / d ** 3)[:, None]
        return b.sum(axis=0)

    def deviation(self, position: np.ndarray) -> tuple[float, float]:
        """(deviation rad, anomaly ratio). Compass heading reads true heading minus the deviation."""
        b = self.anomaly(np.asarray(position, float))
        h = self.config.earth_horizontal_nt
        return math.atan2(b[1], h + b[0]), math.hypot(b[0], b[1]) / h


def steel_points(ob) -> tuple[np.ndarray, np.ndarray]:
    """Point masses (tonnes) representing one obstacle's steel; empty for non-steel obstacles."""
    kind = getattr(ob, "kind", "")
    if hasattr(ob, "radius") and kind in STEEL_WALL_M:
        a, b = np.asarray(ob.p0, float), np.asarray(ob.p1, float)
        length = float(np.linalg.norm(b - a))
        n = max(1, int(math.ceil(length)))
        per_m = 2 * math.pi * ob.radius * STEEL_WALL_M[kind] * 7.85
        frac = (np.arange(n) + 0.5) / n
        return a + frac[:, None] * (b - a), np.full(n, per_m * length / n)
    if hasattr(ob, "half") and kind in STEEL_SHELL_T_PER_M2:
        return box_shell_points(ob, STEEL_SHELL_T_PER_M2[kind])
    if hasattr(ob, "F") and kind in STEEL_SHELL_T_PER_M2:
        return field_shell_points(ob, STEEL_SHELL_T_PER_M2[kind])
    if hasattr(ob, "hp") and kind in STEEL_SHELL_T_PER_M2:
        return hull_shell_points(ob, STEEL_SHELL_T_PER_M2[kind])
    return np.zeros((0, 3)), np.zeros(0)


def hull_shell_points(ob, t_per_m2: float, spacing: float = 2.0):
    """Plate cells of a parametric ship hull (world.ShipHull): both sides and the flat bottom."""
    from .world import _half_breadth
    hp = ob.hp
    xs = np.arange(-hp["length"] / 2 + spacing / 2, hp["length"] / 2, spacing)
    zs = np.arange(hp["top"] + spacing / 2, hp["draft"], spacing)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    hb, fwd = _half_breadth(X.ravel(), Z.ravel(), hp)
    ok = (hb > 0) & (X.ravel() <= fwd)
    side = [np.column_stack([X.ravel()[ok], s * hb[ok], Z.ravel()[ok]]) for s in (-1.0, 1.0)]
    hb_bottom, _ = _half_breadth(xs, np.full(len(xs), hp["draft"]), hp)
    bottom = []
    for x, w in zip(xs, hb_bottom):
        for y in np.arange(-w + spacing / 2, w, spacing):
            bottom.append((x, y, hp["draft"]))
    local = np.vstack(side + [np.asarray(bottom, float).reshape(-1, 3)])
    return ob.world_point(local), np.full(len(local), spacing * spacing * t_per_m2)


def box_shell_points(ob, t_per_m2: float, spacing: float = 2.0):
    half = np.asarray(ob.half, float)
    pts, areas = [], []
    for axis in range(3):
        others = [k for k in range(3) if k != axis]
        n0 = max(1, int(math.ceil(2 * half[others[0]] / spacing)))
        n1 = max(1, int(math.ceil(2 * half[others[1]] / spacing)))
        g0 = (np.arange(n0) + 0.5) / n0 * 2 * half[others[0]] - half[others[0]]
        g1 = (np.arange(n1) + 0.5) / n1 * 2 * half[others[1]] - half[others[1]]
        area = 4 * half[others[0]] * half[others[1]] / (n0 * n1)
        for sign in (-1.0, 1.0):
            for x in g0:
                for y in g1:
                    p = np.zeros(3)
                    p[axis] = sign * half[axis]
                    p[others[0]], p[others[1]] = x, y
                    pts.append(p)
                    areas.append(area)
    local = np.array(pts)
    a = math.radians(getattr(ob, "yaw_deg", 0.0))
    rot = np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])
    return local @ rot.T + np.asarray(ob.center, float), np.array(areas) * t_per_m2


def field_shell_points(ob, t_per_m2: float, spacing: float = 2.1):
    """Plate cells of a distance-field structure, subsampled to about ``spacing``."""
    step = max(1, int(round(spacing / ob.h)))
    sub = ob.F[::step, ::step, ::step]
    cells = np.argwhere(sub < 0.5 * step * ob.h)
    local = ob.lo + cells * step * ob.h
    area = (step * ob.h) ** 2
    return ob.world_point(local), np.full(len(local), area * t_per_m2)


def steel_field_for(world, config: SensorConfig) -> SteelField:
    """One steel model per world and obstacle set, shared by every vehicle in a room."""
    key = (len(world.obstacles), id(world.obstacles), int(getattr(world, "world_seed", 0)),
           config.earth_horizontal_nt, config.earth_vertical_nt, config.steel_nt_per_tonne,
           config.remanence, config.near_field_m)
    cached = getattr(world, "_sensor_steel", None)
    if cached is None or cached[0] != key:
        cached = (key, SteelField(world.obstacles, config, key[2]))
        world._sensor_steel = cached
    return cached[1]


class SensorSuite:
    """Per-vehicle sensors and estimators. ``step`` is the only place that advances state or draws noise."""

    def __init__(self, sim, config: SensorConfig | None = None):
        self.config = config or SensorConfig()
        self.reset(sim)

    @property
    def ideal(self) -> bool:
        return self.config.ideal

    # ── setup ─────────────────────────────────────────────────────────────
    def reset(self, sim) -> None:
        cfg = self.config
        s = sim.vehicle.s
        self.rng = np.random.default_rng(stable_seed(sim.scenario.seed, sim.vehicle_id))
        self.faults: dict[str, float] = {}
        self.fault_depth_offset = 0.0
        self.realigned_at: float | None = None
        self._clock = {"mag": 0.0, "depth": 0.0, "echo": 0.0, "dvl": 1.0}   # the first step pings the DVL
        self.time = 0.0
        site = getattr(sim.scenario, "water", "salt")
        setting = cfg.water_setting or site
        self.density_ratio = WATER_DENSITY.get(site, 1029.0) / WATER_DENSITY.get(setting, 1029.0)
        bed = seabed_type_for(sim.world.biome, getattr(sim.scenario, "seabed_type", None))
        self.seabed_type = "pool" if getattr(sim.scenario, "enclosed", False) else DVL_SEABED.get(bed, "sand")
        self._vegetation(sim.world)
        if cfg.ideal:
            self.frame = None
            return
        low, high = cfg.gyro_drift_deg_min
        drift = self.rng.uniform(low, high) * self.rng.choice((-1.0, 1.0))
        self.gyro_bias = math.radians(drift) / 60.0
        self.zero_offset = float(self.rng.normal(0.0, cfg.depth_zero_sigma_m))
        self.dvl_scale = float(self.rng.uniform(-cfg.dvl_scale_error, cfg.dvl_scale_error))
        self.steel = steel_field_for(sim.world, cfg)
        yaw = sim.vehicle.euler[2]
        self._last_yaw = yaw
        self.yaw_est = wrap_pi(yaw - self.magnetic_deviation(s.pos)[0])
        self._dvl_good = 0
        self._dvl_last_valid = 0.0
        self._dvl_low = False
        self.frame = SensorFrame(q=s.q.copy(), yaw=self.yaw_est, depth=self._depth_reading(sim, noise=False),
                                 vz=float(sim.vehicle.world_velocity()[2]), vel_world=np.zeros(3),
                                 pos=s.pos.copy(), dvl_vel=np.zeros(3))
        self.frame.q = self._estimated_q(s.q, yaw)
        self._sample_echo(sim)
        self._ping_dvl(sim, initial=True)
        self._dvl_ping_ok = False
        if self._ping_reason is not None:
            self.frame.dvl_status, self.frame.dvl_reason = "lost", self._ping_reason
            self._dvl_low = self._ping_reason == "too_low"

    def _vegetation(self, world) -> None:
        rows = []
        for entity in getattr(world, "habitat_entities", []):
            if entity.get("kind") not in VEGETATION:
                continue
            radius, height, dropout, false_echo = VEGETATION[entity["kind"]]
            rows.append((entity["pos"][0], entity["pos"][1], radius, height * entity["scale"], dropout, false_echo))
        # Columns: north, east, footprint radius, canopy height, DVL dropout, echo false-return probability.
        self.vegetation = np.array(rows, float).reshape(-1, 6)

    # ── faults (instructor) ───────────────────────────────────────────────
    def set_fault(self, kind: str, strength: float) -> None:
        if self.ideal:
            raise ValueError("sensor faults need the realistic sensor layer")
        self.faults[kind] = float(strength)

    def clear_fault(self, kind: str) -> None:
        self.faults.pop(kind, None)
        if kind == "depth_sensor":
            self.fault_depth_offset = 0.0

    # ── models ────────────────────────────────────────────────────────────
    def magnetic_deviation(self, position) -> tuple[float, float]:
        deviation, ratio = (0.0, 0.0)
        if self.config.deviation:
            deviation, ratio = self.steel.deviation(position)
        compass = self.faults.get("compass", 0.0)
        return deviation + math.radians(60.0) * compass, ratio + compass

    def _estimated_q(self, q_true: np.ndarray, yaw_true: float) -> np.ndarray:
        correction = q_from_axis_angle(np.array([0.0, 0.0, 1.0]), wrap_pi(self.yaw_est - yaw_true))
        return q_mul(correction, q_true)

    def _depth_reading(self, sim, noise: bool = True) -> float:
        cfg = self.config
        value = float(sim.vehicle.s.pos[2]) * self.density_ratio + self.zero_offset + self.fault_depth_offset
        if noise:
            value += float(self.rng.normal(0.0, cfg.depth_noise_m))
        return round(value / cfg.depth_quantum_m) * cfg.depth_quantum_m

    def _due(self, name: str, dt: float, hz: float) -> bool:
        self._clock[name] += dt
        if self._clock[name] + 1e-9 >= 1.0 / hz:
            self._clock[name] = 0.0
            return True
        return False

    # ── per-step update ──────────────────────────────────────────────────
    def step(self, dt: float, sim) -> SensorFrame | None:
        if self.ideal:
            return None
        cfg = self.config
        v, s = sim.vehicle, sim.vehicle.s
        f = self.frame
        self.time += dt
        yaw = v.euler[2]
        walk = math.radians(cfg.gyro_walk_deg_min) / 60.0 * math.sqrt(dt / 60.0)
        self.gyro_bias += float(self.rng.normal(0.0, walk))
        self.yaw_est = wrap_pi(self.yaw_est + wrap_pi(yaw - self._last_yaw) + self.gyro_bias * dt)
        self._last_yaw = yaw
        if self._due("mag", dt, cfg.mag_rate_hz):
            self._fuse_magnetometer(sim, yaw, 1.0 / cfg.mag_rate_hz)
        f.yaw = self.yaw_est
        f.q = self._estimated_q(s.q, yaw)
        if "depth_sensor" in self.faults:
            self.fault_depth_offset += 0.02 * self.faults["depth_sensor"] * dt
        if self._due("depth", dt, cfg.depth_rate_hz):
            f.depth = self._depth_reading(sim)
        f.vz = float(v.world_velocity()[2])     # inertially aided vertical rate [assumption]
        if self._due("echo", dt, cfg.echo_rate_hz):
            self._sample_echo(sim)
        altitude = f.dvl_altitude if f.dvl_altitude is not None else 10.0
        rate = float(np.interp(altitude, (1.0, 50.0), cfg.dvl_rate_hz[::-1]))
        if self._due("dvl", dt, rate):
            self._ping_dvl(sim)
        self._update_lock(sim)
        self._dead_reckon(sim, dt)
        return f

    def _fuse_magnetometer(self, sim, yaw: float, dt_mag: float) -> None:
        cfg = self.config
        deviation, ratio = self.magnetic_deviation(sim.vehicle.s.pos)
        sigma = math.radians(cfg.mag_noise_deg + cfg.erratic_deg * min(1.0, ratio))
        reading = wrap_pi(yaw - deviation + float(self.rng.normal(0.0, sigma)))
        innovation = wrap_pi(reading - self.yaw_est)
        strong = ratio > cfg.realign_ratio and abs(innovation) > math.radians(cfg.realign_innovation_deg)
        if strong and self.rng.random() < dt_mag / cfg.realign_mean_s:
            self.yaw_est = reading
            self.realigned_at = sim.t
            sim._log("sensor", STRINGS["realigned"])
            return
        self.yaw_est = wrap_pi(self.yaw_est + innovation * min(1.0, dt_mag / cfg.fusion_tau_s))

    def _sample_echo(self, sim) -> None:
        cfg = self.config
        s = sim.vehicle.s
        down = q_rot(s.q, np.array([0.0, 0.0, 1.0]))
        fwd = q_rot(s.q, np.array([1.0, 0.0, 0.0]))
        rays = np.concatenate([cone_directions(down, cfg.echo_cone_deg), cone_directions(fwd, cfg.echo_cone_deg)])
        half = len(rays) // 2
        origins = np.concatenate([np.tile(s.pos + down * 0.2, (half, 1)), np.tile(s.pos + fwd * 0.4, (half, 1))])
        # One batched trace for both sounders, each ray cut at its own sounder's maximum range.
        reach = np.repeat([cfg.altimeter_max_m, cfg.forward_max_m], half)
        traced = raycast_many(sim.world, origins, rays, reach)
        down_hits = tuple(x[:half] for x in traced)
        fwd_hits = tuple(x[half:] for x in traced)
        alt, alt_blind = self._cone_range(sim, origins[0], rays[:half], down_hits, cfg.altimeter_max_m, True)
        rng_, rng_blind = self._cone_range(sim, origins[half], rays[half:], fwd_hits, cfg.forward_max_m, False)
        strength = self.faults.get("altimeter", 0.0)
        if strength and self.rng.random() < strength:
            alt = None if self.rng.random() < 0.5 or alt is None else float(self.rng.uniform(cfg.echo_blind_m, alt))
        self.frame.altitude, self.frame.altitude_blind = alt, alt_blind
        self.frame.range, self.frame.range_blind = rng_, rng_blind

    def _cone_range(self, sim, origin, rays, traced, max_range, downward) -> tuple[float | None, bool]:
        """Nearest strong echo in the cone; (None, True) inside the blind zone, (None, False) for no echo."""
        cfg = self.config
        axis = rays[0]
        t, hit, _, index = traced
        hit = hit & (t <= max_range)
        candidates = list(t[hit])
        if downward and len(self.vegetation):
            for k in np.flatnonzero(hit & (index < 0)):
                canopy = self._canopy(origin + rays[k] * t[k])
                if canopy is not None and self.rng.random() < canopy[1]:
                    candidates.append(t[k] - canopy[0] / max(0.2, abs(rays[k][2])))
        half = math.radians(cfg.echo_cone_deg / 2)
        for school in getattr(sim.world, "fish_schools", []):
            to = np.asarray(school["pos"], float) - origin
            dist = float(np.linalg.norm(to))
            if dist < 1e-6 or dist > max_range:
                continue
            angle = math.acos(max(-1.0, min(1.0, float(np.dot(to, axis)) / dist)))
            if angle < half + math.atan2(2.0, dist) and self.rng.random() < cfg.fish_false_p:
                candidates.append(dist - 1.5)
        if not candidates:
            return None, False
        reading = float(min(candidates))
        if reading < cfg.echo_blind_m:
            return None, True
        quantum = max(0.01, cfg.echo_resolution * reading)
        return round(reading / quantum) * quantum, False

    def _canopy(self, point) -> tuple[float, float, float] | None:
        """(height, echo false-return probability, DVL dropout) of vegetation over a seabed point."""
        veg = self.vegetation
        near = np.hypot(veg[:, 0] - point[0], veg[:, 1] - point[1]) < veg[:, 2]
        if not np.any(near):
            return None
        row = veg[near][np.argmax(veg[near][:, 3])]
        return float(row[3]), float(row[5]), float(row[4])

    def _ping_dvl(self, sim, initial: bool = False) -> None:
        cfg = self.config
        v, s = sim.vehicle, sim.vehicle.s
        f = self.frame
        beam = math.radians(cfg.dvl_beam_deg)
        body = np.array([[math.sin(beam) * math.cos(a), math.sin(beam) * math.sin(a), math.cos(beam)]
                         for a in np.radians((45.0, 135.0, 225.0, 315.0))])
        down = q_rot(s.q, np.array([0.0, 0.0, 1.0]))
        dirs = np.array([q_rot(s.q, d) for d in body])
        origin = s.pos + down * 0.2
        reach = cfg.dvl_max_alt_m / math.cos(beam) * 1.05
        t, hit, normal, index = raycast_many(sim.world, np.tile(origin, (4, 1)), dirs, reach)
        load = float(np.mean(np.abs(s.thrust))) / v.p.thruster_max
        depth = float(s.pos[2])
        aeration = min(0.9, 1.5 * load * max(0.0, 1.0 - depth / cfg.aeration_depth_m))
        silt_here = sim.world.silt_at(s.pos)
        reasons, ranges, altitudes = [], [], []
        vegetated = False
        for k in range(4):
            if not hit[k]:
                ranges.append(None)
                reasons.append("too_high")
                continue
            r = float(t[k])
            alt = r * math.cos(beam)
            ranges.append(r)
            altitudes.append(alt)
            slope = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(normal[k], -down))))))
            limit = float(np.interp(alt, (2.0, 10.0), cfg.dvl_slope_deg))
            if slope > limit:
                reasons.append("slope")
                continue
            point = origin + dirs[k] * r
            causes = {"range": min(1.0, max(0.0, (alt / cfg.dvl_max_alt_m - cfg.dvl_range_fade)
                                            / (1.0 - cfg.dvl_range_fade))),
                      "aeration": aeration, "silt": min(0.95, max(silt_here, sim.world.silt_at(point)))}
            if index[k] < 0:
                causes[self.seabed_type] = SEABED_DROPOUT.get(self.seabed_type, 0.0)
                canopy = self._canopy(point) if len(self.vegetation) else None
                if canopy is not None:
                    causes["vegetation"] = canopy[2]
                    vegetated = True
            keep = 1.0
            for p in causes.values():
                keep *= 1.0 - p
            if initial or self.rng.random() < keep:
                reasons.append(None)
            else:
                reasons.append(max(causes, key=causes.get))
        f.beams = [None if r is None else round(r, 2) for r in ranges]
        f.dvl_altitude = float(np.mean(altitudes)) if altitudes else None
        valid = sum(r is None for r in reasons)
        reason = None
        if "dvl" in self.faults:
            reason = "fault"
        elif f.dvl_altitude is None or f.dvl_altitude > cfg.dvl_max_alt_m:
            reason = "too_high"
        elif f.dvl_altitude < cfg.dvl_min_alt_m:
            reason = "too_low"
        elif valid < 3:
            reason = max(set(r for r in reasons if r), key=reasons.count)
        self._ping_reason = reason
        if reason is not None:
            return
        alt = f.dvl_altitude
        sigma = cfg.dvl_noise_mps[0] + cfg.dvl_noise_mps[1] * alt
        sigma *= 3.0 if self.seabed_type == "pool" else 1.0
        sigma += 0.05 * aeration + (0.03 * load if vegetated else 0.0)
        noise = self.rng.normal(0.0, sigma, 3) if not initial else np.zeros(3)
        f.dvl_vel = s.vel * (1.0 + self.dvl_scale) + noise
        self._dvl_last_valid = self.time
        self._dvl_ping_ok = True

    def _update_lock(self, sim) -> None:
        f = self.frame
        reason = getattr(self, "_ping_reason", None)
        fresh = getattr(self, "_dvl_ping_ok", False)
        self._dvl_ping_ok = False
        previous = f.dvl_status
        if "dvl" in self.faults:
            f.dvl_status, f.dvl_reason = "lost", "fault"
        elif f.dvl_status == "lost":
            if fresh:
                low_ok = not self._dvl_low or (f.dvl_altitude or 0.0) >= self.config.dvl_reacquire_low_m
                self._dvl_good = self._dvl_good + 1 if low_ok else 0
                if self._dvl_good >= self.config.dvl_reacquire_pings:
                    f.dvl_status, f.dvl_reason, self._dvl_low = "locked", None, False
            elif reason is not None:
                self._dvl_good = 0
                f.dvl_reason = reason
        elif fresh:
            f.dvl_status, f.dvl_reason = "locked", None
        elif reason is not None or self.time - self._dvl_last_valid > self.config.dvl_coast_s:
            # Leaving the altitude window ends the lock at once; coasting only bridges beam dropouts.
            window = reason in ("too_low", "too_high")
            if window or self.time - self._dvl_last_valid > self.config.dvl_coast_s:
                f.dvl_status, f.dvl_reason = "lost", reason
                self._dvl_low = reason == "too_low"
                self._dvl_good = 0
            else:
                f.dvl_status, f.dvl_reason = "coasting", reason
        if previous != f.dvl_status and "lost" in (previous, f.dvl_status):
            sim._log("sensor", STRINGS["dvl_lost" if f.dvl_status == "lost" else "dvl_locked"])

    def _dead_reckon(self, sim, dt: float) -> None:
        f = self.frame
        s = sim.vehicle.s
        if f.dvl_status == "lost":
            f.vel_world = np.zeros(3)
        else:
            f.vel_world = q_rot(f.q, f.dvl_vel)
            f.pos[:2] += f.vel_world[:2] * dt
        if s.pos[2] < 0.3:
            f.pos[:2] = s.pos[:2]                 # GPS fix at the surface resets dead reckoning [assumption]
        f.pos[2] = f.depth

    # ── consumers ────────────────────────────────────────────────────────
    def heading(self, sim) -> float:
        """Heading the vehicle believes it has (rad)."""
        return sim.vehicle.euler[2] if self.ideal else self.frame.yaw

    def attitude(self, sim) -> tuple[float, float, float]:
        roll, pitch, yaw = sim.vehicle.euler
        return (roll, pitch, yaw) if self.ideal else (roll, pitch, self.frame.yaw)

    def depth(self, sim) -> float:
        return sim.depth if self.ideal else self.frame.depth

    def quaternion(self, sim) -> np.ndarray:
        return sim.vehicle.s.q if self.ideal else self.frame.q

    def position(self, sim) -> np.ndarray:
        return sim.vehicle.s.pos if self.ideal else self.frame.pos

    def latlng(self, sim) -> tuple[float, float]:
        p = self.position(sim)
        return sim.geo.to_geo(p[0], p[1])

    def sdk_ranges(self, sim) -> tuple[float, float]:
        """(forward distance, altitude) for ``get_rov_status``; no echo reads the maximum range."""
        if self.ideal:
            s = sim.vehicle.s
            fwd = q_rot(s.q, np.array([1.0, 0, 0]))
            down = q_rot(s.q, np.array([0, 0, 1.0]))
            dist = sim.world.raycast(s.pos + fwd * 0.4, fwd, 50.0)
            alt = sim.world.raycast(s.pos + down * 0.2, down, 100.0)
            return dist, alt
        return self._echo_value(self.frame.range, self.frame.range_blind, self.config.forward_max_m), \
            self._echo_value(self.frame.altitude, self.frame.altitude_blind, self.config.altimeter_max_m)

    def _echo_value(self, value, blind, max_range) -> float:
        if value is not None:
            return value
        return self.config.echo_blind_m if blind else max_range

    def nav_altitude(self, sim) -> float:
        """Altitude for ``get_rov_data``: DVL when it has bottom, else the altimeter."""
        if self.ideal:
            s = sim.vehicle.s
            return sim.world.raycast(s.pos, q_rot(s.q, np.array([0, 0, 1.0])), 100.0)
        f = self.frame
        if f.dvl_status != "lost" and f.dvl_altitude is not None:
            return f.dvl_altitude
        return self._echo_value(f.altitude, f.altitude_blind, self.config.altimeter_max_m)

    def dvl_body_velocity(self, sim) -> np.ndarray:
        """Body-frame ground velocity the DVL reports; zeros while bottom lock is lost."""
        if self.ideal:
            return sim.vehicle.s.vel
        return np.zeros(3) if self.frame.dvl_status == "lost" else self.frame.dvl_vel

    def sdk_dvl_extras(self, sim) -> dict:
        """Optional ``get_rov_data`` DVL fields of the realistic layer: lock state and per-beam slant ranges."""
        f = self.frame
        locked = f.dvl_status != "lost"
        return {"velocity_valid": locked, "lock": f.dvl_status, "position_valid": sim.nav.dr_initialized and locked,
                "beams": {f"d{i + 1}": 0.0 if r is None else r for i, r in enumerate(f.beams)}}

    def world_velocity(self, sim) -> np.ndarray:
        return sim.vehicle.world_velocity() if self.ideal else self.frame.vel_world

    def dvl_online(self, sim) -> bool:
        return True if self.ideal else self.frame.dvl_status != "lost"

    def state(self, sim) -> dict:
        """Optional ``state.sensors`` object: what the pilot's instruments show."""
        if self.ideal:
            roll, pitch, yaw = sim.vehicle.euler
            dist, alt = self.sdk_ranges(sim)
            wv = sim.vehicle.world_velocity()
            altitude = sim.vehicle.seabed_depth - float(sim.vehicle.s.pos[2])
            locked = 0.1 <= altitude <= 100.0
            return {"ideal": True, "heading": round(math.degrees(yaw) % 360, 1) % 360, "depth": round(sim.depth, 2),
                    "altitude": round(alt, 2) if alt < 100.0 else None,
                    "range": round(dist, 2) if dist < 50.0 else None,
                    "dvl": {"status": "locked" if locked else "lost", "reason": None if locked else "window",
                            "altitude": round(altitude, 2),
                            "ground_speed_kn": round(math.hypot(wv[0], wv[1]) / KNOT, 2) if locked else None},
                    "pos_est": [round(float(x), 3) for x in sim.vehicle.s.pos], "realigned_t": None, "faults": []}
        f = self.frame
        lost = f.dvl_status == "lost"
        return {"ideal": False, "heading": round(math.degrees(f.yaw) % 360, 1) % 360, "depth": round(f.depth, 2),
                "altitude": None if f.altitude is None else round(f.altitude, 2), "altitude_blind": f.altitude_blind,
                "range": None if f.range is None else round(f.range, 2), "range_blind": f.range_blind,
                "dvl": {"status": f.dvl_status, "reason": f.dvl_reason,
                        "altitude": None if f.dvl_altitude is None else round(f.dvl_altitude, 2),
                        "ground_speed_kn": None if lost else round(math.hypot(*f.vel_world[:2]) / KNOT, 2)},
                "pos_est": [round(float(x), 3) for x in f.pos],
                "realigned_t": None if self.realigned_at is None else round(self.realigned_at, 2),
                "faults": sorted(self.faults)}
