"""Independent analytic/invariant checks for the vehicle time integrator."""
import math
import unittest

import numpy as np

from rov01sim import physics
from rov01sim.physics import Vehicle, VehicleParams, q_from_euler, q_rot, q_conj, coriolis_wrench


def neutral_vehicle(**kwargs):
    params = dict(mass=10., added_mass=(0., 0., 0.), inertia=(1., 1., 1.),
                  net_buoyancy=0., gm=0., linear_drag=(0.,)*6)
    params.update(kwargs)
    vehicle = Vehicle(VehicleParams(**params))
    vehicle.s.pos[2] = 10.
    vehicle.quad_drag[:] = 0.
    vehicle.quad_rdrag[:] = 0.
    return vehicle


class TestPhysicsRealism(unittest.TestCase):
    def test_scalar_and_compiled_derivatives_match_independent_vector_equations(self):
        rng = np.random.default_rng(3012)
        for model in ("rov01", "rov02_heavy", "rov01_pro"):
            v = Vehicle(model_id=model)
            for _ in range(25):
                q = rng.normal(size=4)
                q /= np.linalg.norm(q)
                velocity, omega, current = rng.normal(size=(3, 3))
                wrench = rng.normal(size=6)*20
                v.current_ned = current
                body_current = q_rot(q_conj(q), current)
                relative = velocity-body_current
                up = q_rot(q_conj(q), np.array([0., 0., -1.]))
                inertial = coriolis_wrench(v.p.mass, v.p.added_mass, v.I, velocity, omega, relative)
                force = (wrench[:3] - v._linear_drag[:3]*relative - v.quad_drag*relative*np.abs(relative)
                         + up*v.p.net_buoyancy + inertial[:3]
                         - v._added_mass*np.cross(omega, body_current))
                moment = (wrench[3:] - v._linear_drag[3:]*omega - v.quad_rdrag*omega*np.abs(omega)
                          + np.cross([0., 0., -v.p.gm], up*(v.p.mass*physics.G+v.p.net_buoyancy))
                          + inertial[3:])
                args = (q, velocity, omega, wrench, current, v.p.mass, v._added_mass, v.I,
                        v._linear_drag, v.quad_drag, v.quad_rdrag, v._inv_mass, v._inv_inertia,
                        v.p.net_buoyancy, v.p.gm*(v.p.mass*physics.G+v.p.net_buoyancy))
                for actual in (physics._body_derivatives(*args), v._derivatives(q, velocity, omega, wrench)):
                    np.testing.assert_allclose(actual[0], force/v.M, atol=2e-12)
                    np.testing.assert_allclose(actual[1], moment/v.I, atol=2e-12)

    def test_full_trajectory_matches_without_optional_compiler(self):
        fast, slow = Vehicle(model_id="rov01_pro"), Vehicle(model_id="rov01_pro")
        kernel = physics._fast_derivatives
        command = fast.allocate(np.array([.3, -.15, -.1, 0., 0., .2]))
        for vehicle in (fast, slow):
            vehicle.s.pos[2] = 10.
            vehicle.current_ned[:] = [.2, .1, .02]
        try:
            for _ in range(80):
                fast.step(.01, command)
            physics._fast_derivatives = physics._body_derivatives
            for _ in range(80):
                slow.step(.01, command)
        finally:
            physics._fast_derivatives = kernel
        for name in ("pos", "q", "vel", "omega", "thrust", "accel"):
            np.testing.assert_allclose(getattr(fast.s, name), getattr(slow.s, name), atol=1e-12)

    def test_motor_response_matches_exponential_for_any_step_partition(self):
        for steps in ([.2], [.01]*20, [.003, .047, .02, .13]):
            v = neutral_vehicle(motor_tau=.08)
            for dt in steps:
                v.step(dt, np.ones(6)*.7)
            expected = .7*v.p.thruster_max*(1-math.exp(-.2/.08))
            np.testing.assert_allclose(v.s.thrust, expected, atol=1e-12)

    def test_motor_reversal_crosses_zero_continuously(self):
        v = neutral_vehicle(motor_tau=.08)
        v.s.thrust[:] = v.p.thruster_max
        v.step(.01, -np.ones(6))
        self.assertTrue(np.all(v.s.thrust > 0.))
        v.step(.07, -np.ones(6))
        np.testing.assert_allclose(v.s.thrust, v.p.thruster_max*(-1+2/math.e), atol=1e-12)

    def test_constant_angular_acceleration_has_correct_attitude(self):
        v = neutral_vehicle()
        torque = np.array([0., 0., 0., 0., 0., .4])
        for _ in range(50):
            v.step(.02, np.zeros(6), torque)
        self.assertAlmostEqual(v.s.omega[2], .4, places=12)
        self.assertAlmostEqual(v.euler[2], .2, places=12)

    def test_rotating_free_body_keeps_world_velocity_and_reports_zero_acceleration(self):
        v = neutral_vehicle()
        v.s.q = q_from_euler(.3, -.2, .4)
        v.s.vel[:] = [.8, -.2, .1]
        v.s.omega[:] = [.2, -.3, .7]
        world_velocity = v.world_velocity()
        start = v.s.pos.copy()
        for _ in range(200):
            v.step(.01, np.zeros(6))
            np.testing.assert_allclose(v.s.accel, 0., atol=1e-12)
        np.testing.assert_allclose(v.world_velocity(), world_velocity, atol=2e-5)
        np.testing.assert_allclose(v.s.pos, start + 2*world_velocity, atol=2e-5)
        self.assertAlmostEqual(np.linalg.norm(v.s.q), 1., places=12)

    def test_linear_drag_matches_analytic_exponential_and_converges_quadratically(self):
        errors = []
        for dt in (.02, .01):
            v = neutral_vehicle(linear_drag=(20., 0., 0., 0., 0., 0.))
            v.s.vel[0] = 1.
            for _ in range(round(1./dt)):
                v.step(dt, np.zeros(6))
            errors.append(abs(v.s.vel[0] - math.exp(-2.)))
        self.assertLess(errors[1], errors[0]/3.8)
        self.assertLess(errors[1], .00002)

    def test_quadratic_drag_never_reverses_velocity_or_adds_energy_on_large_step(self):
        v = neutral_vehicle()
        v.quad_drag[0] = 100.
        v.s.vel[0] = 12.
        v.step(.25, np.zeros(6))
        # Analytic scalar solution: v(t) = v0 / (1 + k*v0*t/m).
        self.assertAlmostEqual(v.s.vel[0], 12./31., delta=.004)
        self.assertGreater(v.s.vel[0], 0.)

    def test_anisotropic_unforced_motion_does_not_artificially_gain_energy(self):
        v = neutral_vehicle(added_mass=(3., 8., 12.), inertia=(1., 2., 3.))
        v.s.vel[:] = [.7, -.2, .3]
        v.s.omega[:] = [.2, -.3, .4]
        energy = lambda: .5*(np.dot(v.M*v.s.vel, v.s.vel) + np.dot(v.I*v.s.omega, v.s.omega))
        initial = energy()
        for _ in range(250):
            v.step(.02, np.zeros(6))
        self.assertLess(abs(energy()/initial - 1.), .0001)

    def test_positive_damping_dissipates_energy_with_variable_steps(self):
        v = neutral_vehicle(added_mass=(3., 8., 12.), inertia=(1., 2., 3.),
                            linear_drag=(5., 7., 8., 1., 2., 3.))
        v.quad_drag[:] = [8., 12., 15.]
        v.quad_rdrag[:] = [2., 3., 4.]
        v.s.vel[:] = [.7, -.2, .3]
        v.s.omega[:] = [.2, -.3, .4]
        previous = math.inf
        for dt in [.01, .03, .007, .08]*20:
            v.step(dt, np.zeros(6))
            energy = .5*(np.dot(v.M*v.s.vel, v.s.vel) + np.dot(v.I*v.s.omega, v.s.omega))
            self.assertLess(energy, previous)
            previous = energy

    def test_comoving_uniform_current_stays_drag_free_while_rotating(self):
        v = neutral_vehicle(added_mass=(3., 8., 12.),
                            linear_drag=(7., 10., 15., 0., 0., 0.))
        v.quad_drag[:] = [10., 20., 30.]
        v.current_ned[:] = [.3, -.2, .1]
        v.s.vel[:] = v.current_ned
        v.s.omega[:] = [0., 0., .5]
        for _ in range(100):
            v.step(.01, np.zeros(6))
        np.testing.assert_allclose(v.world_velocity(), v.current_ned, atol=1e-6)

    def test_falcon_passive_axes_have_geometry_based_damping(self):
        v = Vehicle(model_id="rov01_pro")
        self.assertEqual(v.authority[3], 0.)
        self.assertEqual(v.authority[4], 0.)
        self.assertTrue(np.all(v.quad_rdrag[:2] > .05))
        v.s.pos[2] = 10.
        v.s.q = q_from_euler(.5, -.3, 0.)
        for _ in range(1000):
            v.step(.01, np.zeros(5))
        self.assertLess(abs(v.euler[0]), .03)
        self.assertLess(abs(v.euler[1]), .03)

    def test_invalid_inputs_never_mutate_state(self):
        v = neutral_vehicle()
        for dt, command, wrench in ((-.1, np.zeros(6), None),
                                    (.1, np.full(6, np.nan), None),
                                    (.1, np.zeros(5), None),
                                    (.1, np.zeros(6), np.full(6, np.inf))):
            with self.assertRaises(ValueError):
                v.step(dt, command, wrench)
            np.testing.assert_array_equal(v.s.pos, [0., 0., 10.])
            np.testing.assert_array_equal(v.s.thrust, 0.)
            np.testing.assert_array_equal(v.s.vel, 0.)

    def test_zero_step_is_noop(self):
        v = neutral_vehicle()
        v.s.vel[0] = .5
        v.step(0., np.ones(6))
        np.testing.assert_array_equal(v.s.pos, [0., 0., 10.])
        np.testing.assert_array_equal(v.s.thrust, 0.)
        self.assertEqual(v.s.vel[0], .5)


if __name__ == "__main__":
    unittest.main()
