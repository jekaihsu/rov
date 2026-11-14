# Three-player physics timing — 2026-10-02

The reproducible runner is `simulator/tools/benchmark_room.py`. It creates one shared coral-reef world, seed 42, with X1, BlueROV2 Heavy and Falcon, enables depth hold and applies the same fixed stick input. It warms 120 physics ticks, then times 600 ticks at a simulated 0.01 s step. These are backend measurements on the current development machine, excluding browser rendering, network transport, telemetry serialization and initial JIT compilation.

```powershell
python tools/benchmark_room.py --output output/performance/three-after-unprofiled.json --ticks 600
```

| Metric | Before | After |
| --- | ---: | ---: |
| Mean wall time per three-vehicle tick | 9.434 ms | 7.693 ms |
| Wall p95 | 13.536 ms | 10.310 ms |
| Mean process CPU time | 9.427 ms | 7.708 ms |
| Completed compiled tether batches | 99.39% | 99.39% |

The observed mean reduction is 18.5%. Runs are sequential measurements on a shared workstation, not a hardware-independent performance guarantee. The p95 still exceeds the 10 ms budget, so this is not a claim of sustained 100 Hz under all loads.

An initial cProfile run (180 ticks, with profiler overhead) attributed about 32% of cumulative room time to tether stepping and 19% to vehicle physics. Small-vector `numpy.cross` calls repeatedly paid generic axis/broadcast setup costs. The implemented optimization specializes cross products to single 3-vectors and expands quaternion-vector multiplication into its algebraically equivalent expression. It also avoids two temporary four-vectors in each rotation. No physics coefficients, integration steps, tether substeps, contact geometry or cache tolerances changed.

The final three vehicle positions after 720 simulated ticks agree with the pre-optimization baseline within 5e-15 m. A new test compares 100 randomized vector/rotation inputs to independent NumPy and quaternion-product references, including non-unit quaternions. Existing physical-invariant and tether-equivalence tests cover the wider behavior.

Validation: `python -m unittest tests.test_inertial_dynamics tests.test_vehicles tests.test_core tests.test_ecology tests.test_operations` passed all 58 tests in 148.596 seconds.

Remaining significant work is current-field/terrain sampling and collision-distance evaluation in world/ecology code; these were outside this change's file ownership. The compiled tether batch already succeeds on almost all ticks in this run. Reducing tether substeps or relaxing contact tolerances was deliberately unnecessary for the measured improvement.

Raw timing records are stored under `simulator/output/performance/`: `three-before.json` (profiled), `three-before-unprofiled.json`, and `three-after-unprofiled.json`.


## T19 — 2026-11-14

Base: `87b1ff9` (origin/main). Linux x86_64 cloud VM, 5 visible AMD EPYC 9V74 cores,
Python 3.12, NumPy 2.3.5, optional Numba 0.68.1. This is **not a four-core laptop acceptance test**.
Before/after runs were sequential, without concurrent unit tests or profiler processes.
Seed 42, fixed 0.01 s steps, 120 warmup + 600 measured ticks; same stick/depth-hold input.
Initial JIT compilation, browser rendering, network and serialization are excluded from physics times.
Timings are single runs on shared hardware, not statistical confidence intervals.

The only production change specializes single-point current queries. It uses the existing layer
interpolation and gust equations, clips depth exactly as the batch path does, and evaluates the
same shear terms without batch masks and temporary Nx3 arrays. No coefficients, substeps, cache
tolerances, physics parameters or vehicle definitions changed. Floating point evaluation may
round differently; the scalar/batch comparison uses rtol/atol 1e-14.

### Physics measurements

| Scenario | Vehicles | Before mean ms | After mean ms | Before p95 ms | After p95 ms | Before RT | After RT |
|---|---:|---:|---:|---:|---:|---:|---:|
| coral_reef | 1 | 1.475 | 1.098 | 2.391 | 1.640 | 6.78 | 9.11 |
| coral_reef | 2 | 2.079 | 1.870 | 2.801 | 2.475 | 4.81 | 5.35 |
| coral_reef | 3 | 2.994 | 2.562 | 3.733 | 3.201 | 3.34 | 3.90 |
| harbor_inspection | 1 | 1.184 | 0.937 | 1.676 | 1.256 | 8.44 | 10.68 |
| harbor_inspection | 2 | 1.879 | 1.864 | 2.540 | 2.517 | 5.32 | 5.37 |
| harbor_inspection | 3 | 2.800 | 2.374 | 3.799 | 3.171 | 3.57 | 4.21 |
| wreck_survey | 1 | 0.821 | 0.677 | 1.311 | 1.058 | 12.17 | 14.78 |
| wreck_survey | 2 | 1.593 | 1.168 | 2.195 | 1.608 | 6.28 | 8.56 |
| wreck_survey | 3 | 1.838 | 2.078 | 2.383 | 3.562 | 5.44 | 4.81 |
| tether_untangle | 1 | 1.015 | 0.948 | 1.430 | 1.344 | 9.85 | 10.54 |
| tether_untangle | 2 | 1.673 | 1.760 | 2.110 | 2.351 | 5.98 | 5.68 |
| tether_untangle | 3 | 2.631 | 2.220 | 3.388 | 2.788 | 3.80 | 4.50 |

Numba disabled, 3 vehicles, tether_untangle: mean 5.109 → 5.229 ms; p95 5.829 → 6.569 ms; RT 1.96 → 1.91.

### Subsystem profiles

Separate cProfile runs (120 warmup + 180 measured ticks); **overlapping cumulative ms per tick**, not additive exclusive budgets.
Tether includes current and distance queries. Collision here is hull contact only; terrain/SDF
queries also occur inside tether and world updates. Current here is batch sampling only: before
optimization it includes scalar callers; afterward scalar callers use the specialized path.
Consequently that column is a call-path diagnostic, not the total current cost reduction.
Mission excludes campaign/operations. Serialization and transport are measured separately below.
Each cell is before → after.

| Scenario | Vehicles | Rigid body | Tether | Hull collision | Batch current | Mission |
|---|---:|---:|---:|---:|---:|---:|
| coral_reef | 1 | 0.115 → 0.115 | 0.509 → 0.506 | 0.148 → 0.144 | 0.423 → 0.087 | 0.015 → 0.013 |
| coral_reef | 2 | 0.234 → 0.229 | 0.957 → 1.002 | 0.272 → 0.290 | 0.570 → 0.175 | 0.013 → 0.013 |
| coral_reef | 3 | 0.347 → 0.342 | 1.548 → 1.529 | 0.437 → 0.423 | 0.768 → 0.255 | 0.014 → 0.014 |
| harbor_inspection | 1 | 0.126 → 0.122 | 0.516 → 0.499 | 0.134 → 0.124 | 0.439 → 0.089 | 0.013 → 0.012 |
| harbor_inspection | 2 | 0.220 → 0.215 | 1.013 → 1.000 | 0.240 → 0.226 | 0.583 → 0.172 | 0.013 → 0.013 |
| harbor_inspection | 3 | 0.335 → 0.346 | 1.609 → 1.698 | 0.351 → 0.371 | 0.717 → 0.256 | 0.013 → 0.014 |
| wreck_survey | 1 | 0.110 → 0.123 | 0.262 → 0.288 | 0.084 → 0.094 | 0.440 → 0.095 | 0.013 → 0.011 |
| wreck_survey | 2 | 0.212 → 0.217 | 0.493 → 0.508 | 0.160 → 0.166 | 0.546 → 0.165 | 0.019 → 0.020 |
| wreck_survey | 3 | 0.347 → 0.340 | 0.899 → 0.894 | 0.267 → 0.259 | 0.771 → 0.264 | 0.022 → 0.022 |
| tether_untangle | 1 | 0.115 → 0.109 | 0.407 → 0.428 | 0.090 → 0.094 | 0.407 → 0.100 | 0.005 → 0.005 |
| tether_untangle | 2 | 0.233 → 0.237 | 1.177 → 1.182 | 0.186 → 0.396 | 0.611 → 0.176 | 0.006 → 0.006 |
| tether_untangle | 3 | 0.359 → 0.381 | 2.067 → 2.127 | 0.284 → 0.287 | 0.768 → 0.273 | 0.007 → 0.007 |

### Consistency and limitations

Before changing production code, captured two seed-42 three-vehicle trajectories (coral reef and
harbor), 3000 ticks each (30 simulated seconds), checking all three vehicles every simulated second.
The committed fixture comes from the original production implementation. Regression bounds:
Euclidean position error ≤ 1 mm, quaternion sign-invariant chord distance ≤ 1e-6, maximum cable
tension error ≤ 0.5% (1e-9 N absolute floor at zero). Both trajectories pass unchanged bounds.
An independent batch-reference test additionally covers random currents and depth boundaries.

The four existing scenario deployments do **not** establish the globally heaviest cable workload,
a long deployed cable under continuous contact, or sustained laptop performance. No physical
parameters were adjusted to manufacture a heavier or easier workload. The ≥1.5 compiled / ≥1.0
fallback target remains unverified for that acceptance workload. Remaining hot paths are tether
contact/terrain distance evaluation and current batch sampling; a representative long-cable laptop
trace is needed before choosing a more invasive optimization. Existing scenarios may break cables;
the runner now reports final cable length, node count and broken status to expose this limitation.
No claim of sustained 100 Hz for every deployment is made.

### Reproduction

Run the following in `simulator` for **each revision**, with no other benchmark/test process running.
For the baseline, copy the expanded measurement tools into a separate origin/main worktree;
leave its qysim production files untouched.

```bash
for scenario in coral_reef harbor_inspection wreck_survey tether_untangle; do
  for players in 1 2 3; do
    python tools/benchmark_room.py --scenario "$scenario" --players "$players" --ticks 600 \
      --output "/tmp/$scenario-$players.json"
    python tools/benchmark_room.py --scenario "$scenario" --players "$players" --ticks 180 --profile \
      --output "/tmp/$scenario-$players-profile.json"
  done
done
python tools/benchmark_room.py --scenario tether_untangle --ticks 600 --no-numba --output /tmp/fallback.json
PYTHONPATH=. python tools/profile_network.py
python -m unittest tests.test_current_scalar tests.test_performance_regression
python -m unittest discover -s tests
```

Validation output:

```text
Ran 2 tests in 17.613s
OK
Ran 133 tests in 62.430s
OK
```

`docs/reference/own/` referenced by AGENTS.md is absent at this revision. No real-vehicle
parameter or control assumptions were introduced. CI quota is exhausted; local results above
are supplied for review and the PR remains draft.

### Network / serialization

Server code, payload fields, compact JSON encoding and configured 30 Hz state frequency are
unchanged. The existing shared fleet cache is retained; no additional wire optimization was justified
by this narrow current-query change. The tool asserts decoded semantic equality with full JSON for
every sample and reports both synchronized and staggered client schedules. Three clients:

| Paint marks | Compact bytes before / after | Bytes/s before / after | Payload ms before / after | Local transport ms before / after |
|---|---:|---:|---:|---:|
| 0_paint_marks | 61497 / 61497 | 1844910 / 1844910 | 0.468 / 0.477 | 0.101 / 0.104 |
| 128_paint_marks | 206097 / 206097 | 6182910 / 6182910 | 1.041 / 1.070 | 0.293 / 0.382 |

Local transport uses a socketpair and receiving thread; it excludes WebSocket framing, WAN delay,
and production sender scheduling. Serialization timings exclude that transport. Observed timing
variation between identical server revisions is measurement noise, not an optimization claim.
