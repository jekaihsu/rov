"""First-order thermal model of thrusters, motor drivers (MOS) and the electronics housing.

Heat is proportional to electrical load; cooling is strong in water and weak in air. Out of water,
running thrusters for more than ~30 s raises a dry-run
warning (vendor rule for an earlier vehicle of the same family, and common practice for small
electric thrusters).

The vehicle is in water unless ``sim.on_deck`` is set (a deck / pre-dive state; the current
scenarios always start in water). All temperatures and thresholds are provisional assumptions.
"""
from __future__ import annotations

import math

import numpy as np

THERMAL_PARAMETERS = {
    "dry_run_warn_s": {"value": 30.0, "source": "廠商規則：推進器在空氣中運轉不得超過 30 秒（研究報告）"},
    "motor_rise_water_c": {"value": 50.0, "source": "工程假設：水中持續滿推力的穩態溫升"},
    "motor_tau_water_s": {"value": 120.0, "source": "工程假設"},
    "motor_rise_air_c": {"value": 150.0, "source": "工程假設：空氣中散熱差"},
    "motor_tau_air_s": {"value": 60.0, "source": "工程假設"},
    "motor_warn_c": {"value": 70.0, "source": "工程假設；非 X1 規格"},
    "mos_offset_c": {"value": 12.0, "source": "工程假設：與原本固定自檢值 38 °C（26 °C 水溫）一致"},
    "mos_rise_c": {"value": 30.0, "source": "工程假設"},
    "mos_tau_s": {"value": 60.0, "source": "工程假設"},
    "mos_warn_c": {"value": 75.0, "source": "工程假設；非 X1 規格"},
    "housing_offset_c": {"value": 5.0, "source": "工程假設：與原本固定自檢值 31 °C（26 °C 水溫）一致"},
    "housing_rise_c": {"value": 12.0, "source": "工程假設"},
    "housing_tau_s": {"value": 300.0, "source": "工程假設"},
    "housing_warn_c": {"value": 55.0, "source": "工程假設；非 X1 規格"},
    "derate_band_c": {"value": 20.0, "source": "暫定工程假設：超過告警溫度後線性降載至零"},
    "air_c": {"value": 30.0, "source": "工程假設：甲板氣溫"},
}
RUNNING_THRESHOLD = 0.05      # fraction of full thrust that counts as running a motor


def water_temperature(depth: float) -> float:
    """The simulator's existing environment model (surface 26 °C, 0.15 °C/m)."""
    return 26.0 - 0.15 * depth


class ThermalModel:
    def __init__(self, thrusters: int, depth: float = 0.0):
        self.p = {key: item["value"] for key, item in THERMAL_PARAMETERS.items()}
        ambient = water_temperature(depth)
        self.motor_c = np.full(thrusters, ambient)
        self.mos_c = ambient + self.p["mos_offset_c"]
        self.housing_c = ambient + self.p["housing_offset_c"]
        self.dry_run_s = 0.0
        self.injected_c = 0.0
        self.in_water = True

    def step(self, sim, dt: float) -> None:
        self.in_water = not getattr(sim, "on_deck", False)
        ambient = water_temperature(sim.depth) if self.in_water else self.p["air_c"]
        load = np.abs(sim.vehicle.s.thrust) / sim.vehicle.p.thruster_max
        if self.in_water:
            rise, tau = self.p["motor_rise_water_c"], self.p["motor_tau_water_s"]
        else:
            rise, tau = self.p["motor_rise_air_c"], self.p["motor_tau_air_s"]
        target = ambient + rise * load ** 1.5
        self.motor_c += (target - self.motor_c) * (-math.expm1(-dt / tau))
        mean_load = float(np.mean(load)) if len(load) else 0.0
        power = getattr(sim, "power", None)
        powered = power is None or power.lights_on
        hotel_load = sum(power.aux_w.values()) / power.values["hotel_w"] if power else 1.0
        mos_target = ambient + self.p["mos_offset_c"] * powered + self.p["mos_rise_c"] * mean_load
        self.mos_c += (mos_target - self.mos_c) * (-math.expm1(-dt / self.p["mos_tau_s"]))
        housing_target = ambient + self.p["housing_offset_c"] * hotel_load + self.p["housing_rise_c"] * mean_load
        self.housing_c += (housing_target - self.housing_c) * (-math.expm1(-dt / self.p["housing_tau_s"]))
        running = bool(np.any(load > RUNNING_THRESHOLD))
        if self.in_water:
            self.dry_run_s = 0.0
        elif running:
            self.dry_run_s += dt

    @property
    def motor_max_c(self) -> float:
        return float(np.max(self.motor_c)) + self.injected_c if len(self.motor_c) else self.injected_c

    @property
    def mos_reading_c(self) -> float:
        return self.mos_c + self.injected_c

    @property
    def thrust_scale(self) -> float:
        excess = max(0.0, self.motor_max_c - self.p["motor_warn_c"],
                     self.mos_reading_c - self.p["mos_warn_c"], self.housing_c - self.p["housing_warn_c"])
        return max(0.0, 1.0 - excess / self.p["derate_band_c"])

    def warnings(self) -> list:
        found = []
        if self.dry_run_s >= self.p["dry_run_warn_s"]:
            found.append("dry_run")
        if self.motor_max_c >= self.p["motor_warn_c"]:
            found.append("motor_hot")
        if self.mos_reading_c >= self.p["mos_warn_c"] or self.housing_c >= self.p["housing_warn_c"]:
            found.append("electronics_hot")
        return found

    def state(self) -> dict:
        return {
            "motor_c": round(self.motor_max_c, 1),
            "mos_c": round(self.mos_reading_c, 1),
            "housing_c": round(self.housing_c, 1),
            "in_water": self.in_water,
            "dry_run_s": round(self.dry_run_s, 1),
            "derated": self.thrust_scale < 1.0,
            "scale": round(self.thrust_scale, 3),
            "warnings": self.warnings(),
        }
