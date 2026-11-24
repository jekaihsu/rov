"""Gamepad input shaping for ROV-01 (Wave 2): radial deadzone + expo curve.

Pure functions, no simulator state. Mirrored 1:1 by viewer/input_shaping.js
(parity is unit-tested).

    r      = |(x, y)|                      (clipped to 1: square-gate sticks)
    r<=dz  -> (0, 0)                       radial deadzone (no cross-shaped dead band)
    u      = (r - dz) / (1 - dz)           rescale -> output starts at 0 exactly at the
                                           deadzone edge (continuous) and reaches 1 at r=1
    s      = (1 - e) * u + e * u**3        expo blend (e=0 linear, e=1 pure cubic)
    out    = (x, y) * s / r, clamped to [-1, 1]
"""
from __future__ import annotations

import math

DEADZONE_MAX = 0.45
DEFAULT_DEADZONE = 0.08
DEFAULT_EXPO = 0.35


def _num(v, default: float) -> float:
    if isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _clamp(v: float, lo: float, hi: float) -> float:
    f = _num(v, 0.0)
    return lo if f < lo else hi if f > hi else f


def sanitize(deadzone=DEFAULT_DEADZONE, expo=DEFAULT_EXPO) -> tuple[float, float]:
    """Clamp parameters; 0 is a legal value (no silent fallback to defaults)."""
    return (_clamp(_num(deadzone, DEFAULT_DEADZONE), 0.0, DEADZONE_MAX),
            _clamp(_num(expo, DEFAULT_EXPO), 0.0, 1.0))


def expo_curve(u: float, expo: float) -> float:
    u = _clamp(_num(u, 0.0), 0.0, 1.0)
    ex = _clamp(_num(expo, DEFAULT_EXPO), 0.0, 1.0)
    return _clamp((1.0 - ex) * u + ex * u * u * u, 0.0, 1.0)


def radial_deadzone_expo(x, y, deadzone=DEFAULT_DEADZONE, expo=DEFAULT_EXPO) -> tuple[float, float]:
    """Shape one 2-axis stick. Returns (x, y) each in [-1, 1]."""
    dz, ex = sanitize(deadzone, expo)
    x = _clamp(_num(x, 0.0), -1.0, 1.0)
    y = _clamp(_num(y, 0.0), -1.0, 1.0)
    r = math.hypot(x, y)
    if not math.isfinite(r) or r <= dz or r == 0.0:
        return 0.0, 0.0
    rc = min(r, 1.0)
    u = (rc - dz) / max(1e-9, 1.0 - dz)
    scale = expo_curve(u, ex) / r
    return _clamp(x * scale, -1.0, 1.0), _clamp(y * scale, -1.0, 1.0)


def axis_deadzone_expo(v, deadzone=DEFAULT_DEADZONE, expo=DEFAULT_EXPO) -> float:
    """1-D special case (wheels / single axes)."""
    return radial_deadzone_expo(v, 0.0, deadzone, expo)[0]


def shape_stick_2d(x, y, deadzone=DEFAULT_DEADZONE, expo=DEFAULT_EXPO) -> tuple[float, float]:
    """Alias for radial_deadzone_expo (2D stick boundary shaping)."""
    return radial_deadzone_expo(x, y, deadzone, expo)


def shape_gamepad_6dof(raw_axes, deadzone=DEFAULT_DEADZONE, expo=DEFAULT_EXPO) -> dict[str, float]:
    """Boundary-guarded 6-DoF gamepad shaping."""
    axes = raw_axes if isinstance(raw_axes, dict) else {}
    dz, ex = sanitize(deadzone, expo)
    keys = ("surge", "sway", "heave", "roll", "pitch", "yaw")
    return {k: round(axis_deadzone_expo(axes.get(k, 0.0), dz, ex), 6) for k in keys}
