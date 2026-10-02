"""Physical invariants, independent of empirical damping or controller tuning."""
import unittest
import numpy as np
from qysim.physics import Vehicle, coriolis_wrench, cross3, q_rot, q_mul, q_conj


class TestInertialDynamics(unittest.TestCase):
    def test_optimized_vector_math_matches_independent_reference(self):
        rng = np.random.default_rng(910)
        for _ in range(100):
            q = rng.normal(size=4)
            # Include deliberately non-unit quaternions and arbitrary scales.
            a, b = rng.normal(size=(2, 3))
            np.testing.assert_allclose(cross3(a, b), np.cross(a, b), atol=1e-14)
            reference = q_mul(q_mul(q, np.r_[0., a]), q_conj(q))[1:]
            np.testing.assert_allclose(q_rot(q, a), reference, atol=1e-13)

    def test_falcon_allocator_tracks_controllable_axes_without_cancelling_passive_moments(self):
        vehicle = Vehicle(model_id='falcon')
        for axis in (0, 1):
            requested = np.eye(6)[axis] * .5
            actual = vehicle.B @ (vehicle.allocate(requested) * vehicle.p.thruster_max)
            np.testing.assert_allclose(actual[[0, 1, 2, 5]],
                (requested * vehicle.authority)[[0, 1, 2, 5]], atol=1e-10)
            # Horizontal thrusters are below CG: this physical roll/pitch
            # coupling must remain even though those axes lack actuators.
            self.assertGreater(np.linalg.norm(actual[3:5]), .1)

    def test_anisotropic_inertia_coriolis_does_no_work(self):
        rng = np.random.default_rng(719)
        for _ in range(100):
            mass = rng.uniform(1, 100)
            added = rng.uniform(1, 50, 3)
            inertia = rng.uniform(.1, 10, 3)
            velocity, omega = rng.normal(size=(2, 3))
            wrench = coriolis_wrench(mass, added, inertia, velocity, omega)
            self.assertAlmostEqual(np.r_[velocity, omega] @ wrench, 0., delta=1e-10)

    def test_rigid_body_limit_matches_newton_euler(self):
        mass, inertia = 13.5, np.array([.26, .23, .37])
        velocity, omega = np.array([1., .6, .2]), np.array([.3, .4, .5])
        wrench = coriolis_wrench(mass, np.zeros(3), inertia, velocity, omega)
        np.testing.assert_allclose(wrench[:3] / mass + np.cross(omega, velocity), 0., atol=1e-12)
        np.testing.assert_allclose(wrench[3:] + np.cross(omega, inertia * omega), 0., atol=1e-12)

    def test_translation_produces_paired_added_mass_moment(self):
        velocity = np.array([1., 2., 0.])
        wrench = coriolis_wrench(10., [1., 3., 5.], [1., 1., 1.], velocity, np.zeros(3))
        np.testing.assert_allclose(wrench, [0., 0., 0., 0., 0., -4.])

    def test_uniform_current_comoving_body_is_transport_consistent(self):
        mass, added = 13.5, np.array([7., 10., 13.])
        velocity, omega = np.array([.3, -.4, .2]), np.array([.2, .1, -.3])
        # No relative linear flow: added-mass Coriolis moment vanishes.
        wrench = coriolis_wrench(mass, added, [1., 1., 1.], velocity, omega, np.zeros(3))
        transport = -added * np.cross(omega, velocity)
        body_acceleration = (wrench[:3] + transport) / (mass + added)
        np.testing.assert_allclose(body_acceleration + np.cross(omega, velocity), 0., atol=1e-12)
        np.testing.assert_allclose(wrench[3:], 0., atol=1e-12)


if __name__ == '__main__':
    unittest.main()
