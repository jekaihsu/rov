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
            xp = max(x, 0.0)
            s = min(max(x / Rc, 0.0), 1.0)
            onset = s * s * (3.0 - 2.0 * s)
            width = Rc * math.sqrt(1.0 + xp / D)
            amp = 1.0 / (1.0 + xp / (wake_decay_d * D))
            reach = 1.0 if x < wake_range_d * D else 0.0
            deficit = amp * math.exp(-0.5 * (y / width) ** 2) * onset * reach
            phase = two_pi * (strouhal * travel[p] / D - xp / (4.0 * D)) + phase0[c]
            shed = shed_amplitude * amp * onset * reach * math.exp(-0.5 * (y / (1.5 * width)) ** 2) * math.sin(phase)
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
