"""Sediment resuspension, transport and optical turbidity (thruster silt-out model).

Owns everything the world needs to answer "how much sediment is in the water here,
and how far can a camera see through it":

* Source: a per-thruster free-jet model. Outlet velocity follows from momentum flux,
  ``T = rho * A * V0**2`` (so ``V0 = sqrt(T / (rho * A))``; the propeller-wash forms
  ``V0 = 1.33..1.59 * n * D * sqrt(Ct)`` describe the same efflux from rpm). The centreline
  velocity decays as ``Vmax = V0 * min(1, 2.6 * D / x)`` (Fuehrer et al. 1987) with a Gaussian
  radial profile ``exp(-22.2 * (r / x)**2)``. The jet is followed along each thruster's
  world-space axis; where it meets the seabed the bed shear is ``tau = rho * Cf * U**2``.
  Erosion happens only above the seabed type's critical shear, with a Partheniades-type law
  ``E = M * (tau / tau_cr - 1)**1.5`` integrated over the Gaussian footprint. Sediment is
  spawned at the impingement point, not at the vehicle centre. Hull and tether contact with
  a soft bed add a smaller contact source.
* Transport: mass-conserving Gaussian puffs in three grain classes (fine sand 200 um,
  coarse silt 63 um, fine silt 15 um). Each puff settles at its class settling velocity
  (Soulsby 1997, which reduces to Stokes for silt), is advected by ``World.current_at_many``
  (the full local flow, with its terrain-aware log-law bed layer and structure wakes), spreads
  as ``sigma**2 += 2 * K * dt`` (K: still water + current shear + decaying thruster wake) and loses mass only by deposition at the bed
  (flux ``ws * C_bed``) or by leaving the area around the vehicles. Every kilogram is booked
  in ``emitted = suspended + deposited + removed``.
* Optics: concentration ``C`` in mg/L (= g/m3) at any point, with an optional near-bed
  turbid (nepheloid) layer per scenario; beam attenuation ``c = 4.8 / visibility_m + k * C``
  with ``k = 0.5 m2/g`` and visibility ``4.8 / c`` (Zaneveld & Pegau 2003).

All coefficients are provisional engineering values from
``research_notes/感測器_揚沙_通訊/silt_and_visibility.md``; none is an X1 measurement.
"""

from __future__ import annotations

import math

import numpy as np

RHO_WATER = 1025.0             # kg/m3
GRAVITY = 9.81
NU_WATER = 1.05e-6             # m2/s, seawater around 20 C
GRAIN_DENSITY_RATIO = 2.65     # quartz
BLACK_TARGET_CONTRAST = 4.8    # visibility = 4.8 / c (Zaneveld & Pegau 2003)

# Provisional parameters. Not X1 measurements; see docs/reference/silt-validation.md.
SILT_PARAMETERS = {
    "thruster_diameter_m": 0.09,     # assumption from the research notes; X1 unmeasured
    "wall_friction_cf": 0.005,       # wall-jet friction coefficient, literature range 0.003-0.01
    "mass_attenuation_m2_per_g": 0.5,  # c*_p, coastal typical; literature 0.05-1.5
    "diffusivity_m2_s": 1.5e-3,      # still-water horizontal puff diffusivity K0
    "shear_dispersion": 0.1,         # extra K = alpha * |u| * sigma_h in a current
    "jet_diffusivity_m2_s": 0.008,   # residual thruster-wake turbulence, decaying with puff age
    "jet_turbulence_s": 30.0,        # e-folding time of that residual turbulence
    "vertical_diffusion_ratio": 0.3,  # K_v / K_h
    "max_puffs": 160,
    "range_m": 80.0,                 # puffs this far from every vehicle leave the simulation
    "min_peak_mg_l": 0.01,           # below this a puff is optically irrelevant and retired
    "jet_interval_s": 0.05,
}

GRAIN_CLASSES = (
    {"id": "fine_sand", "d_m": 200e-6},
    {"id": "coarse_silt", "d_m": 63e-6},
    {"id": "fine_silt", "d_m": 15e-6},
)

# tau_cr in Pa, erosion constant M in kg/m2/s, grain mix (sand, coarse silt, fine silt).
# Rock never erodes. All provisional (silt_and_visibility.md Q2 and Q8 item 7).
SEABED_TYPES = {
    "fluff": {"tau_cr": 0.05, "erosion": 1.0e-3, "mix": (0.05, 0.30, 0.65), "contact": 1.0},
    "mud": {"tau_cr": 0.20, "erosion": 8e-4, "mix": (0.10, 0.35, 0.55), "contact": 0.8},
    "silt": {"tau_cr": 0.12, "erosion": 8e-4, "mix": (0.25, 0.45, 0.30), "contact": 0.6},
    "sand": {"tau_cr": 0.16, "erosion": 5e-4, "mix": (0.90, 0.08, 0.02), "contact": 0.3},
    "gravel": {"tau_cr": 8.0, "erosion": 5e-5, "mix": (0.97, 0.02, 0.01), "contact": 0.05},
    "rock": {"tau_cr": math.inf, "erosion": 0.0, "mix": (0.0, 0.0, 0.0), "contact": 0.0},
}
BIOME_SEABED = {"reef": "rock", "seagrass": "sand", "harbor": "mud"}
DEFAULT_SEABED = "sand"

# Contact source: kg per newly touching hull sphere at 1 m/s, and kg/s per sliding sphere.
CONTACT_IMPACT_KG = 0.03
CONTACT_SLIDE_KG_S = 0.02
TETHER_SLIDE_KG_S = 0.002

_JET_SAMPLES = np.geomspace(0.05, 12.0, 28)
_FOOTPRINT_S = np.linspace(0.0, 1.0, 13)
_TWO_PI_32 = (2.0 * math.pi) ** 1.5
_SQRT_2PI = math.sqrt(2.0 * math.pi)
_trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")


def settling_velocity(d_m: float) -> float:
    """Soulsby (1997) settling velocity in m/s; equals Stokes for fine silt."""
    s1 = GRAIN_DENSITY_RATIO - 1.0
    d_star = d_m * (GRAVITY * s1 / NU_WATER ** 2) ** (1.0 / 3.0)
    return NU_WATER / d_m * (math.sqrt(10.36 ** 2 + 1.049 * d_star ** 3) - 10.36)


SETTLING = np.array([settling_velocity(c["d_m"]) for c in GRAIN_CLASSES])


def seabed_type_for(biome: str, explicit: str | None = None) -> str:
    """Scenario seabed type: explicit value, else derived from the biome."""
    if explicit:
        if explicit not in SEABED_TYPES:
            raise ValueError(f"unknown seabed type {explicit!r}")
        return explicit
    return BIOME_SEABED.get(biome, DEFAULT_SEABED)


def jet_outlet_velocity(thrust_n, diameter_m: float):
    """Momentum-flux efflux velocity V0 = sqrt(T / (rho * A)), m/s."""
    area = math.pi * diameter_m ** 2 / 4.0
    return np.sqrt(np.abs(np.asarray(thrust_n, float)) / (RHO_WATER * area))


def jet_centreline_velocity(v0, x, diameter_m: float):
    """Fuehrer et al. (1987): Vmax = V0 * 2.6 * D / x, capped at V0 in the potential core."""
    return np.asarray(v0, float) * np.minimum(1.0, 2.6 * diameter_m / np.maximum(np.asarray(x, float), 1e-6))


def footprint_integral(ratio):
    """Integral over the Gaussian bed footprint of (tau/tau_cr - 1)**1.5, in units of pi*x^2/44.4."""
    ratio = np.atleast_1d(np.asarray(ratio, float))
    out = np.zeros_like(ratio)
    live = ratio > 1.0
    if not np.any(live):
        return out
    log_r = np.log(ratio[live])
    s = _FOOTPRINT_S[None, :] * log_r[:, None]
    excess = np.maximum(ratio[live, None] * np.exp(-s) - 1.0, 0.0) ** 1.5
    out[live] = _trapezoid(excess, s, axis=1)
    return out


class SiltField:
    """Gaussian puff field with mass bookkeeping. Positions are NED metres, masses kilograms."""

    def __init__(self, world):
        self.world = world
        self.params = dict(SILT_PARAMETERS)
        self.seabed_type = DEFAULT_SEABED
        self.bnl_height_m = 0.0
        self.bnl_mg_l = 0.0
        self.visibility_m = 12.0
        self.pos = np.zeros((0, 3))
        self.sigma_h = np.zeros(0)
        self.sigma_v = np.zeros(0)
        self.mass = np.zeros(0)
        self.cls = np.zeros(0, int)
        self.age = np.zeros(0)
        self.source_id = np.zeros(0, int)
        self._source_ids: dict = {}
        self._source_names: list[str] = []
        self.emitted = 0.0
        self.deposited = 0.0
        self.removed = 0.0
        self._jet_clock = 0.0
        self._slide_last: dict = {}
        self.last_jets: dict = {}

    # ── configuration ──────────────────────────────────────────────────────
    def configure(self, seabed_type: str, bnl_height_m: float = 0.0, bnl_mg_l: float = 0.0) -> None:
        self.seabed_type = seabed_type_for("", seabed_type)
        self.bnl_height_m = max(0.0, float(bnl_height_m))
        self.bnl_mg_l = max(0.0, float(bnl_mg_l))

    @property
    def bed(self) -> dict:
        return SEABED_TYPES[self.seabed_type]

    @property
    def count(self) -> int:
        return len(self.mass)

    def suspended(self) -> float:
        return float(self.mass.sum())

    def budget(self) -> dict:
        return {"emitted": self.emitted, "suspended": self.suspended(), "deposited": self.deposited,
                "removed": self.removed}

    # ── puff storage ───────────────────────────────────────────────────────
    def add_puff(self, pos, mass_kg: float, grain: int, sigma_h: float, sigma_v: float,
                 source: str = "default") -> None:
        """Insert one puff of a single grain class (mass booked as emitted)."""
        if mass_kg <= 0.0:
            return
        self.emitted += float(mass_kg)
        self._append(np.asarray(pos, float), float(mass_kg), int(grain), sigma_h, sigma_v, source)
        self._enforce_cap()

    def _append(self, pos, mass, grain, sigma_h, sigma_v, source):
        self.pos = np.vstack([self.pos, pos[None, :]])
        self.sigma_h = np.append(self.sigma_h, max(0.05, float(sigma_h)))
        self.sigma_v = np.append(self.sigma_v, max(0.05, float(sigma_v)))
        self.mass = np.append(self.mass, mass)
        self.cls = np.append(self.cls, grain)
        self.age = np.append(self.age, 0.0)
        self.source_id = np.append(self.source_id, self._source_code(source))

    def emit_mix(self, pos, mass_kg: float, mix, sigma_h: float, sigma_v: float, source: str) -> None:
        """Split ``mass_kg`` by grain ``mix`` and emit one puff per class, merging into a fresh puff nearby."""
        pos = np.asarray(pos, float)
        for grain, fraction in enumerate(mix):
            part = mass_kg * float(fraction)
            if part <= 0.0:
                continue
            target = self._fresh_neighbour(pos, grain, source, sigma_h)
            self.emitted += part
            if target is None:
                self._append(pos, part, grain, sigma_h, sigma_v, source)
            else:
                self._merge_into(target, pos, part, sigma_h, sigma_v)
        self._enforce_cap()

    def _source_code(self, source) -> int:
        name = str(source)
        code = self._source_ids.get(name)
        if code is None:
            code = len(self._source_names)
            self._source_ids[name] = code
            self._source_names.append(name)
        return code

    def source_name(self, i: int) -> str:
        return self._source_names[int(self.source_id[i])]

    def _fresh_neighbour(self, pos, grain, source, sigma_h):
        if not self.count:
            return None
        young = (self.cls == grain) & (self.age < 1.0)
        young &= self.source_id == self._source_code(source)
        if not np.any(young):
            return None
        idx = np.flatnonzero(young)
        dist = np.linalg.norm(self.pos[idx] - pos, axis=1)
        best = int(np.argmin(dist))
        if dist[best] > 0.5 * max(sigma_h, float(self.sigma_h[idx[best]])):
            return None
        return int(idx[best])

    def _merge_into(self, i, pos, mass, sigma_h, sigma_v):
        """Mass-weighted merge that conserves mass, centroid and second moments."""
        m1, m2 = float(self.mass[i]), float(mass)
        total = m1 + m2
        c1 = self.pos[i].copy()
        centre = (m1 * c1 + m2 * pos) / total
        d1, d2 = c1 - centre, pos - centre
        var_h = (m1 * (self.sigma_h[i] ** 2 + 0.5 * float(d1[:2] @ d1[:2]))
                 + m2 * (sigma_h ** 2 + 0.5 * float(d2[:2] @ d2[:2]))) / total
        var_v = (m1 * (self.sigma_v[i] ** 2 + d1[2] ** 2) + m2 * (sigma_v ** 2 + d2[2] ** 2)) / total
        self.pos[i] = centre
        self.mass[i] = total
        self.sigma_h[i] = math.sqrt(var_h)
        self.sigma_v[i] = math.sqrt(var_v)
        self.age[i] = (m1 * self.age[i]) / total

    def _remove(self, keep: np.ndarray) -> None:
        self.pos = self.pos[keep]
        self.sigma_h = self.sigma_h[keep]
        self.sigma_v = self.sigma_v[keep]
        self.mass = self.mass[keep]
        self.cls = self.cls[keep]
        self.age = self.age[keep]
        self.source_id = self.source_id[keep]

    def _enforce_cap(self) -> None:
        """Merge the lightest puff into its nearest same-class neighbour until under the cap."""
        cap = int(self.params["max_puffs"])
        while self.count > cap:
            i = int(np.argmin(self.mass))
            same = np.flatnonzero(self.cls == self.cls[i])
            same = same[same != i]
            if not len(same):
                same = np.flatnonzero(np.arange(self.count) != i)
            j = int(same[np.argmin(np.linalg.norm(self.pos[same] - self.pos[i], axis=1))])
            self._merge_into(j, self.pos[i].copy(), float(self.mass[i]),
                             float(self.sigma_h[i]), float(self.sigma_v[i]))
            keep = np.ones(self.count, bool)
            keep[i] = False
            self._remove(keep)

    # ── sources ────────────────────────────────────────────────────────────
    def jet_bed_velocity(self, origins, directions, thrust_n):
        """Bed velocity, impingement point and jet length for each thruster jet.

        ``origins`` (n,3) outlet positions, ``directions`` (n,3) unit jet directions (water
        leaves along these, i.e. opposite to the thrust force), ``thrust_n`` (n,) magnitudes.
        Returns ``(u_bed, impact_points, x_bed, v0)``.
        """
        origins = np.atleast_2d(np.asarray(origins, float))
        directions = np.atleast_2d(np.asarray(directions, float))
        directions = directions / np.maximum(np.linalg.norm(directions, axis=1), 1e-9)[:, None]
        diameter = float(self.params["thruster_diameter_m"])
        v0 = jet_outlet_velocity(thrust_n, diameter)
        n, k = len(origins), len(_JET_SAMPLES)
        points = origins[:, None, :] + directions[:, None, :] * _JET_SAMPLES[None, :, None]
        bed = self.world.seabed_at_many(points.reshape(-1, 3)).reshape(n, k)
        gap = bed - points[:, :, 2]
        # The bed point under each axis sample sits a little further along the jet (x + g * dz) and
        # g * sqrt(1 - dz^2) off the axis; evaluate the jet there.
        along = _JET_SAMPLES[None, :] + gap * directions[:, 2:3]
        radius = np.maximum(gap, 0.0) * np.sqrt(np.maximum(0.0, 1.0 - directions[:, 2:3] ** 2))
        safe_along = np.maximum(along, 1e-6)
        u = jet_centreline_velocity(v0[:, None], safe_along, diameter) * np.exp(-22.2 * (radius / safe_along) ** 2)
        crossed = gap <= 0.0
        first = np.where(crossed.any(axis=1), crossed.argmax(axis=1), k)
        u = np.where((np.arange(k)[None, :] >= first[:, None]) | (along <= 0.0), 0.0, u)
        best = u.argmax(axis=1)
        rows = np.arange(n)
        u_bed = u[rows, best]
        x_bed = np.hypot(np.maximum(along[rows, best], 0.0), radius[rows, best])
        impact = points[rows, best].copy()
        impact[:, 2] = bed[rows, best]
        for i in np.flatnonzero(first < k):
            # The axis itself meets the bed: interpolate the crossing between the bracketing samples.
            hi = int(first[i])
            if hi == 0:
                x_hit = _JET_SAMPLES[0]
            else:
                g0, g1 = gap[i, hi - 1], gap[i, hi]
                x0, x1 = _JET_SAMPLES[hi - 1], _JET_SAMPLES[hi]
                x_hit = x0 + (x1 - x0) * g0 / max(g0 - g1, 1e-9)
            u_hit = float(jet_centreline_velocity(v0[i], x_hit, diameter))
            if u_hit >= u_bed[i]:
                u_bed[i] = u_hit
                x_bed[i] = x_hit
                impact[i] = origins[i] + directions[i] * x_hit
                impact[i, 2] = float(self.world.seabed_at_many(impact[i])[0])
        u_bed = np.where(np.abs(np.asarray(thrust_n, float)) > 0.0, u_bed, 0.0)
        return u_bed, impact, x_bed, v0

    def jet_erosion(self, origins, directions, thrust_n):
        """Erosion rate (kg/s), bed shear (Pa), impact points and jet lengths for each jet."""
        u_bed, impact, x_bed, _ = self.jet_bed_velocity(origins, directions, thrust_n)
        tau = RHO_WATER * float(self.params["wall_friction_cf"]) * u_bed ** 2
        bed = self.bed
        if bed["erosion"] <= 0.0 or not math.isfinite(bed["tau_cr"]):
            return np.zeros(len(u_bed)), tau, impact, x_bed, u_bed
        area_unit = math.pi * x_bed ** 2 / 44.4
        rate = bed["erosion"] * area_unit * footprint_integral(tau / bed["tau_cr"])
        return rate, tau, impact, x_bed, u_bed

    def step_sources(self, dt: float, vehicles) -> None:
        """Every ``jet_interval_s``: thruster erosion at the impact points and tether drag on the bed.

        Each vehicle dict may carry ``jets`` [(outlet NED, jet direction NED, thrust N), ...] and
        ``tether`` (nodes, velocities, node radius).
        """
        self._jet_clock += dt
        interval = float(self.params["jet_interval_s"])
        if self._jet_clock + 1e-9 < interval:
            return
        elapsed, self._jet_clock = self._jet_clock, 0.0
        if self.bed["erosion"] <= 0.0:
            return
        for vehicle in vehicles:
            tether = vehicle.get("tether")
            if tether is not None:
                self.tether_drag(elapsed, tether[0], tether[1], tether[2], str(vehicle.get("id", "default")))
            jets = vehicle.get("jets")
            if not jets:
                continue
            origins = np.array([j[0] for j in jets], float)
            directions = np.array([j[1] for j in jets], float)
            thrust = np.array([j[2] for j in jets], float)
            if not np.any(thrust > 0.5):
                continue
            rate, tau, impact, x_bed, u_bed = self.jet_erosion(origins, directions, thrust)
            vid = str(vehicle.get("id", "default"))
            self.last_jets[vid] = {"rate": rate, "tau": tau, "impact": impact, "x": x_bed, "u": u_bed}
            for i in np.flatnonzero(rate > 0.0):
                self._source(f"{vid}:jet{i}", impact[i], float(rate[i] * elapsed), float(u_bed[i]),
                             float(x_bed[i]), vid)

    def _source(self, key, impact, mass, u_bed, x_bed, vid):
        """Lift eroded mass into a puff over the impact point (rise scales with bed velocity)."""
        rise = min(2.0, 0.3 + 0.6 * u_bed)
        bed_z = float(impact[2])
        centre = np.array([impact[0], impact[1], bed_z - 0.5 * rise])
        sigma_v = max(0.2, 0.4 * rise)
        # The impinging jet turns into a radial wall jet, so the plume is at least as wide as it is tall.
        sigma_h = max(0.35, 0.3 * x_bed + 0.15, 0.75 * sigma_v)
        self.emit_mix(centre, mass, self.bed["mix"], sigma_h, sigma_v, key)

    def contact(self, pos, speed: float, vehicle_id: str, impact: bool) -> None:
        """Hull touching a soft bed: impulsive source on first touch, continuous while sliding."""
        factor = self.bed["contact"]
        if factor <= 0.0:
            return
        if impact:
            mass = CONTACT_IMPACT_KG * factor * (0.3 + speed)
        else:
            last = self._slide_last.get(vehicle_id)
            now = self.world.time
            self._slide_last[vehicle_id] = now
            if last is None or now - last > 0.5:
                return
            mass = CONTACT_SLIDE_KG_S * factor * min(1.0, 0.2 + speed) * (now - last)
        bed_z = self.world.seabed_at(pos)
        centre = np.array([pos[0], pos[1], bed_z - 0.25])
        self.emit_mix(centre, mass, self.bed["mix"], 0.4, 0.25, f"{vehicle_id}:contact")

    def tether_drag(self, dt, nodes, velocities, node_radius: float, vehicle_id: str) -> None:
        """Tether nodes lying on a soft bed and moving across it stir a small amount of sediment."""
        factor = self.bed["contact"]
        if factor <= 0.0 or nodes is None or not len(nodes):
            return
        nodes = np.asarray(nodes, float)
        bed = self.world.seabed_at_many(nodes)
        touching = bed - nodes[:, 2] < node_radius + 0.03
        if not np.any(touching):
            return
        speed = np.linalg.norm(np.asarray(velocities, float)[touching][:, :2], axis=1)
        moving = speed > 0.05
        if not np.any(moving):
            return
        mass = TETHER_SLIDE_KG_S * factor * float(np.sum(np.minimum(speed[moving], 1.0))) * dt
        centre = nodes[touching][moving].mean(axis=0)
        centre[2] = float(bed[touching][moving].mean()) - 0.15
        self.emit_mix(centre, mass, self.bed["mix"], 0.5, 0.15, f"{vehicle_id}:tether")

    # ── transport ──────────────────────────────────────────────────────────
    def step_transport(self, dt: float, vehicle_positions) -> None:
        """Advect, settle, spread and deposit every puff by ``dt`` seconds."""
        if not self.count:
            return
        world = self.world
        p = self.params
        flow = self.near_bed_flow()
        self.pos[:, :2] += flow[:, :2] * dt
        speed = np.linalg.norm(flow[:, :2], axis=1)
        k_h = p["diffusivity_m2_s"] + p["shear_dispersion"] * speed * self.sigma_h
        k_h = k_h + p["jet_diffusivity_m2_s"] * np.exp(-self.age / p["jet_turbulence_s"])
        k_v = p["vertical_diffusion_ratio"] * k_h
        self.sigma_h = np.sqrt(self.sigma_h ** 2 + 2.0 * k_h * dt)
        self.sigma_v = np.sqrt(self.sigma_v ** 2 + 2.0 * k_v * dt)
        ws = SETTLING[self.cls]
        bed = world.seabed_at_many(self.pos)
        self.pos[:, 2] = np.minimum(bed, self.pos[:, 2] + ws * dt)
        height = np.maximum(0.0, bed - self.pos[:, 2])
        # Deposition flux ws * C at the bed, with the bed reflecting the lower half of the puff.
        bed_density = 2.0 * np.exp(-0.5 * (height / self.sigma_v) ** 2) / (_SQRT_2PI * self.sigma_v)
        keep_fraction = np.exp(-ws * bed_density * dt)
        lost = self.mass * (1.0 - keep_fraction)
        self.deposited += float(lost.sum())
        self.mass = self.mass * keep_fraction
        self.age += dt
        self._retire(vehicle_positions)

    def near_bed_flow(self) -> np.ndarray:
        """Current carrying each puff: the world's full local flow (``World.current_at_many``).

        That flow already includes the terrain-aware log-law bed layer (biome roughness), the
        turbulence field and structure wakes/shelter, so silt drifts with the same water that
        pushes the vehicle and tether. Puffs at or below the bed get zero flow."""
        world = self.world
        return world.current_at_many(self.pos, world.time)

    def _retire(self, vehicle_positions) -> None:
        peak = self.peak_mg_l()
        keep = peak >= self.params["min_peak_mg_l"]
        if vehicle_positions is not None and len(vehicle_positions):
            vp = np.atleast_2d(np.asarray(vehicle_positions, float))
            dist = np.linalg.norm(self.pos[:, None, :2] - vp[None, :, :2], axis=2).min(axis=1)
            keep &= dist <= self.params["range_m"]
        if np.all(keep):
            return
        self.removed += float(self.mass[~keep].sum())
        self._remove(keep)

    # ── concentration and optics ───────────────────────────────────────────
    def peak_mg_l(self) -> np.ndarray:
        """Concentration at each puff centre from that puff alone (mg/L)."""
        if not self.count:
            return np.zeros(0)
        return 1000.0 * self.mass / (_TWO_PI_32 * self.sigma_h ** 2 * self.sigma_v)

    def puff_mg_l(self, points) -> np.ndarray:
        """Suspended concentration from the puffs at each point (mg/L), with bed reflection."""
        points = np.atleast_2d(np.asarray(points, float))
        out = np.zeros(len(points))
        if not self.count:
            return out
        bed = self.world.seabed_at_many(self.pos)
        image_z = 2.0 * bed - self.pos[:, 2]
        d = points[:, None, :] - self.pos[None, :, :]
        horizontal = (d[:, :, 0] ** 2 + d[:, :, 1] ** 2) / (2.0 * self.sigma_h ** 2)
        vertical = np.exp(-d[:, :, 2] ** 2 / (2.0 * self.sigma_v ** 2))
        vertical += np.exp(-(points[:, None, 2] - image_z[None, :]) ** 2 / (2.0 * self.sigma_v ** 2))
        weight = self.peak_mg_l()[None, :] * np.exp(-horizontal) * vertical
        below = points[:, 2] > self.world.seabed_at_many(points) + 1e-6
        out = weight.sum(axis=1)
        out[below] = 0.0
        return out

    def background_mg_l(self, points) -> np.ndarray:
        """Near-bed turbid layer C = bnl * exp(-altitude / H), zero when the scenario has none."""
        points = np.atleast_2d(np.asarray(points, float))
        if self.bnl_mg_l <= 0.0 or self.bnl_height_m <= 0.0:
            return np.zeros(len(points))
        altitude = self.world.seabed_at_many(points) - points[:, 2]
        layer = self.bnl_mg_l * np.exp(-np.maximum(0.0, altitude) / self.bnl_height_m)
        return np.where(altitude < -1e-6, 0.0, layer)

    def concentration_mg_l(self, points, include_background: bool = True) -> np.ndarray:
        out = self.puff_mg_l(points)
        if include_background:
            out = out + self.background_mg_l(points)
        return out

    def water_attenuation(self, visibility_m: float | None = None) -> float:
        vis = self.visibility_m if visibility_m is None else visibility_m
        return BLACK_TARGET_CONTRAST / max(0.05, float(vis))

    def attenuation(self, points, visibility_m: float | None = None) -> np.ndarray:
        """Beam attenuation c (1/m) = c_water + k * C."""
        k = self.params["mass_attenuation_m2_per_g"]
        return self.water_attenuation(visibility_m) + k * self.concentration_mg_l(points)

    def optical_depth(self, a, b, samples: int = 24, visibility_m: float | None = None) -> float:
        """Integrated attenuation along the segment a -> b (dimensionless, trapezoid rule)."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        length = float(np.linalg.norm(b - a))
        if length <= 0.0:
            return 0.0
        t = np.linspace(0.0, 1.0, max(2, int(samples)))
        c = self.attenuation(a[None, :] + (b - a)[None, :] * t[:, None], visibility_m)
        return float(_trapezoid(c, t) * length)

    def silt_index(self, points, visibility_m: float | None = None) -> np.ndarray:
        """Legacy 0..1 ``silt``: fraction of attenuation due to sediment = 1 - effective/base visibility."""
        k = self.params["mass_attenuation_m2_per_g"]
        particulate = k * self.concentration_mg_l(points)
        return particulate / (self.water_attenuation(visibility_m) + particulate)

    # ── state export ───────────────────────────────────────────────────────
    def puffs_state(self, limit: int = 64) -> list:
        """Compact puff list [n, e, d, sigma_h, sigma_v, peak_mg_l], strongest first."""
        if not self.count:
            return []
        peak = self.peak_mg_l()
        order = np.argsort(-peak)[:limit]
        rows = np.column_stack([self.pos[order], self.sigma_h[order], self.sigma_v[order], peak[order]])
        return np.round(rows, 3).tolist()

    def legacy_clouds(self, limit: int = 24, visibility_m: float | None = None) -> list:
        """Old ``environment.silt_clouds`` shape: {pos, strength 0..1, radius, age, source}."""
        if not self.count:
            return []
        peak = self.peak_mg_l()
        order = np.argsort(-peak)[:limit]
        k = self.params["mass_attenuation_m2_per_g"]
        cw = self.water_attenuation(visibility_m)
        clouds = []
        for i in order:
            particulate = k * float(peak[i])
            clouds.append({"pos": self.pos[i].copy(), "strength": round(particulate / (cw + particulate), 3),
                           "radius": round(float(self.sigma_h[i]), 3), "age": round(float(self.age[i]), 2),
                           "source": self.source_name(i).split(":")[0]})
        return clouds

    def turbidity_state(self) -> dict:
        return {"seabed_type": self.seabed_type, "c_water": round(self.water_attenuation(), 4),
                "k_m2_per_g": self.params["mass_attenuation_m2_per_g"],
                "bnl_height_m": self.bnl_height_m, "bnl_mg_l": self.bnl_mg_l}
