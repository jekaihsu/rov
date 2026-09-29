"""Remote-controller model: raw PWM channels + operation-mode interpretation.

Channel semantics and operation modes follow the QYSea OpenSDK documentation
(QY_RovController_Manage / QYRovParameterManage.set_rov_controller_operation):
joysticks and wheels are PWM 1000..2000 with 1500 as centre; ``<1500`` is
down/left, ``>1500`` is up/right.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

CHANNELS = ("left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave")
OPERATION_MODES = ("ROV_USA", "ROV_JPN", "ROV_CHN", "UAV_USA", "UAV_JPN", "UAV_CHN")
CTRL_MODES = ("A", "S", "C")          # left switch 0/1/2

# pilot axes: surge(+fwd) sway(+stbd) heave(+up) roll(+stbd down) pitch(+nose up) yaw(+right)
# each entry: axis -> (channel, sign). "Nose down" is listed first in the SDK
# docs for stick-up (低头/抬头), so pitch is the negated stick.
_MAP = {
    "ROV_USA": {"pitch": ("left_ud", -1), "yaw": ("left_lr", 1), "surge": ("right_ud", 1),
                "roll": ("right_lr", 1), "heave": ("left_wave", 1), "sway": ("right_wave", 1)},
    "ROV_JPN": {"surge": ("left_ud", 1), "yaw": ("left_lr", 1), "pitch": ("right_ud", -1),
                "roll": ("right_lr", 1), "heave": ("left_wave", 1), "sway": ("right_wave", 1)},
    "ROV_CHN": {"surge": ("left_ud", 1), "roll": ("left_lr", 1), "pitch": ("right_ud", -1),
                "yaw": ("right_lr", 1), "heave": ("left_wave", 1), "sway": ("right_wave", 1)},
    "UAV_USA": {"heave": ("left_ud", 1), "yaw": ("left_lr", 1), "surge": ("right_ud", 1),
                "sway": ("right_lr", 1), "pitch": ("left_wave", 1), "roll": ("right_wave", 1)},
    "UAV_JPN": {"surge": ("left_ud", 1), "yaw": ("left_lr", 1), "heave": ("right_ud", 1),
                "sway": ("right_lr", 1), "pitch": ("left_wave", 1), "roll": ("right_wave", 1)},
    "UAV_CHN": {"surge": ("left_ud", 1), "sway": ("left_lr", 1), "heave": ("right_ud", 1),
                "yaw": ("right_lr", 1), "pitch": ("left_wave", 1), "roll": ("right_wave", 1)},
}
TRANSLATION = ("surge", "sway", "heave")
ROTATION = ("roll", "pitch", "yaw")
DEADBAND = 0.02


def pwm_to_unit(v: float) -> float:
    x = (float(v) - 1500.0) / 500.0
    x = max(-1.0, min(1.0, x))
    return 0.0 if abs(x) < DEADBAND else x


def clamp_pwm(v) -> int:
    return int(max(1000, min(2000, round(float(v)))))


@dataclass
class RCState:
    left_ud: int = 1500
    left_lr: int = 1500
    right_ud: int = 1500
    right_lr: int = 1500
    left_wave: int = 1500
    right_wave: int = 1500
    rc_lock: int = 1           # 1 = motors locked, 0 = unlocked
    keep_depth: int = 0
    record: int = 0
    photo: int = 0
    left_switch: int = 0       # 0 A, 1 S, 2 C
    right_switch: int = 0      # LED 0 off, 1, 2

    def set_channel(self, name: str, value) -> None:
        if name not in CHANNELS:
            raise KeyError(name)
        setattr(self, name, clamp_pwm(value))

    def centre_sticks(self) -> None:
        for c in CHANNELS:
            setattr(self, c, 1500)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Shaping:
    """Throttle (translation) and rotate curvature/limit, 0..100 like the SDK."""
    throttle_curvature: int = 60
    throttle_limit: int = 100
    rotate_curvature: int = 60
    rotate_limit: int = 100
    custom: bool = False

    @staticmethod
    def _shape(x: float, curvature: int, limit: int) -> float:
        e = max(0, min(100, curvature)) / 100.0 * 0.85
        y = (1 - e) * x + e * x ** 3
        return y * max(0, min(100, limit)) / 100.0


def pilot_command(rc: RCState, operation_mode: str, shaping: Shaping) -> dict:
    """Interpret RC channels as pilot intent per operation mode. Values in [-1, 1]."""
    table = _MAP.get(operation_mode, _MAP["ROV_USA"])
    out = {}
    for axis, (ch, sign) in table.items():
        x = sign * pwm_to_unit(getattr(rc, ch))
        if axis in TRANSLATION:
            out[axis] = Shaping._shape(x, shaping.throttle_curvature, shaping.throttle_limit)
        else:
            out[axis] = Shaping._shape(x, shaping.rotate_curvature, shaping.rotate_limit)
    return out


def ctrl_mode(rc: RCState) -> str:
    return CTRL_MODES[max(0, min(2, int(rc.left_switch)))]
