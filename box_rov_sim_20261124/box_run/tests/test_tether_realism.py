"""Analytic mechanics checks plus accelerated/reference equivalence."""
import math
import pickle
import unittest

import numpy as np

from rov01sim.physics import G, RHO
from rov01sim.tether import Tether, TetherParams
from rov01sim.world import World
from rov01sim._cable_accel import advance


class TetherRealismTests(unittest.TestCase):
    def cable(self, accelerated=False, **kwargs):
        world = World(20)
        world.current.turbulence = 0
        p = TetherParams(accelerated=accelerated, **kwargs)
        cable = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                       length=8., params=p, gland_body=np.zeros(3))
        cable.auto_payout = False
        return cable

    def test_kinematic_endpoints_do_not_drift_under_tension(self):
        for accelerated in (False, True):
            cable = self.cable(accelerated)
            goal = np.array([8.02, 0., 5.])
            cable.step(.01, 0, goal, np.array([1., 0., 0., 0.]), np.array([.2, 0., 0.]))
            np.testing.assert_array_equal(cable.x[0], cable.spool)
            np.testing.assert_array_equal(cable.v[0], np.zeros(3))
            np.testing.assert_array_equal(cable.x[-1], goal)
            np.testing.assert_array_equal(cable.v[-1], [.2, 0., 0.])

    def test_gland_velocity_includes_body_rotation(self):
        cable = self.cable()
        cable.gland_body = np.array([-.4, 0., 0.])
        cable.step(.01, 0, np.array([8.4, 0., 5.]), np.array([1., 0., 0., 0.]),
                   np.array([1., 0., 0.]), rov_omega_body=np.array([0., 0., 2.]))
        np.testing.assert_allclose(cable.v[-1], [1., -.8, 0.])

    def test_payout_rate_depends_on_elapsed_time_not_call_count(self):
        final_lengths = []
        for dt in (.005, .01, .04):
            cable = self.cable(payout_rate=.8)
            cable.auto_payout = True
            cable._cand = []
            cable.tension_spool = 100.
            for i in range(round(1. / dt)):
                cable._update_metrics(i*dt, dt)
            final_lengths.append(cable.length)
        np.testing.assert_allclose(final_lengths, [8.8]*3, atol=1e-12)

    def test_nonfinite_payout_is_atomic_and_next_step_remains_usable(self):
        for accelerated in (False, True):
            for amount in (float('nan'), float('inf'), -float('inf'),
                           np.float64('nan'), np.float64('inf'), -np.float64('inf')):
                with self.subTest(accelerated=accelerated, amount=amount):
                    cable = self.cable(accelerated)
                    reference = self.cable(accelerated)
                    before = pickle.dumps(cable)
                    with self.assertRaisesRegex(ValueError, '^delta_m must be finite$'):
                        cable.payout(amount)
                    self.assertEqual(pickle.dumps(cable), before)
                    args = (.01, 0., cable.x[-1].copy(),
                            np.array([1., 0., 0., 0.]), np.zeros(3))
                    wrench = cable.step(*args)
                    np.testing.assert_array_equal(wrench, reference.step(*args))
                    np.testing.assert_array_equal(cable.x, reference.x)
                    np.testing.assert_array_equal(cable.v, reference.v)
                    self.assertTrue(np.isfinite(wrench).all())
                    self.assertTrue(np.isfinite(cable.x).all())
                    self.assertTrue(np.isfinite(cable.v).all())

    def test_friction_matches_normal_impulse_and_timestep(self):
        final_speeds = []
        for h in (.001, .004):
            cable = self.cable(friction=.6, contact_cache_m=0)
            cable._cand = []
            cable._contact_anchor = None
            cable.x[:, 2] = 20 - cable.p.node_radius
            cable.v[1:-1, 0] = 1.
            for _ in range(round(.2/h)):
                cable.v[1:-1, 2] = 2*h  # known 2 m/s^2 normal loading
                cable.x[1:-1, 2] = 20 - cable.p.node_radius + 2*h*h
                cable._resolve_contact()
            final_speeds.append(cable.v[10, 0])
        np.testing.assert_allclose(final_speeds, [1-.6*2*.2]*2, atol=1e-12)

    def test_unloaded_contact_does_not_glue_tangential_motion(self):
        cable = self.cable()
        cable._cand, cable._contact_anchor = [], None
        cable.x[:, 2] = 20 - cable.p.node_radius + 1e-8
        cable.v[1:-1, 0] = .1
        cable._resolve_contact()
        np.testing.assert_allclose(cable.v[1:-1, 0], .1)

    def test_cylindrical_tangent_drag_uses_wetted_surface_area(self):
        accelerations = []
        for current in ([1., 0., 0.], [0., 1., 0.]):
            cable = self.cable(wet_weight_per_m=0, cd_normal=1.2, cd_tangent=.02)
            cable._cur = np.tile(current, (len(cable.x), 1))
            cable._cand, cable._contact_anchor = [], None
            cable._substep(1e-5, cable.x[-1].copy(), np.zeros(3))
            accelerations.append(np.linalg.norm(cable.v[10])/1e-5)
        expected_normal = .5*RHO*.0095*cable.seg_len*1.2 / cable._node_mass()
        self.assertAlmostEqual(accelerations[1], expected_normal, places=9)
        self.assertAlmostEqual(accelerations[0]/accelerations[1], math.pi*.02/1.2, places=10)

    def test_broken_free_end_has_half_segment_mass(self):
        cable = self.cable(wet_weight_per_m=0, cd_normal=0, cd_tangent=0)
        cable.broken = True
        cable.x[-1, 0] += .001
        cable._cur = np.zeros_like(cable.x)
        cable._cand, cable._contact_anchor = [], None
        stiffness = min(cable.p.ea/cable.seg_len, cable.p.k_max)
        expected = -.001*stiffness/(.5*cable._node_mass())
        cable._substep(1e-5, cable.x[-1].copy(), np.zeros(3))
        self.assertAlmostEqual(cable.v[-1, 0]/1e-5, expected, places=8)

    def test_short_line_adapts_substeps_instead_of_exploding(self):
        cable = self.cable(substeps=1)
        cable.length = 2.
        cable.x[:, 0] = np.linspace(0., 2., len(cable.x))
        for i in range(20):
            wrench = cable.step(.02, i*.02, np.array([2., 0., 5.]),
                                np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertGreater(cable.last_substeps, 1)
        self.assertTrue(np.isfinite(cable.x).all())
        self.assertTrue(np.isfinite(wrench).all())
        self.assertFalse(cable.broken)
        self.assertLess(np.max(np.linalg.norm(cable.v, axis=1)), 1.)

    def test_break_detaches_endpoint_in_failing_tick(self):
        cable = self.cable(breaking_n=10.)
        goal = np.array([8.1, 0., 5.])
        wrench = cable.step(.01, 0, goal, np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertTrue(cable.broken)
        self.assertEqual(len(cable.events), 1)
        self.assertLess(cable.x[-1, 0], goal[0])
        np.testing.assert_array_equal(wrench, np.zeros(6))

    def test_long_span_cross_current_transmits_load_without_breaking(self):
        world = World(100)
        world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 1.
        world.current.turbulence = 0.
        goal = np.array([75., 0., 20.])
        cable = Tether(world, np.zeros(3), goal, length=78., gland_body=np.zeros(3))
        cable.auto_payout = False
        peak_force = 0.
        for i in range(400):
            wrench = cable.step(.01, i*.01, goal, np.array([1., 0., 0., 0.]), np.zeros(3))
            peak_force = max(peak_force, float(np.linalg.norm(wrench[:3])))
        self.assertTrue(np.isfinite(cable.x).all())
        self.assertFalse(cable.broken)
        self.assertGreater(peak_force, .1)
        self.assertGreater(np.max(cable.x[:, 1]), .1)
        self.assertLess(cable.tension_max, cable.p.breaking_n)
        np.testing.assert_array_equal(cable.x[-1], goal)

    def test_loaded_spool_pays_out_at_configured_rate_in_live_step(self):
        cable = self.cable(payout_threshold_n=.01, payout_rate=.4)
        cable.auto_payout = True
        # A uniformly strained cable avoids the propagation delay of pulling
        # only the far end, and exercises the actual force/payout path.
        cable.x[:, 0] *= 1.002
        goal = cable.x[-1].copy()
        before = cable.length
        cable.step(.02, 0, goal, np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertGreater(cable.tension_spool, cable.p.payout_threshold_n)
        self.assertAlmostEqual(cable.length-before, .4*.02, places=12)

    def test_compiled_matches_reference_including_seabed_and_broken_end(self):
        self.assertTrue(callable(advance), "JIT and Python fallback must both be executable")
        for broken in (False, True):
            accelerated, reference = self.cable(True), self.cable(False)
            for cable in (accelerated, reference):
                cable.broken = broken
                cable.x[:, 2] = 19.97
                cable.spool[2] = 19.97
                cable.v[1:-1, 1] = .1
            for i in range(12):
                args = (.01, i*.01, np.array([8., 0., 19.97]),
                        np.array([1., 0., 0., 0.]), np.zeros(3))
                np.testing.assert_allclose(accelerated.step(*args), reference.step(*args), atol=1e-8)
            np.testing.assert_allclose(accelerated.x, reference.x, atol=1e-8)
            np.testing.assert_allclose(accelerated.v, reference.v, atol=1e-8)

    def test_invalid_timestep_does_not_mutate_state(self):
        cable = self.cable()
        before = cable.x.copy()
        for dt in (0., -.1, float('nan')):
            with self.assertRaises(ValueError):
                cable.step(dt, 0, np.array([8., 0., 5.]), np.array([1., 0., 0., 0.]), np.zeros(3))
        np.testing.assert_array_equal(cable.x, before)

    def test_extreme_current_cannot_blow_up_the_cable(self):
        """An absurd current drives explicit quadratic drag toward overflow.
        The step must roll back to a finite state and return a finite wrench
        instead of poisoning x/v (and the vehicle) with NaN/inf forever."""
        for accelerated in (False, True):
            with self.subTest(accelerated=accelerated):
                world = World(20)
                world.current.turbulence = 0
                world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 5000.0
                p = TetherParams(accelerated=accelerated)
                cable = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                               length=8., params=p, gland_body=np.zeros(3))
                cable.auto_payout = False
                with np.errstate(all='ignore'):
                    for _ in range(40):
                        wrench = cable.step(.05, 0., np.array([8., 0., 5.]),
                                            np.array([1., 0., 0., 0.]), np.zeros(3))
                        self.assertTrue(np.all(np.isfinite(wrench)))
                        self.assertTrue(np.all(np.isfinite(cable.x)))
                        self.assertTrue(np.all(np.isfinite(cable.v)))
                        self.assertTrue(math.isfinite(cable.tension_max))

    def test_rollback_leaves_cable_usable_in_normal_current(self):
        """After a non-finite tick is rolled back, a benign step still works."""
        world = World(20)
        world.current.turbulence = 0
        world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 5000.0
        cable = Tether(world, np.array([0., 0., 5.]), np.array([8., 0., 5.]),
                       length=8., params=TetherParams(accelerated=False), gland_body=np.zeros(3))
        cable.auto_payout = False
        with np.errstate(all='ignore'):
            cable.step(.05, 0., np.array([8., 0., 5.]), np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertFalse(cable.broken)
        world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 0.0
        wrench = cable.step(.01, 0., np.array([8., 0., 5.]), np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertTrue(np.all(np.isfinite(wrench)))
        self.assertTrue(np.all(np.isfinite(cable.x)))


if __name__ == '__main__':
    unittest.main()
