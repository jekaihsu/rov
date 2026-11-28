"""Published coefficients and the public PWM–thrust map for the heavy catalogue entry.

Only the catalogue object ``bluerov2_heavy`` uses the map. The offline benchmark
profile is a separate object and keeps its linear motor model. X1 is not read
here. Citations, the pool comparison and the values that were not adopted are
in ``docs/reference/model-o-calibration.md``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Simulator gravity. The thrust table below is already in newtons with this factor.
G = 9.81
SEAWATER_DENSITY = 1025.0

# von Benzon, Sørensen, Uth, Jouffroy, Liniger and Pedersen, 2022, Table A1 and Eq. 18.
# DOI 10.3390/jmse10121898. Pool: 6.1 m diameter, 1.15 m deep, open loop, SBL.
POLYNOMIAL_FULL_N = 30.4
RIGID_INERTIA = (0.26, 0.23, 0.37)
ADDED_INERTIA = (0.189, 0.135, 0.222)
DISPLACED_VOLUME_M3 = 0.0134
MEASURED_SPEED = (0.72, 0.63, 0.71)          # Table 4, m/s; heave is the 120 N case
MEASURED_RATE = (5.2, 4.9, 3.6)              # Table 4 rad/s; the table prints m/s
MEASURED_FORCE = (85.0, 85.0, 120.0)         # N
MEASURED_MOMENT = (26.0, 14.0, 22.0)         # N·m
YAW_ARM_M = 0.1888                           # Wu 2018 Table 4.2, same CAD loci as Table A1

# Manufacturer public bollard sheet, September 2019, static, 10–20 V, PWM 1100–1900 µs.
# File name kept so the table can be checked against the download; see the calibration note.
NOMINAL_VOLTAGE = 16.0
VOLTAGES = np.array((10.0, 12.0, 14.0, 16.0, 18.0, 20.0))

_TABLE = np.loadtxt(Path(__file__).with_name("model_o_thrust.csv"), delimiter=",", skiprows=1)
PWM_US = _TABLE[:, 0]
FORCE_N = _TABLE[:, 1:]


def polynomial_thrust(command):
    """Eq. 18, newtons, for a normalised input in [-1, 1]. Odd polynomial, so it is symmetric."""
    value = np.asarray(command, dtype=float)
    return (-140.3 * value ** 9 + 389.9 * value ** 7 - 404.1 * value ** 5
            + 176.0 * value ** 3 + 8.9 * value)


def _column(voltage):
    """Linear blend of the two neighbouring voltage columns. Ends clamp at 10 V and 20 V."""
    if voltage <= VOLTAGES[0]:
        return FORCE_N[:, 0]
    if voltage >= VOLTAGES[-1]:
        return FORCE_N[:, -1]
    upper = int(np.searchsorted(VOLTAGES, voltage, side="right"))
    lower = upper - 1
    weight = (voltage - VOLTAGES[lower]) / (VOLTAGES[upper] - VOLTAGES[lower])
    return (1.0 - weight) * FORCE_N[:, lower] + weight * FORCE_N[:, upper]


def published_thrust(command, voltage):
    """Bollard newtons for a normalised PWM command. +1 is 1900 µs, −1 is 1100 µs, 0 is 1500 µs."""
    clipped = np.clip(np.asarray(command, dtype=float), -1.0, 1.0)
    pwm = 1500.0 + 400.0 * clipped
    force = np.interp(np.asarray(pwm, dtype=float), PWM_US, _column(float(voltage)))
    return np.asarray(force, dtype=float)


def demand_thrust(command, voltage, scale):
    """Newtons for a normalised force demand, by inverting the 2019 sheet.

    Command +1 asks for ``scale`` newtons and −1 asks for −scale. The PWM that
    the sheet lists for that force is selected, then read back. A demand past
    either endpoint stays on that endpoint: a lower bus voltage therefore
    delivers less than ``scale``, and reverse stops at the weaker bollard.
    A zero demand is exactly 0 N (the deadband centre), not the edge of the plateau.
    """
    demand = np.clip(np.asarray(command, dtype=float), -1.0, 1.0) * float(scale)
    column = _column(float(voltage))
    # A few sheet samples dip by about 0.1 N. The inverse needs a non-decreasing axis.
    rising = np.maximum.accumulate(column)
    pwm = np.interp(demand, rising, PWM_US)
    delivered = np.interp(pwm, PWM_US, column)
    return np.where(np.abs(demand) <= 1e-12, 0.0, np.asarray(delivered, dtype=float))


def pool_voltage():
    """Voltage where full-forward bollard thrust equals Eq. 18 at input 1 (30.4 N).

    The pool paper does not publish the bus voltage. This is the supply voltage on
    the 2019 bollard sheet that reproduces that identified full-scale thrust.
    """
    low = 10.0
    high = 12.0
    for _ in range(48):
        mid = 0.5 * (low + high)
        if float(published_thrust(1.0, mid)) < POLYNOMIAL_FULL_N:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def dominant_time_constant():
    """Seconds. Real pole of the identified thruster transfer function, Eq. 19."""
    poles = np.roots((1.0, 89.0, 9258.0, 108700.0))
    real = poles[np.isclose(poles.imag, 0.0)].real
    return float(-1.0 / real[0])


NOMINAL_FORWARD_N = float(published_thrust(1.0, NOMINAL_VOLTAGE))
POOL_VOLTAGE = pool_voltage()
MOTOR_TAU = dominant_time_constant()
NET_BUOYANCY_N = (DISPLACED_VOLUME_M3 * SEAWATER_DENSITY - 13.5) * G
COMBINED_INERTIA = tuple(rigid + added for rigid, added in zip(RIGID_INERTIA, ADDED_INERTIA))

def literature_thrusters():
    """CAD loci used to reproduce the published yaw moment. Not the loaded visual frame.

    Horizontal positions and 45° axes follow Wu 2018 Table 4.2, which expands the
    rotation recipe in von Benzon 2022 Table A1. Vertical axes point along −z (up
    in the FRD frame) so a positive command is the stronger, forward bollard direction.
    """
    c = 0.7071067811865476
    horizontal = (
        ("T1 HORIZONTAL", (0.156, 0.111, 0.085), (c, -c, 0.0)),
        ("T2 HORIZONTAL", (0.156, -0.111, 0.085), (c, c, 0.0)),
        ("T3 HORIZONTAL", (-0.156, 0.111, 0.085), (-c, -c, 0.0)),
        ("T4 HORIZONTAL", (-0.156, -0.111, 0.085), (-c, c, 0.0)),
    )
    vertical = tuple(
        (f"T{index + 5} VERTICAL", position, (0.0, 0.0, -1.0))
        for index, position in enumerate(
            ((0.120, 0.218, 0.0), (0.120, -0.218, 0.0),
             (-0.120, 0.218, 0.0), (-0.120, -0.218, 0.0))))
    return horizontal + vertical


def steady_body_force(vehicle, stick):
    """Body wrench (N, N·m) after the motor lag has settled at a constant force demand."""
    motors = vehicle.allocate(np.asarray(stick, dtype=float))
    thrust = demand_thrust(motors, vehicle.supply_voltage, vehicle.p.thruster_max)
    return vehicle.B @ thrust, motors


def scalar_response(endpoint, linear, quadratic, inertia, tau, seconds, dt=0.01, speed0=0.0):
    """One-axis step or coast using the same first-order lag as Vehicle.step."""
    count = int(round(seconds / dt))
    speed = np.empty(count)
    value = float(speed0)
    thrust = 0.0 if speed0 == 0.0 else float(endpoint)
    blend = min(1.0, dt / tau)
    for index in range(count):
        thrust += (endpoint - thrust) * blend
        drag = linear * value + quadratic * value * abs(value)
        value += dt * (thrust - drag) / inertia
        speed[index] = value
    return speed


def time_to_fraction(speed, fraction, dt=0.01):
    """Seconds until |speed| first reaches ``fraction`` of its final sample."""
    target = abs(float(speed[-1])) * fraction
    hits = np.flatnonzero(np.abs(speed) >= target)
    if len(hits) == 0:
        return None
    return float(hits[0]) * dt


def prepared_vehicle(voltage, literature=False):
    """Heavy vehicle at depth, neutral buoyancy, supply fixed. Literature loci are opt-in."""
    from dataclasses import replace

    from .physics import Vehicle
    from .vehicles import get_vehicle_definition

    if literature:
        definition = replace(get_vehicle_definition("bluerov2_heavy"), thrusters=literature_thrusters())
        vehicle = Vehicle(definition=definition)
        vehicle.thrust_map = published_thrust
    else:
        vehicle = Vehicle(model_id="bluerov2_heavy")
    vehicle.supply_voltage = float(voltage)
    vehicle.p.net_buoyancy = 0.0
    vehicle.s.pos[2] = 40.0
    vehicle.seabed_depth = 100.0
    return vehicle


def open_loop(vehicle, stick, seconds, dt=0.01):
    """Hold one normalised wrench command. Returns the settled body force and the 6-speed trace."""
    wrench, motors = steady_body_force(vehicle, stick)
    count = int(round(seconds / dt))
    trace = np.empty((count, 6))
    for index in range(count):
        vehicle.step(dt, motors)
        trace[index, 0:3] = vehicle.s.vel
        trace[index, 3:6] = vehicle.s.omega
    return wrench, trace
