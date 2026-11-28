"""Compare each observable against the reviewed baseline and render headless reports."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REFERENCES = HERE / "curves"


def checkpoints(result):
    # Keep the native samples around startup, then 64 evenly spaced native ticks.
    indices = np.unique(np.r_[np.arange(min(20, len(result.rows))),
                              np.linspace(0, len(result.rows) - 1, 64).astype(int)])
    return result.rows[indices]


def write_csv(path, columns, rows):
    np.savetxt(path, rows, delimiter=",", header=",".join(columns), comments="", fmt="%.17g")


def check(result):
    config = json.loads((HERE / "bands.json").read_text(encoding="utf8"))
    spec = config["cases"][result.name]
    if set(spec) != set(result.metrics):
        raise ValueError(f"{result.name}: metric names differ from bands.json")
    failures = []
    for key, value in result.metrics.items():
        low, high = spec[key]
        if not low <= value <= high:
            failures.append(f"{key}={value:.8g} outside [{low}, {high}]")
    if result.name != "timing":
        ref = np.loadtxt(REFERENCES / (result.name + ".csv"), delimiter=",", skiprows=1)
        samples = checkpoints(result)
        np.testing.assert_array_equal(samples[:, 0], ref[:, 0])
        limits = config["curve_peak_fraction"] * np.max(abs(ref[:, 1:]), axis=0) + config["curve_abs_floor"]
        for col in np.flatnonzero((abs(samples[:, 1:] - ref[:, 1:]) > limits).any(axis=0)):
            failures.append(f"{result.columns[col + 1]} curve exceeds {limits[col]:.5g}")
    return failures


def render(result, out):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    write_csv(out / (result.name + ".csv"), result.columns, result.rows)
    ref = None
    if result.name != "timing":
        ref = np.loadtxt(REFERENCES / (result.name + ".csv"), delimiter=",", skiprows=1)
    has_analogue = result.columns[-1].startswith("analogue_")
    columns = result.columns[1:-1] if has_analogue else result.columns[1:]
    fig, axes = plt.subplots(len(columns), 1, squeeze=False, sharex=True,
                             figsize=(7, 2.2 * (len(columns)) + 1), layout="constrained")
    for index, (axis, label) in enumerate(zip(axes[:, 0], columns), 1):
        axis.plot(result.rows[:, 0], result.rows[:, index], lw=1.5, label="current")
        if ref is not None:
            axis.plot(ref[:, 0], ref[:, index], ".", ms=3, label="baseline")
        if has_analogue:
            axis.plot(result.rows[:, 0], result.rows[:, -1], "--", label="analogue (Q2 scalar model)")
        axis.set_ylabel(label)
        axis.grid(alpha=.2)
    axes[0, 0].set_title(result.name)
    axes[0, 0].legend()
    axes[-1, 0].set_xlabel("simulation time (s)")
    fig.savefig(out / (result.name + ".png"), dpi=120)
    plt.close(fig)
