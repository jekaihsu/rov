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

    def reset_holds(self) -> None:
        self.q_hold = self.v.s.q.copy()
        self.depth_hold = None

    def update(self, dt: float, cmd: dict, mode: str, locked: bool, keep_depth: bool,
               heading_target: float | None = None) -> np.ndarray:
        """Return thruster commands in [-1, 1]. ``cmd`` holds surge/sway/heave/roll/pitch/yaw."""
        s = self.v.s
        if locked:
            self.reset_holds()
            self.last_wrench = np.zeros(6)
            return np.zeros(len(self.v.thrusters))

        roll, pitch, yaw = q_to_euler(s.q)
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
                self.q_hold = s.q.copy()
        else:
            _, hp, hy = q_to_euler(self.q_hold)
            if rot_active["pitch"]:
                hp = pitch
            if rot_active["yaw"]:
                hy = yaw
            if heading_target is not None and not rot_active["yaw"]:
                hy = heading_target
            self.q_hold = q_from_euler(0.0, hp, hy)

        q_err = q_mul(q_conj(s.q), self.q_hold)
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
        torque = np.clip(np.array(g.rate_d) * (rate_des - s.omega), -1, 1)

        # ── translation ───────────────────────────────────────────────────
        force = np.array([c["surge"], c["sway"], 0.0])
        heave_world = -c["heave"]                 # NED: +down
        if keep_depth:
            if self.depth_hold is None:
                self.depth_hold = float(s.pos[2])
            self.depth_hold += heave_world * g.depth_rate * dt
            self.depth_hold = max(0.0, min(self.v.seabed_depth - 0.3, self.depth_hold))
            vz = self.v.world_velocity()[2]
            heave_world = g.depth_p * (self.depth_hold - s.pos[2]) - g.depth_d * vz
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
            body_force = q_rot(q_conj(s.q), np.array([0.0, 0.0, vertical_newtons]))
            force += np.divide(body_force, self.v.authority[:3],
                               out=np.zeros(3), where=self.v.authority[:3] > 1e-9)

        wrench = np.clip(np.concatenate([force, torque]), -1.5, 1.5)
        self.last_wrench = wrench
        return self.v.allocate(wrench)
