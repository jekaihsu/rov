"""Environment: obstacles, collision contact, range sensors and ocean current.

Obstacles are simple analytic shapes with signed-distance queries so both the
vehicle hull and every tether node can collide with them cheaply:
    Cylinder  finite capsule-like segment (jacket legs, braces, monopiles, bridge piers)
    Box       oriented box, yaw-only rotation (hull, wreck, caisson)
    Wall      vertical half-space with finite extent (quay wall, dam face)
    FieldMesh arbitrary structure (e.g. a wreck) from a precomputed distance field of its
              collision meshes (tools/build_wreck.py); thin plates get a small thickness
    SnagFeature small seabed item (rock, boulder, debris, rope) that can hook a tether lying on the
              bottom; scenes register them like any other obstacle (see tether_snag.py)
The seabed is a horizontal plane at ``World.seabed_depth`` (NED z, metres).
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from ._flow_accel import turbulence as _compiled_turbulence
from .flow import (COMPONENT_RATIOS, DEFAULT_Z0, SEABED_Z0, StructureFlow, Tide,
                   TurbulenceField,
                   bed_factor, bed_reference_height, cosine_ramp, rotate_xy, turbulence_length, turbulence_vectors)
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
        t = np.clip(np.dot(x - a, ab) / max(float(np.dot(ab, ab)), 1e-12), 0.0, 1.0)
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
        t = np.clip(((X - a) @ ab) / max(float(np.dot(ab, ab)), 1e-12), 0.0, 1.0)
        d = X - (a + t[:, None] * ab)
        n = np.linalg.norm(d, axis=1)
        normal = d / np.maximum(n, 1e-9)[:, None]
        normal[n < 1e-9] = [1.0, 0.0, 0.0]
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


def ship_hull_params(length: float, beam: float, draft: float, top: float | None = None) -> dict:
    """Derived proportions of the parametric ship hull, shared by ``ShipHull`` and its appendages.

    The viewer (viewer/structure_sdf.js) builds its mesh from the same numbers, so changing a proportion here
    must be mirrored there; tests/test_scene_consistency.py compares both.
    """
    return {
        "length": float(length), "beam": float(beam), "draft": float(draft),
        "top": float(-max(2.0, 0.6 * draft) if top is None else top),
        "bilge": min(0.12 * beam, 0.3 * draft),       # bilge radius
        "bow": 0.32 * length,                          # length of the bow taper
        "stern": 0.30 * length,                        # length of the stern taper (counter)
        "rake": 0.04 * length,                         # stem rake: the stem foot sits this far aft
        "aperture": 0.075 * length,                    # propeller aperture under the counter
        "counter": 0.3 * draft,                        # depth of the counter's underside
        "fair": 0.6,                                   # m over which the stern closes in under the counter
    }


def ship_hull_local_sdf(L: np.ndarray, hp: dict) -> np.ndarray:
    """Approximate signed distance (m) of local hull points (x forward, y starboard, z down from the waterline).

    The hull is the intersection of a side surface |y| = hb(x, z) with the deck, the keel plane and its end
    planes; the side distance is scaled by the surface slope. Below the counter the stern ends at the
    propeller aperture instead of the transom (``_aft_end``), which opens the space for propeller and rudder.
    """
    x, y, z = L[:, 0], L[:, 1], L[:, 2]
    hb, fwd_end = _half_breadth(x, z, hp)
    e = 0.05
    hx = (_half_breadth(x + e, z, hp)[0] - _half_breadth(x - e, z, hp)[0]) / (2 * e)
    hz = (_half_breadth(x, z + e, hp)[0] - _half_breadth(x, z - e, hp)[0]) / (2 * e)
    slope = np.minimum(np.sqrt(1 + hx * hx + hz * hz), 6.0)
    side = (np.abs(y) - hb) / slope
    return np.maximum.reduce([side, z - hp["draft"], hp["top"] - z, x - fwd_end, _aft_end(z, hp) - x])


def _aft_end(z, hp):
    """Local x of the stern: the transom above the counter, the propeller aperture below it."""
    t = np.clip((z - hp["counter"]) / hp["fair"], 0.0, 1.0)
    return -hp["length"] / 2 + hp["aperture"] * t * t * (3 - 2 * t)


def _half_breadth(x, z, hp):
    half = hp["length"] / 2
    fwd_mid = half - hp["bow"]
    aft_mid = -half + hp["stern"]
    fwd_end = half - hp["rake"] * np.clip(z / hp["draft"], 0.0, 1.0)
    u_bow = np.clip((x - fwd_mid) / np.maximum(fwd_end - fwd_mid, 1e-6), 0.0, 1.0)
    u_aft = np.clip((aft_mid - x) / np.maximum(aft_mid - _aft_end(z, hp), 1e-6), 0.0, 1.0)
    width = (1 - u_bow ** 2) * (1 - u_aft ** 2)
    rb = hp["bilge"]
    s = np.clip(z - (hp["draft"] - rb), 0.0, rb)
    bilge = rb - np.sqrt(np.maximum(rb * rb - s * s, 0.0))
    return width * hp["beam"] / 2 - bilge, fwd_end


class ShipHull:
    """Parametric displacement hull (flat bottom, round bilge, tapered bow and counter stern).

    ``center`` is the NED point on the waterline at midships, ``yaw_deg`` the heading of the bow. Appendages
    (bilge keels, propeller, rudder) are separate Cylinder/Box obstacles from ``site_dressing.ship_hull``.
    """

    def __init__(self, name: str, center: tuple, yaw_deg: float, length: float, beam: float, draft: float,
                 top: float | None = None, kind: str = "hull"):
        self.name, self.kind = name, kind
        self.center = tuple(float(v) for v in center)
        self.yaw_deg = float(yaw_deg)
        self.hp = ship_hull_params(length, beam, draft, top)
        a = math.radians(self.yaw_deg)
        self.R = np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])

    def to_local(self, X: np.ndarray) -> np.ndarray:
        return (np.atleast_2d(X) - np.asarray(self.center, float)) @ self.R

    def world_point(self, local) -> np.ndarray:
        return np.asarray(local, float) @ self.R.T + np.asarray(self.center, float)

    def sdf_many(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        L = self.to_local(X)
        d = ship_hull_local_sdf(L, self.hp)
        n_local = np.zeros((len(L), 3))
        n_local[:, 2] = -1.0
        near = d < 0.6
        if np.any(near):
            Ln, e = L[near], 0.02
            grad = np.stack([ship_hull_local_sdf(Ln + off, self.hp) - ship_hull_local_sdf(Ln - off, self.hp)
                             for off in (np.array([e, 0, 0]), np.array([0, e, 0]), np.array([0, 0, e]))], 1)
            n_local[near] = grad / np.maximum(np.linalg.norm(grad, axis=1), 1e-9)[:, None]
        return d, n_local @ self.R.T

    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        d, n = self.sdf_many(np.asarray(x, float)[None, :])
        return float(d[0]), n[0]

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        hp = self.hp
        r = math.hypot(hp["length"] / 2, hp["beam"] / 2)
        c = np.asarray(self.center, float)
        return np.array([c[0] - r, c[1] - r, hp["top"]]), np.array([c[0] + r, c[1] + r, hp["draft"]])

    def as_dict(self):
        hp = self.hp
        return {"type": "ship_hull", "name": self.name, "kind": self.kind, "center": list(self.center),
                "yaw_deg": self.yaw_deg, "length": hp["length"], "beam": hp["beam"], "draft": hp["draft"],
                "top": hp["top"]}
class SnagFeature(Cylinder):
    """Small snaggable seabed item: a vertical capsule standing on the seabed at ``point``.

    It is a ``Cylinder`` for contact (so it joins the vectorised capsule queries) but reports its own
    type. ``hold_n`` is the (min, max) holding force range in N; each feature draws its own value from
    it (tether_snag.py). Values are provisional training settings, not measurements: no published
    data on small-ROV tether snag strength exists (research_notes/臍帶纜物理與收放文獻/tether_properties.md §5)."""

    def __init__(self, name: str, point: tuple, radius: float = 0.25, height: float = 0.4,
                 hold_n: tuple = (150.0, 400.0), kind: str = "snag", item: str = "rock", embedded: bool = False):
        base = tuple(float(v) for v in point)
        top = (base[0], base[1], base[2] - max(float(height) - float(radius), 0.0))
        super().__init__(name, base, top, float(radius), kind)
        self.point = base
        self.height = float(height)
        self.hold_n = tuple(hold_n)
        self.item = item
        self.embedded = embedded

    @property
    def snag_hold(self) -> tuple:
        return self.hold_n

    def as_dict(self):
        return {"type": "snag", "name": self.name, "point": list(self.point), "radius": self.radius,
                "height": self.height, "kind": self.kind, "item": self.item,
                **({"embedded": True} if self.embedded else {})}


@functools.lru_cache(maxsize=4)
def _load_field(path: str):
    """Distance field arrays, shared read-only by every FieldMesh that uses the same file."""
    z = np.load(path)
    F = z["field"].astype(np.float32) * float(z["quant"])
    F.setflags(write=False)
    return F, np.asarray(z["origin"], float), float(z["spacing"])


class FieldMesh:
    """Arbitrary static structure from a precomputed unsigned distance field.

    The field is stored in the structure's own frame (X along the hull, Y across, Z up, origin at
    the seabed) and placed in the world by ``origin`` (NED of the local origin) and ``heading_deg``
    (world direction of local +X). Queries are trilinear lookups, so vehicle spheres and tether
    nodes cost the same as the analytic shapes. Plates are thin: ``thickness`` is added as a skin.
    """

    def __init__(self, name: str, field_path, origin: tuple, heading_deg: float = 180.0,
                 kind: str = "wreck", thickness: float = 0.12, model: str | None = None, seabed_depth: float | None = None,
                 snag_hold: tuple | None = None):
        self.name, self.kind, self.thickness, self.model = name, kind, float(thickness), model
        # Optional (min, max) N: lets the tether hook on the structure where it bends round it.
        self.snag_hold = snag_hold
        self.F, self.lo, self.h = _load_field(str(field_path))
        self.shape = np.array(self.F.shape)
        self.hi = self.lo + self.h * (self.shape - 1)
        self.origin = np.asarray(origin, float)
        self.heading_deg = float(heading_deg)
        a = math.radians(heading_deg)
        # proper rotation (both frames right-handed): local X -> heading (cos a, sin a, 0),
        # local Z -> up (0, 0, -1), local Y = Z x X -> (sin a, -cos a, 0)
        c, s_ = math.cos(a), math.sin(a)
        self.R = np.array([[c, s_, 0.0], [s_, -c, 0.0], [0.0, 0.0, -1.0]])
        corners = np.array([[x, y, z] for x in (self.lo[0], self.hi[0]) for y in (self.lo[1], self.hi[1])
                            for z in (self.lo[2], self.hi[2])])
        W = corners @ self.R.T + self.origin
        self._aabb = (W.min(0), W.max(0))
        self.far = float(self.F.max())

    def to_local(self, X: np.ndarray) -> np.ndarray:
        return (X - self.origin) @ self.R          # R is orthonormal: inverse = transpose

    def _lookup(self, L: np.ndarray) -> np.ndarray:
        g = (L - self.lo) / self.h
        g = np.clip(g, 0.0, self.shape - 1.000001)
        i = np.floor(g).astype(int)
        f = g - i
        F = self.F
        x0, y0, z0 = i[:, 0], i[:, 1], i[:, 2]
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        c00 = F[x0, y0, z0] * (1 - fx) + F[x0 + 1, y0, z0] * fx
        c10 = F[x0, y0 + 1, z0] * (1 - fx) + F[x0 + 1, y0 + 1, z0] * fx
        c01 = F[x0, y0, z0 + 1] * (1 - fx) + F[x0 + 1, y0, z0 + 1] * fx
        c11 = F[x0, y0 + 1, z0 + 1] * (1 - fx) + F[x0 + 1, y0 + 1, z0 + 1] * fx
        d = (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz
        # outside the grid the field only bounds the distance from below: add the gap to the box
        gap = np.linalg.norm(np.maximum(self.lo - L, 0) + np.maximum(L - self.hi, 0), axis=1)
        return d + gap

    def sdf_many(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        L = self.to_local(np.atleast_2d(X))
        d = self._lookup(L) - self.thickness
        n_local = np.zeros((len(L), 3))
        n_local[:, 2] = 1.0
        near = d < 0.5                        # normals only matter for points about to touch
        if np.any(near):
            Ln, e = L[near], 0.5 * self.h
            grad = np.stack([self._lookup(Ln + off) - self._lookup(Ln - off)
                             for off in (np.array([e, 0, 0]), np.array([0, e, 0]), np.array([0, 0, e]))], 1)
            n_local[near] = grad / np.maximum(np.linalg.norm(grad, axis=1), 1e-9)[:, None]
        return d, n_local @ self.R.T

    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        d, n = self.sdf_many(np.asarray(x, float)[None, :])
        return float(d[0]), n[0]

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        return self._aabb

    def world_point(self, local) -> np.ndarray:
        return np.asarray(local, float) @ self.R.T + self.origin

    def as_dict(self):
        return {"type": "model", "name": self.name, "kind": self.kind, "model": self.model,
                "origin": self.origin.round(3).tolist(), "heading_deg": self.heading_deg,
                "bounds_local": [self.lo.round(2).tolist(), self.hi.round(2).tolist()]}


@dataclass
class CurrentProfile:
    """Depth-varying current. Speeds in knots, directions in degrees the water flows toward.

    The ambient flow is the three-layer mean profile plus a smooth, anisotropic, spatially
    varying turbulence field (``flow.TurbulenceField``). Call ``step_gust`` exactly once per
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
               injection, tau)
        if self._layer_cache is None or self._layer_cache[0] != key:
            scale, rotate, template = injection
            layers = rotate_xy(self._base_layers(), rotate) * scale
            if template:
                layers = layers + rotate_xy(self._template_layers(), rotate) * template
            if tau is not None:
                layers = self.tide.transform(layers, self.surface_dir + rotate, tau)
            self._layer_cache = (key, layers)
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
        knots = (0.0, seabed / 2, seabed)
        v = np.empty((len(z), 3))
        for k in range(3):
            v[:, k] = np.interp(z, knots, layers[:, k])
        h = seabed - z if heights is None else np.asarray(heights, float)
        roughness = z0 if z0 is not None else self.z0 if self.z0 is not None else DEFAULT_Z0
        v *= bed_factor(h, roughness, bed_reference_height(seabed))[:, None]
        return v

    def mean_at(self, depth: float, seabed: float) -> np.ndarray:
        return self.mean_many([depth], seabed)[0]

    def depth_average(self, seabed: float | None = None) -> np.ndarray:
        """Depth-averaged mean current (advects the turbulence)."""
        s, m, b = self._layers()
        return (s + 2 * m + b) / 4

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
        fallback = np.array([math.cos(a), math.sin(a), 0.0])
        turb = self._field()
        if self.use_compiled and _compiled_turbulence is not None:
            return _compiled_turbulence(np.ascontiguousarray(positions, float), mean, turb.displacement,
                                        1.0 / ell, turb.k, turb.psi + turb.theta, turb.amp, float(self.turbulence),
                                        COMPONENT_RATIOS, fallback[0], fallback[1])
        unit = turb.unit(positions, ell)
        return turbulence_vectors(unit, mean, self.turbulence, positions[:, 2], fallback)

    def shedding_travel(self, depths, seabed: float) -> np.ndarray:
        """Integrated free-stream distance (m) per depth: sets vortex-shedding phase (f = St U / D)."""
        avg = float(np.linalg.norm(self.depth_average(seabed)))
        if avg < 1e-3:
            return np.full(len(np.atleast_1d(depths)), self._travel)
        local = np.linalg.norm(self.mean_many(np.atleast_1d(depths), seabed), axis=1)
        return self._travel * local / avg

    # ── sampling ──────────────────────────────────────────────────────────
    def sample_many(self, positions: np.ndarray, seabed: float, t: float = 0.0, bed=None,
                    z0: float | None = None) -> np.ndarray:
        """Ambient flow (mean profile + turbulence) at NED points.

        Not obstacle-resolving; ``World.current_at_many`` adds structure effects and passes the
        local seabed depth per point (``bed``) and the biome roughness (``z0``). Without them the
        nominal flat seabed and the profile's own roughness are used.
        """
        p = np.atleast_2d(np.asarray(positions, float))
        self._seabed_hint = float(seabed)
        heights = None if bed is None else np.asarray(bed, float) - p[:, 2]
        mean = self.mean_many(p[:, 2], seabed, heights, z0)
        return mean + self.fluctuation_many(p, mean, seabed)

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
        return out


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
    vehicle_id: str = "default"


class World:
    def __init__(self, seabed_depth: float = 30.0):
        self.seabed_depth = seabed_depth
        self.paint_marks: list[dict] = []
        self.paint_serial = 0
        self.paint_last_at: dict[str, float] = {}
        self.obstacles: list = []
        self.current = CurrentProfile()
        self.regional_flows = []
        self.k_contact = 25000.0      # N/m
        self.c_contact = 500.0        # N s/m
        self.mu = 0.4
        self._in_contact: set = set()
        self.events: list[ContactEvent] = []
        self._contacts_by_vehicle: dict = {}
        self.world_seed = 0
        self.biome = "temperate"
        self.terrain = None
        self.habitat_entities = []
        self.fish_schools = []
        self.time = 0.0
        self._ecology_accumulator = 0.0
        from .silt import SiltField
        self.silt_field = SiltField(self)

    def configure_habitat(self, biome: str, seed: int, keep_clear=()) -> None:
        from .ecology import SeabedTerrain, create_habitat
        self.world_seed, self.biome = int(seed), biome
        self.obstacles = [o for o in self.obstacles if o.kind != "habitat"]
        relief = 1.4 if biome == "reef" else .5 if biome == "seagrass" else 0.0
        self.terrain = SeabedTerrain(self.seabed_depth, self.world_seed, relief)
        self.habitat_entities, self.fish_schools = create_habitat(self, biome, self.world_seed, keep_clear)
        self._obstacle_bounds = None

    def seabed_at(self, position: np.ndarray) -> float:
        if self.terrain is None:
            return self.seabed_depth
        return float(self.terrain.sample_many(np.asarray(position)[None, :])[0][0])

    depth_at = seabed_at

    def seabed_at_many(self, positions: np.ndarray) -> np.ndarray:
        positions = np.atleast_2d(np.asarray(positions, float))
        if self.terrain is None:
            return np.full(len(positions), float(self.seabed_depth))
        return self.terrain.sample_many(positions)[0]

    # ── water flow ────────────────────────────────────────────────────────
    def structure_flow(self) -> StructureFlow:
        """Cached analytic flow disturbance for the current obstacle list (habitat props excluded)."""
        key = (id(self.obstacles), len(self.obstacles))
        cached = getattr(self, "_structure_flow", None)
        if cached is None or cached[0] != key:
            cached = (key, StructureFlow(self.obstacles))
            self._structure_flow = cached
        return cached[1]

    def current_at_many(self, points, t: float | None = None) -> np.ndarray:
        """Full local water velocity (NED m/s) at points: ambient profile + turbulence + structures.

        This is the flow the vehicle, tether, silt, fish and work objects feel. ``t`` is accepted
        for API symmetry; the field is evaluated at the current simulation instant (the profile
        clock advanced once per tick by ``CurrentProfile.step_gust``). Zero inside solids.
        """
        P = np.atleast_2d(np.asarray(points, float))
        bed = None
        if self.terrain is not None and self.terrain.relief:
            # Terrain only rises above the nominal floor; points higher than the relief plus the
            # bed layer are unaffected, so only query the terrain near the bottom.
            low = P[:, 2] > self.seabed_depth - self.terrain.relief - bed_reference_height(self.seabed_depth)
            if np.any(low):
                bed = np.full(len(P), self.seabed_depth)
                bed[low] = self.terrain.sample_many(P[low])[0]
        U = self.current.sample_many(P, self.seabed_depth, bed=bed, z0=self.bed_roughness())
        for region in self.regional_flows:
            U += region.sample_many(P)
        flow = self.structure_flow()
        if flow.empty:
            return U
        return flow.apply(P, U, self.current.shedding_travel(P[:, 2], self.seabed_depth))

    def bed_roughness(self) -> float:
        """Roughness length z0 (m): the profile's own value, else the site's seabed type (the silt model's)."""
        if self.current.z0 is not None:
            return float(self.current.z0)
        return SEABED_Z0.get(self.silt_field.seabed_type, DEFAULT_Z0)

    def current_at(self, point, t: float | None = None) -> np.ndarray:
        """Single-point ``current_at_many``."""
        return self.current_at_many(np.asarray(point, float)[None, :], t)[0]

    # ── queries ───────────────────────────────────────────────────────────
    def sdf(self, x: np.ndarray) -> tuple[float, np.ndarray, str]:
        if self.terrain is None or not self.terrain.relief:
            best, n_best = self.seabed_depth - x[2], WORLD_UP.copy()
        else:
            depth, normal = self.terrain.sample_many(np.asarray(x)[None, :])
            best, n_best = float((depth[0] - x[2]) * -normal[0, 2]), normal[0]
        name = "seabed"
        a, b = self._bounds()
        gaps = np.maximum(a - x, 0) + np.maximum(x - b, 0)
        candidates = np.flatnonzero(np.linalg.norm(gaps, axis=1) <= max(0., best))
        for i in candidates:
            ob = self.obstacles[i]
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
                        omega: np.ndarray, vehicle_id: str = "default", hull_spheres=None) -> np.ndarray:
        """Penalty contact wrench (body frame [F; M]) for the hull sphere proxy; logs impacts."""
        from .physics import q_conj
        q_inv = q_conj(q)
        centres_b = _HULL_C if hull_spheres is None else np.array([c for c, _ in hull_spheres], float)
        radii = _HULL_R if hull_spheres is None else np.array([r for _, r in hull_spheres], float)
        previous = self._contacts_by_vehicle.get(vehicle_id, set())
        centres_w = pos + np.array([q_rot(q, c) for c in centres_b])
        extent = float(np.max(np.linalg.norm(centres_b, axis=1) + radii))
        cand = self.near(pos - extent, pos + extent, 0.3)
        dist, normal_w, idx = self.sdf_many(centres_w, cand)
        pen = np.minimum(radii - dist, 0.3)            # cap: never fling the vehicle
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
            if key not in previous and name not in {kk[1] for kk in previous}:
                speed = max(0.0, -vn)
                last = next((e for e in reversed(self.events) if e.obstacle == name and e.vehicle_id == vehicle_id), None)
                if speed < 0.3 and last is not None and t - last.t < 0.3:
                    continue
                sev = "severe" if speed > 0.8 else "hard" if speed > 0.3 else "touch"
                where = ("front" if c_body[0] > 0.2 else "rear" if c_body[0] < -0.2 else "mid") + \
                        ("-stbd" if c_body[1] > 0.1 else "-port" if c_body[1] < -0.1 else "")
                self.events.append(ContactEvent(round(t, 2), name, round(speed, 2), sev, where, vehicle_id))
                if name == "seabed":
                    self.silt_field.contact(pos, speed, vehicle_id, impact=True)
        if any(name == "seabed" for _, name in touching):
            slide = float(np.linalg.norm(q_rot(q, vel_body)[:2]))
            self.silt_field.contact(pos, slide, vehicle_id, impact=False)
        self._in_contact = touching
        self._contacts_by_vehicle[vehicle_id] = touching
        return wrench

    def _bounds(self):
        cached = getattr(self, "_obstacle_bounds", None)
        if cached is None or len(cached[0]) != len(self.obstacles):
            bounds = [ob.aabb() for ob in self.obstacles]
            cached = (np.array([b[0] for b in bounds]).reshape(-1, 3),
                      np.array([b[1] for b in bounds]).reshape(-1, 3))
            self._obstacle_bounds = cached
            self._cylinder_mask = np.array([isinstance(ob, Cylinder) for ob in self.obstacles], bool)
            self._cylinder_a = np.array([ob.p0 if isinstance(ob, Cylinder) else (0,0,0) for ob in self.obstacles], float).reshape(-1,3)
            b = np.array([ob.p1 if isinstance(ob, Cylinder) else (0,0,0) for ob in self.obstacles], float).reshape(-1,3)
            self._cylinder_ab = b - self._cylinder_a
            self._cylinder_den = np.maximum(np.sum(self._cylinder_ab**2,axis=1),1e-12)
            self._cylinder_r = np.array([ob.radius if isinstance(ob, Cylinder) else 0 for ob in self.obstacles])
        return cached

    def near(self, lo: np.ndarray, hi: np.ndarray, margin: float = 1.0) -> list[int]:
        """Vectorised cached broad phase for obstacles overlapping the grown box."""
        cached = self._bounds()
        a, b = cached
        return np.flatnonzero(np.all(a <= hi + margin, axis=1) & np.all(b >= lo - margin, axis=1)).tolist()

    def sdf_many(self, X: np.ndarray, candidates: list[int] | None = None, include_seabed: bool = True
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Vectorised nearest-surface query for many points. Returns (dist, normal, obstacle index; -1 = seabed).

        ``include_seabed=False`` measures obstacles only (seabed distance reported as 1e9)."""
        if not include_seabed:
            dist = np.full(len(X), 1e9)
            normal = np.tile(WORLD_UP, (len(X), 1))
        elif self.terrain is None or not self.terrain.relief:
            dist = self.seabed_depth - X[:, 2]
            normal = np.tile(WORLD_UP, (len(X), 1))
        else:
            depth, normal = self.terrain.sample_many(X)
            dist = (depth - X[:, 2]) * -normal[:, 2]
        idx = np.full(len(X), -1)
        self._bounds()
        ids = np.arange(len(self.obstacles)) if candidates is None else np.asarray(candidates,dtype=int)
        cylinders = ids[self._cylinder_mask[ids]]
        if len(cylinders):
            # Evaluate all capsule contacts in one NumPy batch, including zero-length spheres.
            a, ab = self._cylinder_a[cylinders], self._cylinder_ab[cylinders]
            relative = X[:,None,:] - a[None,:,:]
            projection = np.einsum('nki,ki->nk',relative,ab) / self._cylinder_den[cylinders]
            projection = np.maximum(0.,np.minimum(1.,projection))
            delta = relative - projection[:,:,None]*ab[None,:,:]
            lengths = np.sqrt(np.einsum('nki,nki->nk',delta,delta))
            distances = lengths-self._cylinder_r[cylinders]
            choice = np.argmin(distances,axis=1)
            rows = np.arange(len(X))
            closest = distances[rows,choice]
            hit = closest < dist
            n = delta[rows,choice] / np.maximum(lengths[rows,choice,None],1e-9)
            n[lengths[rows,choice] < 1e-9] = [1.,0.,0.]
            dist[hit], normal[hit], idx[hit] = closest[hit], n[hit], cylinders[choice[hit]]
        for i in ids[~self._cylinder_mask[ids]]:
            ob = self.obstacles[i]
            d, n = ob.sdf_many(X)
            closer = d < dist
            dist = np.where(closer, d, dist)
            normal[closer] = n[closer]
            idx[closer] = i
        return dist, normal, idx

    # ── sediment and turbidity (model in silt.py) ─────────────────────────
    def configure_silt(self, seabed_type: str, bnl_height_m: float = 0.0, bnl_mg_l: float = 0.0) -> None:
        self.silt_field.configure(seabed_type, bnl_height_m, bnl_mg_l)

    @property
    def visibility_m(self) -> float:
        return self.silt_field.visibility_m

    @visibility_m.setter
    def visibility_m(self, value: float) -> None:
        self.silt_field.visibility_m = float(value)

    @property
    def silt_clouds(self) -> list:
        """Legacy view of the strongest puffs (``environment.silt_clouds``)."""
        return self.silt_field.legacy_clouds()

    def emit_silt(self, position, strength: float, source: str = "default") -> None:
        """Legacy source: ``strength`` 1 is about 0.1 kg of the local bed mix around ``position``."""
        bed = self.silt_field.bed
        mix = bed["mix"] if sum(bed["mix"]) > 0 else (0.0, 0.5, 0.5)
        self.silt_field.emit_mix(position, 0.1 * max(0.0, float(strength)), mix, 0.6, 0.4, f"{source}:legacy")

    def silt_concentration_at(self, point) -> float:
        """Suspended sediment at ``point`` in mg/L (puffs plus the near-bed turbid layer)."""
        return float(self.silt_field.concentration_mg_l(np.asarray(point, float))[0])

    def visibility_at(self, point, visibility_m: float | None = None) -> float:
        """Black-target visibility 4.8 / c at ``point`` (m)."""
        c = float(self.silt_field.attenuation(np.asarray(point, float), visibility_m)[0])
        return 4.8 / c

    def optical_depth(self, a, b, samples: int = 24) -> float:
        return self.silt_field.optical_depth(a, b, samples)

    def silt_at(self, position, visibility_m: float | None = None) -> float:
        """Legacy 0..1 silt index = 1 - effective / base visibility at ``position``."""
        return float(self.silt_field.silt_index(np.asarray(position, float), visibility_m)[0])

    def environment_state(self) -> dict:
        return {"fish_schools": [{"id": s["id"], "pos": s["pos"].round(4).tolist(),
                                  "vel": s["vel"].round(4).tolist()} for s in self.fish_schools],
                "silt_clouds": [{**c, "pos": c["pos"].round(3).tolist()} for c in self.silt_clouds],
                "silt_puffs": self.silt_field.puffs_state(),
                "turbidity": self.silt_field.turbidity_state()}

    def step(self, dt: float, vehicles=None) -> None:
        from .ecology import step_schools
        self.time += dt
        vehicles = vehicles or []
        self.silt_field.step_sources(dt, vehicles)
        self._ecology_accumulator += dt
        if self._ecology_accumulator + 1e-9 >= .1:
            elapsed, self._ecology_accumulator = self._ecology_accumulator, 0.0
            step_schools(self, elapsed, vehicles)
            positions = [np.asarray(v["pos"], float) for v in vehicles]
            self.silt_field.step_transport(elapsed, positions)

    def as_dict(self) -> dict:
        return {"seabed_depth": self.seabed_depth, "obstacles": [o.as_dict() for o in self.obstacles],
                "current": self.current.as_dict(), "world_seed": self.world_seed, "generation_version": 1,
                "biome": self.biome, "terrain": self.terrain.as_dict() if self.terrain is not None else None,
                "habitat": {"entities": self.habitat_entities,
                            "fish_schools": [{"id": s["id"], "pos": s["pos"].round(4).tolist(),
                                              "count": s["count"], "phase": s["phase"], "variant": s["variant"]}
                                             for s in self.fish_schools]}}
