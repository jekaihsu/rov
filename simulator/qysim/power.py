"""Vehicle power: a tether power budget for surface-powered vehicles, battery cutoff for the rest.

Tether-powered vehicles (X1) have no battery. Thrusters, lights and the electronics ("hotel")
share an available-power budget; when the demand exceeds it, all thruster commands are scaled
down together so they cannot all reach their individual maxima at once. A power trip (ground
fault / insulation monitor, instructor injection) removes all power until it is reset.

Battery vehicles keep the simulator's existing state-of-charge drain and add a hard cutoff of
motors and lights at empty, re-enabled above a small hysteresis.

All numbers are provisional engineering assumptions, labelled with their source. X1 supply
voltage and power, light wattage and thruster current are unpublished (see
``research_notes/感測器_揚沙_通訊/comms_and_power.md``, Part C item 3).
"""
from __future__ import annotations

import numpy as np

ASSUMED_THRUST_PER_WATT = 0.115    # N/W at full thrust for small electric thrusters (assumption)
LIGHT_LEVELS = (0.0, 0.55, 1.0)    # right_switch 0/1/2, same fractions as the viewer's lamps
BATTERY_RESTART_PERCENT = 2.0      # cutoff hysteresis (assumption)

_ASSUMPTION = "工程假設；非實測"
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

    def _battery_cutoff(self, sim) -> None:
        if self.tether:
            self.cutoff = False
        elif sim.battery <= 0.0:
            self.cutoff = True
        elif sim.battery > BATTERY_RESTART_PERCENT:
            self.cutoff = False

    def apply(self, sim, thr: np.ndarray, rc) -> np.ndarray:
        """Return the thruster commands the power system can deliver this step."""
        self._battery_cutoff(sim)
        powered = not self.tripped and not self.cutoff
        self.lights_on = powered
        level = LIGHT_LEVELS[max(0, min(2, int(rc.right_switch)))] if powered else 0.0
        self.lights_w = self.values["light_w"] * self.values["lights"] * level
        hotel = self.values["hotel_w"] if not self.tripped else 0.0
        if not powered:
            thr = np.zeros_like(thr)
        fraction = np.abs(np.asarray(thr, float))
        self.thruster_w = float(self.values["thruster_full_w"] * np.sum(fraction ** 1.5))
        self.limited = False
        self.scale = 1.0
        available = self.available_w(sim)
        if available is not None and powered:
            budget = max(0.0, available - self.lights_w - hotel)
            if self.thruster_w > budget:
                # Power ~ thrust^1.5, so a uniform thrust scale k changes power by k^1.5.
                self.scale = (budget / self.thruster_w) ** (2.0 / 3.0) if self.thruster_w > 0 else 0.0
                thr = thr * self.scale
                self.thruster_w = budget
                self.limited = True
        self.demand_w = self.thruster_w + self.lights_w + hotel
        return thr

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
            "soc": None if self.tether else round(sim.battery, 1),
        }
