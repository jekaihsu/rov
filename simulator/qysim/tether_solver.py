"""NumPy reference implementation of one tether substep and the contact pass.

``_cable_accel.py`` holds the compiled twin; both must stay numerically equivalent (tests compare
them to 1e-8). See that module's docstring for the algorithm. The reference vectorises everything
except the tridiagonal (Thomas) solve and the sequential contact projection, which are loops in
both paths so the arithmetic order matches.

Axial model (gap 3 in research_notes/臍帶纜物理與收放文獻/simulators_and_current_model.md):
tension-only segments with the physical stiffness EA / l0 (no length-dependent cap) and internal
damping c = zeta * sqrt(EA * w) per MoorDyn's BA rule (cable_dynamics_models.md §2, §6). The axial
spring-damper is integrated with backward Euler, so the 0.01 s outer step stays stable for any EA
and segment length; transverse motion and drag stay explicit (symplectic Euler).
"""
from __future__ import annotations

import math

import numpy as np

from ._cable_accel import (CLEAR_TRAVEL_M, REEL_DRIVE, REEL_INV_MASS, REEL_KINETIC, REEL_ROOM_IN, REEL_ROOM_OUT,
                           REEL_SPEED, REEL_STATIC, REEL_TENSION, REEL_VISCOUS)


def _inv_mass_apply(ms, ma, t, w):
    """M^-1 w per node for structural mass ms (all directions) and added mass ma (normal only)."""
    total = ms + ma
    w_t = np.einsum("ij,ij->i", w, t)
    return w / total[:, None] + (w_t * (1.0 / ms - 1.0 / total))[:, None] * t


def _inv_mass_dot(ms, ma, t, a, b):
    total = ms + ma
    a_t = np.einsum("ij,ij->i", a, t)
    b_t = np.einsum("ij,ij->i", b, t)
    return np.einsum("ij,ij->i", a, b) / total + a_t * b_t * (1.0 / ms - 1.0 / total)


def _thomas(lower, diag, upper, rhs, active, tension):
    n = len(diag)
    cp = [0.0] * n
    dp = [0.0] * n
    for i in range(n):
        lo = lower[i] if active[i] else 0.0
        di = diag[i] if active[i] else 1.0
        up = upper[i] if active[i] else 0.0
        ri = rhs[i] if active[i] else 0.0
        if i == 0:
            cp[i] = up / di
            dp[i] = ri / di
        else:
            den = di - lo * cp[i - 1]
            cp[i] = up / den
            dp[i] = (ri - lo * dp[i - 1]) / den
    tension[n - 1] = dp[n - 1]
    for i in range(n - 2, -1, -1):
        tension[i] = dp[i] - cp[i] * tension[i + 1]


def advance(x, v, water, water_accel, l0, ms, ma, lw, spool, gland, gland_vel, broken, h, ea, c_int,
            diameter, cd_normal, cd_tangent, wet_n_per_m, rho, cap, reel,
            pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension, ei=0.0):
    """Reference substep; same arguments and in-place updates as ``_cable_accel._advance``."""
    n = len(x) - 1
    x[0], v[0] = spool, 0.0
    if not broken:
        x[n], v[n] = gland, gland_vel
    free = np.ones(n + 1, bool)
    free[0] = False
    if not broken:
        free[n] = False
    d = x[1:] - x[:-1]
    length = np.sqrt(np.einsum("ij,ij->i", d, d))
    u = d / np.maximum(length, 1e-9)[:, None]
    left = np.maximum(np.arange(n + 1) - 1, 0)
    right = np.minimum(np.arange(n + 1) + 1, n)
    t = x[right] - x[left]
    t = t / np.maximum(np.sqrt(np.einsum("ij,ij->i", t, t)), 1e-9)[:, None]
    rel = water - v
    proj = np.einsum("ij,ij->i", rel, t)
    vt = proj[:, None] * t
    vn = rel - vt
    vn_mag = np.sqrt(np.einsum("ij,ij->i", vn, vn))
    vt_mag = np.sqrt(np.einsum("ij,ij->i", vt, vt))
    scale = 0.5 * rho * diameter * lw
    force = scale[:, None] * (cd_normal * vn * vn_mag[:, None] + cd_tangent * vt * vt_mag[:, None])
    force[:, 2] += wet_n_per_m * lw
    # Fluid acceleration (Morison inertia): Froude-Krylov rho*A*l*a plus added mass on the normal part.
    acc_t = np.einsum("ij,ij->i", water_accel, t)[:, None] * t
    froude_krylov = rho * 0.25 * math.pi * diameter * diameter * lw
    force += froude_krylov[:, None] * water_accel + ma[:, None] * (water_accel - acc_t)
    cosine = np.einsum("ij,ij->i", u[:-1], u[1:])[:, None]
    stiffness = ei / lw[1:-1, None]
    left = stiffness * (u[1:] - cosine * u[:-1]) / np.maximum(length[:-1, None], 1e-9)
    bend_right = stiffness * (u[:-1] - cosine * u[1:]) / np.maximum(length[1:, None], 1e-9)
    force[:-2] -= left
    force[1:-1] += left - bend_right
    force[2:] += bend_right
    for k in range(len(pin_seg)):
        i, s = int(pin_seg[k]), float(pin_s[k])
        p = (1.0 - s) * x[i] + s * x[i + 1]
        pv = (1.0 - s) * v[i] + s * v[i + 1]
        f = -pin_k[k] * (p - pin_target[k]) - pin_c[k] * pv
        mag = math.sqrt(float(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]))
        pin_force[k] = mag
        if mag > pin_cap[k]:
            f = f * (pin_cap[k] / mag)
        force[i] += (1.0 - s) * f
        force[i + 1] += s * f
    vs = v.copy()
    vs[free] = v[free] + h * _inv_mass_apply(ms[free], ma[free], t[free], force[free])
    inv_j = reel[REEL_INV_MASS]
    pull = reel[REEL_TENSION] + reel[REEL_DRIVE]
    if abs(reel[REEL_SPEED]) < 1e-9 and abs(pull) <= reel[REEL_STATIC]:
        inv_j = 0.0
    if reel[REEL_ROOM_OUT] <= 0.0 and pull >= 0.0:
        inv_j = 0.0
    if reel[REEL_ROOM_IN] <= 0.0 and pull <= 0.0:
        inv_j = 0.0
    reel_star = reel[REEL_SPEED] + h * inv_j * reel[REEL_DRIVE] if inv_j != 0.0 else 0.0
    k_seg = ea / np.maximum(l0, 1e-6)
    beta = k_seg * h + c_int
    diag = np.zeros(n)
    fa, fb = free[:-1], free[1:]
    diag[fa] += _inv_mass_dot(ms[:-1][fa], ma[:-1][fa], t[:-1][fa], u[fa], u[fa])
    diag[fb] += _inv_mass_dot(ms[1:][fb], ma[1:][fb], t[1:][fb], u[fb], u[fb])
    diag[0] += inv_j
    diag += 1.0 / (beta * h)
    upper = np.zeros(n)
    lower = np.zeros(n)
    if n > 1:
        couple = -_inv_mass_dot(ms[1:n], ma[1:n], t[1:n], u[1:], u[:-1])
        inner = free[1:n]
        upper[:-1] = np.where(inner, couple, 0.0)
        lower[1:] = np.where(inner, couple, 0.0)
    rate = np.einsum("ij,ij->i", u, vs[1:] - vs[:-1])
    rate[0] -= reel_star
    rhs = (k_seg * (length - l0) + beta * rate) / (beta * h)
    active = (rhs > 0.0).tolist()
    values = [0.0] * n
    rows = (lower.tolist(), diag.tolist(), upper.tolist(), rhs.tolist())
    for _ in range(12):
        _thomas(*rows, active, values)
        changed = False
        for i in range(n):
            if active[i] and values[i] < 0.0:
                active[i] = False
                changed = True
        if not changed:
            low, _, up, right = rows
            for i in range(n):
                if active[i]:
                    continue
                pull = right[i]
                if i > 0:
                    pull -= low[i] * values[i - 1]
                if i + 1 < n:
                    pull -= up[i] * values[i + 1]
                if pull > 0.0:
                    active[i] = True
                    changed = True
        if not changed:
            break
    solved = np.where(np.array(active, bool), np.array(values), 0.0)
    solved[~np.isfinite(solved)] = 0.0
    tension[:] = np.minimum(np.maximum(solved, 0.0), cap)
    seg_force = tension[:, None] * u
    node_force = np.zeros_like(x)
    node_force[:-1] += seg_force
    node_force[1:] -= seg_force
    v[free] = vs[free] + h * _inv_mass_apply(ms[free], ma[free], t[free], node_force[free])
    speed = reel_star + h * inv_j * tension[0]
    if inv_j > 0.0:
        slip = h * inv_j * (reel[REEL_KINETIC] + reel[REEL_VISCOUS] * abs(speed))
        if abs(speed) <= slip:
            speed = 0.0
        elif speed > 0.0:
            speed -= slip
        else:
            speed += slip
    step = speed * h
    if step > reel[REEL_ROOM_OUT]:
        step = max(reel[REEL_ROOM_OUT], 0.0)
        speed = 0.0
    if step < -reel[REEL_ROOM_IN]:
        step = -max(reel[REEL_ROOM_IN], 0.0)
        speed = 0.0
    l0[0] = max(l0[0] + step, 1e-3)
    reel[REEL_ROOM_OUT] -= step
    reel[REEL_ROOM_IN] += step
    reel[REEL_SPEED] = speed
    reel[REEL_TENSION] = tension[0]
    if broken:
        return np.zeros(3)
    return -tension[n - 1] * u[n - 1] + (bend_right[-1] if n > 1 else 0.0)


def contact_points(x, pt_seg, pt_s):
    s = pt_s[:, None]
    return (1.0 - s) * x[pt_seg] + s * x[pt_seg + 1]


def contact_valid(x, pt_seg, pt_s, anchor, dist0, radius, cache_distance):
    """Reference twin of ``_cable_accel._contact_valid`` (Lipschitz slack for points far from surfaces)."""
    moved = contact_points(x, pt_seg, pt_s) - anchor
    allowed = np.maximum(cache_distance, np.minimum(dist0 - radius - cache_distance, CLEAR_TRAVEL_M))
    return not np.any(np.einsum("ij,ij->i", moved, moved) > allowed * allowed)


def _weights(i, s, n, broken):
    wa = 0.0 if i == 0 else 1.0 - s
    wb = 0.0 if (i + 1 == n and not broken) else s
    return wa, wb, wa * wa + wb * wb


def contact_velocity(x, v, ms, ma, broken, h, pt_seg, pt_s, anchor, dist0, normal, pt_hard, radius,
                     mu_static, mu_kinetic, stribeck_v, regular_v, chafe):
    """Reference contact velocity pass; sequential like the compiled loop because points share nodes."""
    n = len(x) - 1
    if len(pt_seg) == 0:
        return True
    # Cheap vectorised screen: only points near a surface or moving fast can need a correction.
    dist = dist0 + np.einsum("ij,ij->i", contact_points(x, pt_seg, pt_s) - anchor, normal)
    s_col = pt_s[:, None]
    vel = (1.0 - s_col) * v[pt_seg] + s_col * v[pt_seg + 1]
    reach = np.sqrt(np.einsum("ij,ij->i", vel, vel)) * h
    for k in np.flatnonzero(dist - radius < reach + 0.2):
        i, s = int(pt_seg[k]), float(pt_s[k])
        nk = normal[k]
        dk = float(dist0[k])
        vn = 0.0
        for axis in range(3):
            dk += ((1.0 - s) * x[i, axis] + s * x[i + 1, axis] - anchor[k, axis]) * nk[axis]
            vn += ((1.0 - s) * v[i, axis] + s * v[i + 1, axis]) * nk[axis]
        gap = dk - radius
        allowed = -gap / h if gap > 0.0 else 0.0
        if vn >= allowed:
            continue
        wa, wb, wsum = _weights(i, s, n, broken)
        if wsum < 1e-12:
            continue
        push = allowed - vn
        tang = [0.0, 0.0, 0.0]
        for axis in range(3):
            tang[axis] = (1.0 - s) * v[i, axis] + s * v[i + 1, axis] - vn * nk[axis]
        speed = math.sqrt(tang[0] * tang[0] + tang[1] * tang[1] + tang[2] * tang[2])
        mu = (mu_kinetic + (mu_static - mu_kinetic) * math.exp(-speed / stribeck_v)) \
            * math.tanh(math.pi * speed / regular_v)
        seg = [x[i + 1, axis] - x[i, axis] for axis in range(3)]
        un = max(math.sqrt(seg[0] * seg[0] + seg[1] * seg[1] + seg[2] * seg[2]), 1e-9)
        m_s = (1.0 - s) * ms[i] + s * ms[i + 1]
        m_a = (1.0 - s) * ma[i] + s * ma[i + 1]
        along_n = (seg[0] * nk[0] + seg[1] * nk[1] + seg[2] * nk[2]) / un
        along_t = (seg[0] * tang[0] + seg[1] * tang[1] + seg[2] * tang[2]) / (un * max(speed, 1e-12))
        mass_n = m_s + m_a * (1.0 - along_n * along_n)
        mass_t = m_s + m_a * (1.0 - along_t * along_t)
        cut = min(speed, mu * push * mass_n / mass_t)
        ratio = cut / max(speed, 1e-12)
        dv = [push * nk[axis] - ratio * tang[axis] for axis in range(3)]
        for axis in range(3):
            v[i, axis] += wa * dv[axis] / wsum
            v[i + 1, axis] += wb * dv[axis] / wsum
        if pt_hard[k]:
            chafe[i] += mu * mass_n * push * speed
    return True


def integrate(x, v, h, broken):
    last = len(x) if broken else len(x) - 1
    x[1:last] += v[1:last] * h


def project(x, broken, pt_seg, pt_s, anchor, dist0, normal, radius):
    """Reference positional correction (sequential)."""
    n = len(x) - 1
    if len(pt_seg) == 0:
        return
    dist = dist0 + np.einsum("ij,ij->i", contact_points(x, pt_seg, pt_s) - anchor, normal)
    for k in np.flatnonzero(radius - dist > -0.2):
        i, s = int(pt_seg[k]), float(pt_s[k])
        nk = normal[k]
        dk = float(dist0[k])
        for axis in range(3):
            dk += ((1.0 - s) * x[i, axis] + s * x[i + 1, axis] - anchor[k, axis]) * nk[axis]
        pen = min(radius - dk, 0.05)
        if pen <= 0.0:
            continue
        wa, wb, wsum = _weights(i, s, n, broken)
        if wsum < 1e-12:
            continue
        lam = pen / wsum
        for axis in range(3):
            x[i, axis] += wa * lam * nk[axis]
            x[i + 1, axis] += wb * lam * nk[axis]
