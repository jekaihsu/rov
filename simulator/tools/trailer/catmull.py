"""Catmull-Rom camera path evaluation (mirrors viewer/trailer/camera_path.js)."""

from __future__ import annotations

import math
from typing import Any


MODES = ('follow', 'orbit', 'fixed', 'onboard')


def catmull_rom(p0, p1, p2, p3, t: float) -> list[float]:
    """Uniform Catmull-Rom between p1 and p2; t in [0, 1]."""
    t2 = t * t
    t3 = t2 * t
    out = []
    for i in range(len(p1)):
        a, b, c, d = p0[i], p1[i], p2[i], p3[i]
        out.append(0.5 * ((2 * b) + (-a + c) * t
                          + (2 * a - 5 * b + 4 * c - d) * t2
                          + (-a + 3 * b - 3 * c + d) * t3))
    return out


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def segment_index(times: list[float], t: float) -> int:
    if not times:
        return 0
    if t <= times[0]:
        return 0
    for i in range(len(times) - 1):
        if t <= times[i + 1]:
            return i
    return max(0, len(times) - 2)


def _point_at(keyframes: list[dict], attr: str, index: int):
    index = _clamp(index, 0, len(keyframes) - 1)
    return keyframes[int(index)][attr]


def interpolate_vector(keyframes: list[dict], attr: str, t: float) -> list[float] | None:
    """Catmull-Rom for a vector attribute; None when any keyframe omits it (optional lookAt/offset)."""
    if not keyframes:
        return None
    if not all(isinstance(frame.get(attr), (list, tuple)) for frame in keyframes):
        return None
    if len(keyframes) == 1:
        return list(_point_at(keyframes, attr, 0))
    times = [frame['t'] for frame in keyframes]
    i = segment_index(times, t)
    t0 = times[i]
    t1 = times[min(i + 1, len(times) - 1)]
    u = _clamp((t - t0) / (t1 - t0), 0, 1) if t1 > t0 else 0.0
    p0 = _point_at(keyframes, attr, i - 1)
    p1 = _point_at(keyframes, attr, i)
    p2 = _point_at(keyframes, attr, i + 1)
    p3 = _point_at(keyframes, attr, i + 2)
    return catmull_rom(p0, p1, p2, p3, u)


def interpolate_scalar(keyframes: list[dict], attr: str, t: float, fallback: float) -> float:
    if not keyframes:
        return fallback
    series = [{'t': frame['t'], 'v': [fallback if frame.get(attr) is None else float(frame[attr])]}
              for frame in keyframes]
    times = [frame['t'] for frame in series]
    i = segment_index(times, t)
    t0 = times[i]
    t1 = times[min(i + 1, len(times) - 1)]
    u = _clamp((t - t0) / (t1 - t0), 0, 1) if t1 > t0 else 0.0
    p0 = series[_clamp(i - 1, 0, len(series) - 1)]['v']
    p1 = series[i]['v']
    p2 = series[_clamp(i + 1, 0, len(series) - 1)]['v']
    p3 = series[_clamp(i + 2, 0, len(series) - 1)]['v']
    return catmull_rom(p0, p1, p2, p3, u)[0]


def evaluate_camera_path(path: dict[str, Any] | None, t: float, rov: dict[str, Any]) -> dict[str, Any] | None:
    """Return {mode, position, lookAt, fov} or onboard stub; mirrors the viewer module."""
    if not path or not path.get('mode'):
        return None
    mode = path['mode']
    if mode not in MODES:
        raise ValueError(f'unknown camera mode {mode}')
    if mode == 'onboard':
        return {'mode': mode, 'position': None, 'lookAt': None, 'fov': 70.0}
    keyframes = path.get('keyframes') or []
    if not keyframes:
        raise ValueError(f'camera mode {mode} needs keyframes')
    fov = interpolate_scalar(keyframes, 'fov', t, float(path.get('fov', 55)))
    position = rov['position']
    if mode == 'fixed':
        return {
            'mode': mode,
            'position': interpolate_vector(keyframes, 'position', t),
            'lookAt': interpolate_vector(keyframes, 'lookAt', t) or list(position),
            'fov': fov,
        }
    if mode == 'follow':
        offset = interpolate_vector(keyframes, 'offset', t) or [0.0, 1.2, -3.5]
        heading = float(rov.get('heading') or 0.0)
        cos_h = math.cos(heading)
        sin_h = math.sin(heading)
        world = [
            position[0] + offset[0] * cos_h + offset[2] * sin_h,
            position[1] + offset[1],
            position[2] - offset[0] * sin_h + offset[2] * cos_h,
        ]
        look = interpolate_vector(keyframes, 'lookOffset', t) or [0.0, 0.2, 1.5]
        look_at = [
            position[0] + look[0] * cos_h + look[2] * sin_h,
            position[1] + look[1],
            position[2] - look[0] * sin_h + look[2] * cos_h,
        ]
        return {'mode': mode, 'position': world, 'lookAt': look_at, 'fov': fov}
    azimuth = interpolate_scalar(keyframes, 'azimuth', t, 0.0)
    radius = interpolate_scalar(keyframes, 'radius', t, 4.5)
    height = interpolate_scalar(keyframes, 'height', t, 1.2)
    return {
        'mode': mode,
        'position': [
            position[0] + math.cos(azimuth) * radius,
            position[1] + height,
            position[2] + math.sin(azimuth) * radius,
        ],
        'lookAt': list(position),
        'fov': fov,
    }
