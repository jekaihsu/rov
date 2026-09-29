"""6-DOF ROV rigid-body model.

Frames
    body  FRD: x forward, y starboard, z down (origin at the centre of gravity)
    world NED: x north, y east, z down (origin at the local geodetic reference)

The thruster layout is the X1-class vectored layout measured from the Blender
reconstruction: four diagonal thrusters tilted in 3-D plus two longitudinal ones.
Top speeds are matched to the X1 datasheet (forward 4.5 kn, lateral 2.5 kn,
vertical 1.5 kn) by fitting quadratic drag to the allocation's real authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

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
    """Rotate vector v by quaternion q."""
    return q_mul(q_mul(q, np.array([0.0, *v])), q_conj(q))[1:]


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
THRUSTERS = [
    # name,        position (x, y, z),        axis (x, y, z)
    ("T1 PORT_FRONT", (0.250, -0.193, 0.032), (0.32, -0.54, -0.78)),
    ("T2 STBD_FRONT", (0.250, 0.193, 0.032), (0.32, 0.54, -0.78)),
    ("T3 PORT_AFT", (-0.251, -0.171, -0.035), (-0.28, -0.48, 0.83)),
    ("T4 STBD_AFT", (-0.251, 0.171, -0.035), (-0.28, 0.48, 0.83)),
    ("T5 PORT_LONG", (-0.061, -0.205, 0.068), (-1.0, 0.0, 0.0)),
    ("T6 STBD_LONG", (-0.061, 0.205, 0.068), (-1.0, 0.0, 0.0)),
]


@dataclass
class VehicleParams:
    mass: float = 30.0                    # kg in air (X1 datasheet: <= 30 kg)
    net_buoyancy: float = 0.3 * G         # N, slightly positive
    gm: float = 0.03                      # m, CB above CG (righting arm)
    added_mass: tuple = (15.0, 25.0, 30.0)          # kg, surge/sway/heave
    inertia: tuple = (1.1, 1.6, 1.8)                 # kg m^2 incl. added inertia
    thruster_max: float = 148.0           # N per thruster; gives the 30 kgf forward thrust of the X1 datasheet
    motor_tau: float = 0.08               # s, motor/ESC first-order lag
    vmax: tuple = (4.5 * KNOT, 2.5 * KNOT, 1.5 * KNOT)   # m/s surge/sway/heave
    wmax: tuple = (math.radians(120), math.radians(90), math.radians(90))  # rad/s p,q,r at full authority
    linear_drag: tuple = (8.0, 12.0, 15.0, 1.0, 1.0, 1.0)


def allocation_matrix() -> np.ndarray:
    """B (6 x n): columns are the body wrench [F; M] of one unit-thrust thruster."""
    cols = []
    for _, pos, axis in THRUSTERS:
        d = np.asarray(axis, float)
        d /= np.linalg.norm(d)
        r = np.asarray(pos, float)
        cols.append(np.concatenate([d, np.cross(r, d)]))
    return np.array(cols).T


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

    def __init__(self, params: VehicleParams | None = None):
        self.p = params or VehicleParams()
        self.B = allocation_matrix()
        self.B_pinv = np.linalg.pinv(self.B)
        self.s = VehicleState()
        self.current_ned = np.zeros(3)      # water current, world m/s
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

    def _authority(self) -> np.ndarray:
        """Largest achievable force/torque along each wrench axis (thrusters saturated)."""
        out = np.zeros(6)
        for k in range(6):
            e = np.zeros(6)
            e[k] = 1.0
            t = self.B_pinv @ e
            t = t / np.max(np.abs(t))
            out[k] = (self.B @ t)[k] * self.p.thruster_max
        return out

    def allocate(self, wrench_norm: np.ndarray) -> np.ndarray:
        """Map a normalised wrench (each axis in [-1, 1] of its authority) to thruster commands."""
        w = np.asarray(wrench_norm, float) * self.authority
        t = self.B_pinv @ w / self.p.thruster_max
        peak = np.max(np.abs(t))
        return t / peak if peak > 1.0 else t

    def step(self, dt: float, thrust_cmd: np.ndarray, extra_wrench: np.ndarray | None = None) -> None:
        """Advance ``dt`` seconds. ``extra_wrench`` is an external body-frame [F; M]
        (contact forces, tether tension). A non-finite result rolls the state back."""
        p, s = self.p, self.s
        saved = (s.pos.copy(), s.q.copy(), s.vel.copy(), s.omega.copy())
        target = np.clip(np.asarray(thrust_cmd, float), -1, 1) * p.thruster_max
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

        # net buoyancy acts up (world -z), righting moment from CB above CG
        up_body = q_rot(q_inv, np.array([0.0, 0.0, -1.0]))
        F_buoy = up_body * p.net_buoyancy
        weight = p.mass * G
        r_cb = np.array([0.0, 0.0, -p.gm])                   # CB above CG in body frame
        M_right = np.cross(r_cb, up_body * (weight + p.net_buoyancy))

        F_tot = F + F_drag + F_buoy
        # Coriolis-lite: keep velocities consistent while rotating
        F_tot -= self.M * np.cross(s.omega, s.vel)
        s.accel = F_tot / self.M
        s.vel = s.vel + s.accel * dt
        M_tot = Mt + M_drag + M_right - np.cross(s.omega, self.I * s.omega)
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
        if s.pos[2] > self.seabed_depth - 0.05:        # anti-tunnelling; contact forces do the work
            s.pos[2] = self.seabed_depth - 0.05
            if v_world[2] > 0:
                s.vel = q_rot(q_conj(s.q), v_world * np.array([1, 1, 0]))

    # convenience ------------------------------------------------------------
    @property
    def euler(self) -> tuple[float, float, float]:
        return q_to_euler(self.s.q)

    def world_velocity(self) -> np.ndarray:
        return q_rot(self.s.q, self.s.vel)
