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
