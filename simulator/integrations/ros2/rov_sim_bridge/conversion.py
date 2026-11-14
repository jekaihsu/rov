"""Pure protocol conversions: NED/FRD to ENU/FLU and SI commands to RC."""
import math

STRINGS = {"finite": "Expected finite numeric values", "quaternion": "Invalid quaternion"}
CHANNELS = ("left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave")


def finite(values):
    values = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in values):
        raise ValueError(STRINGS["finite"])
    return values


def ned_to_enu(v):
    n, e, d = finite(v)
    return e, n, -d


def frd_to_flu(v):
    x, y, z = finite(v)
    return x, -y, -z


def quaternion(q):
    # q_ENU_FLU = q_ENU_NED * q_NED_FRD * q_FRD_FLU (Hamilton).
    w, x, y, z = finite(q)
    norm = math.sqrt(w*w + x*x + y*y + z*z)
    if norm < 1e-9:
        raise ValueError(STRINGS["quaternion"])
    s = math.sqrt(0.5) / norm
    return (s*(x+y), s*(x-y), s*(w-z), s*(w+z))  # ROS xyzw


def pwm(value):
    return int(round(1500 + 500 * max(-1.0, min(1.0, value))))


def velocity_rc(twist, limits):
    # Shaping is explicitly linear; normal assistance applies exponent 1.5.
    x, y, z, roll, pitch, yaw = finite(twist)
    limits = finite(limits)
    if len(limits) != 3 or min(limits) <= 0:
        raise ValueError(STRINGS["finite"])
    def stick(speed, limit):
        fraction = max(-1.0, min(1.0, speed / limit))
        return math.copysign(abs(fraction) ** (1 / 1.5), fraction)
    return dict(zip(CHANNELS, (
        pwm(pitch / math.radians(60)), pwm(-yaw / math.radians(70)),
        pwm(stick(x, limits[0])), pwm(roll / math.radians(90)),
        pwm(stick(z, limits[2])), pwm(stick(-y, limits[1])),
    )))


class CommandGate:
    """A stale ROS producer can never be kept alive by network heartbeats."""

    def __init__(self, timeout=0.4):
        self.timeout = timeout
        self.reset()

    def reset(self):
        self.armed = False
        self.twist = (0.0,) * 6
        self.depth = None
        self.last_command = -math.inf

    def velocity(self, values, now):
        self.twist = finite(values)
        self.depth = None
        self.last_command = now

    def set_depth(self, value, now):
        value, = finite([value])
        if value < 0:
            raise ValueError(STRINGS["finite"])
        self.depth = value
        self.twist = (0.0,) * 6
        self.last_command = now

    def arm(self, value, now):
        if not value:
            self.reset()
        elif now - self.last_command <= self.timeout:
            self.armed = True

    def packet(self, state, now, led):
        if now - self.last_command > self.timeout:
            self.reset()
        rc = {key: 1500 for key in CHANNELS}
        rc.update(rc_lock=int(not self.armed), keep_depth=0, left_switch=1, right_switch=led)
        if isinstance(state.get("assist"), dict):
            rc.update(assist=1, profile="normal")
        if self.armed:
            rc.update(velocity_rc(self.twist, state["assist"]["speed_limit"]))
            if self.depth is not None:
                hold = state.get("depth_hold")
                hold = state["pos"][2] if hold is None else hold
                rc["keep_depth"] = 1
                rc["left_wave"] = pwm((hold - self.depth) / 0.6)
        return rc
