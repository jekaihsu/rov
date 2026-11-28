"""Ocean flow building blocks shared by ``world.CurrentProfile``.

Every number marked "assumed" is a provisional simulator value from
``research_notes/洋流與波浪對ROV作業/`` and must be replaced by measurements when they exist.

Pieces
    TurbulenceField  smooth anisotropic frozen turbulence: random Fourier modes (Matern-3/2
                     spectrum) advected with the depth-averaged mean current (Taylor hypothesis)
                     plus a slow eddy evolution. The state is integrated once per tick, so the
                     field and its time derivative are bounded and independent of the step size.
    Tide             optional M2/S2 tidal modulation of the layer profile, rectilinear or rotary.
    bed_factor       log-law velocity reduction near the local seabed (biome roughness z0).
    StructureFlow    analytic flow around cylinders (doublet, Gaussian wake, Strouhal shedding)
                     and lee shelter / blocking around boxes, wreck meshes and walls.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields
from typing import ClassVar

import numpy as np

from .physics import G, KNOT
from ._flow_accel import mean_profile as _compiled_mean
from ._flow_accel import turbulence as _compiled_turbulence
from ._flow_accel import pen_flow, wave_velocity
from ._flow_accel import box_flow as _compiled_box
from ._flow_accel import cylinders as _compiled_cylinders

M2_PERIOD_S = 12.4206012 * 3600.0    # principal lunar semidiurnal constituent
S2_PERIOD_S = 12.0 * 3600.0          # principal solar semidiurnal constituent
TIDE_STARTS = ("peak_flood", "slack_before_ebb", "peak_ebb", "slack_before_flood")
KAPPA = 0.4                          # von Karman constant
# Soulsby (1990) roughness lengths via HR Wallingford SR 360, in metres. "rock" is an assumption
# (field values range up to ~10 cm on rough rocky beds).
BED_ROUGHNESS_M = {"mud": 0.0002, "sand": 0.0004, "rippled_sand": 0.006, "gravel": 0.003, "rock": 0.03}
# Seabed type assumed for each habitat biome (assumption, not a survey).
BIOME_BED = {"harbor": "mud", "seagrass": "rippled_sand", "reef": "rock", "temperate": "rippled_sand"}
DEFAULT_Z0 = BED_ROUGHNESS_M["rippled_sand"]
# Roughness length per site seabed type (silt.SEABED_TYPES, the same type the silt model and the viewer's seabed
# use), metres. Assumptions after Soulsby (1990): fluff and mud 0.2 mm, silt 1 mm, sand taken as rippled 6 mm
# (the previous default for every non-harbour site), gravel 10 mm, rock 30 mm.
SEABED_Z0 = {"fluff": 0.0002, "mud": 0.0002, "silt": 0.001, "sand": 0.006, "gravel": 0.01, "rock": 0.03}
STROUHAL = 0.2                       # high-Re circular cylinder (assumed constant)
# Fluid acceleration fed to the inertia terms is clipped to this magnitude (m/s^2). Natural
# currents and gusts stay far below it; it only guards instant host overrides.
MAX_FLUID_ACCEL = 3.0
FLUID_ACCEL_TAU = 0.05               # s, low-pass on the finite-difference flow acceleration

# streamwise : cross-stream : vertical turbulence ratios (Islay 1 : 0.75 : 0.55, open channel 0.71/0.55)
COMPONENT_RATIOS = np.array([1.0, 0.7, 0.5])


class FlowAccelerometer:
    """Filtered, bounded finite-difference acceleration of sampled flow velocities (per point).

    The turbulence and structure fields are smooth, so the difference quotient converges as dt
    shrinks; the low-pass and the clip only remove artefacts of instant external overrides.
    """

    def __init__(self):
        self.previous = None
        self.value = None

    def reset(self) -> None:
        """Forget the history (the sampled points jumped); the next update returns zero."""
        self.previous = None
        self.value = None

    def update(self, velocities: np.ndarray, dt: float) -> np.ndarray:
        v = np.array(velocities, float)
        if self.previous is None or self.previous.shape != v.shape or dt <= 0:
            self.previous, self.value = v, np.zeros_like(v)
            return self.value
        raw = (v - self.previous) / dt
        self.value = self.value + (raw - self.value) * min(1.0, dt / FLUID_ACCEL_TAU)
        norm = np.linalg.norm(self.value, axis=-1, keepdims=True)
        self.value = self.value * np.minimum(1.0, MAX_FLUID_ACCEL / np.maximum(norm, 1e-12))
        self.previous = v
        return self.value


def smoothstep(x):
    """C1 ramp 0..1 for x in 0..1 (clamped)."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def cosine_ramp(x: float) -> float:
    """Raised-cosine ramp 0..1: zero slope at both ends, so injected changes have bounded acceleration."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def rotate_xy(v: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate horizontal NED vectors (last axis) by a compass angle (clockwise seen from above)."""
    if not degrees:
        return v
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    out = np.array(v, float, copy=True)
    out[..., 0] = c * v[..., 0] - s * v[..., 1]
    out[..., 1] = s * v[..., 0] + c * v[..., 1]
    return out


# ── near-bed profile ─────────────────────────────────────────────────────────
def bed_reference_height(seabed: float) -> float:
    """Height above the bed at which the layer profile's bottom value applies (assumed)."""
    return float(min(3.0, max(1.0, 0.1 * seabed)))


def bed_factor(height, z0: float, h_ref: float):
    """Log-law ratio u(h)/u(h_ref) = ln(h/z0)/ln(h_ref/z0), 1 above h_ref and 0 at/below the bed."""
    z0 = max(float(z0), 1e-6)
    h = np.asarray(height, float)
    ratio = np.log(np.maximum(h, z0) / z0) / math.log(max(h_ref, 2 * z0) / z0)
    return np.where(h >= h_ref, 1.0, np.clip(ratio, 0.0, 1.0))


def turbulence_length(seabed: float) -> float:
    """Integral length scale (m): about half the water depth, 2..15 m (Islay 11-14 m; assumed)."""
    return float(min(15.0, max(2.0, 0.5 * seabed)))


# ── tide ─────────────────────────────────────────────────────────────────────
@dataclass
class Tide:
    """Optional tidal modulation. Layer speeds/directions of the profile are the flood flow at factor 1.

    rectilinear  speed factor m2*cos(w2 t + p2) + s2*cos(ws t + ps) + residual; negative = ebb, which
                 sets toward ``ebb_dir`` (default: reversed) scaled by ``ebb_ratio``.
    rotary       the same factor along the flood axis plus ``minor_ratio`` times the quadrature
                 (sin) terms across it, turning clockwise; never fully slack.
    ``start`` picks the time of tide at t = 0: one of TIDE_STARTS or hours after peak flood.
    ``time_scale`` > 1 runs the tide faster for classroom demonstrations (1 = real time).
    """
    kind: str = "rectilinear"
    m2: float = 1.0
    m2_phase_deg: float = 0.0
    s2: float = 0.0
    s2_phase_deg: float = 0.0
    flood_dir: float | None = None
    ebb_dir: float | None = None
    ebb_ratio: float = 1.0
    minor_ratio: float = 0.0
    residual: float = 0.0
    time_scale: float = 1.0
    start: object = "peak_flood"
    period_s: float | None = None  # override the principal constituent only

    @classmethod
    def from_dict(cls, data: dict) -> "Tide":
        """Validated construction from a protocol/scenario dict; unknown keys are rejected."""
        names = {f.name for f in fields(cls)}
        unknown = set(data) - names
        if unknown:
            raise ValueError(f"unknown tide fields {sorted(unknown)}")
        tide = cls(**data)
        tide.validate()
        return tide

    def validate(self) -> None:
        if self.kind not in ("rectilinear", "rotary"):
            raise ValueError("tide kind must be rectilinear or rotary")
        for name in ("m2", "m2_phase_deg", "s2", "s2_phase_deg", "ebb_ratio", "minor_ratio",
                     "residual", "time_scale"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"tide {name} must be finite")
        if self.period_s is not None and (type(self.period_s) not in (int, float)
                                          or not math.isfinite(self.period_s) or not 1 <= self.period_s <= 604800):
            raise ValueError("tide period_s must be 1 second to 7 days")
        for name in ("flood_dir", "ebb_dir"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f"tide {name} must be finite or null")
        if not 0 <= self.m2 <= 2 or not 0 <= self.s2 <= 1 or not 0 <= self.ebb_ratio <= 2:
            raise ValueError("tide amplitudes out of range")
        if not 0 <= self.minor_ratio <= 1 or not -1 <= self.residual <= 1 or not 0 < self.time_scale <= 720:
            raise ValueError("tide ratios out of range")
        self.start_offset_s()

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "period_s" or v is not None}

    def _terms(self, tau):
        w2, ws = 2 * math.pi / (self.period_s or M2_PERIOD_S), 2 * math.pi / S2_PERIOD_S
        a2 = w2 * tau + math.radians(self.m2_phase_deg)
        as_ = ws * tau + math.radians(self.s2_phase_deg)
        major = self.m2 * np.cos(a2) + self.s2 * np.cos(as_) + self.residual
        minor = self.m2 * np.sin(a2) + self.s2 * np.sin(as_)
        return major, minor

    def start_offset_s(self) -> float:
        """Tide time (s) at simulation t = 0 for the requested ``start``."""
        start = self.start
        if isinstance(start, (int, float)) and not isinstance(start, bool):
            if not math.isfinite(start):
                raise ValueError("tide start must be finite")
            return self._peak_tau() + float(start) * 3600.0
        if start not in TIDE_STARTS:
            raise ValueError(f"tide start must be hours or one of {TIDE_STARTS}")
        tau = np.linspace(0.0, self.period_s or M2_PERIOD_S, 4097)
        major, _ = self._terms(tau)
        if start == "peak_flood":
            return float(tau[int(np.argmax(major))])
        if start == "peak_ebb":
            return float(tau[int(np.argmin(major))])
        rising = start == "slack_before_flood"
        sign = np.sign(major)
        idx = np.flatnonzero((sign[:-1] < 0) & (sign[1:] >= 0)) if rising else \
            np.flatnonzero((sign[:-1] > 0) & (sign[1:] <= 0))
        if len(idx) == 0:
            return float(tau[int(np.argmin(np.abs(major)))])
        i = int(idx[0])
        frac = major[i] / (major[i] - major[i + 1])
        return float(tau[i] + frac * (tau[i + 1] - tau[i]))

    def _peak_tau(self) -> float:
        tau = np.linspace(0.0, self.period_s or M2_PERIOD_S, 4097)
        return float(tau[int(np.argmax(self._terms(tau)[0]))])

    def transform(self, layers: np.ndarray, surface_dir: float, tau: float) -> np.ndarray:
        """Apply the tide at tide time ``tau`` to the (3, 3) flood layer vectors."""
        major, minor = self._terms(tau)
        major, minor = float(major), float(minor)
        if self.flood_dir is not None:
            layers = rotate_xy(layers, float(self.flood_dir) - surface_dir)
        if self.kind == "rotary":
            across = rotate_xy(layers, 90.0)
            return layers * major + across * self.minor_ratio * minor
        if major >= 0:
            return layers * major
        flood = surface_dir if self.flood_dir is None else float(self.flood_dir)
        ebb_offset = 180.0 if self.ebb_dir is None else float(self.ebb_dir) - flood
        return rotate_xy(layers, ebb_offset) * (-major) * self.ebb_ratio

    def info(self, tau: float) -> dict:
        """Compact stage summary for viewers: factor, flood/ebb and minutes to the next slack."""
        major, _ = self._terms(tau)
        horizon = self.period_s or 7 * 3600.0
        ahead = tau + np.linspace(0.0, horizon, 421)
        future, _ = self._terms(ahead)
        sign = np.sign(future)
        change = np.flatnonzero(sign[1:] != sign[:-1])
        minutes = None if self.kind == "rotary" or len(change) == 0 else round(float(change[0]) * horizon / 420 / 60, 0)
        stage = "slack" if abs(float(major)) < 0.02 else "flood" if float(major) > 0 else "ebb"
        return {"factor": round(float(major), 3), "stage": stage, "minutes_to_slack": minutes}


@dataclass(frozen=True)
class AiryWave:
    """Regular small-amplitude deep-water wave. Direction is propagation toward, clockwise from north."""

    height_m: float
    period_s: float
    direction_deg: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.height_m, self.period_s, self.direction_deg)):
            raise ValueError("wave parameters must be finite")
        if self.height_m < 0 or self.period_s <= 0:
            raise ValueError("wave requires nonnegative height and positive period")

    def velocity(self, points, time_s):
        omega = math.tau / self.period_s
        k = omega ** 2 / G
        bearing = math.radians(self.direction_deg)
        north, east = math.cos(bearing), math.sin(bearing)
        return wave_velocity(points, omega, k, north, east, 0.5 * self.height_m * omega, time_s)


# ── turbulence ───────────────────────────────────────────────────────────────
class TurbulenceField:
    """Frozen, smoothly evolving unit-variance turbulence with three independent components.

    Each component is ``sqrt(2/N) * sum cos(k_j . (x - D) / ell + psi_j + theta_j)``. Wave
    vectors follow a 3-D Student-t (3 dof) law, whose characteristic function is the Matern-3/2
    correlation: once differentiable, so the field and its time derivative stay bounded.
    ``D`` is the integrated advection displacement and ``theta`` the integrated eddy-evolution
    phase; both advance in ``advance`` with the midpoint rule, so results do not depend on dt.
    """

    MODES = 32
    K_MAX = 5.0                      # truncate the heavy tail of |k| * ell
    # ell = SCALE * L gives correlation 0.36 at the integral length L and integral scale ~0.92 L.
    SCALE = 0.8

    def __init__(self, seed: int = 0):
        rng = np.random.default_rng(int(seed) + 0x5EED)
        z = rng.standard_normal((3, self.MODES, 3))
        chi = rng.chisquare(3, (3, self.MODES))
        k = z * np.sqrt(3.0 / chi)[..., None]
        mag = np.linalg.norm(k, axis=2, keepdims=True)
        self.k = k * np.minimum(1.0, self.K_MAX / np.maximum(mag, 1e-9))
        self.psi = rng.uniform(0.0, 2 * math.pi, (3, self.MODES))
        self.evolve = rng.standard_normal((3, self.MODES))
        self.amp = math.sqrt(2.0 / self.MODES)
        self.displacement = np.zeros(3)
        self.theta = np.zeros((3, self.MODES))
        self.phase = self.psi.copy()
        self._k_all = self.k.reshape(3 * self.MODES, 3).T.copy()

    def advance(self, dt: float, advect: np.ndarray, ell: float, sigma: float) -> None:
        """Integrate advection displacement and eddy evolution over ``dt`` (midpoint velocities)."""
        self.displacement = self.displacement + np.array([advect[0], advect[1], 0.0]) * dt
        rate = max(sigma, 0.02) / ell
        self.theta = self.theta + self.evolve * rate * dt
        self.phase = self.psi + self.theta

    def unit(self, points: np.ndarray, ell: float) -> np.ndarray:
        """(N, 3) unit-variance fluctuations (u, v, w) at NED points, before frame rotation."""
        X = (np.asarray(points, float) - self.displacement) * (1.0 / ell)
        arg = X @ self._k_all + self.phase.ravel()
        return self.amp * np.cos(arg).reshape(len(X), 3, self.MODES).sum(axis=2)

    def unit_rate(self, points: np.ndarray, ell: float, advect: np.ndarray, sigma: float) -> np.ndarray:
        """Analytic time derivative of ``unit`` at fixed points (1/s), for bound checks and tests."""
        X = (np.asarray(points, float) - self.displacement) / ell
        adv = np.array([advect[0], advect[1], 0.0]) / ell
        rate = max(sigma, 0.02) / ell
        out = np.empty((len(X), 3))
        for c in range(3):
            arg = X @ self.k[c].T + (self.psi[c] + self.theta[c])
            omega = -(self.k[c] @ adv) + self.evolve[c] * rate
            out[:, c] = -self.amp * (np.sin(arg) * omega).sum(axis=1)
        return out

    def state(self) -> dict:
        return {"displacement": self.displacement.copy(), "theta": self.theta.copy()}


def turbulence_vectors(unit: np.ndarray, mean: np.ndarray, intensity: float, depths: np.ndarray,
                       fallback_dir: np.ndarray) -> np.ndarray:
    """Scale unit fluctuations into the local mean-flow frame with ratios (1, 0.7, 0.5).

    sigma_u = intensity * |mean|. Vertical fluctuations taper to zero within 2 m of the surface.
    """
    mx, my = mean[:, 0], mean[:, 1]
    speed_h = np.sqrt(mx * mx + my * my)
    sigma = intensity * np.sqrt(speed_h * speed_h + mean[:, 2] * mean[:, 2])
    calm = speed_h < 1e-6
    inv = 1.0 / np.where(calm, 1.0, speed_h)
    ex = np.where(calm, fallback_dir[0], mx * inv)
    ey = np.where(calm, fallback_dir[1], my * inv)
    u = unit[:, 0] * (COMPONENT_RATIOS[0] * sigma)
    v = unit[:, 1] * (COMPONENT_RATIOS[1] * sigma)
    w = unit[:, 2] * (COMPONENT_RATIOS[2] * sigma) * np.clip(np.asarray(depths, float) * 0.5, 0.0, 1.0)
    return np.stack([ex * u - ey * v, ey * u + ex * v, w], axis=1)


@dataclass
class CurrentProfile:
    """Depth-varying current. Speeds in knots, directions in degrees the water flows toward.

    The ambient flow combines a three-layer mean profile, smooth anisotropic turbulence
    and an optional surface wave. Call ``step_gust`` exactly once per
    simulation tick: it advances the turbulence (advected with the depth-averaged current). All
    sampling methods read that state, so every consumer in a tick sees the same flow.

    Compatibility: ``sample``/``sample_many(positions, seabed, t)`` keep their signatures; ``t``
    is accepted but the field is evaluated at the profile clock that ``step_gust`` advances.
    """
    surface_kn: float = 0.0
    surface_dir: float = 90.0
    mid_kn: float = 0.0
    mid_dir: float = 90.0
    bottom_kn: float = 0.0
    bottom_dir: float = 90.0
    turbulence: float = 0.10          # streamwise turbulence intensity sigma_u / U (assumed default)
    gust_tau: float = 6.0             # legacy field, no longer used (integral time is now ~L/U)
    length_scale: float | None = None  # turbulence integral length (m); None = from water depth
    tide: Tide | None = None          # optional tidal modulation; None = steady profile (legacy)
    z0: float | None = None           # bed roughness length (m); None = from the biome / rippled sand
    seed: int = 0
    _clock: float = field(default=0.0, repr=False)
    _turb: object = field(default=None, repr=False)
    _seabed_hint: float = field(default=30.0, repr=False)
    _layer_cache: object = field(default=None, repr=False)
    use_compiled: ClassVar[bool] = True   # numba turbulence loop when available (NumPy is the reference)
    _inj: dict | None = field(default=None, repr=False)
    _tide_cache: object = field(default=None, repr=False)
    _travel: float = field(default=0.0, repr=False)

    wave: AiryWave | None = None
    bypass_flow: bool = False

    # ── layers and mean profile ───────────────────────────────────────────
    def layer(self, which: str) -> np.ndarray:
        kn, d = {"surface": (self.surface_kn, self.surface_dir), "mid": (self.mid_kn, self.mid_dir),
                 "bottom": (self.bottom_kn, self.bottom_dir)}[which]
        a = math.radians(d)
        return np.array([math.cos(a), math.sin(a), 0.0]) * kn * KNOT

    def _base_layers(self) -> np.ndarray:
        return np.array([self.layer("surface"), self.layer("mid"), self.layer("bottom")])

    def _layers(self) -> np.ndarray:
        """(3, 3) layer vectors (surface, mid, bottom) in effect now (cached per input values)."""
        injection = self.injection()
        tau = self.tide_time()
        key = (self.surface_kn, self.surface_dir, self.mid_kn, self.mid_dir, self.bottom_kn, self.bottom_dir,
               injection, id(self.tide), tau)
        if self._layer_cache is None or self._layer_cache[0] != key:
            scale, rotate, template = injection
            layers = rotate_xy(self._base_layers(), rotate) * scale
            if template:
                layers = layers + rotate_xy(self._template_layers(), rotate) * template
            if tau is not None:
                layers = self.tide.transform(layers, self.surface_dir + rotate, tau)
            average = (layers[0] + 2 * layers[1] + layers[2]) / 4
            self._layer_cache = (key, layers, average, float(np.linalg.norm(average)))
        return self._layer_cache[1]

    # ── tide ──────────────────────────────────────────────────────────────
    def tide_time(self) -> float | None:
        """Tide time (s since an arbitrary M2 origin) at the profile clock; None without a tide."""
        if self.tide is None:
            return None
        cache = self._tide_cache
        if cache is None or cache[0] is not self.tide or cache[1] != self.tide.start:
            cache = (self.tide, self.tide.start, self.tide.start_offset_s())
            self._tide_cache = cache
        return cache[2] + self._clock * self.tide.time_scale

    def set_tide_start(self, start) -> None:
        """Choose the time of tide at the current clock (slack, peak or hours after peak flood)."""
        if self.tide is None:
            raise ValueError("this scenario has no tide")
        previous = self.tide.start
        self.tide.start = start
        try:
            offset = self.tide.start_offset_s()
        except ValueError:
            self.tide.start = previous
            raise
        self._tide_cache = (self.tide, start, offset - self._clock * self.tide.time_scale)

    def tide_info(self) -> dict | None:
        """{factor, stage flood|ebb, minutes_to_slack} or None without a tide."""
        tau = self.tide_time()
        return None if tau is None else self.tide.info(tau)

    # ── instructor injection ──────────────────────────────────────────────
    def _template_layers(self) -> np.ndarray:
        """Unit-surface-speed profile shape used when injecting into still water (assumed shape)."""
        a = math.radians(self.surface_dir)
        unit = np.array([math.cos(a), math.sin(a), 0.0]) * KNOT
        return np.array([unit, unit * 0.8, unit * 0.4])

    def injection(self) -> tuple[float, float, float]:
        """(profile scale, rotation deg, still-water template knots) in effect at the profile clock."""
        inj = self._inj
        if inj is None:
            return (1.0, 0.0, 0.0)
        k = cosine_ramp((self._clock - inj["start"]) / inj["ramp"])
        return tuple(float(a + (b - a) * k) for a, b in zip(inj["from"], inj["to"]))

    def inject(self, surface_kn: float, ramp_s: float = 60.0, rotate_deg: float = 0.0) -> None:
        """Ramp the profile to a surface speed of ``surface_kn`` while keeping its shape.

        The layers are multiplied, not overwritten (boundary layer and shear survive); a raised-cosine
        ramp over ``ramp_s`` seconds avoids unphysical jumps; ``rotate_deg`` turns every layer like a
        turning tide. Still water (surface < 0.05 kn) ramps in an assumed 1 : 0.8 : 0.4 profile.
        """
        start = self.injection()
        if self.surface_kn >= 0.05:
            target = (float(surface_kn) / self.surface_kn, float(rotate_deg), 0.0)
        else:
            target = (1.0, float(rotate_deg), float(surface_kn))
        self._inj = {"from": start, "to": target, "start": self._clock, "ramp": max(float(ramp_s), 1e-3)}

    def release(self, ramp_s: float = 60.0) -> None:
        """Ramp back to the configured profile."""
        self._inj = {"from": self.injection(), "to": (1.0, 0.0, 0.0), "start": self._clock,
                     "ramp": max(float(ramp_s), 1e-3)}

    def target_surface_knots(self) -> float:
        """Surface speed (knots) the current injection ramp is heading for."""
        scale, _, template = self._inj["to"] if self._inj else (1.0, 0.0, 0.0)
        return scale * self.surface_kn + template

    def surface_knots(self) -> float:
        """Effective surface-layer speed now (knots), including injections."""
        return float(np.linalg.norm(self._layers()[0])) / KNOT

    def mean_many(self, depths, seabed: float, heights=None, z0: float | None = None) -> np.ndarray:
        """Mean (turbulence-free) current at depths below the surface, NED m/s, shape (N, 3).

        Three-layer interpolation over the nominal depth, then a log-law bed layer: the bottom
        layer value applies at ``bed_reference_height`` (1-3 m) above the bed and the speed falls
        as ln(h/z0) below it. ``heights`` are heights above the local seabed (default: nominal).
        """
        layers = self._layers()
        z = np.asarray(depths, float)
        h = seabed - z if heights is None else np.asarray(heights, float)
        if h.shape != z.shape:
            h = np.broadcast_to(h, z.shape)
        roughness = z0 if z0 is not None else self.z0 if self.z0 is not None else DEFAULT_Z0
        # Retain the original interpolation order for existing scenario/replay trajectories.
        enhanced = self.wave is not None or self.bypass_flow
        if enhanced and self.use_compiled and _compiled_mean is not None and seabed > 0:
            return _compiled_mean(z, h, layers, seabed, roughness, bed_reference_height(seabed))
        knots = (0.0, seabed / 2, seabed)
        v = np.empty((len(z), 3))
        for k in range(3):
            v[:, k] = np.interp(z, knots, layers[:, k])
        v *= bed_factor(h, roughness, bed_reference_height(seabed))[:, None]
        return v

    def mean_at(self, depth: float, seabed: float) -> np.ndarray:
        return self.mean_many([depth], seabed)[0]

    def depth_average(self, seabed: float | None = None) -> np.ndarray:
        """Depth-averaged mean current (advects the turbulence)."""
        self._layers()
        return self._layer_cache[2].copy()

    # ── turbulence ────────────────────────────────────────────────────────
    def reseed(self, seed: int) -> None:
        """Choose the turbulence realisation (scenario seed); resets the turbulence state."""
        self.seed = int(seed)
        self._turb = None

    def _field(self) -> TurbulenceField:
        if self._turb is None:
            self._turb = TurbulenceField(self.seed)
        return self._turb

    def turbulence_scales(self, seabed: float | None = None) -> tuple[float, float]:
        """(integral length L in m, model length ell in m) for this water depth."""
        seabed = self._seabed_hint if seabed is None else seabed
        L = float(self.length_scale) if self.length_scale else turbulence_length(seabed)
        return L, L * TurbulenceField.SCALE

    def step_gust(self, dt: float, rng: np.random.Generator | None = None) -> None:
        """Advance the flow state by ``dt`` (once per tick). ``rng`` is accepted for compatibility."""
        before = self.depth_average()
        self._clock += dt
        after = self.depth_average()
        advect = 0.5 * (before + after)
        self._travel += float(np.linalg.norm(advect)) * dt
        _, ell = self.turbulence_scales()
        self._field().advance(dt, advect, ell, self.turbulence * float(np.linalg.norm(advect)))

    def fluctuation_many(self, positions: np.ndarray, mean: np.ndarray, seabed: float) -> np.ndarray:
        """Turbulent velocity at points given their local mean flow (zero if turbulence is 0)."""
        if self.turbulence <= 0:
            return np.zeros_like(mean)
        _, ell = self.turbulence_scales(seabed)
        a = math.radians(self.surface_dir)
        north, east = math.cos(a), math.sin(a)
        turb = self._field()
        if self.use_compiled and _compiled_turbulence is not None:
            return _compiled_turbulence(np.ascontiguousarray(positions, float), mean, turb.displacement,
                                        1.0 / ell, turb.k, turb.phase, turb.amp, float(self.turbulence),
                                        COMPONENT_RATIOS, north, east)
        unit = turb.unit(positions, ell)
        return turbulence_vectors(unit, mean, self.turbulence, positions[:, 2], (north, east))

    def shedding_travel(self, depths, seabed: float) -> np.ndarray:
        """Integrated free-stream distance (m) per depth: sets vortex-shedding phase (f = St U / D)."""
        self._layers()
        avg = self._layer_cache[3]
        if avg < 1e-3:
            return np.full(len(np.atleast_1d(depths)), self._travel)
        local = np.linalg.norm(self.mean_many(np.atleast_1d(depths), seabed), axis=1)
        return self._travel * local / avg

    # ── sampling ──────────────────────────────────────────────────────────
    def sample_many(self, positions: np.ndarray, seabed: float, t: float = 0.0, bed=None,
                    z0: float | None = None) -> np.ndarray:
        """Ambient flow (mean profile, turbulence and optional wave) at NED points.

        Not obstacle-resolving; ``World.current_at_many`` adds structure effects and passes the
        local seabed depth per point (``bed``) and the biome roughness (``z0``). Without them the
        nominal flat seabed and the profile's own roughness are used.
        """
        p = np.atleast_2d(np.asarray(positions, float))
        self._seabed_hint = float(seabed)
        heights = None if bed is None else np.asarray(bed, float) - p[:, 2]
        mean = self.mean_many(p[:, 2], seabed, heights, z0)
        velocity = mean + self.fluctuation_many(p, mean, seabed)
        if self.wave is not None:
            velocity += self.wave.velocity(p, self._clock)
        return velocity

    def sample(self, position: np.ndarray, seabed: float, t: float = 0.0) -> np.ndarray:
        return self.sample_many(np.asarray(position)[None, :], seabed, t)[0]

    def at_many(self, depths: np.ndarray, seabed: float) -> np.ndarray:
        """Legacy: ambient flow on the vertical through the origin."""
        z = np.asarray(depths, float)
        return self.sample_many(np.stack([np.zeros_like(z), np.zeros_like(z), z], axis=1), seabed)

    def at(self, depth: float, seabed: float) -> np.ndarray:
        return self.at_many(np.array([depth], float), seabed)[0]

    def as_dict(self):
        out = {k: getattr(self, k) for k in ("surface_kn", "surface_dir", "mid_kn", "mid_dir",
                                             "bottom_kn", "bottom_dir", "turbulence")}
        if self.tide is not None:
            out["tide"] = self.tide.as_dict()
        if self.wave is not None:
            out["wave"] = asdict(self.wave)
        if self.bypass_flow:
            out["bypass_flow"] = True
        return out


# ── structures ───────────────────────────────────────────────────────────────
WAKE_DECAY_D = 3.0          # centreline deficit 1/(1 + x/(3D)): 0.75 at 1D, 0.38 at 5D, 0.13 at 20D (assumed)
SHED_AMPLITUDE = 0.4        # peak transverse shedding velocity / U in the near wake (assumed)
WAKE_RANGE_D = 40.0         # wake ignored beyond 40 D downstream
LEE_SHELTER = 0.7           # speed reduction right behind a box / wreck section (assumed)
FRONT_BLOCKING = 0.5        # speed reduction at an upstream face (assumed)


class StructureFlow:
    """Analytic flow disturbance by the world's obstacles (habitat props are ignored).

    Cylinders of any orientation use the flow component normal to their axis: potential-flow
    doublet (stagnation upstream, 2U at the shoulders), a Gaussian wake behind them and an
    alternating transverse shedding velocity at f = St U / D. Boxes and wreck meshes give a lee
    shelter that decays over three body sizes and a weaker blocking zone in front. Walls block
    the normal component and slow the flow in a 2 m boundary layer. Flow is zero inside solids.
    """

    use_compiled = True                  # numba loop when available; the NumPy path is the reference

    def __init__(self, obstacles: list, bypass_flow=False):
        from .site_dressing import NO_WAKE_KINDS
        from .world import Box, Cylinder, FieldMesh, ShipHull, Wall
        # Habitat props and small snaggable seabed items (SnagFeature, kind "snag") are left out: the
        # latter sit inside the near-bed log layer, whose roughness length already stands for them. So are
        # the inspection-site fittings that sit in that layer or are too small to shed a wake (NO_WAKE_KINDS).
        skip = {"habitat", "snag"} | NO_WAKE_KINDS
        cyl = [o for o in obstacles if isinstance(o, Cylinder) and o.kind not in skip]
        self.n_cyl = len(cyl)
        self.cyl_a = np.array([o.p0 for o in cyl], float).reshape(-1, 3)
        b = np.array([o.p1 for o in cyl], float).reshape(-1, 3)
        axis = b - self.cyl_a
        self.cyl_len = np.linalg.norm(axis, axis=1)
        self.cyl_axis = axis / np.maximum(self.cyl_len, 1e-9)[:, None]
        self.cyl_r = np.array([o.radius for o in cyl], float)
        self.cyl_phase = np.arange(self.n_cyl) * 2.399963          # decorrelate neighbouring wakes
        self.bypass_flow = bypass_flow
        self.pen = None
        if bypass_flow and any(o.kind == "pen_net" for o in obstacles):
            from .aquaculture import CENTER, RADIUS, DEPTH
            self.pen = (CENTER, RADIUS, DEPTH)
        self.boxes = []
        for o in obstacles:
            if isinstance(o, Box) and o.kind not in skip:
                self.boxes.append((o, np.asarray(o.center, float), np.asarray(o.half, float),
                                   math.radians(o.yaw_deg), True))
            elif isinstance(o, ShipHull):
                # the hull's bounding box below the waterline: lee shelter and front blocking like a box;
                # not solid, since the box is larger than the hull at bow, stern and bilges
                hp = o.hp
                top = max(hp["top"], 0.0)
                centre = o.world_point((0.0, 0.0, (top + hp["draft"]) / 2))
                half = np.array([hp["length"] / 2, hp["beam"] / 2, (hp["draft"] - top) / 2])
                self.boxes.append((o, centre, half, math.radians(o.yaw_deg), False))
            elif isinstance(o, FieldMesh):
                centre_local = 0.5 * (o.lo + o.hi)
                half = 0.5 * (o.hi - o.lo)
                centre = o.world_point(centre_local)
                self.boxes.append((o, centre, np.array([half[0], half[1], half[2]]),
                                   math.radians(o.heading_deg), False))
        self.walls = [o for o in obstacles if isinstance(o, Wall)]
        reach = [np.r_[self.cyl_r * 2 * WAKE_RANGE_D, 0.0].max()]
        for _, centre, half, _, _ in self.boxes:
            reach.append(float(np.linalg.norm(half)) * 8)
        self.reach = float(max(reach))

    @property
    def empty(self) -> bool:
        return not (self.n_cyl or self.boxes or self.walls or self.pen)

    def apply(self, X: np.ndarray, U: np.ndarray, travel: np.ndarray) -> np.ndarray:
        """Disturbed velocities for points ``X`` given ambient velocities ``U``.

        ``travel`` is the per-point integrated free-stream distance (m) that sets the shedding phase.
        """
        V = U.copy()
        if self.n_cyl and self.use_compiled and _compiled_cylinders is not None:
            V = _compiled_cylinders(np.ascontiguousarray(X, float), V, np.ascontiguousarray(travel, float),
                                    self.cyl_a, self.cyl_axis, self.cyl_len, self.cyl_r, self.cyl_phase,
                                    STROUHAL, SHED_AMPLITUDE, WAKE_DECAY_D, WAKE_RANGE_D)
        elif self.n_cyl:
            V = self._cylinders(X, V, travel)
        if self.pen:
            centre, radius, depth = self.pen
            V = pen_flow(X, V, centre, radius, depth)
        for box in self.boxes:
            V = self._box(X, V, *box)
        for wall in self.walls:
            V = self._wall(X, V, wall)
        return V

    def _cylinders(self, X, U, travel):
        a, ax, R = self.cyl_a, self.cyl_axis, self.cyl_r
        rel = X[:, None, :] - a[None, :, :]
        t = np.einsum("nmi,mi->nm", rel, ax)
        t_in = np.clip(t, 0.0, self.cyl_len[None, :])
        perp = rel - t_in[..., None] * ax[None, :, :]
        along = (t - t_in)
        perp = perp - along[..., None] * ax[None, :, :]
        r = np.linalg.norm(perp, axis=2)
        end_fade = np.exp(-(along / np.maximum(R, 0.3)[None, :]) ** 2)
        Ua = np.einsum("ni,mi->nm", U, ax)
        Up_vec = U[:, None, :] - Ua[..., None] * ax[None, :, :]
        Up = np.linalg.norm(Up_vec, axis=2)
        e1 = Up_vec / np.maximum(Up, 1e-9)[..., None]
        e2 = np.cross(ax[None, :, :], e1)
        x = np.einsum("nmi,nmi->nm", perp, e1)
        y = np.einsum("nmi,nmi->nm", perp, e2)
        Rm = R[None, :]
        D = 2 * Rm
        r2 = np.maximum(r * r, (Rm * Rm))
        doublet_u = -Rm * Rm * (x * x - y * y) / (r2 * r2)
        doublet_v = -Rm * Rm * 2 * x * y / (r2 * r2)
        xp = np.maximum(x, 0.0)
        onset = smoothstep(x / Rm)
        width = Rm * np.sqrt(1.0 + xp / D)
        amp = 1.0 / (1.0 + xp / (WAKE_DECAY_D * D))
        reach = (x < WAKE_RANGE_D * D).astype(float)
        deficit = amp * np.exp(-0.5 * (y / width) ** 2) * onset * reach
        st_travel = travel[:, None] * np.ones_like(Rm)
        phase = 2 * math.pi * (STROUHAL * st_travel / D - xp / (4.0 * D)) + self.cyl_phase[None, :]
        shed = SHED_AMPLITUDE * amp * onset * reach * np.exp(-0.5 * (y / (1.5 * width)) ** 2) * np.sin(phase)
        u1 = (1.0 + doublet_u) * (1.0 - deficit)
        u2 = doublet_v * (1.0 - deficit) + shed
        delta = ((u1 - 1.0) * Up)[..., None] * e1 + (u2 * Up)[..., None] * e2
        active = (Up > 1e-4)[..., None]
        V = U + (delta * end_fade[..., None] * active).sum(axis=1)
        inside = ((r < R[None, :]) & (np.abs(along) < 1e-9)).any(axis=1)
        V[inside] = 0.0
        return V

    def _box(self, X, U, ob, centre, half, yaw, solid):
        if self.bypass_flow and self.use_compiled and _compiled_box is not None:
            return _compiled_box(X, U, centre, half, yaw, solid, ob.kind == "hull",
                                 LEE_SHELTER, FRONT_BLOCKING)
        c, s = math.cos(yaw), math.sin(yaw)
        rel = X - centre
        lx = c * rel[:, 0] + s * rel[:, 1]
        ly = -s * rel[:, 0] + c * rel[:, 1]
        lz = rel[:, 2]
        inside = (np.abs(lx) <= half[0]) & (np.abs(ly) <= half[1]) & (np.abs(lz) <= half[2])
        speed = np.linalg.norm(U[:, :2], axis=1)
        d = U[:, :2] / np.maximum(speed, 1e-9)[:, None]
        dx = c * d[:, 0] + s * d[:, 1]
        dy = -s * d[:, 0] + c * d[:, 1]
        along = lx * dx + ly * dy
        across = -lx * dy + ly * dx
        depth_half = np.abs(half[0] * dx) + np.abs(half[1] * dy)
        width_half = np.abs(half[0] * dy) + np.abs(half[1] * dx)
        size = np.maximum(np.minimum(2 * width_half, 2 * half[2]), 0.5)
        margin = 0.3 * width_half + 0.5
        lateral = np.clip((width_half + margin - np.abs(across)) / margin, 0.0, 1.0)
        vertical = np.clip((half[2] + 0.5 * half[2] + 0.5 - np.abs(lz)) / (0.5 * half[2] + 0.5), 0.0, 1.0)
        behind = np.maximum(along - depth_half, 0.0)
        front = np.maximum(-along - depth_half, 0.0)
        lee = LEE_SHELTER * np.exp(-behind / (3.0 * size)) * (along > 0)
        block = FRONT_BLOCKING * np.exp(-front / size) * (along <= 0)
        factor = 1.0 - (lee + block) * lateral * vertical * (speed > 1e-6)
        if self.bypass_flow and ob.kind == "hull":
            shoulder = np.exp(-((np.abs(across) - width_half - margin) / margin) ** 2)
            taper = 1 - smoothstep(np.abs(along) / np.maximum(0.1, depth_half))
            factor += 0.2 * shoulder * vertical * taper * (speed > 1e-6)
        V = U * factor[:, None]
        if solid:
            V[inside] = 0.0
        else:
            V[inside] = U[inside] * (1.0 - 0.8)
        return V

    @staticmethod
    def _wall(X, U, wall):
        dist, normal = wall.sdf_many(X)
        if not np.any(dist < 3.0):
            return U
        n = normal
        un = np.einsum("ni,ni->n", U, n)
        tangential = U - un[:, None] * n
        layer = np.clip(np.maximum(dist, 0.0) / 2.0, 1e-3, 1.0) ** (1.0 / 7.0)
        into = np.minimum(un, 0.0) * np.clip(dist / 3.0, 0.0, 1.0)
        away = np.maximum(un, 0.0)
        V = tangential * layer[:, None] + (into + away)[:, None] * n
        V[dist <= 0.0] = 0.0
        near = dist < 3.0
        return np.where(near[:, None], V, U)
