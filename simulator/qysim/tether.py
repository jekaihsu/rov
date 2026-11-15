"""Umbilical tether: lumped-mass cable from the topside reel to the ROV gland.

Model (research_notes/臍帶纜物理與收放文獻/, ranked gaps in simulators_and_current_model.md §Q4)
    * lumped masses joined by tension-only segments with the physical axial stiffness EA / l0 and
      near-critical internal damping, integrated implicitly along the cable (tether_solver.py), so
      stiffness no longer scales with deployed length (gap 3)
    * Morison drag split normal / tangential on the full local flow (World.current_at_many: ambient,
      turbulence, structure wakes) and Morison inertia of accelerating water (Froude-Krylov plus
      normal added mass), added mass normal to the cable only,
      mass and wet weight from one bulk density and diameter (gap 8)
    * a reel with drum inertia, brake and tender / motor rate commands; payout is passive in real
      practice, length enters at the spool end only (reel.py, gap 1)
    * contact on nodes and on samples inside long segments, regularised Coulomb friction from the
      contact normal force, wraps for any cylinder orientation and the wreck field (tether_contact.py,
      gap 2); seabed and structure snags that tighten when pulled (tether_snag.py)
    * twist: net vehicle heading turns with a small restoring torque (gap 4)
    * failure: termination (gland) weak link below the cable strength, working-load warning,
      chafe accumulation on hard contact (gap 6)
X1 values are provisional (vehicles.py X1_TETHER_PARAMETERS); none is an X1 measurement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

import numpy as np

from . import tether_contact, tether_solver
from ._cable_accel import (advance as _advance_compiled, advance_batch as _advance_batch,
                           contact_valid as _valid_compiled, contact_velocity as _contact_compiled,
                           integrate as _integrate_compiled, project as _project_compiled)
from .physics import G, RHO, cross3, q_conj, q_rot
from .reel import MIN_LENGTH_M, Reel, ReelParams
from .tether_snag import SnagParams, SnagTracker
from .vehicles import X1_PARAMETERS, X1_TETHER_PARAMETERS
from .flow import FlowAccelerometer
from .world import World

# Rolling stream of solver events for clients (optional state.tether.events). Matches the radio-window
# length used by tether_ops so a late-joining viewer still sees the recent break / snag / stall / twist.
EVENT_LIMIT = 32
TWIST_WARN_TURNS = 2.0          # same console threshold as tether_ops (warning only; no extra force)

GLAND_BODY = np.array(X1_PARAMETERS["gland_body"]["value"])     # tether strain-relief gland, rear of the hull


def _x1(key):
    return X1_TETHER_PARAMETERS[key]["value"]


@dataclass
class TetherParams:
    segments: int = _x1("segments")
    max_segments: int = _x1("max_segments")
    fine_segments: int = _x1("fine_segments")
    min_segment_m: float = _x1("min_segment_m")
    contact_sample_m: float = _x1("contact_sample_m")
    diameter: float = _x1("diameter")
    density: float = _x1("density")
    mass_per_m: float | None = None          # override of density * area (kg/m in air)
    wet_weight_per_m: float | None = None    # override of mass_per_m - RHO * area (kg/m, + sinks)
    added_mass_normal: float = _x1("added_mass_normal")
    ea: float = _x1("ea")
    damping_ratio: float = _x1("damping_ratio")
    cd_normal: float = _x1("cd_normal")
    cd_tangent: float = _x1("cd_tangent")
    max_length: float = _x1("max_length")
    breaking_n: float = _x1("breaking_n")
    termination_ratio: float = _x1("termination_ratio")
    working_load_ratio: float = _x1("working_load_ratio")
    reel_drum_mass_kg: float = _x1("reel_drum_mass_kg")
    reel_free_drag_n: float = _x1("reel_free_drag_n")
    reel_brake_hold_n: float = _x1("reel_brake_hold_n")
    reel_feed_rate: float = _x1("reel_feed_rate")
    reel_feed_force_n: float = _x1("reel_feed_force_n")
    reel_haul_rate: float = _x1("reel_haul_rate")
    reel_pull_cap_n: float = _x1("reel_pull_cap_n")
    reel_servo_tau: float = _x1("reel_servo_tau")
    auto_setpoint_n: float = _x1("auto_setpoint_n")
    auto_deadband_n: float = _x1("auto_deadband_n")
    auto_gain: float = _x1("auto_gain")
    auto_slack_rate: float = _x1("auto_slack_rate")
    stall_speed: float = _x1("stall_speed")
    stall_time: float = _x1("stall_time")
    reel_mode: str = "free"
    gj: float = _x1("gj")
    node_radius: float = _x1("node_radius")
    mu_static: float = _x1("mu_static")
    mu_kinetic: float = _x1("mu_kinetic")
    stribeck_v: float = _x1("stribeck_v")
    friction_regular_v: float = _x1("friction_regular_v")
    chafe_limit_j: float = _x1("chafe_limit_j")
    chafe_failure: bool = _x1("chafe_failure")
    snag_hook_tension_n: float = _x1("snag_hook_tension_n")
    snag_hook_speed: float = _x1("snag_hook_speed")
    snag_hook_angle_deg: float = _x1("snag_hook_angle_deg")
    snag_release_angle_deg: float = _x1("snag_release_angle_deg")
    snag_release_s: float = _x1("snag_release_s")
    snag_tighten_fraction: float = _x1("snag_tighten_fraction")
    snag_tighten_rate: float = _x1("snag_tighten_rate")
    snag_tighten_max: float = _x1("snag_tighten_max")
    snag_pin_stiffness: float = _x1("snag_pin_stiffness")
    snag_pin_damping: float = _x1("snag_pin_damping")
    snag_cooldown_s: float = _x1("snag_cooldown_s")
    substeps: int = _x1("substeps")
    contact_cache_m: float = _x1("contact_cache_m")
    accelerated: bool = _x1("accelerated")

    # ── derived values ────────────────────────────────────────────────────
    @property
    def area(self) -> float:
        return math.pi * (self.diameter / 2) ** 2

    @property
    def mass(self) -> float:
        """Mass per metre in air (kg/m)."""
        return self.density * self.area if self.mass_per_m is None else self.mass_per_m

    @property
    def wet_weight(self) -> float:
        """Net weight in sea water per metre (kg/m, positive sinks, negative floats)."""
        if self.wet_weight_per_m is not None:
            return self.wet_weight_per_m
        return self.mass - RHO * self.area

    @property
    def gland_breaking_n(self) -> float:
        return self.breaking_n * self.termination_ratio

    @property
    def warn_n(self) -> float:
        """Rated working load of the cable (replaces the former arbitrary 250 N warning)."""
        return self.breaking_n * self.working_load_ratio

    @property
    def gland_warn_n(self) -> float:
        return self.gland_breaking_n * self.working_load_ratio

    @property
    def internal_damping(self) -> float:
        """Segment damping c = zeta * sqrt(EA * w) in N s/m (MoorDyn BA rule, per unit strain rate * l)."""
        return self.damping_ratio * math.sqrt(self.ea * self.mass)

    def reel_params(self) -> ReelParams:
        return ReelParams(self.reel_drum_mass_kg, self.reel_free_drag_n, self.reel_brake_hold_n,
                          self.reel_feed_rate, self.reel_feed_force_n, self.reel_haul_rate,
                          self.reel_pull_cap_n, self.reel_servo_tau, self.auto_setpoint_n,
                          self.auto_deadband_n, self.auto_gain, self.auto_slack_rate,
                          self.stall_speed, self.stall_time)

    def snag_params(self) -> SnagParams:
        return SnagParams(self.snag_hook_tension_n, self.snag_hook_speed, self.snag_hook_angle_deg,
                          self.snag_release_angle_deg, self.snag_release_s, self.snag_tighten_fraction,
                          self.snag_tighten_rate, self.snag_tighten_max, self.snag_pin_stiffness,
                          self.snag_pin_damping, self.snag_cooldown_s)

    @classmethod
    def with_overrides(cls, overrides: dict | None) -> "TetherParams":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (overrides or {}).items() if k in names})


class Tether:
    def __init__(self, world: World, spool_ned: np.ndarray, rov_gland_ned: np.ndarray,
                 length: float | None = None, params: TetherParams | None = None, gland_body=None):
        self.p = params or TetherParams()
        self.gland_body = np.asarray(GLAND_BODY if gland_body is None else gland_body, float)
        self.world = world
        self.spool = np.asarray(spool_ned, float)
        span = float(np.linalg.norm(rov_gland_ned - self.spool))
        total = min(self.p.max_length, length or max(5.0, span * 1.25))
        count = max(1, int(round(total / max(total / self.p.segments, self.p.min_segment_m))))
        self.l_nom = total / count
        self.l0 = np.full(count, self.l_nom)
        self.x = self._bight(self.spool, np.asarray(rov_gland_ned, float), total, count)
        self.v = np.zeros_like(self.x)
        self.chafe = np.zeros(count)
        self.reel = Reel(self.p.reel_params(), self.p.mass, self.p.max_length, self.p.reel_mode)
        self.snags = SnagTracker(self.p.snag_params())
        self.broken = False
        self.break_reason = ""
        self.tension_rov = 0.0
        self.tension_spool = 0.0
        self.tension_max = 0.0
        self.force_on_rov = np.zeros(3)
        self.contact_nodes = 0
        self.snag_names: list[str] = []
        self.wraps: dict[str, float] = {}
        self.events: list[dict] = []
        self.turns = 0.0
        self._twist_warned = False
        self._heading = None
        self._seg_tension = np.zeros(count)
        self.last_batch_complete = False
        self._stepped = False
        self._laid_out = False
        self._contacts = None
        self._contact_key = None
        self._wrap_contacts = None
        self._flow_accel = FlowAccelerometer()      # filtered water acceleration at the nodes (fluid inertia)

    # ── length and reel commands ──────────────────────────────────────────
    @property
    def length(self) -> float:
        """Deployed (unstretched) length."""
        return float(np.sum(self.l0))

    @length.setter
    def length(self, value: float) -> None:
        """Scenario / test set-up only: rescale every segment at once. Operators use the reel."""
        total = float(np.clip(value, MIN_LENGTH_M, self.p.max_length))
        self.l0 *= total / self.length

    @property
    def seg_len(self) -> float:
        return self.length / len(self.l0)

    @property
    def auto_payout(self) -> bool:
        return self.reel.mode == "auto"

    @auto_payout.setter
    def auto_payout(self, value: bool) -> None:
        """Legacy toggle: on = constant-tension controller, off = hold the current length."""
        self.reel.command("auto" if value else "hold")

    def payout(self, metres: float) -> None:
        """Legacy ``payout`` message: move the deployed length by ``metres`` at the reel's rate."""
        base = self.reel.target if self.reel.target is not None else self.length
        self.reel.request_length(base + metres, self.length)

    def reel_command(self, command: str) -> None:
        self.reel.command(command)

    def layout(self, points: list) -> None:
        """Lay the cable along a polyline (spool -> ... -> gland), e.g. pre-wrapped around a pile."""
        pts = np.asarray(points, float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        total = float(s[-1])
        count = self.p.segments
        targets = np.linspace(0.0, total, count + 1)
        self.x = np.stack([np.interp(targets, s, pts[:, k]) for k in range(3)], axis=1)
        self.v = np.zeros_like(self.x)
        length = min(self.p.max_length, total * 1.02)
        self.l_nom = length / count
        self.l0 = np.full(count, self.l_nom)
        self.chafe = np.zeros(count)
        self._seg_tension = np.zeros(count)
        self.snags.clear()
        self._laid_out = True
        self._reset_flow_nodes()
        self._contacts = None

    def _bight(self, a: np.ndarray, b: np.ndarray, length: float, n: int) -> np.ndarray:
        """Nodes along a smooth slack curve of arc length ``length`` from ``a`` to ``b``.

        The excess cable hangs as a bight that sags a little and streams down-current (how a
        near-neutral umbilical actually lies), instead of being squeezed onto the straight line."""
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
        """Let the cable relax in the current with the ROV held still and the reel braked."""
        mode, target = self.reel.mode, self.reel.target
        self.reel.command("hold")
        for _ in range(int(seconds / dt)):
            self.step(dt, 0.0, rov_pos, rov_q, np.zeros(3))
        self.reel.command(mode)
        self.reel.target = target
        self.reel.state[0] = 0.0
        self.v[:] = 0.0
        self.events.clear()
        self.reel.events.clear()
        self.snags.clear()
        self.snags.events.clear()
        self.turns = 0.0
        self._twist_warned = False
        self._heading = None

    # ── discretisation ────────────────────────────────────────────────────
    def _node_masses(self):
        """Per-node structural mass, normal added mass and hydrodynamic length (half segments at ends)."""
        lw = np.zeros(len(self.l0) + 1)
        lw[:-1] += 0.5 * self.l0
        lw[1:] += 0.5 * self.l0
        ms = self.p.mass * lw
        ma = self.p.added_mass_normal * RHO * self.p.area * lw
        return np.maximum(ms, 1e-9), ma, lw

    def _insert_node(self, seg: int, frac: float) -> None:
        """Split segment ``seg`` at ``frac`` (0 = spool-side node) without changing the cable shape."""
        self._contacts = None
        self._edit_flow_nodes(lambda a: np.insert(a, seg + 1, (1.0 - frac) * a[seg] + frac * a[seg + 1], axis=0))
        point = (1.0 - frac) * self.x[seg] + frac * self.x[seg + 1]
        vel = (1.0 - frac) * self.v[seg] + frac * self.v[seg + 1]
        rest = self.l0[seg]
        self.x = np.insert(self.x, seg + 1, point, axis=0)
        self.v = np.insert(self.v, seg + 1, vel, axis=0)
        self.l0 = np.concatenate([self.l0[:seg], [frac * rest, (1.0 - frac) * rest], self.l0[seg + 1:]])
        self.chafe = np.insert(self.chafe, seg, self.chafe[seg])
        self._seg_tension = np.insert(self._seg_tension, seg, self._seg_tension[seg])

    def _edit_flow_nodes(self, edit) -> None:
        """Keep the per-node water-acceleration history aligned when nodes are inserted or removed."""
        meter = self._flow_accel
        if isinstance(meter, FlowAccelerometer) and meter.previous is not None and len(meter.previous) == len(self.x):
            meter.previous = edit(meter.previous)
            meter.value = edit(meter.value)

    def _reset_flow_nodes(self) -> None:
        """Nodes jumped (lay-out, teleport): restart the water-acceleration estimate instead of
        reading the jump as an acceleration of the water."""
        if isinstance(self._flow_accel, FlowAccelerometer):
            self._flow_accel.reset()

    def split_segment(self, seg: int, frac: float) -> None:
        self._insert_node(seg, frac)

    def _remove_node(self, node: int) -> None:
        """Merge the two segments that meet at interior ``node``."""
        self._contacts = None
        self._edit_flow_nodes(lambda a: np.delete(a, node, axis=0))
        self.l0[node - 1] += self.l0[node]
        self.l0 = np.delete(self.l0, node)
        self.chafe[node - 1] = max(self.chafe[node - 1], self.chafe[node])
        self.chafe = np.delete(self.chafe, node)
        self._seg_tension[node - 1] = max(self._seg_tension[node - 1], self._seg_tension[node])
        self._seg_tension = np.delete(self._seg_tension, node)
        self.x = np.delete(self.x, node, axis=0)
        self.v = np.delete(self.v, node, axis=0)

    def _resegment(self) -> None:
        """Payout grows segment 0; split it when long, merge it when short, coarsen when too many."""
        target = self.l_nom
        while self.l0[0] > 1.5 * target:
            self._insert_node(0, 1.0 - target / self.l0[0])
        while len(self.l0) > 1 and self.l0[0] < 0.3 * target:
            self._remove_node(1)
        hooked = [h.s_rov for h in self.snags.hooks]
        while len(self.l0) > self.p.max_segments:
            n = len(self.l0)
            last = n - 1 - self.p.fine_segments
            if last <= 1:
                break
            pair = self.l0[1:last] + self.l0[2:last + 1]
            from_end = np.cumsum(self.l0[::-1])[::-1]          # rest length from node j to the gland
            order = np.argsort(pair, kind="stable")
            for k in order:
                node = int(k) + 2
                if not any(abs(from_end[node] - s) < 1e-6 for s in hooked):
                    self._remove_node(node)
                    break
            else:
                break

    # ── simulation ───────────────────────────────────────────────────────
    def step(self, dt: float, t_now: float, rov_pos: np.ndarray, rov_q: np.ndarray,
             rov_vel_world: np.ndarray) -> np.ndarray:
        """Advance the cable; returns the body-frame wrench [F; M] the tether applies to the ROV."""
        p = self.p
        gland = rov_pos + q_rot(rov_q, self.gland_body)
        gland_vel = np.asarray(rov_vel_world, float)
        h = dt / p.substeps
        self._reseat(gland)
        # Full local flow (ambient + turbulence + structure wakes) and its filtered rate of change.
        water = self.world.current_at_many(self.x, t_now)
        self._cur = water
        water_accel = self._flow_accel.update(water, dt)
        self._cand = self.world.near(self.x.min(axis=0), self.x.max(axis=0), 3.0)
        contacts = self._reuse_contacts()
        ms, ma, lw = self._node_masses()
        reel = self.reel.prepare(self.length)
        pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap = self.snags.pins(self.l0)
        pin_force = np.zeros(len(pin_seg))
        tension = np.zeros(len(self.l0))
        args = (water, water_accel, ms, ma, lw, gland, gland_vel, h, reel, pin_seg, pin_s, pin_target, pin_k,
                pin_c, pin_cap, pin_force, tension)
        complete = False
        if p.accelerated and _advance_batch is not None and p.contact_cache_m > 0:
            complete, f_rov, peaks, contacts = self._run_batch(contacts, *args)
        self.last_batch_complete = bool(complete)
        self._stepped = True
        if not complete:
            f_rov, peaks, contacts = self._run_loop(contacts, *args)
        self._seg_tension = tension.copy()
        self.tension_spool = float(tension[0])
        self.tension_rov = float(peaks[1])
        self.tension_max = float(peaks[0])
        self.reel.finish(dt, t_now)
        self._contacts = contacts
        self._update_metrics(contacts, pin_force, dt, t_now)
        self._resegment()
        wrench = np.zeros(6)
        if self.broken:
            self.force_on_rov = np.zeros(3)
            return wrench
        self.force_on_rov = f_rov
        f_body = q_rot(q_conj(rov_q), f_rov)
        wrench[:3] = f_body
        wrench[3:] = cross3(self.gland_body, f_body) + self._twist_moment(rov_q)
        return wrench

    def translate(self, delta: np.ndarray) -> None:
        """Move the cable with a teleported vehicle: nodes 1..n shift by ``delta``, the spool stays.

        The spool segment takes up the change; if it got longer the extra rest length is treated as
        paid out (a teleport is not physical, and a stiff cable must not see it as a stretch)."""
        self.x[1:] += np.asarray(delta, float)
        self.x[0] = self.spool
        self._reset_flow_nodes()
        span = float(np.linalg.norm(self.x[1] - self.x[0]))
        if span > self.l0[0]:
            self.l0[0] = min(span, self.l0[0] + max(self.p.max_length - self.length, 0.0))

    def _reseat(self, gland: np.ndarray) -> None:
        """Teleport guard: if the gland is far from the cable end (scenario set-up, a vehicle placed
        by a test or tool), move the cable with it instead of feeding the jump to the stiff cable."""
        if self.broken:
            return
        delta = gland - self.x[-1]
        if float(np.dot(delta, delta)) <= 0.05 ** 2:
            return
        if not self._stepped and not self._laid_out:
            # never simulated: lay the default bight to where the gland really is
            self.x = self._bight(self.spool, gland, self.length, len(self.l0))
            self.v[:] = 0.0
            self._reset_flow_nodes()
            return
        self.translate(delta)

    def _reuse_contacts(self):
        """Keep last tick's contact planes while every point is still well inside its cache distance.

        Same rule the substep loop uses, applied across ticks; the set is rebuilt whenever the
        segmentation, the broken state or the nearby obstacles change."""
        p = self.p
        key = (len(self.l0), self.broken, tuple(self._cand))
        cached = self._contacts
        if (cached is not None and p.contact_cache_m > 0 and self._contact_key == key and
                self._valid_reference(cached)):
            return cached
        self._contact_key = key
        return self._build_contacts()

    def _valid_reference(self, c) -> bool:
        compiled = self.p.accelerated and _valid_compiled is not None
        valid = _valid_compiled if compiled else tether_solver.contact_valid
        # half the cache distance, so the whole next tick usually fits inside the compiled batch
        half = 0.5 * self.p.contact_cache_m
        return bool(valid(self.x, c.seg, c.s, c.anchor, c.dist0, self.p.node_radius, half))

    def _build_contacts(self):
        p = self.p
        return tether_contact.build(self.world, self.x, self._cand, self.broken, p.node_radius,
                                    p.contact_sample_m, p.contact_cache_m)

    def _solver_scalars(self):
        p = self.p
        return (p.ea, p.internal_damping, p.diameter, p.cd_normal, p.cd_tangent, p.wet_weight * G, RHO,
                2.0 * p.breaking_n)

    def _friction(self):
        p = self.p
        return p.node_radius, p.mu_static, p.mu_kinetic, p.stribeck_v, p.friction_regular_v

    def _run_batch(self, contacts, water, water_accel, ms, ma, lw, gland, gland_vel, h, reel, pin_seg, pin_s,
                   pin_target, pin_k, pin_c, pin_cap, pin_force, tension):
        p = self.p
        saved = (self.x.copy(), self.v.copy(), self.l0.copy(), reel.copy(), self.chafe.copy())
        f_rov = np.zeros(3)
        peaks = np.zeros(2)
        ea, damping, diameter, cdn, cdt, wet, rho, cap = self._solver_scalars()
        radius, mu_s, mu_k, v_s, v_reg = self._friction()
        c = contacts
        ok = _advance_batch(self.x, self.v, water, water_accel, self.l0, ms, ma, lw, self.spool, gland, gland_vel,
                            self.broken, h, ea, damping, diameter, cdn, cdt, wet, rho, cap, reel,
                            pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension,
                            p.substeps, c.seg, c.s, c.anchor, c.dist0, c.normal, c.hard, p.contact_cache_m,
                            radius, mu_s, mu_k, v_s, v_reg, self.chafe, f_rov, peaks)
        if not ok:
            self.x, self.v, self.l0 = saved[0], saved[1], saved[2]
            reel[:] = saved[3]
            self.chafe = saved[4]
        return ok, f_rov, peaks, contacts

    def _run_loop(self, contacts, water, water_accel, ms, ma, lw, gland, gland_vel, h, reel, pin_seg, pin_s,
                  pin_target, pin_k, pin_c, pin_cap, pin_force, tension):
        """Substep loop that refreshes contact planes when they expire (reference geometry path)."""
        p = self.p
        compiled = p.accelerated and _advance_compiled is not None
        advance = _advance_compiled if compiled else tether_solver.advance
        valid = _valid_compiled if compiled else tether_solver.contact_valid
        contact = _contact_compiled if compiled else tether_solver.contact_velocity
        integrate = _integrate_compiled if compiled else tether_solver.integrate
        project = _project_compiled if compiled else tether_solver.project
        ea, damping, diameter, cdn, cdt, wet, rho, cap = self._solver_scalars()
        radius, mu_s, mu_k, v_s, v_reg = self._friction()
        f_rov = np.zeros(3)
        peaks = np.zeros(2)
        pin_peak = np.zeros(len(pin_seg))
        for step in range(p.substeps):
            point = gland + gland_vel * h * (step + 1)
            out = advance(self.x, self.v, water, water_accel, self.l0, ms, ma, lw, self.spool, point, gland_vel,
                          self.broken, h, ea, damping, diameter, cdn, cdt, wet, rho, cap, reel, pin_seg, pin_s, pin_target,
                          pin_k, pin_c, pin_cap, pin_force, tension)
            pin_peak = np.maximum(pin_peak, pin_force)
            f_rov += out / p.substeps
            peaks[0] = max(peaks[0], float(tension.max()))
            peaks[1] = max(peaks[1], float(tension[-1]))
            c = contacts
            if p.contact_cache_m <= 0 or not valid(self.x, c.seg, c.s, c.anchor, c.dist0, p.node_radius,
                                                   p.contact_cache_m):
                contacts = self._build_contacts()
                c = contacts
            contact(self.x, self.v, ms, ma, self.broken, h, c.seg, c.s, c.anchor, c.dist0, c.normal, c.hard,
                    radius, mu_s, mu_k, v_s, v_reg, self.chafe)
            integrate(self.x, self.v, h, self.broken)
            project(self.x, self.broken, c.seg, c.s, c.anchor, c.dist0, c.normal, radius)
        pin_force[:] = pin_peak
        return f_rov, peaks, contacts

    def _twist_moment(self, rov_q: np.ndarray) -> np.ndarray:
        """Count net heading turns (twist put into the tether) and return the restoring body moment.

        The far end never rotates (a reel slip ring passes power, it does not untwist the cable,
        shipboard_handling.md §6), so the twist the vehicle adds is its net heading change: by the
        rod identity Lk = Tw + Wr, loops formed while circling turn into twist once the cable is
        pulled straight [inferred]. Torque = GJ * twist angle / deployed length about the vertical.
        Buckham 2003 notes a twist-flexible termination behaves like GJ ~ 0 (cable_dynamics_models.md §2),
        so this is an upper estimate and stays small (0.016 N m per turn on 40 m)."""
        forward = q_rot(rov_q, np.array([1.0, 0.0, 0.0]))
        heading = math.atan2(forward[1], forward[0])
        if self._heading is not None:
            self.turns += ((heading - self._heading + math.pi) % (2 * math.pi) - math.pi) / (2 * math.pi)
        self._heading = heading
        return q_rot(q_conj(rov_q), np.array([0.0, 0.0, self.twist_torque_nm]))

    @property
    def twist_torque_nm(self) -> float:
        """Restoring moment about the vertical from the net twist (GJ * twist angle / deployed length)."""
        return -self.p.gj * 2 * math.pi * self.turns / max(self.length, MIN_LENGTH_M)

    def _update_metrics(self, contacts, pin_force, dt: float, t_now: float) -> None:
        p = self.p
        n = len(self.x) - 1
        if not self.broken and self.tension_rov > p.gland_breaking_n:
            self._break(t_now, "gland", self.tension_rov)
        if not self.broken and self.tension_max > p.breaking_n:
            self._break(t_now, "cable", self.tension_max)
        if not self.broken and p.chafe_failure and self.chafe_fraction >= 1.0:
            self._break(t_now, "chafe", self.tension_max)
        touch = tether_contact.touching(contacts, self.x, p.node_radius, max(p.contact_cache_m, 0.0))
        node_touch = np.zeros(n + 1, bool)
        node_obstacle = np.full(n + 1, -1)
        k = contacts.node_count
        valid = contacts.seg[:k] + np.round(contacts.s[:k]).astype(np.int64) <= n
        nodes = (contacts.seg[:k] + np.round(contacts.s[:k]).astype(np.int64))[valid]
        node_touch[nodes] = touch[:k][valid]
        node_obstacle[nodes] = contacts.obstacle[:k][valid]
        self.contact_nodes = int(node_touch.sum())
        names = sorted({self.world.obstacles[i].name for i in contacts.obstacle[touch] if i >= 0})
        self.snag_names = names
        if contacts is not self._wrap_contacts:
            # winding only changes once points have moved; reused contact planes mean they have not
            self.wraps = tether_contact.wrap_counts(self.world, self.x, self._cand, node_touch, node_obstacle)
            self._wrap_contacts = contacts
        self.snags.update(self, contacts, touch, pin_force, dt, t_now)
        self.events.extend(self.reel.events)
        self.reel.events.clear()
        self.events.extend(self.snags.events)
        self.snags.events.clear()
        # Warn past ±2 turns; re-arm below 1.75 so yaw jitter at the threshold does not repeat the event.
        twist_warning = abs(self.turns) > TWIST_WARN_TURNS or (self._twist_warned and abs(self.turns) > 1.75)
        if twist_warning and not self._twist_warned:
            self.events.append({"t": round(t_now, 2), "type": "tether_twist",
                                "turns": round(self.turns, 2)})
        self._twist_warned = twist_warning

    def _break(self, t_now: float, reason: str, tension: float) -> None:
        self.broken = True
        self.break_reason = reason
        self.events.append({"t": round(t_now, 2), "type": "tether_break", "where": reason,
                            "tension_n": round(tension, 1)})

    @property
    def chafe_fraction(self) -> float:
        return float(self.chafe.max() / self.p.chafe_limit_j) if len(self.chafe) else 0.0

    @property
    def over_working_load(self) -> bool:
        """Cable above its rated working load, or the gland above the termination's working load."""
        return self.tension_max > self.p.warn_n or self.tension_rov > self.p.gland_warn_n

    def state(self) -> dict:
        return {
            "nodes": np.round(self.x, 3).tolist(),
            "length": round(self.length, 1),
            "tension_rov": round(self.tension_rov, 1),
            "tension_spool": round(self.tension_spool, 1),
            "tension_max": round(self.tension_max, 1),
            "warn": self.over_working_load,
            "broken": self.broken,
            "contact_nodes": self.contact_nodes,
            "snagged_on": self.snag_names,
            "wraps": self.wraps,
            "auto_payout": self.auto_payout,
            "max_length": self.p.max_length,
            "reel": self.reel.state_dict(),
            "turns": round(self.turns, 2),
            "snags": self.snags.state(),
            "chafe": round(min(self.chafe_fraction, 1.0), 3),
            "working_load_n": round(self.p.warn_n, 1),
            "gland_working_load_n": round(self.p.gland_warn_n, 1),
            "break_reason": self.break_reason or None,
            # Optional: recent solver events. Absent on older hosts; clients that ignore it keep working.
            "events": list(self.events[-EVENT_LIMIT:]),
        }


# von Benzon 2022, Table A1; only measured diameter/mass and cited drag terms.
# Remaining solver settings are simulator estimates, not a reconstruction of
# the paper's axial stiffness (6.437e10 Pa) or complete inspection trajectory.
BENCHMARK_TETHER_PARAMETERS = {
    "diameter": .0075,
    "mass_per_m": .043,
    "cd_normal": 1.2,
    "cd_tangent": .01,
}
