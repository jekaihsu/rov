"""6-DOF ROV rigid-body model.

Frames
    body  FRD: x forward, y starboard, z down (origin at the centre of gravity)
    world NED: x north, y east, z down (origin at the local geodetic reference)

The thruster layout is the ROV-01 6-thruster vectored layout
reconstruction: four diagonal thrusters tilted in 3-D plus two longitudinal ones.
Nominal independent-axis speeds use ROV-01 spec targets (forward 4.5 kn,
lateral 2.5 kn, vertical 1.5 kn) to fit drag. Coupled free-body speeds can differ;
these fits are not experimental validation of complete vehicle motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from .vehicles import ROV01_THRUSTERS, get_vehicle_definition

try:
    from numba import njit
except ImportError:
    njit = None

KNOT = 0.514444
RHO = 1025.0
G = 9.81


# ── quaternion helpers (w, x, y, z), body → world ─────────────────────────
def q_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ])


def q_conj(q: np.ndarray) -> np.ndarray:
    return np.array([q[0], -q[1], -q[2], -q[3]])


def q_rot(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate one 3-vector: expanded q * (0,v) * conjugate(q).

    Avoids temporary four-vectors in this per-vehicle/per-collision hot path.
    Keeps the original behavior for non-unit quaternions as well.
    """
    w, x, y, z = q
    vx, vy, vz = v
    dot = x*vx + y*vy + z*vz
    scale = w*w - x*x - y*y - z*z
    return np.array([scale*vx + 2*(x*dot + w*(y*vz-z*vy)),
                     scale*vy + 2*(y*dot + w*(z*vx-x*vz)),
                     scale*vz + 2*(z*dot + w*(x*vy-y*vx))])


def cross3(a, b):
    """Cross product specialized to single 3-vectors, with no broadcast setup."""
    ax, ay, az = a
    bx, by, bz = b
    return np.array([ay*bz-az*by, az*bx-ax*bz, ax*by-ay*bx])


def q_from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    n = np.linalg.norm(axis)
    if n < 1e-12 or abs(angle) < 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    s = math.sin(angle / 2) / n
    return np.array([math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s])


def q_from_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """ZYX (yaw, pitch, roll) aerospace convention, radians."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return np.array([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ])


def q_to_euler(q: np.ndarray) -> tuple[float, float, float]:
    """Return (roll, pitch, yaw) radians, ZYX convention."""
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    sp = max(-1.0, min(1.0, 2 * (w * y - z * x)))
    pitch = math.asin(sp)
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


# ── thruster layout (body FRD, metres, relative to CG) ────────────────────
# Measured from the ROV-01 hydrodynamic reference (Blender: -Y fwd, +X stbd, +Z up;
# CG assumed 170 mm above the skid plane). Axis = direction of positive thrust.
THRUSTERS = list(ROV01_THRUSTERS)  # Legacy imports remain compatible.


MAX_WATER_CURRENT_MS = 50.0   # physical bound on ambient current speed (m/s)


@dataclass
class VehicleParams:
    mass: float = 30.0                    # kg in air (ROV-01 spec: <= 30 kg)
    net_buoyancy: float = 0.3 * G         # N, slightly positive
    gm: float = 0.03                      # m, CB above CG (righting arm)
    added_mass: tuple = (15.0, 25.0, 30.0)          # kg, surge/sway/heave
    inertia: tuple = (1.1, 1.6, 1.8)                 # kg m^2 incl. added inertia
    thruster_max: float = 148.0           # N per thruster; gives the 30 kgf forward thrust of the ROV-01 spec
    motor_tau: float = 0.08               # s, motor/ESC first-order lag
    vmax: tuple = (4.5 * KNOT, 2.5 * KNOT, 1.5 * KNOT)   # m/s surge/sway/heave
    wmax: tuple = (math.radians(120), math.radians(90), math.radians(90))  # rad/s p,q,r at full authority
    linear_drag: tuple = (8.0, 12.0, 15.0, 1.0, 1.0, 1.0)


def allocation_matrix(thrusters=None) -> np.ndarray:
    """B (6 x n): columns are the body wrench [F; M] of one unit-thrust thruster."""
    cols = []
    for _, pos, axis in (THRUSTERS if thrusters is None else thrusters):
        d = np.asarray(axis, float)
        d /= np.linalg.norm(d)
        r = np.asarray(pos, float)
        cols.append(np.concatenate([d, cross3(r, d)]))
    return np.array(cols).T


def coriolis_wrench(mass, added_mass, inertia, velocity, omega, relative_velocity=None):
    """Return -C_RB(nu)nu - C_A(nu_r)nu_r for diagonal inertia at CG.

    ``inertia`` includes rotational added inertia; irrotational current has no
    angular component. With still water this wrench performs zero work. See
    Fossen's marine-craft model; translational added mass must be inside the
    cross product, and its paired angular coupling must not be omitted.
    """
    velocity, omega = np.asarray(velocity), np.asarray(omega)
    relative = velocity if relative_velocity is None else np.asarray(relative_velocity)
    added_momentum = np.asarray(added_mass) * relative
    force = -mass * cross3(omega, velocity) - cross3(omega, added_momentum)
    moment = -cross3(omega, np.asarray(inertia) * omega) - cross3(relative, added_momentum)
    return np.concatenate((force, moment))


def _body_derivatives(q, velocity, omega, wrench, current, mass, added, inertia,
                      linear, quadratic, rotational, inv_mass, inv_inertia,
                      net_buoyancy, righting):
    """Scalar diagonal Fossen equations, shared by optional JIT and fallback.

    Expanding these tiny vector products avoids intermediate NumPy arrays at
    both midpoint stages. No fast-math or alternate force model is used.
    """
    w, x, y, z = q
    cn, ce, cd = current
    cx = (1-2*(y*y+z*z))*cn + 2*(x*y+w*z)*ce + 2*(x*z-w*y)*cd
    cy = 2*(x*y-w*z)*cn + (1-2*(x*x+z*z))*ce + 2*(y*z+w*x)*cd
    cz = 2*(x*z+w*y)*cn + 2*(y*z-w*x)*ce + (1-2*(x*x+y*y))*cd
    u, v, h = velocity
    p, a, r = omega
    ur, vr, hr = u-cx, v-cy, h-cz
    mx, my, mz = added[0]*ur, added[1]*vr, added[2]*hr
    ux, uy, uz = 2*(w*y-x*z), -2*(w*x+y*z), 2*(x*x+y*y)-1
    force = np.empty(3)
    moment = np.empty(3)
    force[0] = wrench[0] - (linear[0]+quadratic[0]*abs(ur))*ur + ux*net_buoyancy
    force[1] = wrench[1] - (linear[1]+quadratic[1]*abs(vr))*vr + uy*net_buoyancy
    force[2] = wrench[2] - (linear[2]+quadratic[2]*abs(hr))*hr + uz*net_buoyancy
    # Rigid-body and added-mass Coriolis, plus rotating current transport.
    force[0] -= mass*(a*h-r*v) + a*mz-r*my + added[0]*(a*cz-r*cy)
    force[1] -= mass*(r*u-p*h) + r*mx-p*mz + added[1]*(r*cx-p*cz)
    force[2] -= mass*(p*v-a*u) + p*my-a*mx + added[2]*(p*cy-a*cx)
    moment[0] = wrench[3] - (linear[3]+rotational[0]*abs(p))*p + righting*uy
    moment[1] = wrench[4] - (linear[4]+rotational[1]*abs(a))*a - righting*ux
    moment[2] = wrench[5] - (linear[5]+rotational[2]*abs(r))*r
    moment[0] -= a*r*(inertia[2]-inertia[1]) + vr*mz-hr*my
    moment[1] -= r*p*(inertia[0]-inertia[2]) + hr*mx-ur*mz
    moment[2] -= p*a*(inertia[1]-inertia[0]) + ur*my-vr*mx
    return force*inv_mass, moment*inv_inertia


_fast_derivatives = njit(cache=True)(_body_derivatives) if njit is not None else _body_derivatives


@dataclass
class VehicleState:
    pos: np.ndarray = field(default_factory=lambda: np.zeros(3))          # NED m
    q: np.ndarray = field(default_factory=lambda: np.array([1.0, 0, 0, 0]))
    vel: np.ndarray = field(default_factory=lambda: np.zeros(3))          # body m/s
    omega: np.ndarray = field(default_factory=lambda: np.zeros(3))        # body rad/s
    thrust: np.ndarray = field(default_factory=lambda: np.zeros(len(THRUSTERS)))  # N
    accel: np.ndarray = field(default_factory=lambda: np.zeros(3))        # inertial acceleration expressed in body, m/s^2


class Vehicle:
    """Thruster-driven 6-DOF body. Call ``step(dt, thrust_cmd)`` with per-thruster
    commands in [-1, 1]."""

    def __init__(self, params: VehicleParams | None = None, *, model_id="rov01", definition=None):
        self.definition = definition or get_vehicle_definition(model_id)
        self.model_id = self.definition.id
        self.thrusters = self.definition.thrusters
        self.capabilities = self.definition.capabilities
        self.p = params or VehicleParams(**self.definition.params)
        self.B = allocation_matrix(self.thrusters)
        # Optimize only independently controlled axes. ROV-01-PRO cannot cancel
        # horizontal-thrust roll/pitch moments; asking the inverse to do so
        # would unnecessarily sacrifice attainable surge/sway authority.
        axes = ("surge", "sway", "heave", "roll", "pitch", "yaw")
        controlled = [i for i, axis in enumerate(axes) if axis in self.capabilities]
        self.B_pinv = np.zeros((len(self.thrusters), 6))
        self.B_pinv[:, controlled] = np.linalg.pinv(self.B[controlled, :])
        self.s = VehicleState(thrust=np.zeros(len(self.thrusters)))
        self.current_ned = np.zeros(3)      # water current, world m/s
        self.seabed_depth = 30.0            # m
        m = self.p.mass
        self.M = np.array([m + a for a in self.p.added_mass])
        self.I = np.array(self.p.inertia)
        self._added_mass = np.asarray(self.p.added_mass, dtype=float)
        self._linear_drag = np.asarray(self.p.linear_drag, dtype=float)
        self._inv_mass = 1.0 / self.M
        self._inv_inertia = 1.0 / self.I
        # authority per wrench axis with every thruster at full scale
        self.authority = self._authority()
        f_max = self.authority[:3]
        vmax = np.array(self.p.vmax)
        lin = np.array(self.p.linear_drag[:3])
        self.quad_drag = np.maximum((f_max - lin * vmax) / vmax ** 2, 1.0)
        m_max = self.authority[3:]
        wmax = np.array(self.p.wmax)
        lin_r = np.array(self.p.linear_drag[3:])
        self.quad_rdrag = np.maximum((m_max - lin_r * wmax) / wmax ** 2, 0.05)
        # A passive axis still experiences rotational water resistance. Inferring
        # it from actuator authority alone gave ROV-01-PRO almost no quadratic roll
        # or pitch drag. Uniform strip integration gives E[|r|^3] = a^3 / 4
        # over [-a, a]. Hull envelopes and existing translation drag are estimates,
        # not tow-tank measurements; retain rated-axis fits where they exist.
        half_extent = np.max([np.abs(c) + radius
                              for c, radius in self.definition.hull_spheres], axis=0)
        x3, y3, z3 = half_extent ** 3 / 4.0
        dx, dy, dz = self.quad_drag
        passive_drag = np.array([dz*y3 + dy*z3, dz*x3 + dx*z3, dy*x3 + dx*y3])
        self.quad_rdrag = np.where(m_max > 1e-9, self.quad_rdrag,
                                  np.maximum(self.quad_rdrag, passive_drag))

    def _authority(self) -> np.ndarray:
        """Largest achievable force/torque along each wrench axis (thrusters saturated)."""
        out = np.zeros(6)
        for k in range(6):
            if ("surge", "sway", "heave", "roll", "pitch", "yaw")[k] not in self.capabilities:
                continue
            e = np.zeros(6)
            e[k] = 1.0
            t = self.B_pinv @ e
            peak = np.max(np.abs(t))
            if peak < 1e-9:
                continue
            t = t / peak
            out[k] = (self.B @ t)[k] * self.p.thruster_max
        return out

    def allocate(self, wrench_norm: np.ndarray, health: np.ndarray | None = None) -> np.ndarray:
        """Map a normalised wrench (each axis in [-1, 1] of its authority) to thruster commands,
        with automatic Moore-Penrose fault reallocation when any thruster health is degraded/jammed."""
        w = np.asarray(wrench_norm, float) * self.authority
        from .wave1 import allocate_6thruster_with_fault_compensation
        return allocate_6thruster_with_fault_compensation(
            self.B, self.B_pinv, w / self.p.thruster_max, health=health
        )

    def step(self, dt: float, thrust_cmd: np.ndarray, extra_wrench: np.ndarray | None = None) -> None:
        """Advance ``dt`` seconds. ``extra_wrench`` is an external body-frame [F; M]
        (contact forces, tether tension), held fixed over this step.

        Exponential motor response and a midpoint rigid-body update reduce
        frame-rate-dependent throttle and artificial energy gain. Large steps
        and unusually fast motion are subdivided for damping/rotation stability.
        Invalid inputs raise before mutation; a non-finite result rolls back.
        """
        p, s = self.p, self.s
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("dt must be finite and nonnegative")
        if dt == 0:
            return
        command = np.asarray(thrust_cmd, dtype=float)
        external = np.zeros(6) if extra_wrench is None else np.asarray(extra_wrench, dtype=float)
        if command.shape != s.thrust.shape or not np.all(np.isfinite(command)):
            raise ValueError("thruster commands must be finite and match the vehicle")
        if external.shape != (6,) or not np.all(np.isfinite(external)):
            raise ValueError("extra_wrench must contain six finite body-frame components")
        target = np.clip(command, -1, 1) * p.thruster_max
        # No real water body moves faster than MAX_WATER_CURRENT_MS (a tidal race is ~5 m/s). Bounding the
        # forcing at its physical limit keeps the drag Jacobian, and so the substep count, finite for
        # absurd inputs instead of hitting the substep guard. NaN/inf is left alone: the finite-state
        # rollback below handles it.
        cur_speed = float(np.linalg.norm(self.current_ned))
        if math.isfinite(cur_speed) and cur_speed > MAX_WATER_CURRENT_MS:
            self.current_ned = self.current_ned * (MAX_WATER_CURRENT_MS / cur_speed)
        relative = s.vel - q_rot(q_conj(s.q), self.current_ned)
        # Midpoint has a finite stability region. Bound each substep by the
        # local drag Jacobian as well as attitude rotation, without velocity caps.
        stiffness = max(float(np.max((self._linear_drag[:3] + 2*self.quad_drag*np.abs(relative)) * self._inv_mass)),
                        float(np.max((self._linear_drag[3:] + 2*self.quad_rdrag*np.abs(s.omega)) * self._inv_inertia)))
        count = max(1, math.ceil(dt / .02), math.ceil(dt * stiffness * 2),
                    math.ceil(dt * float(np.linalg.norm(s.omega)) / .1))
        if count > 1024:
            raise ValueError("step requires too many substeps; reduce dt or check state")
        h = dt / count
        alpha = 1.0 if p.motor_tau <= 0 else -math.expm1(-h / p.motor_tau)
        alpha_half = 1.0 if p.motor_tau <= 0 else -math.expm1(-h * .5 / p.motor_tau)
        saved = tuple(value.copy() for value in (s.pos, s.q, s.vel, s.omega, s.thrust, s.accel))
        for _ in range(count):
            start_thrust = target if p.motor_tau <= 0 else s.thrust
            a0, angular0 = self._derivatives(s.q, s.vel, s.omega, self.B @ start_thrust + external)
            mid_vel = s.vel + a0 * (h * .5)
            mid_omega = s.omega + angular0 * (h * .5)
            mid_q = self._advance_attitude(s.q, s.omega, h * .5)
            mid_thrust = s.thrust + (target - s.thrust) * alpha_half
            accel, angular = self._derivatives(mid_q, mid_vel, mid_omega, self.B @ mid_thrust + external)
            # A body-axis velocity derivative includes a rotating-frame term.
            # IMU consumers need inertial acceleration, then subtract gravity.
            inertial_accel_world = q_rot(mid_q, accel + cross3(mid_omega, mid_vel))
            s.pos = s.pos + q_rot(mid_q, mid_vel) * h
            s.vel = s.vel + accel * h
            s.omega = s.omega + angular * h
            s.q = self._advance_attitude(s.q, mid_omega, h)
            s.thrust = s.thrust + (target - s.thrust) * alpha
            s.accel = q_rot(q_conj(s.q), inertial_accel_world)
            if not np.all(np.isfinite(np.concatenate((s.pos, s.vel, s.omega, s.q, s.accel, s.thrust)))):
                s.pos, s.q, s.vel, s.omega, s.thrust, s.accel = saved
                return
            # Contact forces supply physical response; these planes only prevent
            # tunnelling. Velocity is over ground: never add current a second time.
            bottom = max(0., self.seabed_depth - .05)
            if s.pos[2] < 0. or s.pos[2] > bottom:
                at_surface = s.pos[2] < 0.
                s.pos[2] = 0. if at_surface else bottom
                v_world = q_rot(s.q, s.vel)
                if (at_surface and v_world[2] < 0.) or (not at_surface and v_world[2] > 0.):
                    v_world[2] = 0.
                    s.vel = q_rot(q_conj(s.q), v_world)

    @staticmethod
    def _advance_attitude(q, omega, dt):
        angle = float(np.linalg.norm(omega)) * dt
        if angle < 1e-12:
            return q.copy()
        scale = math.sin(angle * .5) * dt / angle
        result = q_mul(q, np.array([math.cos(angle * .5), *(omega * scale)]))
        return result / np.linalg.norm(result)

    def _derivatives(self, q, velocity, omega, wrench):
        """Body-axis derivatives for the diagonal Fossen model at one stage."""
        p = self.p
        return _fast_derivatives(q, velocity, omega, wrench, self.current_ned,
                                 p.mass, self._added_mass, self.I,
                                 self._linear_drag, self.quad_drag, self.quad_rdrag,
                                 self._inv_mass, self._inv_inertia, p.net_buoyancy,
                                 p.gm*(p.mass*G + p.net_buoyancy))

    # convenience ------------------------------------------------------------
    @property
    def euler(self) -> tuple[float, float, float]:
        return q_to_euler(self.s.q)

    def world_velocity(self) -> np.ndarray:
        return q_rot(self.s.q, self.s.vel)
