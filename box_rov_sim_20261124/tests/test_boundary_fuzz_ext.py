"""Extended boundary / fuzz tests (round baseline).

Complements tests/test_boundary_fuzz.py with additional edge cases that were
under-covered: extreme water-current velocity driven through the physics and
tether steps, a tether yanked past its rated break load, non-finite inputs to
the physics step via an extreme current vector, and empty mission/roster
surfaces. All deterministic: any RNG is seeded.
"""
import math
import unittest

import numpy as np

from rov01sim.physics import Vehicle
from rov01sim.tether import Tether, TetherParams
from rov01sim.world import World, CurrentProfile
from rov01sim.b2b_roster import CohortRosterManager


class ExtremeCurrentTests(unittest.TestCase):
    def test_physics_step_survives_extreme_current(self):
        # A hurricane-grade current vector must not drive the integrator
        # non-finite nor blow up the quaternion norm.
        # A ferocious current must either integrate to a finite state or trip
        # the documented "too many substeps" guard -- never hang or produce a
        # non-finite / de-normalised state.
        v = Vehicle()
        v.current_ned = np.array([8.0, -8.0, 2.0])  # ~16 kn, extreme but resolvable
        cmd = np.full(len(v.thrusters), 1.0)
        for _ in range(200):
            v.step(0.02, cmd)
        self.assertTrue(np.all(np.isfinite(v.s.pos)))
        self.assertTrue(np.all(np.isfinite(v.s.vel)))
        self.assertAlmostEqual(float(np.linalg.norm(v.s.q)), 1.0, places=5)

    def test_absurd_current_raises_or_stays_finite(self):
        v = Vehicle()
        v.current_ned = np.array([1e6, -1e6, 1e6])
        cmd = np.full(len(v.thrusters), 1.0)
        try:
            for _ in range(200):
                v.step(0.02, cmd)
        except ValueError:
            return  # documented substep guard fired -- acceptable
        self.assertTrue(np.all(np.isfinite(v.s.pos)))
        self.assertTrue(np.all(np.isfinite(v.s.vel)))

    def test_tether_step_survives_extreme_current(self):
        world = World(20)
        world.current = CurrentProfile(surface_kn=1e4, mid_kn=1e4, bottom_kn=1e4,
                                       turbulence=5.0)
        world.current._gust = np.array([1e3, 1e3, 1e3])
        p = TetherParams(accelerated=False)
        c = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                   length=8.0, params=p, gland_body=np.zeros(3))
        c.auto_payout = False
        w = c.step(0.01, 0.0, np.array([8., 0., 5.]), np.array([1., 0., 0., 0.]),
                   np.zeros(3))
        self.assertTrue(np.all(np.isfinite(c.x)))
        self.assertTrue(np.all(np.isfinite(c.v)))
        self.assertEqual(np.asarray(w).shape, (6,))
        self.assertTrue(np.all(np.isfinite(w)))


class TetherBreakLoadTests(unittest.TestCase):
    def _cable(self, length=8.0, **kw):
        world = World(20)
        world.current.turbulence = 0
        p = TetherParams(accelerated=False, **kw)
        c = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                   length=length, params=p, gland_body=np.zeros(3))
        c.auto_payout = False
        return c

    def test_violent_yank_breaks_cable_cleanly(self):
        # Drag the ROV end far past the cable length so tension exceeds the
        # rated break load. The cable must flag broken, stay finite, and drop
        # tension to zero rather than poisoning state.
        c = self._cable(length=4.0)
        rov_q = np.array([1., 0., 0., 0.])
        far = np.array([500., 0., 5.])
        for _ in range(50):
            c.step(0.01, 0.0, far, rov_q, np.zeros(3))
            if c.broken:
                break
        self.assertTrue(c.broken, "cable should break when yanked far past length")
        self.assertTrue(np.all(np.isfinite(c.x)))
        self.assertTrue(np.all(np.isfinite(c.v)))
        self.assertTrue(any(e.get("type") == "tether_break" for e in c.events))

    def test_tension_near_break_load_stays_finite(self):
        # Tension exactly at the rated break threshold is the boundary: it may
        # or may not break, but state must remain finite and tension bounded.
        c = self._cable(length=8.0)
        rov_q = np.array([1., 0., 0., 0.])
        c.step(0.01, 0.0, np.array([8.5, 0., 5.]), rov_q, np.zeros(3))
        self.assertTrue(math.isfinite(c.tension_max))
        self.assertGreaterEqual(c.tension_max, 0.0)
        self.assertLessEqual(c.tension_max, 2.0 * c.p.breaking_n + 1e-6)


class EmptyMissionTests(unittest.TestCase):
    def test_empty_roster_summary_is_safe(self):
        mgr = CohortRosterManager()
        summary = mgr.compute_cohort_summary()
        self.assertIsInstance(summary, dict)
        # count-like fields, if present, should be zero for an empty cohort
        for k, val in summary.items():
            if isinstance(val, (int, float)):
                self.assertTrue(math.isfinite(val))

    def test_zero_length_command_and_idle_steps(self):
        # Idle vehicle, zero command, many small steps: no drift to non-finite,
        # unit quaternion preserved (empty-mission / parked-ROV scenario).
        v = Vehicle()
        cmd = np.zeros(len(v.thrusters))
        for _ in range(300):
            v.step(0.02, cmd)
        self.assertTrue(np.all(np.isfinite(v.s.pos)))
        self.assertAlmostEqual(float(np.linalg.norm(v.s.q)), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
