"""6-DOF ROV rigid-body model.

Frames
    body  FRD: x forward, y starboard, z down (origin at the centre of gravity)
    world NED: x north, y east, z down (origin at the local geodetic reference)

The thruster layout is the X1-class vectored layout measured from the Blender
reconstruction: four diagonal thrusters tilted in 3-D plus two longitudinal ones.
Nominal independent-axis speeds use provisional reseller targets (forward 4.5 kn,
lateral 2.5 kn, vertical 1.5 kn) to fit drag. Coupled free-body speeds can differ;
these fits are not experimental validation of complete vehicle motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from .vehicles import X1_THRUSTERS, X1_PARAMETERS, get_vehicle_definition

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


def q_matrix(q: np.ndarray) -> np.ndarray:
    """Rotation matrix (body -> world) of a unit quaternion (w, x, y, z)."""
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


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
# Measured from the X1 Blender reconstruction (Blender: -Y fwd, +X stbd, +Z up;
# CG assumed 170 mm above the skid plane). Axis = direction of positive thrust.
THRUSTERS = list(X1_THRUSTERS)  # Legacy imports remain compatible.


@dataclass
class VehicleParams:
    mass: float = X1_PARAMETERS["mass"]["value"]
    net_buoyancy: float = X1_PARAMETERS["net_buoyancy"]["value"]
    gm: float = X1_PARAMETERS["gm"]["value"]
    added_mass: tuple = X1_PARAMETERS["added_mass"]["value"]
    inertia: tuple = X1_PARAMETERS["inertia"]["value"]
    thruster_max: float = X1_PARAMETERS["thruster_max"]["value"]
    motor_tau: float = X1_PARAMETERS["motor_tau"]["value"]
    vmax: tuple = X1_PARAMETERS["vmax"]["value"]
    wmax: tuple = X1_PARAMETERS["wmax"]["value"]
    quadratic_drag: tuple | None = X1_PARAMETERS["quadratic_drag"]["value"]
    reverse_ratio: float = X1_PARAMETERS["reverse_ratio"]["value"]
    thrust_asymmetry: bool = X1_PARAMETERS["thrust_asymmetry"]["value"]
    linear_drag: tuple = X1_PARAMETERS["linear_drag"]["value"]


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


@dataclass
class VehicleState:
    pos: np.ndarray = field(default_factory=lambda: np.zeros(3))          # NED m
    q: np.ndarray = field(default_factory=lambda: np.array([1.0, 0, 0, 0]))
    vel: np.ndarray = field(default_factory=lambda: np.zeros(3))          # body m/s
    omega: np.ndarray = field(default_factory=lambda: np.zeros(3))        # body rad/s
    thrust: np.ndarray = field(default_factory=lambda: np.zeros(len(THRUSTERS)))  # N
    accel: np.ndarray = field(default_factory=lambda: np.zeros(3))        # body m/s^2 (specific force w/o gravity)


class Vehicle:
    """Thruster-driven 6-DOF body. Call ``step(dt, thrust_cmd)`` with per-thruster
    commands in [-1, 1]."""

    def __init__(self, params: VehicleParams | None = None, *, model_id="x1", definition=None):
        self.definition = definition or get_vehicle_definition(model_id)
        self.model_id = self.definition.id
        self.thrusters = self.definition.thrusters
        self.capabilities = self.definition.capabilities
        self.p = params or VehicleParams(**self.definition.params)
        self.B = allocation_matrix(self.thrusters)
        # Optimize only independently controlled axes. Falcon cannot cancel
        # horizontal-thrust roll/pitch moments; asking the inverse to do so
        # would unnecessarily sacrifice attainable surge/sway authority.
        axes = ("surge", "sway", "heave", "roll", "pitch", "yaw")
        controlled = [i for i, axis in enumerate(axes) if axis in self.capabilities]
        self.B_pinv = np.zeros((len(self.thrusters), 6))
        self.B_pinv[:, controlled] = np.linalg.pinv(self.B[controlled, :])
        self.s = VehicleState(thrust=np.zeros(len(self.thrusters)))
        self.current_ned = np.zeros(3)      # water current, world m/s
        self.current_accel_ned = np.zeros(3)  # water acceleration along the path, world m/s^2
        self.current_points = None          # optional (body points (k,3), world currents (k,3))
        self.seabed_depth = 30.0            # m
        m = self.p.mass
        self.M = np.array([m + a for a in self.p.added_mass])
        self.I = np.array(self.p.inertia)
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

        if self.p.quadratic_drag is not None:
            self.quad_drag = np.asarray(self.p.quadratic_drag[:3], float)
            self.quad_rdrag = np.asarray(self.p.quadratic_drag[3:], float)

    def _uneven_flow_wrench(self, q_inv, v_rel, lin) -> tuple[np.ndarray, np.ndarray]:
        """Drag wrench from flow that differs across the hull (shear, wake edges).

        ``current_points`` holds body points and the world flow sampled there. The drag is
        linearised about the centre-of-gravity flow and shared equally among the points, so a
        uniform flow gives exactly zero and an uneven one gives the force and torque of the
        differences (e.g. yaw when the bow is in a pile's wake and the stern is not).
        """
        points, flows = self.current_points
        gain = (lin[:3] + 2.0 * self.quad_drag * np.abs(v_rel)) / len(points)
        delta = (np.asarray(flows) - self.current_ned) @ q_matrix(self.s.q)     # world -> body rows
        f = gain * delta
        return f.sum(axis=0), np.cross(points, f).sum(axis=0)

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

    def allocate(self, wrench_norm: np.ndarray) -> np.ndarray:
        """Map a normalised wrench (each axis in [-1, 1] of its authority) to thruster commands."""
        w = np.asarray(wrench_norm, float) * self.authority
        t = self.B_pinv @ w / self.p.thruster_max
        peak = np.max(np.abs(t))
        return t / peak if peak > 1.0 else t

    def step(self, dt: float, thrust_cmd: np.ndarray, extra_wrench: np.ndarray | None = None,
             *, hull_contact: bool = False) -> None:
        """Advance ``dt`` seconds. ``extra_wrench`` is an external body-frame [F; M]
        (contact forces, tether tension). A non-finite result rolls the state back."""
        p, s = self.p, self.s
        saved = (s.pos.copy(), s.q.copy(), s.vel.copy(), s.omega.copy())
        target = np.clip(np.asarray(thrust_cmd, float), -1, 1) * p.thruster_max
        if p.thrust_asymmetry:
            target = np.where(target < 0, target * p.reverse_ratio, target)
        s.thrust += (target - s.thrust) * min(1.0, dt / p.motor_tau)
        wrench = self.B @ s.thrust
        if extra_wrench is not None:
            wrench = wrench + extra_wrench
        F, Mt = wrench[:3], wrench[3:]

        q_inv = q_conj(s.q)
        current_body = q_rot(q_inv, self.current_ned)
        v_rel = s.vel - current_body
        lin = np.array(p.linear_drag)
        F_drag = -lin[:3] * v_rel - self.quad_drag * v_rel * np.abs(v_rel)
        M_drag = -lin[3:] * s.omega - self.quad_rdrag * s.omega * np.abs(s.omega)
        if self.current_points is not None:
            F_shear, M_shear = self._uneven_flow_wrench(q_inv, v_rel, lin)
            F_drag = F_drag + F_shear
            M_drag = M_drag + M_shear

        # net buoyancy acts up (world -z), righting moment from CB above CG
        up_body = q_rot(q_inv, np.array([0.0, 0.0, -1.0]))
        F_buoy = up_body * p.net_buoyancy
        weight = p.mass * G
        r_cb = np.array([0.0, 0.0, -p.gm])                   # CB above CG in body frame
        M_right = cross3(r_cb, up_body * (weight + p.net_buoyancy))

        F_tot = F + F_drag + F_buoy
        inertial = coriolis_wrench(p.mass, p.added_mass, self.I, s.vel, s.omega, v_rel)
        F_tot += inertial[:3]
        # The locally frozen NED current still rotates in body coordinates:
        # M_A * d(v_c_body)/dt = -M_A * (omega x v_c_body).
        F_tot -= np.asarray(p.added_mass) * cross3(s.omega, current_body)
        # Fluid acceleration (Froude-Krylov + added mass): (rho V + M_A) * dv_c/dt in body axes.
        # The engine supplies dv_c/dt along the vehicle path, filtered and bounded (flow.py).
        if np.any(self.current_accel_ned):
            displaced = p.mass + p.net_buoyancy / G
            F_tot += (displaced + np.asarray(p.added_mass)) * q_rot(q_inv, self.current_accel_ned)
        s.accel = F_tot / self.M
        s.vel = s.vel + s.accel * dt
        M_tot = Mt + M_drag + M_right + inertial[3:]
        s.omega = s.omega + M_tot / self.I * dt

        # integrate attitude and position
        wn = np.linalg.norm(s.omega)
        if wn > 1e-9:
            s.q = q_mul(s.q, q_from_axis_angle(s.omega, wn * dt))
            s.q /= np.linalg.norm(s.q)
        if not (np.all(np.isfinite(s.vel)) and np.all(np.isfinite(s.omega)) and np.all(np.isfinite(s.q))):
            s.pos, s.q, s.vel, s.omega = saved[0], saved[1], np.zeros(3), np.zeros(3)
            return
        # ``vel`` is the body-frame velocity over ground (drag acts on vel - current), so the
        # current must not be added again here
        v_world = q_rot(s.q, s.vel)
        s.pos = s.pos + v_world * dt

        # surface and seabed limits (``vel`` is velocity over ground: drop its vertical part)
        if s.pos[2] < 0.0:
            s.pos[2] = 0.0
            if v_world[2] < 0:
                s.vel = q_rot(q_conj(s.q), v_world * np.array([1, 1, 0]))
        # Standalone vehicles retain their floor stop. The engine resolves the whole swept hull.
        if not hull_contact and s.pos[2] > self.seabed_depth - 0.05:
            s.pos[2] = self.seabed_depth - 0.05
            if v_world[2] > 0:
                s.vel = q_rot(q_conj(s.q), v_world * np.array([1, 1, 0]))

    # convenience ------------------------------------------------------------
    @property
    def euler(self) -> tuple[float, float, float]:
        return q_to_euler(self.s.q)

    def world_velocity(self) -> np.ndarray:
        return q_rot(self.s.q, self.s.vel)
