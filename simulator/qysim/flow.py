"""Ocean flow building blocks shared by ``world.CurrentProfile``.

Every number marked "assumed" is a provisional simulator value from
``research_notes/洋流與波浪對ROV作業/`` and must be replaced by measurements when they exist.

Pieces
    TurbulenceField  smooth anisotropic frozen turbulence: random Fourier modes (Matern-3/2
                     spectrum) advected with the depth-averaged mean current (Taylor hypothesis)
                     plus a slow eddy evolution. The state is integrated once per tick, so the
                     field and its time derivative are bounded and independent of the step size.
    Tide             optional M2/S2 tidal modulation of the layer profile, rectilinear or rotary.
    StructureFlow    analytic flow around cylinders (doublet, Gaussian wake, Strouhal shedding)
                     and lee shelter / blocking around boxes, wreck meshes and walls.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields

import numpy as np

M2_PERIOD_S = 12.4206012 * 3600.0    # principal lunar semidiurnal constituent
S2_PERIOD_S = 12.0 * 3600.0          # principal solar semidiurnal constituent
TIDE_STARTS = ("peak_flood", "slack_before_ebb", "peak_ebb", "slack_before_flood")
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
        return asdict(self)

    def _terms(self, tau):
        w2, ws = 2 * math.pi / M2_PERIOD_S, 2 * math.pi / S2_PERIOD_S
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
        tau = np.linspace(0.0, M2_PERIOD_S, 4097)
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
        tau = np.linspace(0.0, M2_PERIOD_S, 4097)
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
        ahead = tau + np.linspace(0.0, 7 * 3600.0, 421)
        future, _ = self._terms(ahead)
        sign = np.sign(future)
        change = np.flatnonzero(sign[1:] != sign[:-1])
        minutes = None if self.kind == "rotary" or len(change) == 0 else round(float(change[0]), 0)
        stage = "slack" if abs(float(major)) < 0.02 else "flood" if float(major) > 0 else "ebb"
        return {"factor": round(float(major), 3), "stage": stage, "minutes_to_slack": minutes}


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
        self._k_all = self.k.reshape(3 * self.MODES, 3).T.copy()

    def advance(self, dt: float, advect: np.ndarray, ell: float, sigma: float) -> None:
        """Integrate advection displacement and eddy evolution over ``dt`` (midpoint velocities)."""
        self.displacement = self.displacement + np.array([advect[0], advect[1], 0.0]) * dt
        rate = max(sigma, 0.02) / ell
        self.theta = self.theta + self.evolve * rate * dt

    def unit(self, points: np.ndarray, ell: float) -> np.ndarray:
        """(N, 3) unit-variance fluctuations (u, v, w) at NED points, before frame rotation."""
        X = (np.asarray(points, float) - self.displacement) * (1.0 / ell)
        arg = X @ self._k_all + (self.psi + self.theta).ravel()
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

    def __init__(self, obstacles: list):
        from .world import Box, Cylinder, FieldMesh, Wall
        cyl = [o for o in obstacles if isinstance(o, Cylinder) and o.kind != "habitat"]
        self.n_cyl = len(cyl)
        self.cyl_a = np.array([o.p0 for o in cyl], float).reshape(-1, 3)
        b = np.array([o.p1 for o in cyl], float).reshape(-1, 3)
        axis = b - self.cyl_a
        self.cyl_len = np.linalg.norm(axis, axis=1)
        self.cyl_axis = axis / np.maximum(self.cyl_len, 1e-9)[:, None]
        self.cyl_r = np.array([o.radius for o in cyl], float)
        self.cyl_phase = np.arange(self.n_cyl) * 2.399963          # decorrelate neighbouring wakes
        self.boxes = []
        for o in obstacles:
            if isinstance(o, Box) and o.kind != "habitat":
                self.boxes.append((o, np.asarray(o.center, float), np.asarray(o.half, float),
                                   math.radians(o.yaw_deg), True))
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
        return not (self.n_cyl or self.boxes or self.walls)

    def apply(self, X: np.ndarray, U: np.ndarray, travel: np.ndarray) -> np.ndarray:
        """Disturbed velocities for points ``X`` given ambient velocities ``U``.

        ``travel`` is the per-point integrated free-stream distance (m) that sets the shedding phase.
        """
        V = U.copy()
        if self.n_cyl:
            V = self._cylinders(X, V, travel)
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

    @staticmethod
    def _box(X, U, ob, centre, half, yaw, solid):
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
