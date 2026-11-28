"""Draw the heavy-configuration pool comparison next to the identified model.

Writes SVG into docs/design/model-o-calibration/. Run from the repository root:

    python simulator/tools/model_o_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulator"))

from qysim.vehicles import MODEL_O_PARAMS
from qysim.model_o import (  # noqa: E402
    MOTOR_TAU,
    POOL_VOLTAGE,
    VOLTAGES,
    MEASURED_RATE,
    MEASURED_SPEED,
    open_loop,
    polynomial_thrust,
    prepared_vehicle,
    published_thrust,
    scalar_response,
)

OUT = ROOT / "docs" / "design" / "model-o-calibration"
DT = 0.01


def _map(value, low, high, start, size):
    if high == low:
        return start
    return start + (value - low) / (high - low) * size


def _frame(width, height, title, xlabel, ylabel, xmin, xmax, ymin, ymax):
    left, top, plot_w, plot_h = 64, 36, width - 88, height - 72
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f4f1ea"/>',
        f'<text x="{width / 2}" y="22" text-anchor="middle" font-family="sans-serif" '
        f'font-size="15">{title}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#333"/>',
        f'<text x="{left + plot_w / 2}" y="{height - 8}" text-anchor="middle" font-size="12" '
        f'font-family="sans-serif">{xlabel}</text>',
        f'<text x="16" y="{top + plot_h / 2}" text-anchor="middle" font-size="12" '
        f'font-family="sans-serif" transform="rotate(-90 16 {top + plot_h / 2})">{ylabel}</text>',
    ]
    return parts, left, top, plot_w, plot_h


def _points(xs, ys, left, top, plot_w, plot_h, xmin, xmax, ymin, ymax):
    coords = []
    for x_value, y_value in zip(xs, ys):
        x_pixel = _map(x_value, xmin, xmax, left, plot_w)
        y_pixel = _map(y_value, ymin, ymax, top + plot_h, -plot_h)
        coords.append(f"{x_pixel:.1f},{y_pixel:.1f}")
    return " ".join(coords)


def _legend(parts, items, x_pos, y_pos):
    for index, (color, label) in enumerate(items):
        y_line = y_pos + index * 16
        parts.append(f'<line x1="{x_pos}" y1="{y_line}" x2="{x_pos + 18}" y2="{y_line}" '
                     f'stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{x_pos + 24}" y="{y_line + 4}" font-size="11" '
                     f'font-family="sans-serif">{label}</text>')


def write_thrust(path):
    parts, left, top, plot_w, plot_h = _frame(
        760, 460, "繫樁推力對正規化指令", "正規化指令（−1 = 1100 µs，+1 = 1900 µs）",
        "推力 (N)", -1, 1, -70, 70)
    command = np.linspace(-1, 1, 81)
    colors = ("#9aa0a6", "#5f6f8f", "#2f6f4e", "#1d4e89", "#b86e00", "#8c2f39")
    legend = []
    for voltage, color in zip(VOLTAGES, colors):
        force = published_thrust(command, float(voltage))
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.6" points="'
                     f'{_points(command, force, left, top, plot_w, plot_h, -1, 1, -70, 70)}"/>')
        legend.append((color, f"{voltage:.0f} V 公開繫樁"))
    poly = polynomial_thrust(command)
    parts.append(f'<polyline fill="none" stroke="#111" stroke-width="1.4" stroke-dasharray="5 4" points="'
                 f'{_points(command, poly, left, top, plot_w, plot_h, -1, 1, -70, 70)}"/>')
    legend.append(("#111", "Eq. 18（對稱，滿推 30.4 N）"))
    _legend(parts, legend, left + 12, top + 16)
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf8")


def write_surge(path):
    parts, left, top, plot_w, plot_h = _frame(
        760, 460, "前進步階：模擬與識別模型", "時間 (s)", "前進速度 (m/s)", 0, 4, 0, 0.85)
    mass = MODEL_O_PARAMS["mass"] + MODEL_O_PARAMS["added_mass"][0]
    legend = []
    colors = {1.0: "#1d4e89", 0.5: "#b86e00"}
    for stick, color in colors.items():
        vehicle = prepared_vehicle(POOL_VOLTAGE)
        wrench, trace = open_loop(vehicle, [stick, 0, 0, 0, 0, 0], 4.0, DT)
        time = np.arange(len(trace)) * DT
        reference = scalar_response(wrench[0], 13.7, 141.0, mass, MOTOR_TAU, 4.0, DT)
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.8" points="'
                     f'{_points(time, trace[:, 0], left, top, plot_w, plot_h, 0, 4, 0, 0.85)}"/>')
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.2" stroke-dasharray="4 3" points="'
                     f'{_points(time, reference, left, top, plot_w, plot_h, 0, 4, 0, 0.85)}"/>')
        legend.append((color, f"推力比例 {stick:.0%}，實線模擬、虛線同力一維模型"))
    parts.append(f'<line x1="{left}" y1="{_map(MEASURED_SPEED[0], 0, 0.85, top + plot_h, -plot_h):.1f}" '
                 f'x2="{left + plot_w}" y2="{_map(MEASURED_SPEED[0], 0, 0.85, top + plot_h, -plot_h):.1f}" '
                 f'stroke="#8c2f39" stroke-dasharray="2 3"/>')
    legend.append(("#8c2f39", "Table 4 前進 0.72 m/s"))
    _legend(parts, legend, left + 16, top + 16)
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf8")


def write_steady(path):
    parts, left, top, plot_w, plot_h = _frame(
        760, 460, "穩態速度對推力比例（水池等效電壓）", "推力比例（+1 受該電壓端點限制）",
        "速度 (m/s 或 rad/s)", 0.15, 1.05, 0, 4.2)
    sticks = np.round(np.arange(0.2, 1.01, 0.1), 5)
    series = {
        "前進": ([], "#1d4e89", 0, False),
        "側移": ([], "#2f6f4e", 1, False),
        "上浮": ([], "#b86e00", 2, False),
        "偏航": ([], "#8c2f39", 5, True),
    }
    for stick in sticks:
        for name, (values, _color, axis, literature) in series.items():
            command = np.zeros(6)
            command[0 if axis == 0 else 1 if axis == 1 else 2 if axis == 2 else 5] = stick
            if axis == 2:
                command[2] = -stick
            vehicle = prepared_vehicle(POOL_VOLTAGE, literature=literature)
            _, trace = open_loop(vehicle, command, 6.0, DT)
            values.append(abs(float(trace[-1, axis])))
    legend = []
    for name, (values, color, _axis, _literature) in series.items():
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.7" points="'
                     f'{_points(sticks, values, left, top, plot_w, plot_h, 0.15, 1.05, 0, 4.2)}"/>')
        legend.append((color, name))
    marks = ((1.0, MEASURED_SPEED[0]), (1.0, MEASURED_SPEED[1]), (1.0, MEASURED_SPEED[2]),
             (1.0, MEASURED_RATE[2]))
    for x_value, y_value in marks:
        x_pixel = _map(x_value, 0.15, 1.05, left, plot_w)
        y_pixel = _map(y_value, 0, 4.2, top + plot_h, -plot_h)
        parts.append(f'<circle cx="{x_pixel:.1f}" cy="{y_pixel:.1f}" r="3.5" fill="#111"/>')
    legend.append(("#111", "Table 4 滿輸入"))
    _legend(parts, legend, left + 16, top + 16)
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf8")


def write_coast(path):
    parts, left, top, plot_w, plot_h = _frame(
        760, 420, "前進自由衰減（鬆桿）", "時間 (s)", "前進速度 (m/s)", 0, 6, 0, 0.8)
    vehicle = prepared_vehicle(POOL_VOLTAGE)
    vehicle.s.vel[0] = MEASURED_SPEED[0]
    count = int(6.0 / DT)
    speed = np.empty(count)
    for index in range(count):
        vehicle.step(DT, np.zeros(8))
        speed[index] = vehicle.s.vel[0]
    mass = MODEL_O_PARAMS["mass"] + MODEL_O_PARAMS["added_mass"][0]
    reference = scalar_response(0.0, 13.7, 141.0, mass, MOTOR_TAU, 6.0, DT, speed0=MEASURED_SPEED[0])
    time = np.arange(count) * DT
    parts.append(f'<polyline fill="none" stroke="#1d4e89" stroke-width="1.8" points="'
                 f'{_points(time, speed, left, top, plot_w, plot_h, 0, 6, 0, 0.8)}"/>')
    parts.append(f'<polyline fill="none" stroke="#1d4e89" stroke-width="1.2" stroke-dasharray="4 3" points="'
                 f'{_points(time, reference, left, top, plot_w, plot_h, 0, 6, 0, 0.8)}"/>')
    _legend(parts, (("#1d4e89", "實線模擬，虛線 Table A1 一維模型"),), left + 16, top + 18)
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_thrust(OUT / "thrust-pwm.svg")
    write_surge(OUT / "surge-step.svg")
    write_steady(OUT / "steady-inputs.svg")
    write_coast(OUT / "coast.svg")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
