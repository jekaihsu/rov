"""Supply resistance, protected thruster allocation and vehicle electrical loads.

All estimated X1 parameters await the electrical and thermal measurement checklist.
"""
from __future__ import annotations

import math

import numpy as np

ASSUMED_THRUST_PER_WATT = 0.115    # N/W at full thrust for small electric thrusters (assumption)
LIGHT_LEVELS = (0.0, 0.55, 1.0)    # right_switch 0/1/2, same fractions as the viewer's lamps
BATTERY_RESTART_PERCENT = 2.0      # cutoff hysteresis (assumption)

_ASSUMPTION = "暫定工程假設；非實測"
POWER_PROFILES = {
    "x1": {
        "type": {"value": "tether", "source": "real-rov-research.md: X1 由纜線供電、無電池"},
        "available_w": {"value": 4800.0, "source": _ASSUMPTION + "：X1 供電功率未公開；約可同時供應燈光、"
                                                      "電子負載與全部推進器滿推力的 60%"},
        "thruster_full_w": {"value": 1290.0, "source": _ASSUMPTION + "：暫定推力 148 N ÷ 約 0.115 N/W"},
        "light_w": {"value": 60.0, "source": _ASSUMPTION + "：每盞 6000 lm（經銷商）÷ 約 100 lm/W"},
        "lights": {"value": 2, "source": "經銷商：兩盞 LED"},
        "hotel_w": {"value": 50.0, "source": _ASSUMPTION + "：相機、電子艙、通訊模組"},
    },
    "falcon": {
        "type": {"value": "tether", "source": _ASSUMPTION + "：此類電動觀察／輕作業級 ROV 多由水面供電"},
        "available_w": {"value": 3000.0, "source": _ASSUMPTION},
        "thruster_full_w": {"value": 960.0, "source": _ASSUMPTION + "：推力 110 N ÷ 約 0.115 N/W"},
        "light_w": {"value": 60.0, "source": _ASSUMPTION},
        "lights": {"value": 2, "source": _ASSUMPTION},
        "hotel_w": {"value": 60.0, "source": _ASSUMPTION},
    },
    "bluerov2_heavy": {
        "type": {"value": "battery", "source": "電池供電機型（研究報告：電池型 ROV 操作）"},
        "thruster_full_w": {"value": 430.0, "source": _ASSUMPTION + "：推力 50 N ÷ 約 0.115 N/W"},
        "light_w": {"value": 15.0, "source": _ASSUMPTION},
        "lights": {"value": 2, "source": _ASSUMPTION},
        "hotel_w": {"value": 20.0, "source": _ASSUMPTION},
        "voltage_empty": {"value": 12.0, "source": "研究報告：4S 鋰電池低於 12.0 V 有損壞風險"},
        "voltage_full": {"value": 16.8, "source": _ASSUMPTION + "：4S 滿電 4.2 V/cell"},
    },
}


def loaded_voltage(source, resistance, watts):
    """High-voltage operating point of P = V (E - V) / R, or zero on collapse."""
    discriminant = source * source - 4.0 * resistance * watts
    return (source + math.sqrt(discriminant)) / 2.0 if discriminant >= 0 else 0.0


# Current limits refer to the vehicle input bus, including equivalent branch currents
# upstream of the onboard converters. Cable resistance is for BOTH conductors per paid-out metre.
for model, profile in POWER_PROFILES.items():
    battery = profile["type"]["value"] == "battery"
    estimates = {
        "cutoff_v": 12.0 if battery else 180.0,
        "derate_v": 14.0 if battery else 270.0,
        "restart_margin_v": 0.1 if battery else 10.0,
        "branch_limit_a": 28.0 if battery else 4.4,
        "total_limit_a": 90.0 if battery else profile["available_w"]["value"] / 300.0,
        "camera_w": 6.0 if battery else 12.0,
        "record_w": 2.0,
        "gimbal_w": 2.0,
        "sensors_w": 5.0 if battery else 10.0,
    }
    if battery:
        estimates["internal_ohm"] = 0.010
        # Match 0.004 percent/s at the legacy full-charge, lamps-off idle operating point.
        idle = profile["hotel_w"]["value"]
        voltage = profile["voltage_full"]["value"]
        idle_bus = loaded_voltage(voltage, estimates["internal_ohm"], idle)
        estimates["capacity_ah"] = (idle / idle_bus) * 100 / (0.004 * 3600)
    else:
        estimates.update(source_v=300.0, loop_ohm_m=0.018)
    for key, value in estimates.items():
        profile[key] = {"value": value, "source": _ASSUMPTION + "；見 x1-measurement-checklist.md PF"}


def profile_values(model_id: str) -> dict:
    profile = POWER_PROFILES.get(model_id, POWER_PROFILES["bluerov2_heavy"])
    return {key: item["value"] for key, item in profile.items()}


class PowerSystem:
    def __init__(self, model_id: str = "x1"):
        self.values = profile_values(model_id)
        self.type = self.values["type"]
        self.tripped = False
        self.cutoff = False
        self.limited = False
        self.scale = 1.0
        self.demand_w = 0.0
        self.thruster_w = 0.0
        self.lights_w = 0.0
        self.lights_on = True
        self.bus_v = None
        self.current_a = 0.0
        self.aux_w = {}
        self.voltage_limited = False

    @property
    def tether(self) -> bool:
        return self.type == "tether"

    def trip(self) -> None:
        self.tripped = True

    def reset(self) -> None:
        self.tripped = False

    def available_w(self, sim) -> float | None:
        if not self.tether:
            return None
        # An instructor "battery" injection on a tether vehicle sags the supply instead.
        supply = max(0.0, min(1.0, sim.battery / 100.0))
        return self.values["available_w"] * supply

    def apply(self, sim, thr: np.ndarray, rc) -> np.ndarray:
        """Reserve accessories first, then preserve signed thrust ratios under all limits."""
        p = self.values
        available = self.available_w(sim)
        if self.tether:
            source = p["source_v"] * available / p["available_w"]
            resistance = p["loop_ohm_m"] * getattr(getattr(sim, "tether", None), "length", 0.0)
        else:
            source = self.voltage(sim)
            resistance = p["internal_ohm"]

        recording = getattr(getattr(sim, "camera", None), "recording_since", None) is not None
        self.aux_w = {
            "camera": p["camera_w"] + recording * p["record_w"],
            "gimbal": p["gimbal_w"],
            "sensors": p["sensors_w"],
            "electronics": p["hotel_w"] - p["camera_w"] - p["gimbal_w"] - p["sensors_w"],
        }
        self.lights_w = p["light_w"] * p["lights"] * LIGHT_LEVELS[max(0, min(2, int(rc.right_switch)))]
        auxiliary = self.lights_w + sum(self.aux_w.values())
        idle_v = loaded_voltage(source, resistance, auxiliary)
        if idle_v <= p["cutoff_v"]:
            self.cutoff = True
        elif (idle_v >= p["cutoff_v"] + p["restart_margin_v"]
              and (self.tether or sim.battery > BATTERY_RESTART_PERCENT)):
            self.cutoff = False
        self.lights_on = not (self.cutoff or self.tripped)
        self.voltage_limited = False
        self.scale = 1.0
        self.limited = False
        if not self.lights_on:
            self.bus_v = 0.0 if self.tripped else source
            self.aux_w = dict.fromkeys(self.aux_w, 0.0)
            self.current_a = 0.0
            self.thruster_w = 0.0
            self.demand_w = 0.0
            self.lights_w = 0.0
            return np.zeros_like(thr)

        magnitude = np.abs(thr)
        peak = float(magnitude.max())
        full_w = p["thruster_full_w"]
        requested = full_w * float(np.sum(magnitude ** 1.5))
        # Stay on the stable branch of the source load line.
        limit_a = p["total_limit_a"]
        if resistance > 0:
            limit_a = min(limit_a, source / (2.0 * resistance))
        budget = limit_a * (source - limit_a * resistance)
        budget = min(budget, available) if available is not None else budget
        self.thruster_w = min(requested, max(0.0, budget - auxiliary))

        if requested:
            # All branch powers scale together. Find the largest feasible motor power
            # below the shared budget. Lower power raises bus voltage monotonically.
            def feasible(watts):
                voltage = loaded_voltage(source, resistance, auxiliary + watts)
                fraction = peak * (watts / requested) ** (2.0 / 3.0)
                cap = min(1.0, max(0.0, (voltage - p["cutoff_v"]) / (p["derate_v"] - p["cutoff_v"])))
                return fraction <= cap, full_w * fraction ** 1.5 <= voltage * p["branch_limit_a"]

            voltage_ok, current_ok = feasible(self.thruster_w)
            if not (voltage_ok and current_ok):
                low, high = 0.0, self.thruster_w
                for _ in range(36):
                    mid = (low + high) / 2
                    if all(feasible(mid)):
                        low = mid
                    else:
                        high = mid
                self.voltage_limited = not feasible(high)[0]
                self.thruster_w = low
            self.scale = (self.thruster_w / requested) ** (2.0 / 3.0)
        self.limited = self.scale < 1.0
        self.demand_w = auxiliary + self.thruster_w
        self.bus_v = loaded_voltage(source, resistance, self.demand_w)
        self.current_a = self.demand_w / self.bus_v
        return thr * self.scale

    def voltage(self, sim) -> float | None:
        if self.tether:
            return None
        low = self.values["voltage_empty"]
        high = self.values["voltage_full"]
        return low + (high - low) * max(0.0, min(1.0, sim.battery / 100.0))

    def state(self, sim) -> dict:
        available = self.available_w(sim)
        voltage = self.voltage(sim)
        return {
            "type": self.type,
            "available_w": None if available is None else round(available),
            "demand_w": round(self.demand_w),
            "thruster_w": round(self.thruster_w),
            "lights_w": round(self.lights_w),
            "limited": self.limited,
            "scale": round(self.scale, 3),
            "tripped": self.tripped,
            "cutoff": self.cutoff,
            "lights_on": self.lights_on,
            "voltage_v": None if voltage is None else round(voltage, 2),
            "bus_v": None if self.bus_v is None else round(self.bus_v, 3),
            "current_a": round(self.current_a, 3),
            "aux_w": self.aux_w.copy(),
            "voltage_limited": self.voltage_limited,
            "soc": None if self.tether else round(sim.battery, 1),
        }
