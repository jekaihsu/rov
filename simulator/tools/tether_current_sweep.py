"""Plot fixed-end cable shape and tension, and time the full warm Tether.step at 100 Hz."""
from pathlib import Path
import sys
from time import perf_counter_ns

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim.tether import TetherParams
from qysim.tether_reference import CableCase, IDENTITY, ends, settle_on_curve, steady_current_cable, upward_catenary


def main():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    params = TetherParams()
    for length in (60, 120):
        for speed in (0, 0.15, 0.3, 0.5):
            case = CableCase("sweep", length, 0.8 * length, 50., speed)
            curve, _ = (steady_current_cable if speed else upward_catenary)(case, params)
            cable = settle_on_curve(case, curve, 20)
            gland = ends(case)[1]
            zero = np.zeros(3)
            times = []
            for i in range(500):
                start = perf_counter_ns()
                cable.step(0.01, 20 + 0.01 * i, gland, IDENTITY, zero)
                times.append((perf_counter_ns() - start) / 1e6)
            label = f"{speed:g} m/s"
            print(f"{length} m, {label}: {np.linalg.norm(cable.force_on_rov):.3f} N; "
                  f"step ms mean/p95/max {np.mean(times):.3f}/{np.percentile(times, 95):.3f}/{max(times):.3f}")
            if cable.broken or not np.isfinite(cable.x).all():
                raise ValueError("Cable failed in fixed-end sweep")
            if length == 60:
                axes[0].plot(cable.x[:, 0], cable.x[:, 1], label=label)
                axes[1].plot(cable.x[:, 0], cable.x[:, 2])
                arc = np.cumsum(cable.l0) - cable.l0 / 2
                axes[2].plot(arc, cable._seg_tension)
    axes[0].legend()
    axes[0].set(xlabel="North (m)", ylabel="East (m)", title="Plan")
    axes[1].set(xlabel="North (m)", ylabel="Depth (m)", title="Elevation")
    axes[1].invert_yaxis()
    axes[2].set(xlabel="Distance from reel (m)", ylabel="Axial tension (N)", title="Load along cable")
    fig.suptitle("60 m deployed across a 48 m span in uniform crossflow")
    fig.savefig(Path(__file__).resolve().parents[2] / "docs/design/tether-calibration/current-sweep.png", dpi=140)


if __name__ == "__main__":
    main()
