"""Optional compiled loops for ``flow.py``: turbulence synthesis and cylinder flow disturbance.

Numba is optional (requirements-fast.txt). The reference NumPy implementations stay in flow.py
and the tests compare both. Same equations, evaluated point by point without temporaries.
"""
import math

import numpy as np

try:
    from numba import njit
except ImportError:
    njit = None


def _cylinders(X, U, travel, a, ax, length, R, phase0, strouhal, shed_amplitude, wake_decay_d, wake_range_d):
    n, m = X.shape[0], a.shape[0]
    V = U.copy()
    inside = np.zeros(n, np.bool_)
    two_pi = 2.0 * math.pi
    for p in range(n):
        for c in range(m):
            rx, ry, rz = X[p, 0] - a[c, 0], X[p, 1] - a[c, 1], X[p, 2] - a[c, 2]
            axx, axy, axz = ax[c, 0], ax[c, 1], ax[c, 2]
            t = rx * axx + ry * axy + rz * axz
            t_in = min(max(t, 0.0), length[c])
            along = t - t_in
            px, py, pz = rx - t * axx, ry - t * axy, rz - t * axz
            r = math.sqrt(px * px + py * py + pz * pz)
            Rc = R[c]
            if r < Rc and along == 0.0:
                inside[p] = True
            fade_scale = max(Rc, 0.3)
            end_fade = math.exp(-(along / fade_scale) ** 2)
            if end_fade < 1e-12:
                continue
            ua = U[p, 0] * axx + U[p, 1] * axy + U[p, 2] * axz
            ux, uy, uz = U[p, 0] - ua * axx, U[p, 1] - ua * axy, U[p, 2] - ua * axz
            up = math.sqrt(ux * ux + uy * uy + uz * uz)
            if up <= 1e-4:
                continue
            e1x, e1y, e1z = ux / up, uy / up, uz / up
            e2x = axy * e1z - axz * e1y
            e2y = axz * e1x - axx * e1z
            e2z = axx * e1y - axy * e1x
            x = px * e1x + py * e1y + pz * e1z
            y = px * e2x + py * e2y + pz * e2z
            D = 2.0 * Rc
            r2 = max(r * r, Rc * Rc)
            du = -Rc * Rc * (x * x - y * y) / (r2 * r2)
            dv = -Rc * Rc * 2.0 * x * y / (r2 * r2)
            u1, u2 = (1.0 + du) - 1.0, dv
            if 0 < x < wake_range_d * D:
                s = min(x / Rc, 1.0)
                onset = s * s * (3.0 - 2.0 * s)
                width = Rc * math.sqrt(1.0 + x / D)
                amp = 1.0 / (1.0 + x / (wake_decay_d * D))
                deficit = amp * math.exp(-0.5 * (y / width) ** 2) * onset
                phase = two_pi * (strouhal * travel[p] / D - x / (4.0 * D)) + phase0[c]
                shed = shed_amplitude * amp * onset * math.exp(-0.5 * (y / (1.5 * width)) ** 2) * math.sin(phase)
                u1 = (1.0 + du) * (1.0 - deficit) - 1.0
                u2 = dv * (1.0 - deficit) + shed
            k1, k2 = u1 * up * end_fade, u2 * up * end_fade
            V[p, 0] += k1 * e1x + k2 * e2x
            V[p, 1] += k1 * e1y + k2 * e2y
            V[p, 2] += k1 * e1z + k2 * e2z
    for p in range(n):
        if inside[p]:
            V[p, 0] = 0.0
            V[p, 1] = 0.0
            V[p, 2] = 0.0
    return V


cylinders = njit(cache=True)(_cylinders) if njit is not None else None


def _turbulence(X, mean, displacement, inv_ell, k, phase, amp, intensity, ratios, fallback_x, fallback_y):
    """Fused ``TurbulenceField.unit`` + ``turbulence_vectors`` (k: (3, modes, 3), phase: (3, modes))."""
    n, modes = X.shape[0], k.shape[1]
    out = np.zeros((n, 3))
    unit = np.zeros(3)
    for p in range(n):
        mx, my, mz = mean[p, 0], mean[p, 1], mean[p, 2]
        speed_h = math.sqrt(mx * mx + my * my)
        sigma = intensity * math.sqrt(speed_h * speed_h + mz * mz)
        if sigma == 0.0:
            continue
        x = (X[p, 0] - displacement[0]) * inv_ell
        y = (X[p, 1] - displacement[1]) * inv_ell
        z = (X[p, 2] - displacement[2]) * inv_ell
        for c in range(3):
            total = 0.0
            for j in range(modes):
                total += math.cos(x * k[c, j, 0] + y * k[c, j, 1] + z * k[c, j, 2] + phase[c, j])
            unit[c] = amp * total
        if speed_h < 1e-6:
            ex, ey = fallback_x, fallback_y
        else:
            ex, ey = mx / speed_h, my / speed_h
        u = unit[0] * ratios[0] * sigma
        v = unit[1] * ratios[1] * sigma
        taper = min(max(X[p, 2] * 0.5, 0.0), 1.0)
        out[p, 0] = ex * u - ey * v
        out[p, 1] = ey * u + ex * v
        out[p, 2] = unit[2] * ratios[2] * sigma * taper
    return out


turbulence = njit(cache=True)(_turbulence) if njit is not None else None


def _mean_profile(depths, heights, layers, seabed, roughness, ref_height):
    """Three-layer interpolation and log-law bed factor, without temporary arrays."""
    out = np.empty((len(depths), 3))
    z0 = max(roughness, 1e-6)
    denominator = math.log(max(ref_height, 2 * z0) / z0)
    for i in range(len(depths)):
        level = min(2., max(0., depths[i] * 2 / seabed))
        lower = min(1, int(level))
        weight = level - lower
        factor = 1.
        if heights[i] < ref_height:
            factor = max(0., math.log(max(z0, heights[i]) / z0) / denominator)
        for axis in range(3):
            start = layers[lower, axis]
            out[i, axis] = (start + weight * (layers[lower + 1, axis] - start)) * factor
    return out


def _box_flow(X, U, centre, half, yaw, solid, bypass, shelter, blocking):
    V = U.copy()
    c, s = math.cos(yaw), math.sin(yaw)
    for i in range(len(X)):
        z = abs(X[i, 2] - centre[2])
        if z >= 1.5 * half[2] + 0.5:
            continue
        x, y = X[i, 0] - centre[0], X[i, 1] - centre[1]
        lx, ly = c * x + s * y, -s * x + c * y
        factor = 1.
        if abs(lx) <= half[0] and abs(ly) <= half[1] and z <= half[2]:
            factor = 0. if solid else 1. - 0.8
        else:
            speed = math.hypot(U[i, 0], U[i, 1])
            if speed <= 1e-6:
                continue
            dx = (c * U[i, 0] + s * U[i, 1]) / speed
            dy = (-s * U[i, 0] + c * U[i, 1]) / speed
            along = lx * dx + ly * dy
            across = abs(-lx * dy + ly * dx)
            length = half[0] * abs(dx) + half[1] * abs(dy)
            width = half[0] * abs(dy) + half[1] * abs(dx)
            size = max(min(2 * width, 2 * half[2]), 0.5)
            margin = 0.3 * width + 0.5
            vertical = min(1., (1.5 * half[2] + 0.5 - z) / (0.5 * half[2] + 0.5))
            lateral = max(0., min(1., (width + margin - across) / margin))
            gap = max(0., abs(along) - length)
            if lateral:
                deficit = shelter * math.exp(-gap / (3 * size)) if along > 0 else blocking * math.exp(-gap / size)
                factor -= deficit * lateral * vertical
            if bypass and abs(along) < length:
                u = min(1., abs(along) / max(length, 0.1))
                shoulder = math.exp(-((across - width - margin) / margin) ** 2)
                factor += 0.2 * shoulder * vertical * (1 - u * u * (3 - 2 * u))
        for axis in range(3):
            V[i, axis] *= factor
    return V


mean_profile = njit(cache=True)(_mean_profile) if njit is not None else None
box_flow = njit(cache=True)(_box_flow) if njit is not None else None


def _ramp(u):
    u = min(1., max(0., u))
    return u * u * (3 - 2 * u)


# Single pointwise implementation also works as pure Python without Numba.
if njit is not None:
    _ramp = njit(inline="always")(_ramp)


def _pen_flow(X, U, centre, radius, depth):
    """Porous net envelope: attenuate the through-flow and accelerate the shoulders."""
    V = U.copy()
    for i in range(len(X)):
        x = (X[i, 0] - centre[0]) / radius
        y = (X[i, 1] - centre[1]) / radius
        radial = math.hypot(x, y)
        if radial >= 3 or X[i, 2] >= depth + 2:
            continue
        speed = math.hypot(U[i, 0], U[i, 1])
        if speed == 0:
            continue
        along = (x * U[i, 0] + y * U[i, 1]) / speed
        across = abs(x * U[i, 1] - y * U[i, 0]) / speed
        shelter = (1 - _ramp((across - 0.8) / 0.25)) * _ramp((along + 1.2) / 0.4)
        shoulder = math.exp(-((across - 1.05) / 0.2) ** 2 - along ** 2)
        fade = (1 - _ramp(radial - 2)) * _ramp((depth + 2 - X[i, 2]) / 2)
        factor = 1 + fade * (0.18 * shoulder - 0.3 * shelter)
        V[i, 0] *= factor
        V[i, 1] *= factor
    return V


pen_flow = njit(cache=True)(_pen_flow) if njit is not None else _pen_flow


def _wave_velocity(points, omega, k, north, east, amplitude, time_s):
    """Particle velocity in NED at each submerged point on a deep-water Airy orbit."""
    out = np.empty((len(points), 3))
    for i in range(len(points)):
        phase = k * (north * points[i, 0] + east * points[i, 1]) - omega * time_s
        speed = amplitude * math.exp(-k * max(points[i, 2], 0.))
        horizontal = speed * math.cos(phase)
        out[i, 0] = north * horizontal
        out[i, 1] = east * horizontal
        out[i, 2] = -speed * math.sin(phase)
    return out


wave_velocity = njit(cache=True)(_wave_velocity) if njit is not None else _wave_velocity
