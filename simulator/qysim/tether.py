"""Umbilical tether: lumped-mass cable from the surface spool to the ROV.

Model
    * N segments, tension-only springs (a cable cannot push), with axial damping
    * per-node hydrodynamic drag split into normal / tangential components, using
      the depth-dependent current at each node
    * small wet weight (near-neutral tether), added mass
    * node-vs-obstacle contact with Coulomb friction, so the cable drapes, snags
      and wraps around piles and hulls
    * spool at node 0 (pinned), ROV gland at node N (kinematic, follows the vehicle);
      the last segment's force is returned to the vehicle as an external wrench
    * automatic payout when the spool-side tension exceeds a threshold, hard stop at
      the maximum length, break at the rated tensile strength
Defaults follow the X1 tether datasheet: 9.5 mm diameter, 350 m, 300 kgf tensile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .physics import G, RHO, q_rot, q_conj
from .world import World, Cylinder

GLAND_BODY = np.array([-0.38, 0.0, -0.06])     # tether strain-relief gland, rear of the hull


@dataclass
class TetherParams:
    segments: int = 40
    diameter: float = 0.0095          # m
    mass_per_m: float = 0.12          # kg/m in air
    wet_weight_per_m: float = 0.004   # kg/m net sinking weight in sea water (near neutral)
    ea: float = 20000.0               # N, effective axial stiffness (softened for real-time)
    k_max: float = 9000.0             # N/m per-segment stiffness cap (numerical stability)
    damping_ratio: float = 0.6
    cd_normal: float = 1.2
    cd_tangent: float = 0.02
    max_length: float = 350.0         # m
    breaking_n: float = 300 * G       # 300 kgf
    warn_n: float = 250.0             # N tension warning
    payout_threshold_n: float = 45.0
    payout_rate: float = 1.0          # m/s
    node_radius: float = 0.03
    friction: float = 0.6
    substeps: int = 10


class Tether:
    def __init__(self, world: World, spool_ned: np.ndarray, rov_gland_ned: np.ndarray,
                 length: float | None = None, params: TetherParams | None = None):
        self.p = params or TetherParams()
        self.world = world
        self.spool = np.asarray(spool_ned, float)
        span = float(np.linalg.norm(rov_gland_ned - self.spool))
        self.length = min(self.p.max_length, length or max(5.0, span * 1.25))
        n = self.p.segments
        t = np.linspace(0.0, 1.0, n + 1)[:, None]
        # lay out with a gentle sag so the cable starts slack
        self.x = self.spool * (1 - t) + np.asarray(rov_gland_ned, float) * t
        self.x[:, 2] += np.sin(np.pi * t[:, 0]) * max(0.0, self.length - span) * 0.3
        self.v = np.zeros_like(self.x)
        self.auto_payout = True
        self.broken = False
        self.tension_rov = 0.0
        self.tension_spool = 0.0
        self.tension_max = 0.0
        self.force_on_rov = np.zeros(3)
        self.contact_nodes = 0
        self.snag_names: list[str] = []
        self.wraps: dict[str, float] = {}
        self.events: list[dict] = []

    # ── helpers ───────────────────────────────────────────────────────────
    @property
    def seg_len(self) -> float:
        return self.length / self.p.segments

    def payout(self, metres: float) -> None:
        self.length = float(np.clip(self.length + metres, 2.0, self.p.max_length))

    def layout(self, points: list) -> None:
        """Lay the cable along a polyline (spool -> ... -> gland), e.g. pre-wrapped around a pile."""
        pts = np.asarray(points, float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        total = float(s[-1])
        targets = np.linspace(0.0, total, self.p.segments + 1)
        self.x = np.stack([np.interp(targets, s, pts[:, k]) for k in range(3)], axis=1)
        self.v = np.zeros_like(self.x)
        self.length = min(self.p.max_length, total * 1.02)

    def _node_mass(self) -> float:
        l = self.seg_len
        added = RHO * math.pi * (self.p.diameter / 2) ** 2 * l
        return self.p.mass_per_m * l + added

    # ── simulation ───────────────────────────────────────────────────────
    def step(self, dt: float, t_now: float, rov_pos: np.ndarray, rov_q: np.ndarray,
             rov_vel_world: np.ndarray) -> np.ndarray:
        """Advance the cable; returns the body-frame wrench [F; M] the tether applies to the ROV."""
        p = self.p
        gland = rov_pos + q_rot(rov_q, GLAND_BODY)
        h = dt / p.substeps
        f_rov = np.zeros(3)
        self._cur = self.world.current.at_many(self.x[:, 2], self.world.seabed_depth)
        self._cand = self.world.near(self.x.min(axis=0), self.x.max(axis=0), 2.0)
        for _ in range(p.substeps):
            f_rov = self._substep(h, gland, rov_vel_world)
        self._update_metrics(t_now)
        if self.broken:
            self.force_on_rov = np.zeros(3)
            return np.zeros(6)
        self.force_on_rov = f_rov
        f_body = q_rot(q_conj(rov_q), f_rov)
        return np.concatenate([f_body, np.cross(GLAND_BODY, f_body)])

    def _substep(self, h: float, gland: np.ndarray, gland_vel: np.ndarray) -> np.ndarray:
        p, x, v = self.p, self.x, self.v
        n = p.segments
        m = self._node_mass()
        l0 = self.seg_len
        k = min(p.ea / l0, p.k_max)
        c = 2 * p.damping_ratio * math.sqrt(k * m)

        # kinematic ends
        x[0], v[0] = self.spool, 0.0
        if not self.broken:
            x[n], v[n] = gland, gland_vel

        d = x[1:] - x[:-1]
        L = np.linalg.norm(d, axis=1)
        u = d / np.maximum(L, 1e-9)[:, None]
        stretch = L - l0
        rel_v = np.einsum("ij,ij->i", v[1:] - v[:-1], u)
        f_mag = np.where(stretch > 0, k * stretch + c * rel_v, 0.0)       # tension only
        # tension-only, capped at twice the breaking load so a violent yank breaks the cable
        # instead of blowing up the explicit integrator
        f_mag = np.clip(np.nan_to_num(f_mag, nan=0.0, posinf=0.0), 0.0, 2.0 * p.breaking_n)
        f_seg = f_mag[:, None] * u
        F = np.zeros_like(x)
        F[:-1] += f_seg
        F[1:] -= f_seg

        # drag against water moving with the local current
        vr = self._cur - v
        tang = np.zeros_like(x)
        tang[1:-1] = x[2:] - x[:-2]
        tang[0], tang[-1] = d[0], d[-1]
        tang /= np.maximum(np.linalg.norm(tang, axis=1), 1e-9)[:, None]
        vt = np.einsum("ij,ij->i", vr, tang)[:, None] * tang
        vn = vr - vt
        area = p.diameter * l0
        F += 0.5 * RHO * area * (p.cd_normal * vn * np.linalg.norm(vn, axis=1)[:, None]
                                 + p.cd_tangent * vt * np.linalg.norm(vt, axis=1)[:, None])
        F[:, 2] += p.wet_weight_per_m * l0 * G

        v += F / m * h
        x += v * h

        # obstacle contact with friction
        dist, normal, _ = self.world.sdf_many(x, self._cand)
        pen = p.node_radius - dist
        hit = pen > 0
        hit[0] = False
        if not self.broken:
            hit[n] = False
        if np.any(hit):
            x[hit] += normal[hit] * pen[hit, None]
            vn_mag = np.einsum("ij,ij->i", v[hit], normal[hit])
            into = np.minimum(vn_mag, 0.0)
            v[hit] -= into[:, None] * normal[hit]
            vt_vec = v[hit] - np.einsum("ij,ij->i", v[hit], normal[hit])[:, None] * normal[hit]
            vt_n = np.linalg.norm(vt_vec, axis=1)
            reduce = np.clip(1.0 - p.friction * (np.abs(into) + 0.05) / np.maximum(vt_n, 1e-6), 0.0, 1.0)
            v[hit] = v[hit] - vt_vec + vt_vec * reduce[:, None]

        self.tension_spool = float(f_mag[0])
        self.tension_rov = float(f_mag[-1])
        self.tension_max = float(f_mag.max())
        self._seg_tension = f_mag
        return -f_seg[-1] if not self.broken else np.zeros(3)

    def _update_metrics(self, t_now: float) -> None:
        p = self.p
        if self.auto_payout and not self.broken and self.tension_spool > p.payout_threshold_n:
            self.payout(p.payout_rate * 0.01)
        if not self.broken and self.tension_max > p.breaking_n:
            self.broken = True
            self.events.append({"t": round(t_now, 2), "type": "tether_break",
                                "tension_n": round(self.tension_max, 1)})
        dist, _, idx = self.world.sdf_many(self.x, self._cand)
        touching = dist < p.node_radius + 0.02
        touching[0] = False
        self.contact_nodes = int(touching.sum())
        names = sorted({self.world.obstacles[i].name for i in idx[touching] if i >= 0})
        self.snag_names = names
        self.wraps = self._wrap_counts()

    def _wrap_counts(self) -> dict[str, float]:
        """Net turns of cable around each (near-vertical) cylinder, from the cable's winding angle."""
        out = {}
        for ob in self.world.obstacles:
            if not isinstance(ob, Cylinder):
                continue
            a, b = np.asarray(ob.p0, float), np.asarray(ob.p1, float)
            axis = b - a
            if abs(axis[2]) < 0.7 * np.linalg.norm(axis):
                continue
            zmin, zmax = min(a[2], b[2]), max(a[2], b[2])
            near = (self.x[:, 2] >= zmin - 0.5) & (self.x[:, 2] <= zmax + 0.5)
            rel = self.x[:, :2] - a[:2]
            r = np.linalg.norm(rel, axis=1)
            near &= r < ob.radius + 2.5
            ang = np.arctan2(rel[:, 1], rel[:, 0])
            total = 0.0
            for i in range(1, len(ang)):
                if near[i] and near[i - 1]:
                    total += (ang[i] - ang[i - 1] + math.pi) % (2 * math.pi) - math.pi
            turns = total / (2 * math.pi)
            if abs(turns) >= 0.25:
                out[ob.name] = float(round(turns, 2))
        return out

    def state(self) -> dict:
        return {
            "nodes": np.round(self.x, 3).tolist(),
            "length": round(self.length, 1),
            "tension_rov": round(self.tension_rov, 1),
            "tension_spool": round(self.tension_spool, 1),
            "tension_max": round(self.tension_max, 1),
            "warn": self.tension_max > self.p.warn_n,
            "broken": self.broken,
            "contact_nodes": self.contact_nodes,
            "snagged_on": self.snag_names,
            "wraps": self.wraps,
            "auto_payout": self.auto_payout,
            "max_length": self.p.max_length,
        }
