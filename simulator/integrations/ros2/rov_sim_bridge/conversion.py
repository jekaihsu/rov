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


def euler_to_quaternion(roll_deg, pitch_deg, yaw_deg):
    """NED/FRD body->world quaternion [w, x, y, z] from ZYX Euler angles in degrees."""
    roll, pitch, yaw = (math.radians(v) for v in finite((roll_deg, pitch_deg, yaw_deg)))
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    q = (cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy, cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy)
    return q if q[0] >= 0 else tuple(-v for v in q)


def estimated_pose(state):
    """Pose the vehicle's own instruments report: ``(pos_ned, q_wxyz, depth_m, source)``.

    Uses the optional ``state.sensors`` layer (dead-reckoned position, pressure depth, fused heading)
    when the host sends it; roll and pitch stay as streamed, as on the SDK. Older hosts without the
    layer fall back to physics truth and report ``source == "truth"``.
    """
    sensors = state.get("sensors")
    if not isinstance(sensors, dict) or sensors.get("pos_est") is None or sensors.get("heading") is None:
        return finite(state["pos"]), finite(state["q"]), float(state["pos"][2]), "truth"
    roll, pitch = finite(state["euler"][:2])
    q = euler_to_quaternion(roll, pitch, sensors["heading"])
    north, east, _ = finite(sensors["pos_est"])
    depth = float(sensors.get("depth", state["pos"][2]))
    return (north, east, depth), q, depth, "sensors"


def dvl_usable(state, world):
    """Velocity assistance needs bottom lock; the server falls back to manual thrust while it is lost."""
    sensors = state.get("sensors")
    if isinstance(sensors, dict) and isinstance(sensors.get("dvl"), dict):
        return sensors["dvl"].get("status") != "lost"
    altitude = world.get("seabed_depth", -math.inf) - state.get("pos", [0, 0, 0])[2]
    return 0.1 < altitude < 100


def range_reading(value, maximum, blind=0.3):
    """SDK echo-sounder value -> REP 117 Range: +Inf for no echo, -Inf inside the blind zone."""
    value, = finite([value])
    if value >= maximum:
        return math.inf
    if value <= blind + 1e-6:
        return -math.inf
    return value


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
