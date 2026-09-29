"""Environment: obstacles, collision contact, range sensors and ocean current.

Obstacles are simple analytic shapes with signed-distance queries so both the
vehicle hull and every tether node can collide with them cheaply:
    Cylinder  finite capsule-like segment (jacket legs, braces, monopiles, bridge piers)
    Box       oriented box, yaw-only rotation (hull, wreck, caisson)
    Wall      vertical half-space with finite extent (quay wall, dam face)
The seabed is a horizontal plane at ``World.seabed_depth`` (NED z, metres).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .physics import KNOT, q_rot

WORLD_UP = np.array([0.0, 0.0, -1.0])


@dataclass
class Cylinder:
    name: str
    p0: tuple                 # NED end point
    p1: tuple
    radius: float
    kind: str = "pile"

    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        a, b = np.asarray(self.p0, float), np.asarray(self.p1, float)
        ab = b - a
        t = np.clip(np.dot(x - a, ab) / np.dot(ab, ab), 0.0, 1.0)
        c = a + t * ab
        d = x - c
        n = np.linalg.norm(d)
        normal = d / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])
        return n - self.radius, normal

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        a, b = np.asarray(self.p0, float), np.asarray(self.p1, float)
        return np.minimum(a, b) - self.radius, np.maximum(a, b) + self.radius

    def sdf_many(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a, b = np.asarray(self.p0, float), np.asarray(self.p1, float)
        ab = b - a
        t = np.clip(((X - a) @ ab) / np.dot(ab, ab), 0.0, 1.0)
        d = X - (a + t[:, None] * ab)
        n = np.linalg.norm(d, axis=1)
        normal = d / np.maximum(n, 1e-9)[:, None]
        return n - self.radius, normal

    def as_dict(self):
        return {"type": "cylinder", "name": self.name, "p0": list(self.p0), "p1": list(self.p1),
                "radius": self.radius, "kind": self.kind}


@dataclass
class Box:
    name: str
    center: tuple             # NED
    half: tuple               # half extents along its local x (length), y (beam), z (height)
    yaw_deg: float = 0.0
    kind: str = "hull"

    def _rot(self):
        a = math.radians(self.yaw_deg)
        return np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])

    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        R = self._rot()
        p = R.T @ (x - np.asarray(self.center, float))
        h = np.asarray(self.half, float)
        q = np.abs(p) - h
        outside = np.maximum(q, 0.0)
        dist = np.linalg.norm(outside) + min(max(q[0], max(q[1], q[2])), 0.0)
        if dist > 0:
            nl = np.sign(p) * outside
            nl = nl / (np.linalg.norm(nl) + 1e-12)
        else:
            i = int(np.argmax(q))
            nl = np.zeros(3)
            nl[i] = np.sign(p[i]) or 1.0
        return dist, R @ nl

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        c, r = np.asarray(self.center, float), float(np.linalg.norm(self.half))
        return c - r, c + r

    def sdf_many(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        R = self._rot()
        P = (X - np.asarray(self.center, float)) @ R          # rows: R.T @ (x - c)
        h = np.asarray(self.half, float)
        q = np.abs(P) - h
        outside = np.maximum(q, 0.0)
        o_len = np.linalg.norm(outside, axis=1)
        inside = np.minimum(q.max(axis=1), 0.0)
        dist = o_len + inside
        nl = np.sign(P) * outside / np.maximum(o_len, 1e-12)[:, None]
        ins = o_len <= 0
        if np.any(ins):
            i = np.argmax(q[ins], axis=1)
            n_in = np.zeros((int(ins.sum()), 3))
            sgn = np.sign(P[ins][np.arange(len(i)), i])
            n_in[np.arange(len(i)), i] = np.where(sgn == 0, 1.0, sgn)
            nl[ins] = n_in
        return dist, nl @ R.T

    def as_dict(self):
        return {"type": "box", "name": self.name, "center": list(self.center), "half": list(self.half),
                "yaw_deg": self.yaw_deg, "kind": self.kind}


@dataclass
class Wall:
    name: str
    point: tuple              # a point on the face (NED)
    normal_deg: float         # compass direction the face looks toward (deg, 0 = north)
    width: float = 60.0
    top: float = 0.0          # NED z of the top edge (0 = surface)
    kind: str = "wall"

    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        a = math.radians(self.normal_deg)
        n = np.array([math.cos(a), math.sin(a), 0.0])
        p = np.asarray(self.point, float)
        d = float(np.dot(x - p, n))
        t = np.array([-n[1], n[0], 0.0])
        along = float(np.dot(x - p, t))
        if abs(along) > self.width / 2 or x[2] < self.top:
            return 1e3, n
        return d, n

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        return np.full(3, -1e9), np.full(3, 1e9)        # large face: never culled

    def sdf_many(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a = math.radians(self.normal_deg)
        n = np.array([math.cos(a), math.sin(a), 0.0])
        t = np.array([-n[1], n[0], 0.0])
        rel = X - np.asarray(self.point, float)
        d = rel @ n
        off = (np.abs(rel @ t) > self.width / 2) | (X[:, 2] < self.top)
        return np.where(off, 1e3, d), np.tile(n, (len(X), 1))

    def as_dict(self):
        return {"type": "wall", "name": self.name, "point": list(self.point), "normal_deg": self.normal_deg,
                "width": self.width, "top": self.top, "kind": self.kind}


@dataclass
class CurrentProfile:
    """Depth-varying current. Speeds in knots, directions in degrees the water flows toward."""
    surface_kn: float = 0.0
    surface_dir: float = 90.0
    mid_kn: float = 0.0
    mid_dir: float = 90.0
    bottom_kn: float = 0.0
    bottom_dir: float = 90.0
    turbulence: float = 0.15          # gust std-dev as a fraction of the local speed
    gust_tau: float = 6.0             # s, gust correlation time
    _gust: np.ndarray = field(default_factory=lambda: np.zeros(3), repr=False)

    def layer(self, which: str) -> np.ndarray:
        kn, d = {"surface": (self.surface_kn, self.surface_dir), "mid": (self.mid_kn, self.mid_dir),
                 "bottom": (self.bottom_kn, self.bottom_dir)}[which]
        a = math.radians(d)
        return np.array([math.cos(a), math.sin(a), 0.0]) * kn * KNOT

    def mean_at(self, depth: float, seabed: float) -> np.ndarray:
        s, m, b = self.layer("surface"), self.layer("mid"), self.layer("bottom")
        mid_d = seabed / 2
        if depth <= mid_d:
            t = depth / max(mid_d, 1e-6)
            v = s * (1 - t) + m * t
        else:
            t = (depth - mid_d) / max(seabed - mid_d, 1e-6)
            v = m * (1 - t) + b * t
        # boundary layer: current dies off in the last metre above the seabed
        above = seabed - depth
        if above < 1.0:
            v = v * max(0.0, above)
        return v

    def step_gust(self, dt: float, rng: np.random.Generator) -> None:
        k = dt / self.gust_tau
        self._gust += -self._gust * k + math.sqrt(2 * k) * rng.standard_normal(3) * np.array([1, 1, 0.3])

    def at_many(self, depths: np.ndarray, seabed: float) -> np.ndarray:
        s, m, b = self.layer("surface"), self.layer("mid"), self.layer("bottom")
        z = np.clip(np.asarray(depths, float), 0.0, seabed)
        mid_d = seabed / 2
        t1 = np.clip(z / max(mid_d, 1e-6), 0, 1)[:, None]
        t2 = np.clip((z - mid_d) / max(seabed - mid_d, 1e-6), 0, 1)[:, None]
        v = np.where((z <= mid_d)[:, None], s * (1 - t1) + m * t1, m * (1 - t2) + b * t2)
        v = v * np.clip(seabed - z, 0.0, 1.0)[:, None]
        speed = np.maximum(0.05, np.linalg.norm(v, axis=1))[:, None]
        return v + self._gust * self.turbulence * speed

    def at(self, depth: float, seabed: float) -> np.ndarray:
        v = self.mean_at(depth, seabed)
        return v + self._gust * self.turbulence * max(0.05, float(np.linalg.norm(v)))

    def as_dict(self):
        return {k: getattr(self, k) for k in ("surface_kn", "surface_dir", "mid_kn", "mid_dir",
                                              "bottom_kn", "bottom_dir", "turbulence")}


# vehicle collision proxy: spheres in body FRD approximating the 770 x 560 x 400 mm envelope
HULL_SPHERES = [((x, y, z), 0.14) for x in (0.26, -0.26) for y in (0.17, -0.17) for z in (0.07, -0.08)] + \
               [((0.36, 0.0, 0.0), 0.12), ((-0.36, 0.0, 0.0), 0.12)]


_HULL_C = np.array([c for c, _ in HULL_SPHERES], float)
_HULL_R = np.array([r for _, r in HULL_SPHERES], float)


@dataclass
class ContactEvent:
    t: float
    obstacle: str
    speed: float             # m/s normal impact speed
    severity: str            # touch / hard / severe
    where: str               # body location label


class World:
    def __init__(self, seabed_depth: float = 30.0):
        self.seabed_depth = seabed_depth
        self.obstacles: list = []
        self.current = CurrentProfile()
        self.k_contact = 25000.0      # N/m
        self.c_contact = 500.0        # N s/m
        self.mu = 0.4
        self._in_contact: set = set()
        self.events: list[ContactEvent] = []
        self.silt = 0.0               # 0..1 seabed silt cloud (visibility)

    # ── queries ───────────────────────────────────────────────────────────
    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray, str]:
        best, n_best, name = self.seabed_depth - x[2], WORLD_UP.copy(), "seabed"
        for ob in self.obstacles:
            d, n = ob.sdf(x)
            if d < best:
                best, n_best, name = d, n, ob.name
        return best, n_best, name

    def raycast(self, origin: np.ndarray, direction: np.ndarray, max_range: float = 50.0,
                step: float = 0.05) -> float:
        """Sphere-traced range along ``direction`` (NED). Returns max_range if nothing is hit."""
        d = direction / np.linalg.norm(direction)
        t = 0.0
        while t < max_range:
            s, _, _ = self.sdf(origin + d * t)
            if s < 0.02:
                return t
            t += max(step, s)
        return max_range

    # ── vehicle contact ───────────────────────────────────────────────────
    def vehicle_contact(self, t: float, pos: np.ndarray, q: np.ndarray, vel_body: np.ndarray,
                        omega: np.ndarray) -> np.ndarray:
        """Penalty contact wrench (body frame [F; M]) for the hull sphere proxy; logs impacts."""
        from .physics import q_conj
        q_inv = q_conj(q)
        centres_b = _HULL_C
        centres_w = pos + np.array([q_rot(q, c) for c in centres_b])
        cand = self.near(pos - 0.6, pos + 0.6, 0.3)
        dist, normal_w, idx = self.sdf_many(centres_w, cand)
        pen = np.minimum(_HULL_R - dist, 0.3)            # cap: never fling the vehicle
        wrench = np.zeros(6)
        touching = set()
        for k in np.nonzero(pen > 0)[0]:
            c_body = centres_b[k]
            name = "seabed" if idx[k] < 0 else self.obstacles[idx[k]].name
            key = (int(k), name)
            touching.add(key)
            v_pt_body = vel_body + np.cross(omega, c_body)
            n_body = q_rot(q_inv, normal_w[k])
            vn = float(np.dot(v_pt_body, n_body))           # <0 approaching
            f_n = max(0.0, self.k_contact * pen[k] - self.c_contact * min(vn, 0.0))
            v_t = v_pt_body - vn * n_body
            vt = np.linalg.norm(v_t)
            f_t = -self.mu * f_n * v_t / vt if vt > 1e-4 else np.zeros(3)
            F = f_n * n_body + f_t
            wrench[:3] += F
            wrench[3:] += np.cross(c_body, F)
            if key not in self._in_contact and name not in {kk[1] for kk in self._in_contact}:
                speed = max(0.0, -vn)
                last = next((e for e in reversed(self.events) if e.obstacle == name), None)
                if speed < 0.3 and last is not None and t - last.t < 0.3:
                    continue
                sev = "severe" if speed > 0.8 else "hard" if speed > 0.3 else "touch"
                where = ("front" if c_body[0] > 0.2 else "rear" if c_body[0] < -0.2 else "mid") + \
                        ("-stbd" if c_body[1] > 0.1 else "-port" if c_body[1] < -0.1 else "")
                self.events.append(ContactEvent(round(t, 2), name, round(speed, 2), sev, where))
                if name == "seabed":
                    self.silt = min(1.0, self.silt + 0.3 + speed)
        self._in_contact = touching
        return wrench

    def near(self, lo: np.ndarray, hi: np.ndarray, margin: float = 1.0) -> list[int]:
        """Indices of obstacles whose bounding box overlaps [lo, hi] grown by ``margin``."""
        out = []
        for i, ob in enumerate(self.obstacles):
            a, b = ob.aabb()
            if np.all(a <= hi + margin) and np.all(b >= lo - margin):
                out.append(i)
        return out

    def sdf_many(self, X: np.ndarray, candidates: list[int] | None = None
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Vectorised nearest-surface query for many points. Returns (dist, normal, obstacle index; -1 = seabed)."""
        dist = self.seabed_depth - X[:, 2]
        normal = np.tile(WORLD_UP, (len(X), 1))
        idx = np.full(len(X), -1)
        for i in (range(len(self.obstacles)) if candidates is None else candidates):
            ob = self.obstacles[i]
            d, n = ob.sdf_many(X)
            closer = d < dist
            dist = np.where(closer, d, dist)
            normal[closer] = n[closer]
            idx[closer] = i
        return dist, normal, idx

    def step(self, dt: float) -> None:
        self.silt = max(0.0, self.silt - dt / 25.0)

    def as_dict(self) -> dict:
        return {"seabed_depth": self.seabed_depth, "obstacles": [o.as_dict() for o in self.obstacles],
                "current": self.current.as_dict()}
