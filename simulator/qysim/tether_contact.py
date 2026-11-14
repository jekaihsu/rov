"""Tether contact geometry: contact points, wrap counting and contact metrics.

Gap 2 in research_notes/臍帶纜物理與收放文獻/simulators_and_current_model.md: node-only contact let
long segments (8.75 m at 350 m deployed) tunnel through 1.6 m piles, and wraps were only counted
round near-vertical cylinders. Here contact acts on "contact points": every free node plus samples
inside any segment that could reach an obstacle. A segment is sampled only when the obstacle
distances of its end nodes allow it to touch (distance fields are 1-Lipschitz, so a segment of
length L whose ends are d_a and d_b away cannot reach a surface when d_a + d_b > L + 2r), so the
cost stays close to node-only contact far from structures. The seabed plane needs no samples: a
segment between two nodes above a plane is above it.

Each point carries a tangent plane (anchor, distance, normal) refreshed when it moves more than
``contact_cache_m``; the solver projects penetrating points out by moving both end nodes with
barycentric weights.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .site_dressing import APPURTENANCE_KINDS
from .world import Cylinder, SnagFeature, Wall


@dataclass
class ContactSet:
    seg: np.ndarray          # int segment index of each point
    s: np.ndarray            # position along the segment, 0 = spool-side node
    anchor: np.ndarray       # (k, 3) point position when the plane was taken
    dist0: np.ndarray        # signed distance at the anchor
    normal: np.ndarray       # surface normal at the anchor
    obstacle: np.ndarray     # obstacle index, -1 = seabed
    hard: np.ndarray         # bool: structure (chafes), not seabed
    node_count: int          # the first node_count points are nodes 1..n-1 (+ node n when broken)


def node_points(n: int, broken: bool) -> tuple[np.ndarray, np.ndarray]:
    seg = np.arange(1, n, dtype=np.int64)
    s = np.zeros(n - 1)
    if broken:
        seg = np.append(seg, n - 1)
        s = np.append(s, 1.0)
    return seg, s


def _merge(seabed, obstacles):
    """Nearest surface of (seabed query, obstacles-only query), each a (dist, normal, idx) triple."""
    closer = obstacles[0] < seabed[0]
    dist = np.where(closer, obstacles[0], seabed[0])
    normal = np.where(closer[:, None], obstacles[1], seabed[1])
    idx = np.where(closer, obstacles[2], seabed[2])
    return dist, normal, idx


def build(world, x: np.ndarray, cand: list[int], broken: bool, radius: float, spacing: float,
          cache_m: float) -> ContactSet:
    """Contact points with fresh tangent planes for the cable shape ``x``."""
    n = len(x) - 1
    seg, s = node_points(n, broken)
    if n <= 1:
        seg, s = np.zeros(0, np.int64), np.zeros(0)
    node = seg + np.round(s).astype(np.int64)
    floor = world.sdf_many(x, [])
    if cand:
        far = world.sdf_many(x, cand, include_seabed=False)
        dist, normal, idx = _merge(floor, far)
    else:
        far = None
        dist, normal, idx = floor
    pts = x[node]
    dist, normal, idx = dist[node], normal[node], idx[node]
    node_count = len(seg)
    if far is not None:
        length = np.linalg.norm(x[1:] - x[:-1], axis=1)
        # 0.1 m margin per node covers CLEAR_TRAVEL_M of travel before the set is rebuilt
        reach = far[0][:-1] + far[0][1:] < length + 2.0 * (radius + 0.1)
        count = np.where(reach, np.ceil(length / spacing).astype(np.int64), 1)
        extra = np.maximum(count - 1, 0)
        seg_extra = np.repeat(np.arange(n, dtype=np.int64), extra)
        if len(seg_extra):
            first = np.repeat(np.cumsum(extra) - extra, extra)
            k = np.arange(len(seg_extra)) - first + 1
            s_extra = k / count[seg_extra]
            p_extra = (1.0 - s_extra)[:, None] * x[seg_extra] + s_extra[:, None] * x[seg_extra + 1]
            d2, n2, i2 = world.sdf_many(p_extra, cand)
            keep = d2 < radius + cache_m + 0.05
            seg = np.concatenate([seg, seg_extra[keep]])
            s = np.concatenate([s, s_extra[keep]])
            pts = np.concatenate([pts, p_extra[keep]])
            dist = np.concatenate([dist, d2[keep]])
            normal = np.concatenate([normal, n2[keep]])
            idx = np.concatenate([idx, i2[keep]])
    return ContactSet(seg.astype(np.int64), s.astype(float), pts, dist, normal, idx.astype(np.int64),
                      idx >= 0, node_count)


def distances(contacts: ContactSet, x: np.ndarray) -> np.ndarray:
    """Tangent-plane distance of every contact point for the current cable shape."""
    n = len(x) - 1
    s = contacts.s[:, None]
    pts = (1.0 - s) * x[contacts.seg] + s * x[np.minimum(contacts.seg + 1, n)]
    return contacts.dist0 + np.einsum("ij,ij->i", pts - contacts.anchor, contacts.normal)


def touching(contacts: ContactSet, x: np.ndarray, radius: float, cache_m: float) -> np.ndarray:
    """Points within 2 cm of contact. Only points that started near a surface can be: a point stays
    within ``cache_m`` of its anchor, or within its clearance when it started clear (see
    ``_cable_accel._contact_valid``), or the set is rebuilt."""
    out = np.zeros(len(contacts.seg), bool)
    near = np.flatnonzero(contacts.dist0 < radius + 0.02 + cache_m)
    if len(near) == 0:
        return out
    n = len(x) - 1
    seg = contacts.seg[near]
    s = contacts.s[near][:, None]
    pts = (1.0 - s) * x[seg] + s * x[np.minimum(seg + 1, n)]
    dist = contacts.dist0[near] + np.einsum("ij,ij->i", pts - contacts.anchor[near], contacts.normal[near])
    out[near] = dist < radius + 0.02
    return out


def _axis_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Canonical (axis, e1, e2): axis flipped so its largest component is positive; vertical gives x, y."""
    a = axis / np.linalg.norm(axis)
    if a[int(np.argmax(np.abs(a)))] < 0:
        a = -a
    ref = np.zeros(3)
    ref[int(np.argmin(np.abs(a)))] = 1.0
    e1 = ref - np.dot(ref, a) * a
    e1 /= np.linalg.norm(e1)
    return a, e1, np.cross(a, e1)


_FRAMES: dict = {}


def _cylinder_frame(ob: Cylinder):
    """(p0, axis, e1, e2, lo, hi) of a cylinder, cached while its end points stay the same."""
    key = (id(ob), ob.p0, ob.p1)
    frame = _FRAMES.get(key)
    if frame is None:
        p0 = np.asarray(ob.p0, float)
        axis = np.asarray(ob.p1, float) - p0
        if float(np.linalg.norm(axis)) < 1e-9:
            frame = ()
        else:
            a, e1, e2 = _axis_basis(axis)
            along = float(np.dot(axis, a))
            frame = (p0, a, e1, e2, min(0.0, along), max(0.0, along))
        if len(_FRAMES) > 4096:
            _FRAMES.clear()
        _FRAMES[key] = frame
    return frame


def _winding(x: np.ndarray, ob: Cylinder) -> float:
    """Signed turns of the cable round a cylinder axis of any orientation (piles, braces, masts)."""
    frame = _cylinder_frame(ob)
    if not frame:
        return 0.0
    p0, a, e1, e2, lo, hi = frame
    rel = x - p0
    along = rel @ a
    radial = rel - along[:, None] * a
    near = (along >= lo - 0.5) & (along <= hi + 0.5)
    near &= np.linalg.norm(radial, axis=1) < ob.radius + 2.5
    ang = np.arctan2(radial @ e2, radial @ e1)
    step = (np.diff(ang) + math.pi) % (2 * math.pi) - math.pi
    both = near[1:] & near[:-1]
    return float(np.sum(step[both])) / (2 * math.pi)


def _contact_turning(x: np.ndarray, node_touch: np.ndarray, node_obstacle: np.ndarray, index: int) -> float:
    """Unsigned turns of cable direction over the nodes resting on one obstacle (boxes, wrecks, rocks)."""
    d = np.diff(x, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1), 1e-9)[:, None]
    cosang = np.clip(np.einsum("ij,ij->i", d[1:], d[:-1]), -1.0, 1.0)
    inner = node_touch[1:-1] & (node_obstacle[1:-1] == index)
    return float(np.sum(np.arccos(cosang)[inner])) / (2 * math.pi)


def wrap_counts(world, x: np.ndarray, cand: list[int], node_touch: np.ndarray,
                node_obstacle: np.ndarray) -> dict[str, float]:
    """Turns of cable round each nearby obstacle; reported when at least a quarter turn.

    Cylinders keep the signed winding count the untangle scenario relies on (now for any axis
    orientation, so horizontal and inclined braces count too). Other shapes, including the wreck
    distance field, report the unsigned turning of the cable over the nodes touching them."""
    out = {}
    for i in cand:
        ob = world.obstacles[i]
        # fittings (anodes, J-tubes, scour rock...) are touched and snagged but do not report turns
        if ob.kind == "habitat" or ob.kind in APPURTENANCE_KINDS or isinstance(ob, Wall):
            continue
        if isinstance(ob, SnagFeature):
            turns = _contact_turning(x, node_touch, node_obstacle, i)
        elif isinstance(ob, Cylinder):
            turns = _winding(x, ob)
        elif hasattr(ob, "sdf_many"):
            turns = _contact_turning(x, node_touch, node_obstacle, i)
        else:
            continue
        if abs(turns) >= 0.25:
            out[ob.name] = float(round(turns, 2))
    return out
