"""Tether snags: hooking on seabed items and snaggable structures, tightening and release.

Grounded in the snag accounts in research_notes/真实 ROV 操作体验研究/operations_tether_sonar.md:
    * a tether lying on the bottom catches on rocks, debris, lines and wreck parts (§1, §7)
    * "Do NOT pull the tether": pulling tightened the Lake Michigan snag on the Senator wreck (§7 B)
    * the recovery procedure is to turn round, follow the tether back to the snag and back out the
      way the vehicle came (VideoRay emergency snag response, §1)

Model (all thresholds provisional training settings; no published snag-strength data exists):
    hook     a cable point touches a snaggable obstacle (``SnagFeature`` or an obstacle with
             ``snag_hold``) while that segment carries tension and is dragged sideways across it,
             or bends round it by more than ``hook_angle_deg``
    hold     the hooked cable point is pinned to the feature by a stiff spring whose force is
             capped at the holding force; beyond the cap the cable drags through the snag
    tighten  while the vehicle-side pull exceeds a fraction of the holding force, the holding force
             grows (the knot tightens), up to ``tighten_max`` times its drawn value
    release  once the vehicle has come back and moved to the other side, the cable no longer bends
             round the feature in the hooked sense; with low vehicle-side tension for
             ``release_s`` the snag lets go
A neutral tether held off the bottom never touches low seabed items, so it cannot hook on them;
a negative tether lying on the seabed can.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

import numpy as np


@dataclass
class SnagParams:
    hook_tension_n: float
    hook_speed: float
    hook_angle_deg: float
    release_angle_deg: float
    release_s: float
    tighten_fraction: float
    tighten_rate: float
    tighten_max: float
    pin_stiffness: float
    pin_damping: float
    cooldown_s: float


@dataclass
class Hook:
    obstacle: int
    name: str
    target: np.ndarray
    s_rov: float             # rest length from the gland to the hooked cable point
    hold_n: float
    base_hold_n: float
    since: float
    sense: float             # sign of the horizontal bend when it hooked
    force_n: float = 0.0
    tension_n: float = 0.0
    slack_clock: float = 0.0


def snag_hold(ob):
    """(min, max) holding force for a snaggable obstacle, or None."""
    return getattr(ob, "snag_hold", None)


def drawn_hold(name: str, seed: int, hold: tuple) -> float:
    rng = np.random.default_rng((zlib.crc32(name.encode("utf-8")) ^ int(seed)) & 0xFFFFFFFF)
    lo, hi = float(hold[0]), float(hold[1])
    return lo + (hi - lo) * float(rng.random())


def locate(l0: np.ndarray, s_rov: float) -> tuple[int, float]:
    """(segment, fraction from its spool-side node) of the cable point s_rov metres from the gland."""
    from_end = np.cumsum(l0[::-1])
    k = int(np.searchsorted(from_end, s_rov))
    k = min(k, len(l0) - 1)
    seg = len(l0) - 1 - k
    start_from_end = from_end[k]                # rest distance from the gland to the spool-side node
    frac = 1.0 - (s_rov - (start_from_end - l0[seg])) / max(l0[seg], 1e-9)
    return seg, float(np.clip(frac, 0.0, 1.0))


def chord_bend(x: np.ndarray, l0: np.ndarray, node: int, reach: float = 1.5) -> float:
    """Signed horizontal bend at ``node`` between chords ``reach`` metres of cable to either side.

    Chords instead of the two adjacent segments, so a slack loop next to the snag does not hide
    which side of the feature the cable leaves on."""
    n = len(x) - 1
    if node <= 0 or node >= n:
        return 0.0
    back = node - 1
    walked = l0[back]
    while back > 0 and walked < reach:
        back -= 1
        walked += l0[back]
    ahead = node + 1
    walked = l0[node]
    while ahead < n and walked < reach:
        walked += l0[ahead]
        ahead += 1
    return horizontal_bend(x[node] - x[back], x[ahead] - x[node])


def horizontal_bend(before: np.ndarray, after: np.ndarray) -> float:
    """Signed angle (rad) between two directions projected on the horizontal plane."""
    a = before[:2]
    b = after[:2]
    if np.linalg.norm(a) < 1e-6 or np.linalg.norm(b) < 1e-6:
        return 0.0
    return math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])


class SnagTracker:
    def __init__(self, params: SnagParams):
        self.p = params
        self.hooks: list[Hook] = []
        self.cooldown: dict[str, float] = {}
        self.events: list[dict] = []

    def clear(self) -> None:
        self.hooks.clear()
        self.cooldown.clear()

    def pins(self, l0: np.ndarray):
        """Solver arrays for the hooks: segment, fraction, target, stiffness, damping, cap."""
        k = len(self.hooks)
        seg = np.zeros(k, np.int64)
        frac = np.zeros(k)
        target = np.zeros((k, 3))
        for j, hook in enumerate(self.hooks):
            seg[j], frac[j] = locate(l0, hook.s_rov)
            target[j] = hook.target
        stiff = np.full(k, self.p.pin_stiffness)
        damp = np.full(k, self.p.pin_damping)
        cap = np.array([h.hold_n for h in self.hooks], float)
        return seg, frac, target, stiff, damp, cap

    def update(self, tether, contacts, touch: np.ndarray, pin_force: np.ndarray, dt: float, t_now: float):
        """Advance existing hooks and look for new ones; may insert a node at a new hook point."""
        x, l0, tension = tether.x, tether.l0, tether._seg_tension
        p = self.p
        kept = []
        for hook, force in zip(self.hooks, pin_force):
            seg, frac = locate(l0, hook.s_rov)
            hook.force_n = float(force)
            hook.tension_n = float(tension[min(seg + (1 if frac > 0.5 else 0), len(l0) - 1)])
            if force > hook.hold_n:
                hook.s_rov = self._closest_s_rov(x, l0, hook.target)
            if hook.tension_n > p.tighten_fraction * hook.hold_n:
                grow = p.tighten_rate * (hook.tension_n - p.tighten_fraction * hook.hold_n) * dt
                hook.hold_n = min(hook.hold_n + grow, p.tighten_max * hook.base_hold_n)
            node = seg + (1 if frac > 0.5 else 0)
            bend = chord_bend(x, l0, node)
            unwound = hook.sense * bend < math.radians(p.release_angle_deg)
            if unwound and hook.tension_n < 0.5 * hook.hold_n:
                hook.slack_clock += dt
            else:
                hook.slack_clock = 0.0
            if hook.slack_clock >= p.release_s or tether.broken:
                self.cooldown[hook.name] = t_now + p.cooldown_s
                self.events.append({"t": round(t_now, 2), "type": "tether_snag_released", "obstacle": hook.name})
                continue
            kept.append(hook)
        self.hooks = kept
        if not tether.broken:
            self._hook_new(tether, contacts, touch, t_now)

    def _closest_s_rov(self, x, l0, target):
        a, b = x[:-1], x[1:]
        ab = b - a
        t = np.clip(np.einsum("ij,ij->i", target - a, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-12),
                    0.0, 1.0)
        d = np.linalg.norm(a + t[:, None] * ab - target, axis=1)
        seg = int(np.argmin(d))
        return float(np.sum(l0[seg + 1:]) + (1.0 - t[seg]) * l0[seg])

    def _hook_new(self, tether, contacts, touch, t_now):
        p = self.p
        world, x, v, l0 = tether.world, tether.x, tether.v, tether.l0
        n = len(x) - 1
        held = {h.name for h in self.hooks}
        for k in np.flatnonzero(touch & (contacts.obstacle >= 0)):
            index = int(contacts.obstacle[k])
            ob = world.obstacles[index]
            hold = snag_hold(ob)
            if hold is None or ob.name in held or self.cooldown.get(ob.name, -1.0) > t_now:
                continue
            seg, frac = int(contacts.seg[k]), float(contacts.s[k])
            if seg >= n or tether._seg_tension[seg] < p.hook_tension_n:
                continue
            u = x[seg + 1] - x[seg]
            u /= max(np.linalg.norm(u), 1e-9)
            vel = (1.0 - frac) * v[seg] + frac * v[seg + 1]
            sideways = vel - np.dot(vel, u) * u
            node = seg + (1 if frac > 0.5 else 0)
            bend = chord_bend(x, l0, node)
            dragged = np.linalg.norm(sideways) > p.hook_speed
            wrapped = abs(bend) > math.radians(p.hook_angle_deg)
            if not (dragged or wrapped):
                continue
            point = (1.0 - frac) * x[seg] + frac * x[seg + 1]
            if 0.0 < frac < 1.0 and 0.15 < frac * l0[seg] and 0.15 < (1.0 - frac) * l0[seg]:
                tether.split_segment(seg, frac)
                node = seg + 1
            else:
                node = seg if frac <= 0.5 else seg + 1
            if node <= 0 or node >= n + (1 if tether.broken else 0):
                continue
            s_rov = float(np.sum(tether.l0[node:]))
            if wrapped:
                sense = math.copysign(1.0, bend)
            else:
                side = np.cross(u, sideways)
                sense = math.copysign(1.0, side[2]) if abs(side[2]) > 1e-9 else 1.0
            base = drawn_hold(ob.name, getattr(world, "world_seed", 0), hold)
            self.hooks.append(Hook(index, ob.name, point.copy(), s_rov, base, base, round(t_now, 2), sense))
            held.add(ob.name)
            self.events.append({"t": round(t_now, 2), "type": "tether_snag", "obstacle": ob.name,
                                "hold_n": round(base, 1)})
            x, l0 = tether.x, tether.l0
            n = len(x) - 1
            return

    def state(self) -> list[dict]:
        return [{"name": h.name, "point": np.round(h.target, 2).tolist(), "held": True, "since": h.since,
                 "hold_n": round(h.hold_n, 1), "tension_n": round(h.tension_n, 1)} for h in self.hooks]
