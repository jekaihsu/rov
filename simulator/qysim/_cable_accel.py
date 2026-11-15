"""Compiled (Numba) twin of the tether substep in ``tether.py``.

The reference implementation is the NumPy code in ``tether_solver.py``; this module repeats the
same arithmetic as scalar loops so Numba can compile it. Numba is optional. No fast-math
transforms are used, and tests compare both paths to 1e-8 (``tests/test_ecology.py``).

One substep (h = dt / substeps) does:
    1. kinematic ends: spool node pinned, gland node moved along its tick velocity
    2. explicit forces: Morison drag (normal + tangential), wet weight, fluid acceleration (Froude-Krylov
       plus normal added mass, from the filtered water acceleration at the node), snag pins
    3. implicit axial solve: tension-only compliant segments (EA / l0) with MoorDyn-style
       internal damping, solved as one tridiagonal system with an active set (slack segments
       carry no tension). The reel's line inertia couples to segment 0.
    4. reel payout grows segment 0 only (node positions move after the contact pass)
Then, per substep, a contact velocity pass over "contact points" (nodes and samples inside long
segments), the position update, and a positional projection (see ``_batch``).
"""
import math

import numpy as np

try:
    from numba import njit
except ImportError:
    njit = None

# reel state vector layout, shared with tether_solver.py
REEL_SPEED = 0          # payout speed, m/s (+ = out)
REEL_INV_MASS = 1       # 1 / equivalent line inertia of drum and wound tether, 1/kg
REEL_DRIVE = 2          # servo / tender force along payout, N
REEL_STATIC = 3         # static friction or brake holding force, N
REEL_KINETIC = 4        # kinetic friction or brake slip force, N
REEL_ROOM_OUT = 5       # tether still on the drum, m
REEL_ROOM_IN = 6        # deployed length above the minimum, m
REEL_TENSION = 7        # spool-segment tension of the previous substep, N
REEL_VISCOUS = 8        # viscous drum drag (slip clutch), N s/m
REEL_SIZE = 9
# Largest travel of a clear contact point before its plane is refreshed (see _contact_valid).
CLEAR_TRAVEL_M = 0.05


def _inv_mass_dot(ms, ma, tx, ty, tz, ax, ay, az, bx, by, bz):
    """b . M^-1 a for a node with structural mass ms and added mass ma normal to tangent t."""
    total = ms + ma
    a_t = ax * tx + ay * ty + az * tz
    b_t = bx * tx + by * ty + bz * tz
    return (ax * bx + ay * by + az * bz) / total + a_t * b_t * (1.0 / ms - 1.0 / total)


def _advance(x, v, water, water_accel, l0, ms, ma, lw, spool, gland, gland_vel, broken, h, ea, c_int,
             diameter, cd_normal, cd_tangent, wet_n_per_m, rho, cap, reel,
             pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension):
    n = len(x) - 1
    x[0] = spool
    v[0] = 0.0
    if not broken:
        x[n] = gland
        v[n] = gland_vel
    free = np.ones(n + 1)
    free[0] = 0.0
    if not broken:
        free[n] = 0.0
    # segment geometry
    u = np.empty((n, 3))
    length = np.empty(n)
    for i in range(n):
        dx = x[i + 1, 0] - x[i, 0]
        dy = x[i + 1, 1] - x[i, 1]
        dz = x[i + 1, 2] - x[i, 2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz)
        length[i] = L
        den = max(L, 1e-9)
        u[i, 0] = dx / den
        u[i, 1] = dy / den
        u[i, 2] = dz / den
    # node tangents
    t = np.empty((n + 1, 3))
    for j in range(n + 1):
        left = max(0, j - 1)
        right = min(n, j + 1)
        tx = x[right, 0] - x[left, 0]
        ty = x[right, 1] - x[left, 1]
        tz = x[right, 2] - x[left, 2]
        norm = max(math.sqrt(tx * tx + ty * ty + tz * tz), 1e-9)
        t[j, 0] = tx / norm
        t[j, 1] = ty / norm
        t[j, 2] = tz / norm
    # explicit forces: drag, wet weight, fluid acceleration
    force = np.zeros((n + 1, 3))
    area = 0.25 * math.pi * diameter * diameter
    for j in range(n + 1):
        rx = water[j, 0] - v[j, 0]
        ry = water[j, 1] - v[j, 1]
        rz = water[j, 2] - v[j, 2]
        proj = rx * t[j, 0] + ry * t[j, 1] + rz * t[j, 2]
        vx = proj * t[j, 0]
        vy = proj * t[j, 1]
        vz = proj * t[j, 2]
        nx = rx - vx
        ny = ry - vy
        nz = rz - vz
        vn = math.sqrt(nx * nx + ny * ny + nz * nz)
        vt = math.sqrt(vx * vx + vy * vy + vz * vz)
        scale = 0.5 * rho * diameter * lw[j]
        force[j, 0] += scale * (cd_normal * nx * vn + cd_tangent * vx * vt)
        force[j, 1] += scale * (cd_normal * ny * vn + cd_tangent * vy * vt)
        force[j, 2] += scale * (cd_normal * nz * vn + cd_tangent * vz * vt) + wet_n_per_m * lw[j]
        # Morison inertia of accelerating water: Froude-Krylov rho*A*l*a plus added mass on the normal part
        ax = water_accel[j, 0]
        ay = water_accel[j, 1]
        az = water_accel[j, 2]
        a_t = ax * t[j, 0] + ay * t[j, 1] + az * t[j, 2]
        fk = rho * area * lw[j]
        force[j, 0] += fk * ax + ma[j] * (ax - a_t * t[j, 0])
        force[j, 1] += fk * ay + ma[j] * (ay - a_t * t[j, 1])
        force[j, 2] += fk * az + ma[j] * (az - a_t * t[j, 2])
    # snag pins: a point of the cable held by a feature, force capped at the holding force
    for k in range(len(pin_seg)):
        i = pin_seg[k]
        s = pin_s[k]
        fx = 0.0
        fy = 0.0
        fz = 0.0
        for axis in range(3):
            p = (1.0 - s) * x[i, axis] + s * x[i + 1, axis]
            pv = (1.0 - s) * v[i, axis] + s * v[i + 1, axis]
            f = -pin_k[k] * (p - pin_target[k, axis]) - pin_c[k] * pv
            if axis == 0:
                fx = f
            elif axis == 1:
                fy = f
            else:
                fz = f
        mag = math.sqrt(fx * fx + fy * fy + fz * fz)
        pin_force[k] = mag
        if mag > pin_cap[k]:
            ratio = pin_cap[k] / mag
            fx *= ratio
            fy *= ratio
            fz *= ratio
        force[i, 0] += (1.0 - s) * fx
        force[i, 1] += (1.0 - s) * fy
        force[i, 2] += (1.0 - s) * fz
        force[i + 1, 0] += s * fx
        force[i + 1, 1] += s * fy
        force[i + 1, 2] += s * fz
    # predicted velocities
    vs = np.empty((n + 1, 3))
    for j in range(n + 1):
        if free[j] == 0.0:
            for axis in range(3):
                vs[j, axis] = v[j, axis]
            continue
        total = ms[j] + ma[j]
        f_t = force[j, 0] * t[j, 0] + force[j, 1] * t[j, 1] + force[j, 2] * t[j, 2]
        extra = f_t * (1.0 / ms[j] - 1.0 / total)
        for axis in range(3):
            vs[j, axis] = v[j, axis] + h * (force[j, axis] / total + extra * t[j, axis])
    # reel: locked while at rest and the line pull plus drive stays inside the static friction
    inv_j = reel[REEL_INV_MASS]
    if abs(reel[REEL_SPEED]) < 1e-9 and abs(reel[REEL_TENSION] + reel[REEL_DRIVE]) <= reel[REEL_STATIC]:
        inv_j = 0.0
    if reel[REEL_ROOM_OUT] <= 0.0 and reel[REEL_TENSION] + reel[REEL_DRIVE] >= 0.0:
        inv_j = 0.0
    if reel[REEL_ROOM_IN] <= 0.0 and reel[REEL_TENSION] + reel[REEL_DRIVE] <= 0.0:
        inv_j = 0.0
    reel_star = reel[REEL_SPEED] + h * inv_j * reel[REEL_DRIVE]
    if inv_j == 0.0:
        reel_star = 0.0
    # tridiagonal system for segment tensions
    lower = np.zeros(n)
    diag = np.ones(n)
    upper = np.zeros(n)
    rhs = np.zeros(n)
    beta = np.empty(n)
    for i in range(n):
        a = i
        b = i + 1
        k = ea / max(l0[i], 1e-6)
        beta[i] = k * h + c_int
        d = 0.0
        if free[a] != 0.0:
            d += _inv_mass_dot(ms[a], ma[a], t[a, 0], t[a, 1], t[a, 2], u[i, 0], u[i, 1], u[i, 2],
                               u[i, 0], u[i, 1], u[i, 2])
        if free[b] != 0.0:
            d += _inv_mass_dot(ms[b], ma[b], t[b, 0], t[b, 1], t[b, 2], u[i, 0], u[i, 1], u[i, 2],
                               u[i, 0], u[i, 1], u[i, 2])
        if i == 0:
            d += inv_j
        diag[i] = 1.0 / (beta[i] * h) + d
        if i + 1 < n and free[b] != 0.0:
            upper[i] = -_inv_mass_dot(ms[b], ma[b], t[b, 0], t[b, 1], t[b, 2], u[i + 1, 0], u[i + 1, 1],
                                      u[i + 1, 2], u[i, 0], u[i, 1], u[i, 2])
        if i > 0 and free[a] != 0.0:
            lower[i] = -_inv_mass_dot(ms[a], ma[a], t[a, 0], t[a, 1], t[a, 2], u[i - 1, 0], u[i - 1, 1],
                                      u[i - 1, 2], u[i, 0], u[i, 1], u[i, 2])
        rate = 0.0
        for axis in range(3):
            rate += u[i, axis] * (vs[b, axis] - vs[a, axis])
        if i == 0:
            rate -= reel_star
        rhs[i] = (k * (length[i] - l0[i]) + beta[i] * rate) / (beta[i] * h)
    active = np.empty(n, dtype=np.bool_)
    for i in range(n):
        active[i] = rhs[i] > 0.0
    cp = np.empty(n)
    dp = np.empty(n)
    for _ in range(12):
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
        changed = False
        for i in range(n):
            if active[i] and tension[i] < 0.0:
                active[i] = False
                changed = True
        if not changed:
            # complementarity: a slack segment whose neighbours' tensions would still leave it
            # stretched at the end of the substep must carry tension too
            for i in range(n):
                if active[i]:
                    continue
                pull = rhs[i]
                if i > 0:
                    pull -= lower[i] * tension[i - 1]
                if i + 1 < n:
                    pull -= upper[i] * tension[i + 1]
                if pull > 0.0:
                    active[i] = True
                    changed = True
        if not changed:
            break
    for i in range(n):
        value = tension[i] if active[i] else 0.0
        if not math.isfinite(value):
            value = 0.0
        tension[i] = min(max(value, 0.0), cap)
    # velocities (positions move after the contact velocity pass, see _integrate)
    for j in range(n + 1):
        if free[j] == 0.0:
            continue
        fx = 0.0
        fy = 0.0
        fz = 0.0
        if j < n:
            fx += tension[j] * u[j, 0]
            fy += tension[j] * u[j, 1]
            fz += tension[j] * u[j, 2]
        if j > 0:
            fx -= tension[j - 1] * u[j - 1, 0]
            fy -= tension[j - 1] * u[j - 1, 1]
            fz -= tension[j - 1] * u[j - 1, 2]
        total = ms[j] + ma[j]
        f_t = fx * t[j, 0] + fy * t[j, 1] + fz * t[j, 2]
        extra = f_t * (1.0 / ms[j] - 1.0 / total)
        v[j, 0] = vs[j, 0] + h * (fx / total + extra * t[j, 0])
        v[j, 1] = vs[j, 1] + h * (fy / total + extra * t[j, 1])
        v[j, 2] = vs[j, 2] + h * (fz / total + extra * t[j, 2])
    # reel speed and spool-end length
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
    out = np.zeros(3)
    if not broken:
        out[0] = -tension[n - 1] * u[n - 1, 0]
        out[1] = -tension[n - 1] * u[n - 1, 1]
        out[2] = -tension[n - 1] * u[n - 1, 2]
    return out


def _contact_valid(x, pt_seg, pt_s, anchor, dist0, radius, cache_distance):
    """False once any contact point has left the neighbourhood where its tangent plane holds.

    A point that started well clear of every surface may move further: distance fields are
    1-Lipschitz, so after moving less than (dist0 - radius - cache) it is still clear and the
    plane estimate cannot report a false contact either. The extra travel is capped at
    CLEAR_TRAVEL_M so the segment-sampling margin in tether_contact.build stays valid."""
    for k in range(len(pt_seg)):
        i = pt_seg[k]
        s = pt_s[k]
        moved = 0.0
        for axis in range(3):
            p = (1.0 - s) * x[i, axis] + s * x[i + 1, axis]
            moved += (p - anchor[k, axis]) ** 2
        allowed = max(cache_distance, min(dist0[k] - radius - cache_distance, CLEAR_TRAVEL_M))
        if moved > allowed * allowed:
            return False
    return True


def _contact_velocity(x, v, ms, ma, broken, h, pt_seg, pt_s, anchor, dist0, normal, pt_hard, radius,
                      mu_static, mu_kinetic, stribeck_v, regular_v, chafe):
    """Velocity-level contact before positions move: stop approach, regularised Coulomb friction.

    A point may close its gap to the surface in this substep but not pass it; the normal impulse
    that stops it is the contact normal force, and friction removes up to mu times that impulse
    from the sliding velocity (Palm & Eskilsson 2020 eq. 16 tanh-regularised Coulomb, with a
    static-to-kinetic decay). Acting on the post-solve velocity, which already contains this
    substep's tension, gives Coulomb sliding (capstan T2/T1 = exp(mu theta) round a wrap) rather
    than a velocity-limited drag. Hard contacts add friction work to the segment's chafe."""
    n = len(x) - 1
    for k in range(len(pt_seg)):
        i = pt_seg[k]
        s = pt_s[k]
        dist = dist0[k]
        vn = 0.0
        for axis in range(3):
            dist += ((1.0 - s) * x[i, axis] + s * x[i + 1, axis] - anchor[k, axis]) * normal[k, axis]
            vn += ((1.0 - s) * v[i, axis] + s * v[i + 1, axis]) * normal[k, axis]
        gap = dist - radius
        allowed = -gap / h if gap > 0.0 else 0.0
        if vn >= allowed:
            continue
        wa = 1.0 - s
        wb = s
        if i == 0:
            wa = 0.0
        if i + 1 == n and not broken:
            wb = 0.0
        wsum = wa * wa + wb * wb
        if wsum < 1e-12:
            continue
        push = allowed - vn
        tx = 0.0
        ty = 0.0
        tz = 0.0
        for axis in range(3):
            comp = (1.0 - s) * v[i, axis] + s * v[i + 1, axis] - vn * normal[k, axis]
            if axis == 0:
                tx = comp
            elif axis == 1:
                ty = comp
            else:
                tz = comp
        speed = math.sqrt(tx * tx + ty * ty + tz * tz)
        mu = (mu_kinetic + (mu_static - mu_kinetic) * math.exp(-speed / stribeck_v)) \
            * math.tanh(math.pi * speed / regular_v)
        # added mass acts normal to the cable only, so the normal and friction impulses see
        # different effective masses
        ux = x[i + 1, 0] - x[i, 0]
        uy = x[i + 1, 1] - x[i, 1]
        uz = x[i + 1, 2] - x[i, 2]
        un = max(math.sqrt(ux * ux + uy * uy + uz * uz), 1e-9)
        m_s = (1.0 - s) * ms[i] + s * ms[i + 1]
        m_a = (1.0 - s) * ma[i] + s * ma[i + 1]
        along_n = (ux * normal[k, 0] + uy * normal[k, 1] + uz * normal[k, 2]) / un
        along_t = (ux * tx + uy * ty + uz * tz) / (un * max(speed, 1e-12))
        mass_n = m_s + m_a * (1.0 - along_n * along_n)
        mass_t = m_s + m_a * (1.0 - along_t * along_t)
        cut = min(speed, mu * push * mass_n / mass_t)
        ratio = cut / max(speed, 1e-12)
        dvx = push * normal[k, 0] - ratio * tx
        dvy = push * normal[k, 1] - ratio * ty
        dvz = push * normal[k, 2] - ratio * tz
        v[i, 0] += wa * dvx / wsum
        v[i, 1] += wa * dvy / wsum
        v[i, 2] += wa * dvz / wsum
        v[i + 1, 0] += wb * dvx / wsum
        v[i + 1, 1] += wb * dvy / wsum
        v[i + 1, 2] += wb * dvz / wsum
        if pt_hard[k]:
            chafe[i] += mu * mass_n * push * speed
    return True


def _integrate(x, v, h, broken):
    """Move the free nodes with their final substep velocity (symplectic Euler)."""
    n = len(x) - 1
    last = n + 1 if broken else n
    for j in range(1, last):
        for axis in range(3):
            x[j, axis] += v[j, axis] * h


def _project(x, broken, pt_seg, pt_s, anchor, dist0, normal, radius):
    """Positional correction for points still inside a surface (at most 5 cm per substep)."""
    n = len(x) - 1
    for k in range(len(pt_seg)):
        i = pt_seg[k]
        s = pt_s[k]
        dist = dist0[k]
        for axis in range(3):
            dist += ((1.0 - s) * x[i, axis] + s * x[i + 1, axis] - anchor[k, axis]) * normal[k, axis]
        pen = min(radius - dist, 0.05)
        if pen <= 0.0:
            continue
        wa = 1.0 - s
        wb = s
        if i == 0:
            wa = 0.0
        if i + 1 == n and not broken:
            wb = 0.0
        wsum = wa * wa + wb * wb
        if wsum < 1e-12:
            continue
        lam = pen / wsum
        for axis in range(3):
            x[i, axis] += wa * lam * normal[k, axis]
            x[i + 1, axis] += wb * lam * normal[k, axis]


def _batch(x, v, water, water_accel, l0, ms, ma, lw, spool, gland, gland_vel, broken, h, ea, c_int,
           diameter, cd_normal, cd_tangent, wet_n_per_m, rho, cap, reel,
           pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension,
           substeps, pt_seg, pt_s, anchor, dist0, normal, pt_hard, cache_distance, radius,
           mu_static, mu_kinetic, stribeck_v, regular_v, chafe, rov_force, peaks):
    """Every substep of one tick with cached contact planes; False asks for the reference loop.

    ``rov_force`` returns the substep-averaged pull on the gland, ``peaks`` the highest segment
    tension and highest gland-segment tension of any substep."""
    n = len(x) - 1
    for axis in range(3):
        rov_force[axis] = 0.0
    peaks[0] = 0.0
    peaks[1] = 0.0
    pin_peak = np.zeros(len(pin_seg))
    point = np.empty(3)
    for step in range(substeps):
        for axis in range(3):
            point[axis] = gland[axis] + gland_vel[axis] * h * (step + 1)
        out = advance(x, v, water, water_accel, l0, ms, ma, lw, spool, point, gland_vel, broken, h, ea, c_int,
                      diameter, cd_normal, cd_tangent, wet_n_per_m, rho, cap, reel,
                      pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension)
        for k in range(len(pin_seg)):
            pin_peak[k] = max(pin_peak[k], pin_force[k])
        for axis in range(3):
            rov_force[axis] += out[axis] / substeps
        for i in range(n):
            peaks[0] = max(peaks[0], tension[i])
        peaks[1] = max(peaks[1], tension[n - 1])
        if not contact_valid(x, pt_seg, pt_s, anchor, dist0, radius, cache_distance):
            return False
        contact_velocity(x, v, ms, ma, broken, h, pt_seg, pt_s, anchor, dist0, normal, pt_hard, radius,
                         mu_static, mu_kinetic, stribeck_v, regular_v, chafe)
        integrate(x, v, h, broken)
        project(x, broken, pt_seg, pt_s, anchor, dist0, normal, radius)
    for k in range(len(pin_seg)):
        pin_force[k] = pin_peak[k]
    return n >= 0


def _batch_resume(x, v, water, water_accel, l0, ms, ma, lw, spool, gland, gland_vel, broken, h, ea, c_int,
           diameter, cd_normal, cd_tangent, wet_n_per_m, rho, cap, reel,
           pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension,
           substeps, pt_seg, pt_s, anchor, dist0, normal, pt_hard, cache_distance, radius,
           mu_static, mu_kinetic, stribeck_v, regular_v, chafe, rov_force, peaks, start_step, pin_peak):
    """Run until contact planes expire; return the pending substep, or substeps when done.

    The caller refreshes geometry and finishes that contact pass, then resumes without
    replaying forces or resetting the accumulated force, tension and pin peaks.
    """
    n = len(x) - 1
    point = np.empty(3)
    for step in range(start_step, substeps):
        for axis in range(3):
            point[axis] = gland[axis] + gland_vel[axis] * h * (step + 1)
        out = advance(x, v, water, water_accel, l0, ms, ma, lw, spool, point, gland_vel, broken, h, ea, c_int,
                      diameter, cd_normal, cd_tangent, wet_n_per_m, rho, cap, reel,
                      pin_seg, pin_s, pin_target, pin_k, pin_c, pin_cap, pin_force, tension)
        for k in range(len(pin_seg)):
            pin_peak[k] = max(pin_peak[k], pin_force[k])
        for axis in range(3):
            rov_force[axis] += out[axis] / substeps
        for i in range(n):
            peaks[0] = max(peaks[0], tension[i])
        peaks[1] = max(peaks[1], tension[n - 1])
        if not contact_valid(x, pt_seg, pt_s, anchor, dist0, radius, cache_distance):
            return step
        contact_velocity(x, v, ms, ma, broken, h, pt_seg, pt_s, anchor, dist0, normal, pt_hard, radius,
                         mu_static, mu_kinetic, stribeck_v, regular_v, chafe)
        integrate(x, v, h, broken)
        project(x, broken, pt_seg, pt_s, anchor, dist0, normal, radius)
    for k in range(len(pin_seg)):
        pin_force[k] = pin_peak[k]
    return substeps


if njit is not None:
    _inv_mass_dot = njit(cache=True)(_inv_mass_dot)
    advance = njit(cache=True)(_advance)
    contact_valid = njit(cache=True)(_contact_valid)
    contact_velocity = njit(cache=True)(_contact_velocity)
    integrate = njit(cache=True)(_integrate)
    project = njit(cache=True)(_project)
    advance_batch = njit(cache=True)(_batch)
    advance_batch_resume = njit(cache=True)(_batch_resume)
else:
    advance = None
    contact_valid = None
    contact_velocity = None
    integrate = None
    project = None
    advance_batch = None
    advance_batch_resume = None


FAST_REQUIREMENTS = "requirements-fast.txt"


def compiled_available():
    """True when the numba-compiled tether path is importable in this interpreter."""
    return advance_batch is not None


def solver_status_line(compiled=None):
    """One startup line naming the active tether path and how to enable the fast one."""
    if compiled is None:
        compiled = compiled_available()
    if compiled:
        return "[qysim] tether solver: compiled (numba) - fast path active"
    return ("[qysim] tether solver: NumPy fallback - same physics but slower; rooms with several vehicles "
            f"may run below real time. Enable the compiled path with: pip install -r {FAST_REQUIREMENTS}")
