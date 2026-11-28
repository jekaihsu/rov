"""Coupled kinetic energy, hydrostatic signs and installed-disk regressions."""
import unittest

import numpy as np

from qysim.physics import G, Vehicle, momentum_coriolis, q_from_euler
from qysim.vehicles import VEHICLE_DEFINITIONS


def single_disk(depth=10., speed=0., current=0., command=1.):
    vehicle = Vehicle()
    vehicle.s.pos[2] = depth
    vehicle.s.vel = speed * vehicle.axes[4]
    vehicle.current_ned = current * vehicle.axes[4]
    vehicle.step(.01, command * np.eye(6)[4])
    return vehicle


class VehicleHydroTests(unittest.TestCase):
    def test_mass_and_coriolis_structure(self):
        velocity = np.array([1., -.4, .3, .25, -.7, .8])
        for model in VEHICLE_DEFINITIONS:
            vehicle = Vehicle(model_id=model)
            for matrix in (vehicle.rigid_matrix, vehicle.added_matrix, vehicle.mass_matrix):
                np.testing.assert_allclose(matrix, matrix.T)
                self.assertGreater(min(np.linalg.eigvalsh(matrix)), 0.)
                c = momentum_coriolis(matrix @ velocity)
                self.assertAlmostEqual(velocity @ c @ velocity, 0.)
        vehicle = Vehicle()
        self.assertAlmostEqual(vehicle.added_matrix[0, 4], -.015 * vehicle.p.added_mass[0])
        self.assertAlmostEqual(vehicle.added_matrix[1, 3], .015 * vehicle.p.added_mass[1])
        oblique = np.array([1., 2., 0., 0., 0., 0.])
        loads = -momentum_coriolis(vehicle.added_matrix @ oblique) @ oblique
        self.assertAlmostEqual(loads[5], -2 * (25 - 15))

    def test_neutral_unpowered_energy_after_impulse(self):
        for model in VEHICLE_DEFINITIONS:
            vehicle = Vehicle(model_id=model)
            vehicle.s.pos[2] = 500
            vehicle.seabed_depth = 1000
            vehicle.p.net_buoyancy = vehicle.p.gm = 0.
            idle = np.zeros(len(vehicle.thrusters))
            vehicle.step(.01, idle, np.array([8e4, -2e4, 3e4, 1e4, -2e4, 1e4]))
            previous = float('inf')
            for _ in range(300):
                velocity = np.concatenate((vehicle.s.vel, vehicle.s.omega))
                energy = .5 * velocity @ vehicle.mass_matrix @ velocity
                self.assertTrue(np.isfinite(energy))
                self.assertLessEqual(energy, previous)
                previous = energy
                vehicle.step(.01, idle)

    def test_drag_opposes_relative_flow_on_all_six_axes(self):
        for axis in range(6):
            for sign in (-1., 1.):
                v = Vehicle(model_id="bluerov2_heavy")
                v.s.pos[2] = 10
                v.p.net_buoyancy = 0.
                relative = np.eye(6)[axis] * sign * .5
                v.s.vel = relative[:3].copy()
                v.s.omega = relative[3:].copy()
                if axis < 3:
                    v.current_ned[axis] = 1.
                    v.s.vel[axis] += 1.
                dt = .01
                damping = v.p.linear_drag[axis] + .5 * v.p.quadratic_drag[axis]
                expected = -relative[axis] * damping / (v.mass_matrix[axis, axis] + dt * damping)
                v.step(dt, np.zeros(8))
                actual = np.concatenate((v.s.vel - v.current_ned, v.s.omega))
                self.assertAlmostEqual((actual[axis] - relative[axis]) / dt, expected)

    def test_static_restoring_loads(self):
        for roll, pitch in ((.1, 0.), (0., -.1)):
            v = Vehicle()
            v.s.pos[2] = 10
            v.s.q = q_from_euler(roll, pitch, 0)
            dt = 1e-7
            v.step(dt, np.zeros(6))
            loads = v.mass_matrix @ np.concatenate((v.s.vel, v.s.omega)) / dt
            buoyancy = v.p.mass * G + v.p.net_buoyancy
            self.assertAlmostEqual(loads[3], -v.p.gm * buoyancy * np.sin(roll), places=5)
            self.assertAlmostEqual(loads[4], -v.p.gm * buoyancy * np.sin(pitch), places=5)
            self.assertAlmostEqual(np.linalg.norm(loads[:3]), v.p.net_buoyancy, places=5)
            self.assertLess(loads[2], 0.)

    def test_shaft_inflow_and_ventilation(self):
        bollard = single_disk()
        forward = bollard.s.thrust[4]
        self.assertAlmostEqual(bollard.shaft[4], -np.expm1(-.01 / bollard.p.motor_tau))
        self.assertAlmostEqual(single_disk(command=-1.).s.thrust[4], -bollard.p.reverse_ratio * forward)
        self.assertLess(single_disk(speed=.5).s.thrust[4], forward)
        self.assertAlmostEqual(single_disk(speed=.5, current=.5).s.thrust[4], forward)
        self.assertLess(single_disk(depth=0.).s.thrust[4], forward)
        self.assertEqual(single_disk(depth=-.2).s.thrust[4], 0.)
        # A reversal must cross zero over time.
        bollard.step(.001, -np.eye(6)[4])
        self.assertGreater(bollard.shaft[4], 0.)

    def test_pair_wake_and_hull_loss(self):
        v = Vehicle()
        v.s.pos[2] = 10
        i, j = np.unravel_index(np.argmax(v.forward_wake), v.forward_wake.shape)
        self.assertGreater(v.forward_wake[i, j], 0.)
        solo = np.eye(6)[i]
        v.step(.01, solo)
        isolated = v.s.thrust[i]
        self.assertAlmostEqual(isolated, v.p.thruster_max * v.shaft[i]**2 * (1 - v.fit.hull_loss))
        pair = Vehicle()
        pair.s.pos[2] = 10
        pair.step(.01, solo + np.eye(6)[j])
        self.assertLess(pair.s.thrust[i], isolated)
