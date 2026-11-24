"""Adversarial Red-Team Stress Audit (/interrogate) for ROV-01 Simulator (#80).

Covers all 4 mandatory red-team attack surfaces plus Worker 4 ACT-01..04 invariants:
  - Attack 1: NaN / Inf / Huge Float / Malformed Joystick Injection
  - Attack 2: Multi-Thruster Singularity & All 2^6 = 64 Fault Mask Fuzzing
  - Attack 3: 2,000-Step Randomized UT Gauging & Autopilot State Machine Invariant Fuzzing (M_06, M_07, M_08)
  - Attack 4: Collision Impulse & Hull Score Underflow/Overflow & Cooldown Fuzzing
"""
from __future__ import annotations

import math
import random
import unittest
import numpy as np

from rov01sim.engine import Simulator
from rov01sim.input_shaping import (
    axis_deadzone_expo,
    expo_curve,
    radial_deadzone_expo,
    shape_gamepad_6dof,
    shape_stick_2d,
)
from rov01sim.physics import Vehicle
from rov01sim.wave1 import (
    Wave1Manager,
    allocate_6thruster_with_fault_compensation,
    apply_deadzone_and_expo,
    shape_6dof_gamepad,
)


class TestAttack1NanInfHugeFloatInjection(unittest.TestCase):
    """Attack 1: NaN / Inf / Huge Float / Malformed Joystick Injection."""

    MALFORMED_SCALARS = [
        float("nan"),
        float("inf"),
        float("-inf"),
        1e308,
        -1e308,
        1e19,
        -1e19,
        None,
        "nan",
        "inf",
        "invalid",
        True,
        False,
        [],
        {},
    ]

    def test_input_shaping_functions_reject_nan_inf_and_malformed(self):
        for bad in self.MALFORMED_SCALARS:
            val_expo = expo_curve(bad, bad)
            self.assertTrue(math.isfinite(val_expo), f"expo_curve leaked non-finite for {bad!r}")
            self.assertGreaterEqual(val_expo, 0.0)
            self.assertLessEqual(val_expo, 1.0)

            val_axis = axis_deadzone_expo(bad, deadzone=bad, expo=bad)
            self.assertTrue(math.isfinite(val_axis), f"axis_deadzone_expo leaked non-finite for {bad!r}")
            self.assertGreaterEqual(val_axis, -1.0)
            self.assertLessEqual(val_axis, 1.0)

            val_w1_axis = apply_deadzone_and_expo(bad, deadzone=bad, expo=bad)
            self.assertTrue(math.isfinite(val_w1_axis))
            self.assertGreaterEqual(val_w1_axis, -1.0)
            self.assertLessEqual(val_w1_axis, 1.0)

            sx, sy = radial_deadzone_expo(bad, bad, deadzone=bad, expo=bad)
            self.assertTrue(math.isfinite(sx) and math.isfinite(sy))
            self.assertLessEqual(math.hypot(sx, sy), 1.0 + 1e-6)

            s2x, s2y = shape_stick_2d(bad, bad, deadzone=bad, expo=bad)
            self.assertTrue(math.isfinite(s2x) and math.isfinite(s2y))
            self.assertGreaterEqual(s2x, -1.0)
            self.assertLessEqual(s2x, 1.0)
            self.assertGreaterEqual(s2y, -1.0)
            self.assertLessEqual(s2y, 1.0)

            for fn in (shape_gamepad_6dof, shape_6dof_gamepad):
                shaped6 = fn(
                    {
                        "surge": bad,
                        "sway": bad,
                        "heave": bad,
                        "roll": bad,
                        "pitch": bad,
                        "yaw": bad,
                        "deadzone": bad,
                        "expo": bad,
                    },
                    deadzone=bad,
                    expo=bad,
                )
                for axis in ("surge", "sway", "heave", "roll", "pitch", "yaw"):
                    v = shaped6[axis]
                    self.assertTrue(math.isfinite(v), f"Axis {axis} non-finite for {bad!r}: {v}")
                    self.assertGreaterEqual(v, -1.0)
                    self.assertLessEqual(v, 1.0)

    def test_wave1_engine_step_zero_nan_inf_leak_into_pwm_pid_or_hull(self):
        sim = Simulator("mission_1_pool", seed=7, model_id="rov01")
        sim.rc_physical.rc_lock = 0
        w1 = sim.wave1
        w1.set_depth_hold(True, target_depth_m=2.5)
        w1.set_heading_hold(True, target_heading_deg=90.0)

        adversarial_payloads = [
            {"surge": float("nan"), "sway": float("inf"), "heave": float("-inf"), "yaw": 1e308, "roll": -1e308, "pitch": float("nan"), "deadzone": float("nan"), "expo": float("inf")},
            {"surge": 1e308, "sway": -1e308, "heave": 1e308, "yaw": float("nan"), "roll": float("inf"), "pitch": float("-inf"), "deadzone": -999, "expo": 999},
            {"surge": None, "sway": "nan", "heave": True, "yaw": [], "roll": {}, "pitch": "inf", "deadzone": None, "expo": "bad"},
        ]

        for payload in adversarial_payloads:
            shaped = w1.apply_gamepad_6dof(payload, deadzone=payload["deadzone"], expo=payload["expo"])
            for k, v in shaped.items():
                self.assertTrue(math.isfinite(v), f"apply_gamepad_6dof leaked {v} on {k}")
                self.assertGreaterEqual(v, -1.0)
                self.assertLessEqual(v, 1.0)

            # Corrupt internal PID state & targets intentionally before step() to verify self-healing
            w1._depth_pid_i = float("nan")
            w1._heading_pid_i = float("inf")
            w1.target_depth_m = float("nan")
            w1.target_heading_deg = float("-inf")

            cmd_override = w1.step(float("nan"))
            if cmd_override is not None:
                for k, v in cmd_override.items():
                    self.assertTrue(math.isfinite(v), f"w1.step override {k} non-finite: {v}")

            sim.step(0.02)

            for idx, thrust_n in enumerate(sim.vehicle.s.thrust):
                self.assertTrue(math.isfinite(float(thrust_n)), f"Thruster T{idx+1} thrust non-finite: {thrust_n}")

            self.assertTrue(math.isfinite(w1.hull_integrity))
            self.assertGreaterEqual(w1.hull_integrity, 0.0)
            self.assertLessEqual(w1.hull_integrity, 100.0)
            sop = w1.compute_sop_evaluation()
            self.assertTrue(math.isfinite(sop["total_score"]))
            self.assertGreaterEqual(sop["total_score"], 0.0)
            self.assertLessEqual(sop["total_score"], 100.0)
            self.assertTrue(math.isfinite(w1._depth_pid_i))
            self.assertTrue(math.isfinite(w1._heading_pid_i))
            self.assertTrue(math.isfinite(w1.depth_hold_error_m))
            self.assertTrue(math.isfinite(w1.heading_hold_error_deg))

            # Verify RC PWM channels remain strictly in [1000, 2000] and finite
            for ch_name in ("left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave"):
                pwm = getattr(sim.rc_physical, ch_name)
                self.assertTrue(math.isfinite(pwm), f"RC channel {ch_name} non-finite: {pwm}")
                self.assertGreaterEqual(pwm, 1000)
                self.assertLessEqual(pwm, 2000)


class TestAttack2MultiThrusterSingularityFuzzing(unittest.TestCase):
    """Attack 2: Fuzz all 2^6 = 64 combinations of thruster fault masks."""

    def test_all_64_fault_masks_never_raise_and_stay_bounded(self):
        v = Vehicle(model_id="rov01")
        test_wrenches = [
            np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            np.array([150.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            np.array([0.0, -150.0, 0.0, 0.0, 0.0, 0.0]),
            np.array([0.0, 0.0, 200.0, 0.0, 0.0, 0.0]),
            np.array([120.0, -95.0, 140.0, 15.0, -20.0, 35.0]),
            np.array([1e9, -1e9, 1e9, -1e9, 1e9, -1e9]),
            np.array([float("nan"), float("inf"), float("-inf"), 1e308, -1e308, 0.0]),
        ]
        for mask_int in range(64):
            health_mask = np.array([1.0 if (mask_int & (1 << i)) else 0.0 for i in range(6)], dtype=float)
            for w in test_wrenches:
                for dmp in (0.05, 0.0, -0.1, float("nan"), float("inf")):
                    u = allocate_6thruster_with_fault_compensation(v.B, v.B_pinv, w, health=health_mask, damping=dmp)
                    self.assertEqual(u.shape, (6,))
                    for i, val in enumerate(u):
                        fval = float(val)
                        self.assertTrue(math.isfinite(fval), f"mask={health_mask} wrench={w} produced non-finite u[{i}]={fval}")
                        self.assertGreaterEqual(fval, -1.0 - 1e-9)
                        self.assertLessEqual(fval, 1.0 + 1e-9)
                        if health_mask[i] == 0.0:
                            self.assertEqual(fval, 0.0, f"Faulted thruster T{i+1} must be 0.0, got {fval}")


class TestAttack3UtAndAutopilotStateMachineInvariantFuzzing(unittest.TestCase):
    """Attack 3: 2,000 randomized step sequences fuzzing UT Gauging & Autopilot TLA+ invariants."""

    def test_2000_randomized_steps_preserve_m06_m07_m08_invariants(self):
        rng = random.Random(20261025)
        sim = Simulator("mission_2_hull_ut", seed=42, model_id="rov01")
        w1 = sim.wave1

        invariant_breaches = []

        for step_idx in range(2000):
            action = rng.choice(
                [
                    "toggle_depth_hold",
                    "toggle_heading_hold",
                    "inject_snag",
                    "resolve_snag",
                    "attempt_emergency_surface",
                    "start_ut",
                    "attempt_direct_sample",
                    "step_sim",
                    "reset_sim",
                ]
            )

            if action == "toggle_depth_hold":
                w1.set_depth_hold(rng.choice([True, False]), target_depth_m=rng.uniform(1.0, 20.0))
            elif action == "toggle_heading_hold":
                w1.set_heading_hold(rng.choice([True, False]), target_heading_deg=rng.uniform(0.0, 360.0))
            elif action == "inject_snag":
                w1.inject_tether_snag()
            elif action == "resolve_snag":
                w1.resolve_tether_snag()
            elif action == "attempt_emergency_surface":
                res = w1.trigger_emergency_surface(rng.choice([True, False]))
                if w1._is_tether_entangled() and w1.emergency_surface_active:
                    invariant_breaches.append(
                        f"step {step_idx}: Inv_NoEmergencySurfaceWhenEntangled breached on trigger ({res['mode_state']})"
                    )
            elif action == "start_ut":
                w1.start_ut_coupling(
                    "UT-01",
                    tilt_deg=rng.choice([rng.uniform(0.2, 2.8), rng.uniform(3.2, 15.0)]),
                    distance_m=rng.choice([rng.uniform(0.2, 0.6), rng.uniform(0.8, 3.0)]),
                )
            elif action == "attempt_direct_sample":
                cp0 = w1.ut_checkpoints[0]
                was_completed = cp0.completed
                probe_tilt = rng.choice([rng.uniform(0.2, 2.8), rng.uniform(3.2, 18.0)])
                res = w1.sample_ut_checkpoint("UT-01", tilt_deg=probe_tilt)
                if not was_completed and cp0.completed:
                    if (
                        not w1.depth_hold_active
                        or w1._is_tether_entangled()
                        or w1.emergency_surface_active
                        or w1.mission_aborted
                        or probe_tilt > 3.0
                        or w1._manual_6dof_forced
                    ):
                        invariant_breaches.append(
                            f"step {step_idx}: Inv_UtSampleRequiresCoupledAndStable breached via sample_ut_checkpoint "
                            f"(depth_hold={w1.depth_hold_active}, tilt={probe_tilt:.2f}, entangled={w1._is_tether_entangled()})"
                        )
            elif action == "reset_sim":
                sim.wave1 = Wave1Manager(sim)
                w1 = sim.wave1

            # Advance wave1 step and check all M_06 / M_07 / M_08 invariants
            cp0 = w1.ut_checkpoints[0]
            was_cp0_completed = cp0.completed
            w1.step(0.25)

            # 1) Inv_NoEmergencySurfaceWhenEntangled
            if w1._is_tether_entangled() and (w1.emergency_surface_active or w1.mode_state == "emergency_surface"):
                invariant_breaches.append(
                    f"step {step_idx}: Inv_NoEmergencySurfaceWhenEntangled violated after step()"
                )

            # 2) Inv_UtSampleRequiresCoupledAndStable
            if not was_cp0_completed and cp0.completed:
                if (
                    not w1.depth_hold_active
                    or w1.ut_tilt_deg > 3.0
                    or w1._is_tether_entangled()
                    or w1.emergency_surface_active
                    or w1.mission_aborted
                ):
                    invariant_breaches.append(
                        f"step {step_idx}: Inv_UtSampleRequiresCoupledAndStable violated on step transition "
                        f"(depth_hold={w1.depth_hold_active}, tilt={w1.ut_tilt_deg:.2f}, entangled={w1._is_tether_entangled()})"
                    )

            # 3) Inv_ZeroHullForcesAbort
            if w1.hull_integrity <= 0.0:
                if not w1.mission_aborted or sim.rc_physical.rc_lock != 1 or np.any(np.abs(sim.vehicle.s.thrust) > 1e-9):
                    invariant_breaches.append(
                        f"step {step_idx}: Inv_ZeroHullForcesAbort violated (aborted={w1.mission_aborted}, rc_lock={sim.rc_physical.rc_lock})"
                    )

        self.assertEqual(invariant_breaches, [], f"Found invariant breaches: {invariant_breaches[:5]}")


class TestAttack4CollisionImpulseAndHullScoreBounds(unittest.TestCase):
    """Attack 4: Collision Impulse & Hull Score Underflow/Overflow & Cooldown Window."""

    def test_negative_massive_and_rapid_micro_collisions_preserve_bounds(self):
        sim = Simulator("mission_2_hull_ut", seed=42, model_id="rov01")
        w1 = sim.wave1

        # 1. Moderate collision reduces hull below 100.0
        w1.inject_collision_impulse(1.0, zone="front")
        hull_after_hit = w1.hull_integrity
        self.assertLess(hull_after_hit, 100.0)
        self.assertGreater(hull_after_hit, 0.0)

        # 2. Negative impulses, NaN, and -Inf must NEVER heal hull_integrity above hull_after_hit
        for neg_imp in (-0.5, -10.0, -1e9, float("-inf"), float("nan")):
            w1.inject_collision_impulse(neg_imp, zone="front")
            self.assertEqual(
                w1.hull_integrity,
                hull_after_hit,
                f"Negative/NaN impulse {neg_imp} mutated hull_integrity to {w1.hull_integrity}",
            )

        # 3. 50 rapid consecutive micro-collisions within the 0.25s cooldown window
        sim2 = Simulator("mission_2_hull_ut", seed=42, model_id="rov01")
        w2 = sim2.wave1
        for i in range(50):
            sim2.t = i * 0.002  # total 0.098s < 0.25s cooldown
            w2.inject_collision_impulse(0.20, zone="front")
        # Only the first micro-collision within the 0.25s window should have counted
        self.assertEqual(w2.collision_count, 1)
        self.assertGreater(w2.hull_integrity, 95.0)

        # 4. Massive 1e9 N*s impulse clamps hull_integrity to 0.0 and triggers Inv_ZeroHullForcesAbort
        w2.inject_collision_impulse(1e9, zone="front")
        self.assertEqual(w2.hull_integrity, 0.0)
        self.assertTrue(w2.mission_aborted)
        self.assertEqual(sim2.rc_physical.rc_lock, 1)
        self.assertTrue(np.allclose(sim2.vehicle.s.thrust, 0.0))

        sop = w2.compute_sop_evaluation()
        self.assertGreaterEqual(sop["total_score"], 0.0)
        self.assertLess(sop["total_score"], 60.0)
        self.assertEqual(sop["sop_cert_status"], "Failed_Retry")
        self.assertIn("F", sop["grade"])


if __name__ == "__main__":
    unittest.main()
