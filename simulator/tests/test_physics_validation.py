"""Literature force-matched benchmarks and calibration identifiability regressions."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

from qysim.physics import Vehicle, VehicleParams
from qysim.vehicles import BENCHMARK_HEAVY, X1_PARAMETERS

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('fit_measurements', ROOT / 'docs/reference/fit_measurements.py')
FITTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FITTER)


class TestPhysicsValidation(unittest.TestCase):
    def test_literature_force_matched_terminal_speeds(self):
        for axis, force, expected in ((0, 85., .72), (1, 85., .63), (2, 120., .71)):
            with self.subTest(axis=axis):
                vehicle = Vehicle(definition=BENCHMARK_HEAVY)
                vehicle.s.pos[2] = 10
                vehicle.seabed_depth = 100
                vehicle.p.net_buoyancy = 0  # isolate measured one-axis tow/step experiment
                wrench = np.eye(6)[axis] * force
                for _ in range(1500):
                    vehicle.step(.01, np.zeros(8), wrench)
                actual = vehicle.s.vel[axis]
                self.assertLess(abs(actual / expected - 1), .15)
                print(f'T20 axis {axis}: literature={expected}, simulated={actual:.5f}, '
                      f'error={abs(actual / expected - 1):.2%}')

    def test_coast_and_yaw(self):
        vehicle = Vehicle(definition=BENCHMARK_HEAVY)
        vehicle.p.net_buoyancy = 0
        vehicle.s.pos[2] = 10
        vehicle.s.vel[0] = .72
        for _ in range(1500):
            vehicle.step(.01, np.zeros(8))
        self.assertLess(abs(vehicle.s.pos[0] / .30 - 1), .15)
        print(f'T20 coast: literature-derived=.30, simulated={vehicle.s.pos[0]:.5f}')
        # Isolated yaw moment: 20 Nm gives sqrt(20/1.5)=3.65 rad/s.
        vehicle = Vehicle(definition=BENCHMARK_HEAVY)
        vehicle.p.net_buoyancy = 0
        vehicle.s.pos[2] = 10
        for _ in range(1000):
            vehicle.step(.01, np.zeros(8), np.array([0., 0., 0., 0., 0., 20.]))
        self.assertLess(abs(vehicle.s.omega[2] / 3.7 - 1), .15)
        print(f'T20 yaw at 20 Nm: literature-derived=3.7, simulated={vehicle.s.omega[2]:.5f}')

    def test_motor_asymmetry_and_switch(self):
        for enabled in (True, False):
            vehicle = Vehicle(definition=BENCHMARK_HEAVY)
            vehicle.p.thrust_asymmetry = enabled
            vehicle.s.pos[2] = 10
            command = -np.eye(8)[0]
            vehicle.step(vehicle.p.motor_tau, command)
            ratio = 4.1 / 5.25 if enabled else 1.
            expected = command * vehicle.p.thruster_max * ratio * (1 - np.exp(-1))**2
            np.testing.assert_allclose(vehicle.s.thrust, expected * (1 - vehicle.fit.hull_loss))

    def test_legacy_force_and_drag_unchanged(self):
        # The heavy catalogue entry is calibrated in test_model_o_literature.
        for model in ('x1', 'falcon'):
            vehicle = Vehicle(model_id=model)
            self.assertEqual(vehicle.p.reverse_ratio, .9)
            self.assertIsNone(vehicle.p.quadratic_drag)
            p = vehicle.p
            expected = np.maximum((vehicle.authority[:3] - np.array(p.linear_drag[:3]) * p.vmax)
                                  / np.array(p.vmax) ** 2, 1.)
            np.testing.assert_array_equal(vehicle.quad_drag, expected)
            vehicle.s.pos[2] = 10
            command = -np.eye(len(vehicle.thrusters))[0]
            vehicle.step(p.motor_tau, command)
            expected = command * p.thruster_max * .9 * (1 - np.exp(-1))**2
            np.testing.assert_allclose(vehicle.s.thrust, expected * (1 - vehicle.fit.hull_loss))

    def test_legacy_trajectory_with_asymmetry_switch_is_identical(self):
        for model in ('x1', 'bluerov2_heavy', 'falcon'):
            enabled = Vehicle(model_id=model)
            disabled = Vehicle(model_id=model)
            enabled.p.reverse_ratio = disabled.p.reverse_ratio = 1.0
            disabled.p.thrust_asymmetry = False
            enabled.s.pos[2] = disabled.s.pos[2] = 10
            for i in range(200):
                command = np.sin(np.arange(len(enabled.thrusters)) + i * .03)
                enabled.step(.01, command)
                disabled.step(.01, command)
            np.testing.assert_array_equal(enabled.s.pos, disabled.s.pos)
            np.testing.assert_array_equal(enabled.s.q, disabled.s.q)

    def test_x1_evidence_covers_every_parameter(self):
        self.assertTrue(all(item['level'] in ('official', 'reseller', 'estimated')
                            for item in X1_PARAMETERS.values()))
        for name in VehicleParams.__dataclass_fields__:
            self.assertIn(name, X1_PARAMETERS)

    def test_fit_literature_step_and_coast(self):
        rows = []
        v = 0.
        mass = 13.5 + 6.36
        for i in range(4000):
            u = 1. if i < 2000 else 0.
            rows.append(dict(axis='surge', time_s=i * .001, velocity=v,
                             command=u, effective_mass=mass))
            v += .001 * (85 * u - 13.7 * v - 141 * v * abs(v)) / mass
        result = FITTER.fit(rows)['surge']
        for key, expected in (('thrust', 85), ('linear_drag', 13.7), ('quadratic_drag', 141)):
            self.assertLess(abs(result[key] / expected - 1), .15)
        print(f'T20 literature synthetic trace fit: {result}')
        with self.assertRaises(ValueError):
            FITTER.fit(rows[:1])
        with self.assertRaises(ValueError):
            FITTER.fit([dict(row, velocity=0) for row in rows[:20]])
        with self.assertRaises(ValueError):
            FITTER.fit([dict(row, time_s=0) for row in rows[:20]])
