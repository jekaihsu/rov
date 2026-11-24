"""Round-2 boundary / fuzz extension tests (2026-10-26).

Complements tests/test_boundary_fuzz.py. Focuses on gaps not already
covered there: extreme *external water current* on the 6-DOF vehicle
(existing suite only drives extreme thrust), the empty-mission scoring
path in mission_modes, and extreme current on the tether sampler.

Deterministic, hang-guarded (fixed step counts). No network/DB access.
"""
import math
import unittest

import numpy as np

from rov01sim.physics import Vehicle
from rov01sim.tether import Tether, TetherParams
from rov01sim.world import World


class ExtremeCurrentPhysicsTests(unittest.TestCase):
    """Extreme external water current must never poison vehicle state."""

    def test_absurd_steady_current_stays_finite(self):
        for cur in (1e3, 1e6, 1e12):
            v = Vehicle()
            v.current_ned = np.array([cur, -cur, cur / 2.0])
            for _ in range(200):  # fixed, guarded
                v.step(0.02, np.zeros(len(v.thrusters)))
            self.assertTrue(np.all(np.isfinite(v.s.pos)), f"pos nonfinite at cur={cur}")
            self.assertTrue(np.all(np.isfinite(v.s.vel)), f"vel nonfinite at cur={cur}")
            # quaternion must stay normalised through drag transport
            self.assertAlmostEqual(float(np.linalg.norm(v.s.q)), 1.0, places=4)

    def test_nonfinite_current_does_not_crash_or_hang(self):
        # A NaN/inf current should either raise or roll back; never hang.
        v = Vehicle()
        v.current_ned = np.array([float("nan"), float("inf"), 0.0])
        try:
            v.step(0.02, np.zeros(len(v.thrusters)))
        except (ValueError, FloatingPointError):
            return
        # if it didn't raise, state must still be finite (snapshot rollback)
        self.assertTrue(np.all(np.isfinite(v.s.pos)))

    def test_opposing_current_and_thrust_bounded(self):
        v = Vehicle()
        v.current_ned = np.array([50.0, 0.0, 0.0])
        cmd = np.full(len(v.thrusters), 1.0)
        for _ in range(300):
            v.step(0.02, cmd)
        self.assertTrue(np.all(np.isfinite(v.s.pos)))
        self.assertTrue(np.all(np.isfinite(v.s.vel)))


class ExtremeCurrentTetherTests(unittest.TestCase):
    def _cable(self):
        world = World(20)
        p = TetherParams(accelerated=False)
        c = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                   length=8.0, params=p, gland_body=np.zeros(3))
        c.auto_payout = False
        return c

    def test_extreme_world_current_tether_finite(self):
        c = self._cable()
        c.world.current.bottom_kn = 1e6
        c.world.current.turbulence = 10.0
        rov_q = np.array([1., 0., 0., 0.])
        for _ in range(50):
            c.step(0.01, 0.0, np.array([8., 0., 5.]), rov_q, np.zeros(3))
        self.assertTrue(np.all(np.isfinite(c.x)))
        self.assertTrue(np.all(np.isfinite(c.v)))


class EmptyMissionScoringTests(unittest.TestCase):
    """mission_modes scoring must not divide by zero on an empty target set."""

    def test_empty_targets_score_is_none_not_crash(self):
        from rov01sim import mission_modes as mm

        class _Veh:
            vehicle_id = 1

        class _Sim:
            vehicle_id = 1

        run = mm.MissionRun.__new__(mm.MissionRun)
        run.mode = 'scenario_training'
        run.status = 'active'
        run.elapsed = 0.0
        run.targets = []          # empty mission
        run.dwell = {}
        run.last_photo = None
        state = run.state(_Sim())
        self.assertEqual(state['total'], 0)
        self.assertIsNone(state['score'])       # guarded div-by-zero
        self.assertIsNone(state['time_limit'])


if __name__ == "__main__":
    unittest.main()
