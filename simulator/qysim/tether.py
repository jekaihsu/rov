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

from .physics import G, RHO, q_rot, q_conj, cross3
from .world import World, Cylinder
from ._cable_accel import advance as _advance_compiled, advance_batch as _advance_batch

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
    contact_cache_m: float = 0.01     # max displacement before refreshing local contact planes
    accelerated: bool = True         # optional Numba kernel; equations match NumPy fallback


class Tether:
    def __init__(self, world: World, spool_ned: np.ndarray, rov_gland_ned: np.ndarray,
                 length: float | None = None, params: TetherParams | None = None, gland_body=None):
        self.p = params or TetherParams()
        self.gland_body = np.asarray(GLAND_BODY if gland_body is None else gland_body, float)
        self.world = world
        self.spool = np.asarray(spool_ned, float)
        span = float(np.linalg.norm(rov_gland_ned - self.spool))
        self.length = min(self.p.max_length, length or max(5.0, span * 1.25))
        self.x = self._bight(self.spool, np.asarray(rov_gland_ned, float), self.length)
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

    def _bight(self, a: np.ndarray, b: np.ndarray, length: float) -> np.ndarray:
        """Nodes along a smooth slack curve of arc length ``length`` from ``a`` to ``b``.

        The excess cable hangs as a bight that sags a little and streams down-current (how a
        near-neutral umbilical actually lies), instead of being squeezed onto the straight line."""
        n = self.p.segments
        mid = 0.5 * (a + b)
        cur = self.world.current.mean_at(float(mid[2]), self.world.seabed_depth)
        side = np.array([cur[0], cur[1], 0.0])
        if np.linalg.norm(side) < 1e-3:                       # slack water: bow out sideways
            ab = b - a
            side = np.array([-ab[1], ab[0], 0.0])
            if np.linalg.norm(side) < 1e-6:
                side = np.array([0.0, 1.0, 0.0])
        side /= np.linalg.norm(side)
        bow = side * 0.8 + np.array([0.0, 0.0, 0.6])          # downstream and a bit deeper
        bow /= np.linalg.norm(bow)
        tt = np.linspace(0.0, 1.0, 400)[:, None]

        def curve(h: float) -> np.ndarray:
            c = mid + bow * h
            return (1 - tt) ** 2 * a + 2 * (1 - tt) * tt * c + tt ** 2 * b

        def arc(h: float) -> float:
            return float(np.linalg.norm(np.diff(curve(h), axis=0), axis=1).sum())

        lo, hi = 0.0, max(1.0, length)
        if arc(0.0) >= length:
            pts = curve(0.0)
        else:
            while arc(hi) < length:
                hi *= 2
            for _ in range(40):
                h = 0.5 * (lo + hi)
                lo, hi = (h, hi) if arc(h) < length else (lo, h)
            pts = curve(0.5 * (lo + hi))
        # keep it out of the seabed and below the surface
        pts[:, 2] = np.clip(pts[:, 2], 0.0, self.world.seabed_depth - 0.05)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        targets = np.linspace(0.0, s[-1], n + 1)
        return np.stack([np.interp(targets, s, pts[:, k]) for k in range(3)], axis=1)

    def settle(self, seconds: float, rov_pos: np.ndarray, rov_q: np.ndarray, dt: float = 0.01) -> None:
        """Let the cable relax in the current with the ROV held still (before the run starts)."""
        auto, self.auto_payout = self.auto_payout, False
        for _ in range(int(seconds / dt)):
            self.step(dt, 0.0, rov_pos, rov_q, np.zeros(3))
        self.auto_payout = auto
        self.v[:] = 0.0
        self.events.clear()

    def _node_mass(self) -> float:
        l = self.seg_len
        added = RHO * math.pi * (self.p.diameter / 2) ** 2 * l
        return self.p.mass_per_m * l + added

    # ── simulation ───────────────────────────────────────────────────────
    def step(self, dt: float, t_now: float, rov_pos: np.ndarray, rov_q: np.ndarray,
             rov_vel_world: np.ndarray) -> np.ndarray:
        """Advance the cable; returns the body-frame wrench [F; M] the tether applies to the ROV."""
        p = self.p
        gland = rov_pos + q_rot(rov_q, self.gland_body)
        h = dt / p.substeps
        f_rov = np.zeros(3)
        self._cur = self.world.current.sample_many(self.x, self.world.seabed_depth, t_now)
        self._cand = self.world.near(self.x.min(axis=0), self.x.max(axis=0), 2.0)
        self._contact_anchor = None
        complete = False
        if p.accelerated and _advance_batch is not None and p.contact_cache_m > 0:
            anchor,saved_v = self.x.copy(),self.v.copy()
            distances,normals,_ = self.world.sdf_many(anchor,self._cand)
            mass,rest = self._node_mass(),self.seg_len
            stiffness = min(p.ea/rest,p.k_max)
            damping = 2*p.damping_ratio*math.sqrt(stiffness*mass)
            complete,magnitudes,f_rov = _advance_batch(self.x,self.v,self._cur,self.spool,gland,
                rov_vel_world,self.broken,h,mass,rest,stiffness,damping,p.diameter,p.cd_normal,
                p.cd_tangent,p.wet_weight_per_m,p.breaking_n,p.substeps,anchor,distances,normals,
                p.contact_cache_m,p.node_radius,p.friction)
            if complete:
                self.tension_spool,self.tension_rov = float(magnitudes[0]),float(magnitudes[-1])
                self.tension_max = float(magnitudes.max())
                self._seg_tension = magnitudes
            else:
                self.x[:],self.v[:] = anchor,saved_v
        self.last_batch_complete = bool(complete)
        if not complete:
            for _ in range(p.substeps):
                f_rov = self._substep(h, gland, rov_vel_world)
        self._update_metrics(t_now)
        if self.broken:
            self.force_on_rov = np.zeros(3)
            return np.zeros(6)
        self.force_on_rov = f_rov
        f_body = q_rot(q_conj(rov_q), f_rov)
        return np.concatenate([f_body, cross3(self.gland_body, f_body)])

    def _substep(self, h: float, gland: np.ndarray, gland_vel: np.ndarray) -> np.ndarray:
        p, x, v = self.p, self.x, self.v
        n = p.segments
        m = self._node_mass()
        l0 = self.seg_len
        k = min(p.ea / l0, p.k_max)
        c = 2 * p.damping_ratio * math.sqrt(k * m)

        if p.accelerated and _advance_compiled is not None:
            f_mag, force = _advance_compiled(x,v,self._cur,self.spool,gland,gland_vel,self.broken,
                                             h,m,l0,k,c,p.diameter,p.cd_normal,p.cd_tangent,
                                             p.wet_weight_per_m,p.breaking_n)
            self._resolve_contact()
            self.tension_spool = float(f_mag[0])
            self.tension_rov = float(f_mag[-1])
            self.tension_max = float(f_mag.max())
            self._seg_tension = f_mag
            return force

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

        self._resolve_contact()
        self.tension_spool = float(f_mag[0])
        self.tension_rov = float(f_mag[-1])
        self.tension_max = float(f_mag.max())
        self._seg_tension = f_mag
        return -f_seg[-1] if not self.broken else np.zeros(3)

    def _resolve_contact(self):
        p,x,v = self.p,self.x,self.v
        n = p.segments

        # obstacle contact with friction
        # Retain every force-integration substep. Static contact geometry changes
        # little within a 10 ms tick: use a local tangent plane until any node
        # moves 1 cm, then refresh. Flat seabeds remain exact; curved proxies are
        # approximated over a distance below the 3 cm cable collision radius.
        if (self._contact_anchor is None or p.contact_cache_m <= 0 or
                np.max(np.sum((x-self._contact_anchor)**2,axis=1)) > p.contact_cache_m**2):
            self._contact_anchor = x.copy()
            self._contact_dist, self._contact_normal, _ = self.world.sdf_many(x, self._cand)
        normal = self._contact_normal
        dist = self._contact_dist + np.einsum('ij,ij->i',x-self._contact_anchor,normal)
        pen = np.minimum(p.node_radius - dist, 0.05)     # push out at most 5 cm per substep
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
            if not isinstance(ob, Cylinder) or ob.kind == "habitat":
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
