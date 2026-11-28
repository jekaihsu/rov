"""Flight controller: pilot intent -> normalised body wrench.

Modes (RC left switch, as documented by the SDK):
    A  attitude-stable: roll is held level and the roll stick is ignored
    S  sport: full 6-DOF, 360 deg roll/pitch; releasing a rotation stick holds attitude
    C  VR head-tracking: flown like A in the simulator (no headset input)
Depth keeping holds world depth; the heave input then moves the depth set-point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .physics import Vehicle, q_conj, q_mul, q_rot, q_from_euler, q_to_euler

ACTIVE = 0.02

# speed fraction, authority/mass acceleration fraction, jerk multiplier,
# yaw rate fraction, stick exponent. All limits scale with the selected vehicle.
PROFILES = {
    "cine": (0.30, 0.10, 12.0, 0.30, 2.0),
    "normal": (0.52, 0.35, 20.0, 0.50, 1.5),
    "sport": (0.70, 0.90, 30.0, 0.75, 1.0),
}


@dataclass
class ControllerGains:
    rate_max: tuple = (math.radians(90), math.radians(60), math.radians(70))   # roll, pitch, yaw rad/s
    att_p: float = 3.0            # attitude error (rad) -> rate (rad/s)
    rate_d: tuple = (0.9, 0.9, 0.9)   # normalised torque per rad/s of rate error
    depth_p: float = 1.6          # normalised heave per metre of depth error
    depth_d: float = 1.6          # per m/s vertical speed
    depth_rate: float = 0.6       # m/s set-point slew at full heave input


class FlightController:
    def __init__(self, vehicle: Vehicle, gains: ControllerGains | None = None):
        self.v = vehicle
        self.g = gains or ControllerGains()
        self.q_hold = vehicle.s.q.copy()
        self.depth_hold: float | None = None
        self.last_wrench = np.zeros(6)
        self.reset_assist()

    def reset_assist(self) -> None:
        self.assist_level = 0
        self.profile = "normal"
        self.velocity_target = np.zeros(3)
        self.acceleration = np.zeros(3)
        self.velocity_integral = np.zeros(3)
        self.position_integral = np.zeros(3)
        self.position_hold = None
        self.yaw_rate = 0.0
        self.limited = False
        self.control_frame = None

    def assist_state(self) -> dict:
        speed, _, _, yaw, _ = PROFILES[self.profile]
        return {
            "level": self.assist_level,
            "profile": self.profile,
            "holding": self.position_hold is not None,
            "limited": self.limited,
            "speed_limit": (np.asarray(self.v.p.vmax) * speed).tolist(),
            "yaw_rate_limit": math.degrees(self.v.p.wmax[2] * yaw),
        }

    def assist_force(self, dt, c, mode, keep_depth, measured=None):
        """Ground velocity PI in a heading-aligned (A/C) or body (S) frame.

        The reference is a critically damped, acceleration/jerk bounded filter.
        Conditional integration and bounded integrators prevent allocation windup.
        ``measured`` (a sensors.SensorFrame) supplies attitude, ground velocity and position estimates;
        ``None`` reads physics truth, the pre-sensor-layer behaviour.
        """
        v = self.v
        q_now = v.s.q if measured is None else measured.q
        ground_velocity = v.world_velocity() if measured is None else measured.vel_world
        position = v.s.pos if measured is None else measured.pos
        speed, accel, jerk, _, exponent = PROFILES[self.profile]
        limits = np.asarray(v.p.vmax) * speed
        amax = v.authority[:3] / v.M * accel
        frame = q_now if mode == "S" else q_from_euler(0, 0, q_to_euler(q_now)[2])
        if self.control_frame is not None:
            rotation = q_mul(q_conj(frame), self.control_frame)
            self.velocity_integral = q_rot(rotation, self.velocity_integral)
            self.velocity_target = q_rot(rotation, self.velocity_target)
            self.acceleration = q_rot(rotation, self.acceleration)
        self.control_frame = frame.copy()
        velocity = q_rot(q_conj(frame), ground_velocity)
        sticks = np.array([c["surge"], c["sway"], -c["heave"]])
        target = np.sign(sticks) * np.abs(sticks) ** exponent * limits
        active = np.any(np.abs(sticks) > ACTIVE)
        if active or self.assist_level != 2:
            self.position_hold = None
            self.position_integral[:] = 0
        elif self.position_hold is None and np.linalg.norm(ground_velocity) < 0.05:
            self.position_hold = position.copy()
        if self.position_hold is not None:
            error = self.position_hold - position
            if keep_depth:
                error[2] = 0
            if not self.limited:
                self.position_integral = np.clip(self.position_integral + error * dt, -0.5, 0.5)
            target = q_rot(q_conj(frame), 0.8 * error + 0.15 * self.position_integral)
            target -= 0.25 * velocity
            target = np.clip(target, -limits, limits)
        jerk_command = 256.0 * (target - self.velocity_target) - 32.0 * self.acceleration
        self.acceleration = np.clip(
            self.acceleration + np.clip(jerk_command, -amax * jerk, amax * jerk) * dt, -amax, amax)
        self.velocity_target += self.acceleration * dt
        error = self.velocity_target - velocity
        old_integral = self.velocity_integral.copy()
        settling = (np.abs(error) < 0.05) & (np.abs(self.acceleration) < 0.05)
        integration_error = error if self.position_hold is not None else np.where(settling, error, 0.0)
        self.velocity_integral = np.clip(old_integral + integration_error * dt,
                                         -v.authority[:3] / v.M, v.authority[:3] / v.M)
        # Normalized gains derived from effective mass and independent axis authority.
        drag = np.asarray(v.p.linear_drag[:3]) * self.velocity_target
        drag += v.quad_drag * self.velocity_target * np.abs(self.velocity_target)
        newtons = v.M * (4.0 * error + 2.0 * self.velocity_integral) + drag
        if keep_depth:
            # Depth is controlled in world coordinates even in S mode.
            world_force = q_rot(frame, newtons)
            world_force[2] = 0
            newtons = q_rot(q_conj(frame), world_force)
            self.velocity_integral[2] = 0
        force = q_rot(q_conj(q_now), q_rot(frame, newtons))
        force = np.divide(force, v.authority[:3], out=np.zeros(3), where=v.authority[:3] > 1e-9)
        return force, old_integral

    def reset_holds(self, q_now: np.ndarray | None = None) -> None:
        self.q_hold = (self.v.s.q if q_now is None else q_now).copy()
        self.depth_hold = None
        self.reset_assist()

    def update(self, dt: float, cmd: dict, mode: str, locked: bool, keep_depth: bool,
               heading_target: float | None = None, assist: int = 0, profile: str = "normal",
               dvl_valid: bool = True, measured=None) -> np.ndarray:
        """Return thruster commands in [-1, 1]. ``cmd`` holds surge/sway/heave/roll/pitch/yaw.

        ``measured`` is the sensor layer's frame. Heading, depth and position hold then servo on estimates,
        so sensor errors move the real vehicle. ``None`` reads truth exactly as before the layer existed.
        """
        s = self.v.s
        q_now = s.q if measured is None else measured.q
        if not dvl_valid:
            assist = 0
        if locked:
            self.reset_holds(q_now)
            self.profile = profile if profile in PROFILES else "normal"
            self.last_wrench = np.zeros(6)
            return np.zeros(len(self.v.thrusters))

        if assist != self.assist_level or profile != self.profile:
            self.reset_assist()
        self.assist_level = assist
        self.profile = profile if profile in PROFILES else "normal"
        if not assist:
            self.reset_assist()
            self.profile = profile if profile in PROFILES else "normal"
        roll, pitch, yaw = q_to_euler(q_now)
        c = {k: float(cmd.get(k, 0.0)) for k in ("surge", "sway", "heave", "roll", "pitch", "yaw")}
        for axis in c:
            if axis not in self.v.capabilities:
                c[axis] = 0.0
        if mode != "S":
            c["roll"] = 0.0
        rot_active = {k: abs(c[k]) > ACTIVE for k in ("roll", "pitch", "yaw")}

        # ── attitude hold target ────────────────────────────────────────────
        if mode == "S":
            if any(rot_active.values()):
                self.q_hold = q_now.copy()
        else:
            _, hp, hy = q_to_euler(self.q_hold)
            if rot_active["pitch"]:
                hp = pitch
            if rot_active["yaw"]:
                hy = yaw
            if heading_target is not None and not rot_active["yaw"]:
                hy = heading_target
            self.q_hold = q_from_euler(0.0, hp, hy)

        q_err = q_mul(q_conj(q_now), self.q_hold)
        if q_err[0] < 0:
            q_err = -q_err
        err = 2.0 * q_err[1:]                     # body-frame rotation vector to target

        g = self.g
        rate_des = np.zeros(3)
        axis_cmd = (c["roll"], c["pitch"], c["yaw"])
        for i, name in enumerate(("roll", "pitch", "yaw")):
            if rot_active[name]:
                rate_des[i] = axis_cmd[i] * g.rate_max[i]
            else:
                rate_des[i] = max(-g.rate_max[i], min(g.rate_max[i], g.att_p * err[i]))
        if assist:
            yaw_max = self.v.p.wmax[2] * PROFILES[self.profile][3]
            yaw_target = np.clip(rate_des[2], -yaw_max, yaw_max)
            self.yaw_rate += float(np.clip(yaw_target - self.yaw_rate, -yaw_max * dt, yaw_max * dt))
            rate_des[2] = self.yaw_rate
        omega = s.omega if measured is None else measured.omega
        torque = np.clip(np.array(g.rate_d) * (rate_des - omega), -1, 1)

        # ── translation ───────────────────────────────────────────────────
        force = np.array([c["surge"], c["sway"], 0.0])
        heave_world = -c["heave"]                 # NED: +down
        if keep_depth:
            depth = s.pos[2] if measured is None else measured.depth
            if self.depth_hold is None:
                self.depth_hold = float(depth)
            self.depth_hold += heave_world * g.depth_rate * dt
            self.depth_hold = max(0.0, min(self.v.seabed_depth - 0.3, self.depth_hold))
            vz = self.v.world_velocity()[2] if measured is None else measured.vz
            heave_world = g.depth_p * (self.depth_hold - depth) - g.depth_d * vz
        else:
            self.depth_hold = None
        if mode == "S" and not keep_depth:
            force[2] += heave_world               # body-frame heave in sport mode
        else:
            # A depth controller commands world-vertical FORCE, even in sport
            # mode. Rotate newtons, not normalised axis demands: the vehicle's
            # surge/sway/heave authority differs, so rotating the latter would
            # introduce a spurious horizontal force when the body is tilted.
            vertical_newtons = heave_world * self.v.authority[2]
            body_force = q_rot(q_conj(q_now), np.array([0.0, 0.0, vertical_newtons]))
            force += np.divide(body_force, self.v.authority[:3],
                               out=np.zeros(3), where=self.v.authority[:3] > 1e-9)

        if assist:
            assisted, old_integral = self.assist_force(dt, c, mode, keep_depth, measured)
            if keep_depth:
                vertical_newtons = heave_world * self.v.authority[2]
                depth_force = q_rot(q_conj(q_now), np.array([0.0, 0.0, vertical_newtons]))
                assisted += np.divide(depth_force, self.v.authority[:3],
                                      out=np.zeros(3), where=self.v.authority[:3] > 1e-9)
            force = np.clip(assisted, -1.0, 1.0)
            demand = np.concatenate([assisted, torque])
            motors = self.v.B_pinv @ (demand * self.v.authority) / self.v.p.thruster_max
            self.limited = bool(np.max(np.abs(motors)) > 1.0)
            if self.limited:
                self.velocity_integral = old_integral
        wrench = np.clip(np.concatenate([force, torque]), -1.5, 1.5)
        self.last_wrench = wrench
        return self.v.allocate(wrench)
