"""Write the three tether-calibration figures under docs/design/tether-calibration/.

Run from the simulator directory:

    python tools/plot_tether_calibration.py

Matplotlib is optional and is not a simulator runtime dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from qysim.tether import TetherParams
from qysim.tether_reference import (
    CALIBRATION_CASES,
    settle_on_curve,
    steady_current_cable,
    upward_catenary,
)

FIGURES = Path(__file__).resolve().parents[2] / "docs" / "design" / "tether-calibration"


def _reference(case, params):
    if case.current_east_m_s == 0.0:
        return upward_catenary(case, params)
    return steady_current_cable(case, params)


def _draw(case, reference, force, tether) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    solver = tether.x
    gland = tether.force_on_rov
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 4.0))
    mark = max(1, len(reference) // 12)
    axes[0].plot(solver[:, 0], solver[:, 1], color="#1f4b99", label="solver", linewidth=2.2)
    axes[0].plot(reference[:, 0], reference[:, 1], linestyle="none", marker="o", markevery=mark,
                 color="#c45500", label="reference", markersize=5)
    axes[0].set_xlabel("north (m)")
    axes[0].set_ylabel("east (m)")
    axes[0].set_title("plan")
    east_span = float(np.ptp(np.concatenate([reference[:, 1], solver[:, 1]])))
    if east_span > 2.0:
        axes[0].set_aspect("equal", adjustable="datalim")
    else:
        axes[0].set_ylim(-2.0, 2.0)
    axes[0].legend(frameon=False)
    axes[1].plot(solver[:, 0], solver[:, 2], color="#1f4b99", label="solver", linewidth=2.2)
    axes[1].plot(reference[:, 0], reference[:, 2], linestyle="none", marker="o", markevery=mark,
                 color="#c45500", label="reference", markersize=5)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("north (m)")
    axes[1].set_ylabel("depth (m)")
    axes[1].set_title("elevation")
    axes[1].legend(frameon=False)
    current = case.current_east_m_s
    figure.suptitle(f"{case.name}: {case.length_m:.0f} m payout, eastward current {current:.3f} m/s")
    note = (
        f"gland force solver [{gland[0]:.2f}, {gland[1]:.2f}, {gland[2]:.2f}] N"
        f"\nreference [{force[0]:.2f}, {force[1]:.2f}, {force[2]:.2f}] N"
    )
    figure.text(0.01, 0.01, note, fontsize=8, family="monospace")
    figure.tight_layout(rect=(0.0, 0.08, 1.0, 0.94))
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{case.name}.png"
    figure.savefig(path, dpi=120)
    plt.close(figure)
    print(path)


def main() -> None:
    params = TetherParams()
    for case in CALIBRATION_CASES:
        reference, force = _reference(case, params)
        seconds = 25.0 if case.length_m > 60.0 else 20.0
        tether = settle_on_curve(case, reference, seconds)
        bow = float(tether.x[:, 1].max())
        sag = case.depth_m - float(tether.x[:, 2].min())
        load = float(np.linalg.norm(tether.force_on_rov))
        print(
            f"{case.name}: sag {sag:.3f} m, east bow {bow:.3f} m, "
            f"|F| {load:.3f} N, F {np.array2string(tether.force_on_rov, precision=3)}"
        )
        _draw(case, reference, force, tether)


if __name__ == "__main__":
    main()
