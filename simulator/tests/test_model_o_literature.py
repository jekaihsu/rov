"""Published heavy-configuration coefficients, the public thrust map, and the pool comparison.

X1 and the other catalogue vehicle keep the authority they had before this calibration.
"""
import unittest

import numpy as np

from qysim.model_o import (
    MEASURED_MOMENT,
    MEASURED_RATE,
    MEASURED_SPEED,
    MODEL_O_PARAMS,
    MODEL_O_SOURCES,
    MOTOR_TAU,
    POOL_VOLTAGE,
    POLYNOMIAL_FULL_N,
    YAW_ARM_M,
    demand_thrust,
    open_loop,
    polynomial_thrust,
    prepared_vehicle,
    published_thrust,
    scalar_response,
    time_to_fraction,
)
from qysim.physics import G, Vehicle
from qysim.vehicles import BENCHMARK_HEAVY

DT = 0.01
# von Benzon 2022 §4.2: steady surge/sway error about 10%, yaw about 12%, heave 15% only at 20% input.
SURGE_SWAY = 0.10
HEAVE = 0.10
YAW = 0.12


def _relative(actual, expected):
    return abs(actual / expected - 1.0)


class TestModelOLiterature(unittest.TestCase):
    def test_every_override_names_a_published_source(self):
        for key in MODEL_O_PARAMS:
            self.assertIn(key, ("mass", "net_buoyancy", "gm", "added_mass", "inertia", "thruster_max",
                                "motor_tau", "vmax", "wmax", "linear_drag", "quadratic_drag"))
        for key in ("mass", "gm", "added_mass", "inertia", "linear_drag", "quadratic_drag",
                    "thruster_max", "motor_tau", "vmax", "wmax", "thrust_curve", "displaced_volume"):
            self.assertTrue(MODEL_O_SOURCES[key])
        self.assertEqual(MODEL_O_PARAMS["mass"], 13.5)
        self.assertEqual(MODEL_O_PARAMS["gm"], 0.01)
        self.assertEqual(MODEL_O_PARAMS["added_mass"], (6.36, 7.12, 18.68))
        self.assertEqual(MODEL_O_PARAMS["linear_drag"], (13.7, 0.0, 33.0, 0.0, 0.8, 0.0))
        self.assertEqual(MODEL_O_PARAMS["quadratic_drag"], (141.0, 217.0, 190.0, 1.19, 0.47, 1.5))
        self.assertEqual(MODEL_O_PARAMS["vmax"], MEASURED_SPEED)
        self.assertEqual(MODEL_O_PARAMS["wmax"], MEASURED_RATE)

    def test_public_sheet_endpoints_and_deadband(self):
        cases = ((16.0, 1.0, 5.25), (16.0, -1.0, -4.1), (12.0, 1.0, 3.71),
                 (12.0, -1.0, -2.92), (20.0, 1.0, 6.7), (20.0, -1.0, -5.05), (10.0, 1.0, 2.93))
        for voltage, command, kgf in cases:
            with self.subTest(voltage=voltage, command=command):
                newtons = float(published_thrust(command, voltage))
                self.assertLess(_relative(newtons, kgf * G), 0.01)
        self.assertAlmostEqual(float(published_thrust(0.0, 16.0)), 0.0, places=6)
        self.assertAlmostEqual(float(published_thrust(1.0, POOL_VOLTAGE)), POLYNOMIAL_FULL_N, places=6)
        self.assertAlmostEqual(float(polynomial_thrust(1.0)), POLYNOMIAL_FULL_N, places=6)

    def test_force_demand_inverts_the_sheet_and_voltage_clips_it(self):
        nominal = Vehicle(model_id="bluerov2_heavy")
        half = 0.5 * nominal.p.thruster_max
        nominal.step(nominal.p.motor_tau * 20, np.full(8, 0.5))
        self.assertLess(_relative(float(nominal.s.thrust[0]), half), 0.01)
        # The raw 50% PWM sample is well below half the forward bollard, so this is the inverse.
        self.assertLess(float(published_thrust(0.5, 16.0)), half * 0.8)
        low = Vehicle(model_id="bluerov2_heavy")
        low.supply_voltage = 12.0
        low.step(low.p.motor_tau * 20, np.ones(8))
        endpoint = float(published_thrust(1.0, 12.0))
        self.assertLess(_relative(float(low.s.thrust[0]), endpoint), 0.01)
        self.assertLess(float(low.s.thrust[0]), low.p.thruster_max)
        self.assertAlmostEqual(float(demand_thrust(0.0, 16.0, half)), 0.0, places=6)

    def test_other_vehicles_keep_linear_motors_and_authority(self):
        frozen = {
            "x1": np.array([293.20979, 293.60007, 420.4393, 91.24438, 120.13926, 60.68]),
            "falcon": np.array([378.45677, 224.43367, 110.0, 0.0, 0.0, 125.63885]),
        }
        for model, authority in frozen.items():
            vehicle = Vehicle(model_id=model)
            self.assertIsNone(vehicle.thrust_map)
            self.assertIsNone(vehicle.p.quadratic_drag)
            np.testing.assert_allclose(vehicle.authority, authority, rtol=0, atol=5e-5)
        benchmark = Vehicle(definition=BENCHMARK_HEAVY)
        self.assertIsNone(benchmark.thrust_map)
        heavy = Vehicle(model_id="bluerov2_heavy")
        self.assertIs(heavy.thrust_map, published_thrust)
        self.assertIsNotNone(heavy.p.quadratic_drag)
        # Faster assist reference on this hull only; other hulls keep the original filter.
        self.assertEqual(heavy.assist_speed_gain, 6.0)
        self.assertEqual(Vehicle(model_id="x1").assist_speed_gain, 1.0)
        self.assertEqual(Vehicle(model_id="falcon").assist_speed_gain, 1.0)

    def test_pool_step_matches_table_4(self):
        cases = (
            ("surge", [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0, MEASURED_SPEED[0], SURGE_SWAY, False),
            ("sway", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 1, MEASURED_SPEED[1], SURGE_SWAY, False),
            ("heave", [0.0, 0.0, -1.0, 0.0, 0.0, 0.0], 2, -MEASURED_SPEED[2], HEAVE, False),
            ("yaw", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0], 5, MEASURED_RATE[2], YAW, True),
        )
        for name, stick, axis, expected, tolerance, literature in cases:
            with self.subTest(axis=name):
                vehicle = prepared_vehicle(POOL_VOLTAGE, literature=literature)
                _, trace = open_loop(vehicle, stick, 8.0, DT)
                actual = float(trace[-1, axis])
                self.assertLess(_relative(actual, expected), tolerance)
                print(f"Model O {name}: table={expected}, simulated={actual:.5f}, "
                      f"error={_relative(actual, expected):.2%}")

    def test_surge_time_constant_matches_the_identified_model(self):
        vehicle = prepared_vehicle(POOL_VOLTAGE)
        wrench, trace = open_loop(vehicle, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 8.0, DT)
        mass = MODEL_O_PARAMS["mass"] + MODEL_O_PARAMS["added_mass"][0]
        reference = scalar_response(wrench[0], 13.7, 141.0, mass, MOTOR_TAU, 8.0, DT)
        simulated = time_to_fraction(trace[:, 0], 0.632, DT)
        identified = time_to_fraction(reference, 0.632, DT)
        self.assertLess(_relative(simulated, identified), 0.05)
        self.assertLess(_relative(float(trace[-1, 0]), float(reference[-1])), 0.01)
        print(f"Model O surge 63% rise: identified={identified:.3f} s, simulated={simulated:.3f} s")

    def test_coast_and_published_yaw_moment(self):
        vehicle = prepared_vehicle(POOL_VOLTAGE)
        vehicle.s.vel[0] = MEASURED_SPEED[0]
        for _ in range(1200):
            vehicle.step(DT, np.zeros(8))
        self.assertLess(_relative(float(vehicle.s.pos[0]), 0.30), 0.10)
        print(f"Model O coast from 0.72 m/s: derived=0.30 m, simulated={vehicle.s.pos[0]:.5f} m")
        yaw = prepared_vehicle(POOL_VOLTAGE)
        moment = np.zeros(6)
        moment[5] = MEASURED_MOMENT[2]
        for _ in range(800):
            yaw.step(DT, np.zeros(8), moment)
        balance = (MEASURED_MOMENT[2] / MODEL_O_PARAMS["quadratic_drag"][5]) ** 0.5
        self.assertLess(_relative(float(yaw.s.omega[2]), balance), 0.02)
        self.assertLess(_relative(float(yaw.s.omega[2]), MEASURED_RATE[2]), YAW)
        print(f"Model O yaw at 22 N·m: table={MEASURED_RATE[2]}, balance={balance:.3f}, "
              f"simulated={yaw.s.omega[2]:.3f}")

    def test_literature_yaw_arm(self):
        vehicle = prepared_vehicle(POOL_VOLTAGE, literature=True)
        arms = np.abs(vehicle.B[5, :4])
        np.testing.assert_allclose(arms, YAW_ARM_M, atol=1e-3)


if __name__ == "__main__":
    unittest.main()
