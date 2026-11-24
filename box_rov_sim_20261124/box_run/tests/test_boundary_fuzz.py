"""Boundary / degenerate-input fuzz tests for the public simulation APIs.

Hand-rolled parametrized cases (hypothesis is not installed in this env).
Every test is deterministic and guards all loops against hanging. These
exercise extreme / degenerate inputs against the public surfaces of:
physics.py, tether.py, b2b_roster.py, input_shaping.py.
"""
import math
import unittest

import numpy as np

from rov01sim.physics import Vehicle
from rov01sim.tether import Tether, TetherParams
from rov01sim.world import World
from rov01sim import input_shaping as ishape
from rov01sim.b2b_roster import TraineeSessionRecord, CohortRosterManager


# ───────────────────────── input_shaping.py ─────────────────────────
class InputShapingBoundaryTests(unittest.TestCase):
    BAD = [float("nan"), float("inf"), float("-inf"), None, "x", True, False]
    EXTREME = [-1e9, -2.0, -1.0, 0.0, 1.0, 2.0, 1e9]

    def test_radial_output_always_bounded(self):
        for x in self.EXTREME + self.BAD:
            for y in self.EXTREME + self.BAD:
                ox, oy = ishape.radial_deadzone_expo(x, y)
                self.assertTrue(math.isfinite(ox) and math.isfinite(oy))
                self.assertLessEqual(abs(ox), 1.0 + 1e-9)
                self.assertLessEqual(abs(oy), 1.0 + 1e-9)

    def test_params_out_of_range_are_sanitized(self):
        for dz in self.BAD + [-5.0, 0.0, 99.0]:
            for ex in self.BAD + [-5.0, 0.0, 99.0]:
                ox, oy = ishape.radial_deadzone_expo(0.5, 0.5, dz, ex)
                self.assertTrue(math.isfinite(ox) and math.isfinite(oy))

    def test_deadzone_zeros_small_input(self):
        ox, oy = ishape.radial_deadzone_expo(0.01, 0.0, deadzone=0.1)
        self.assertEqual((ox, oy), (0.0, 0.0))

    def test_6dof_handles_junk_rosters(self):
        for raw in [None, {}, "nope", [1, 2, 3], {"surge": float("nan"), "yaw": 1e9}]:
            out = ishape.shape_gamepad_6dof(raw)
            self.assertEqual(set(out), {"surge", "sway", "heave", "roll", "pitch", "yaw"})
            for v in out.values():
                self.assertTrue(math.isfinite(v) and abs(v) <= 1.0 + 1e-9)


# ───────────────────────────── physics.py ───────────────────────────
class PhysicsBoundaryTests(unittest.TestCase):
    def _veh(self):
        return Vehicle()

    def test_zero_dt_is_noop(self):
        v = self._veh()
        before = v.s.pos.copy()
        v.step(0.0, np.zeros(len(v.thrusters)))
        np.testing.assert_array_equal(v.s.pos, before)

    def test_negative_and_nonfinite_dt_raise(self):
        v = self._veh()
        for dt in (-1.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                v.step(dt, np.zeros(len(v.thrusters)))

    def test_nonfinite_commands_raise_and_do_not_mutate(self):
        v = self._veh()
        before = v.s.pos.copy()
        cmd = np.zeros(len(v.thrusters))
        cmd[0] = float("nan")
        with self.assertRaises(ValueError):
            v.step(0.01, cmd)
        np.testing.assert_array_equal(v.s.pos, before)

    def test_wrong_shape_command_raises(self):
        v = self._veh()
        with self.assertRaises(ValueError):
            v.step(0.01, np.zeros(len(v.thrusters) + 3))

    def test_bad_extra_wrench_raises(self):
        v = self._veh()
        with self.assertRaises(ValueError):
            v.step(0.01, np.zeros(len(v.thrusters)), extra_wrench=np.zeros(5))
        with self.assertRaises(ValueError):
            v.step(0.01, np.zeros(len(v.thrusters)),
                   extra_wrench=np.array([float("inf")] * 6))

    def test_huge_dt_either_subdivides_or_raises(self):
        # Large dt should either resolve to a finite state (subdivided) or raise
        # the documented "too many substeps" guard -- never hang or go non-finite.
        for dt in (1.0, 50.0, 1e4):
            v = self._veh()
            try:
                v.step(dt, np.full(len(v.thrusters), 1.0))
            except ValueError:
                continue
            self.assertTrue(np.all(np.isfinite(v.s.pos)))
            self.assertTrue(np.all(np.isfinite(v.s.vel)))

    def test_full_throttle_many_steps_stays_finite(self):
        v = self._veh()
        cmd = np.full(len(v.thrusters), 1.0)
        for _ in range(500):  # guarded, fixed count
            v.step(0.02, cmd)
        self.assertTrue(np.all(np.isfinite(v.s.pos)))
        self.assertTrue(np.all(np.isfinite(v.s.q)))
        self.assertAlmostEqual(float(np.linalg.norm(v.s.q)), 1.0, places=5)


# ───────────────────────────── tether.py ────────────────────────────
class TetherBoundaryTests(unittest.TestCase):
    def _cable(self, length=8.0, **kw):
        world = World(20)
        world.current.turbulence = 0
        p = TetherParams(accelerated=False, **kw)
        c = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                   length=length, params=p, gland_body=np.zeros(3))
        c.auto_payout = False
        return c

    def test_zero_and_negative_dt_raise(self):
        c = self._cable()
        rov_q = np.array([1., 0., 0., 0.])
        for dt in (0.0, -0.01, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                c.step(dt, 0.0, np.array([8., 0., 5.]), rov_q, np.zeros(3))

    def test_zero_length_is_clamped(self):
        # Constructor clamps length to a >=2.0 minimum; must not blow up.
        c = self._cable(length=0.0)
        self.assertGreaterEqual(c.length, 2.0)
        c.step(0.01, 0.0, np.array([8., 0., 5.]), np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertTrue(np.all(np.isfinite(c.x)))

    def test_payout_nonfinite_raises(self):
        c = self._cable()
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                c.payout(bad)

    def test_payout_clamped_to_bounds(self):
        c = self._cable()
        c.payout(1e9)
        self.assertLessEqual(c.length, c.p.max_length)
        c.payout(-1e9)
        self.assertGreaterEqual(c.length, 2.0)

    def test_absurd_current_rolls_back_not_poisons(self):
        c = self._cable()
        c.world.current.turbulence = 0
        rov_q = np.array([1., 0., 0., 0.])
        # First take a known-good state, then shove an enormous ROV velocity in
        # (quadratic drag can overflow); state must remain finite afterward.
        c.step(0.01, 0.0, np.array([8., 0., 5.]), rov_q, np.zeros(3))
        good = c.x.copy()
        c.step(0.01, 0.0, np.array([8., 0., 5.]), rov_q, np.full(3, 1e12))
        self.assertTrue(np.all(np.isfinite(c.x)))
        # either advanced finitely or rolled back to the snapshot
        self.assertTrue(np.all(np.isfinite(c.v)))
        _ = good

    def test_wrench_return_is_finite_6vector(self):
        c = self._cable()
        w = c.step(0.01, 0.0, np.array([8.05, 0., 5.]), np.array([1., 0., 0., 0.]),
                   np.array([0.1, 0., 0.]))
        self.assertEqual(np.asarray(w).shape, (6,))
        self.assertTrue(np.all(np.isfinite(w)))


# ──────────────────────────── b2b_roster.py ─────────────────────────
class RosterBoundaryTests(unittest.TestCase):
    def test_nonfinite_numeric_fields_sanitized(self):
        r = TraineeSessionRecord(
            "T001",
            hull_integrity_pct=float("nan"),
            ut_max_tilt_deg=float("inf"),
            elapsed_sec=float("-inf"),
            total_score=float("nan"),
            ut_avg_thickness_error_mm=float("inf"),
            tether_snag_count=-5,
            ut_checkpoints_completed=999,
        )
        self.assertTrue(0.0 <= r.hull_integrity_pct <= 100.0)
        self.assertTrue(0.0 <= r.ut_max_tilt_deg <= 180.0)
        self.assertGreaterEqual(r.elapsed_sec, 0.0)
        self.assertTrue(0.0 <= r.total_score <= 100.0)
        self.assertGreaterEqual(r.tether_snag_count, 0)
        self.assertTrue(0 <= r.ut_checkpoints_completed <= 10)

    def test_empty_and_junk_ids(self):
        for tid in ("", "   ", "X"):
            r = TraineeSessionRecord(tid)
            self.assertIsInstance(r.trainee_id, str)
            self.assertTrue(r.verification_hash)

    def test_roundtrip_signature_stable(self):
        r = TraineeSessionRecord("T42", total_score=95.0, hull_integrity_pct=100.0)
        d = r.to_dict()
        r2 = TraineeSessionRecord.from_dict(d)
        self.assertEqual(r.verification_hash, r2.verification_hash)

    def test_empty_roster_summary(self):
        mgr = CohortRosterManager()
        summary = mgr.compute_cohort_summary()
        self.assertIsInstance(summary, dict)

    def test_hull_zero_forces_fail(self):
        r = TraineeSessionRecord("T0", hull_integrity_pct=0.0, total_score=100.0)
        self.assertEqual(r.total_score, 0.0)
        self.assertEqual(r.grade, "F")


if __name__ == "__main__":
    unittest.main()
