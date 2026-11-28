"""Steady umbilical shapes used only to check the lumped-mass tether.

Nothing in the room loop imports this module. The catenary and the uniform-current
cable are integrated on their own, with the same Morison split the solver uses
(normal and tangential drag on diameter times length, wet weight along z-down).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import root

from .physics import G, RHO
from .tether import Tether, TetherParams
from .world import World

# 1 knot in metres per second (international nautical mile).
KNOT_MS = 1852.0 / 3600.0
IDENTITY = np.array([1.0, 0.0, 0.0, 0.0])


@dataclass(frozen=True)
class CableCase:
    """Fixed-end payout used by the calibration note and its tests.

    Both ends sit at the same depth so a neutrally buoyant cable stays submerged.
    The current, when present, is eastward: across the north-south span.
    """

    name: str
    length_m: float
    span_m: float
    depth_m: float
    current_east_m_s: float


# Three cases named in docs/prompts/Q3-tether-parameters.md.
# 0.5 kn is the cross-flow the prompt asks for. Spans keep the buoyant arch
# and the current bow clear of the surface and the seabed.
CALIBRATION_CASES = (
    CableCase("still-50m", 50.0, 40.0, 20.0, 0.0),
    CableCase("cross-50m", 50.0, 40.0, 20.0, 0.5 * KNOT_MS),
    CableCase("cross-100m", 100.0, 70.0, 25.0, 0.5 * KNOT_MS),
)


def case_by_name(name: str) -> CableCase:
    for item in CALIBRATION_CASES:
        if item.name == name:
            return item
    raise KeyError(name)


def ends(case: CableCase) -> tuple[np.ndarray, np.ndarray]:
    spool = np.array([0.0, 0.0, case.depth_m])
    gland = np.array([case.span_m, 0.0, case.depth_m])
    return spool, gland


def specific_weight_n_per_m(params: TetherParams) -> float:
    """Signed wet weight, newtons per metre, positive downward (NED)."""
    return params.wet_weight * G


def catenary_parameter(length_m: float, span_m: float) -> float:
    """Solve 2 a sinh(span / 2a) = length for the catenary parameter a."""
    lo = 1e-6
    hi = 1e6
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        reached = 2.0 * mid * math.sinh(span_m / (2.0 * mid))
        if reached > length_m:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def upward_catenary(case: CableCase, params: TetherParams, samples: int = 201) -> tuple[np.ndarray, np.ndarray]:
    """Inextensible buoyant catenary between level ends, and the gland force.

    The cable is lighter than seawater, so the arch is upward. Horizontal tension
    is |q| a and the end tension is |q| a cosh(span / 2a). The force on the
    vehicle is that tension directed back into the cable.
    """
    if case.current_east_m_s != 0.0:
        raise ValueError("the closed-form catenary is the still-water case")
    length = case.length_m
    span = case.span_m
    parameter = catenary_parameter(length, span)
    station = np.linspace(0.0, length, samples)
    from_crown = parameter * np.arcsinh((station - 0.5 * length) / parameter)
    north = from_crown + 0.5 * span
    lift = parameter * (math.cosh(span / (2.0 * parameter)) - np.cosh(from_crown / parameter))
    points = np.stack([north, np.zeros(samples), case.depth_m - lift], axis=1)
    phi = span / (2.0 * parameter)
    tension = abs(specific_weight_n_per_m(params)) * parameter * math.cosh(phi)
    force = tension * np.array([-1.0 / math.cosh(phi), 0.0, -math.tanh(phi)])
    return points, force


def _drag_per_metre(params: TetherParams, current: np.ndarray, tangent: np.ndarray) -> np.ndarray:
    tangential_speed = float(np.dot(current, tangent))
    tangential = tangential_speed * tangent
    normal = current - tangential
    scale = 0.5 * RHO * params.diameter
    normal_term = params.cd_normal * normal * float(np.linalg.norm(normal))
    tangential_term = params.cd_tangent * tangential * abs(tangential_speed)
    return scale * (normal_term + tangential_term)


def steady_current_cable(case: CableCase, params: TetherParams, steps: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Steady cable in a uniform current. Shoots the spool tension onto the gland.

    Arc length is the unstretched length. Geometry uses the axial stretch T/EA.
    Drag and weight are per unstretched metre, matching the solver's rest length.
    The returned force is the force on the vehicle.
    """
    spool, gland = ends(case)
    current = np.array([0.0, case.current_east_m_s, 0.0])
    weight = np.array([0.0, 0.0, specific_weight_n_per_m(params)])
    step = case.length_m / steps

    def integrate(tension_0: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        position = spool.copy()
        tension = np.array(tension_0, float)
        points = [position.copy()]
        for _ in range(steps):
            magnitude = float(np.linalg.norm(tension))
            tangent = tension / max(magnitude, 1e-9)
            stretch = 1.0 + magnitude / params.ea
            drag = _drag_per_metre(params, current, tangent)
            position = position + stretch * tangent * step
            tension = tension - (drag + weight) * step
            points.append(position.copy())
        return position, tension, np.stack(points)

    def residual(tension_0: np.ndarray) -> np.ndarray:
        end, _tension, _points = integrate(tension_0)
        return end - gland

    chord = gland - spool
    chord = chord / max(float(np.linalg.norm(chord)), 1e-9)
    downstream = np.array([0.0, 1.0, 0.0])
    guesses = (
        chord * 5.0,
        (chord + 0.35 * downstream) * 8.0,
        chord * 20.0 + np.array([0.0, 4.0, -0.5]),
    )
    tension_0 = _solve_tension(residual, guesses)
    end, tension_end, points = integrate(tension_0)
    miss = float(np.linalg.norm(end - gland))
    if miss > 1e-6:
        raise RuntimeError(f"{case.name} steady cable missed the gland by {miss:.3e} m")
    # tension_end is the internal force exerted across the gland by the cable
    # on the outward side. The vehicle feels the opposite.
    return points, -tension_end


def _solve_tension(residual, guesses) -> np.ndarray:
    for guess in guesses:
        solved = root(residual, np.array(guess, float), method="hybr")
        if solved.success and float(np.linalg.norm(solved.fun)) < 1e-6:
            return np.array(solved.x, float)
    raise RuntimeError("steady cable tension did not converge")


class _UniformCurrent:
    """Spatially uniform current. Same contract the validation tests use."""

    z0 = None

    def __init__(self, velocity: np.ndarray):
        self.velocity = np.array(velocity, float)

    def sample_many(self, positions, seabed, t=0.0, bed=None, z0=None):
        count = len(np.atleast_2d(positions))
        return np.tile(self.velocity, (count, 1))

    def sample(self, position, seabed, t=0.0):
        return self.velocity.copy()

    def mean_at(self, depth, seabed):
        return self.velocity.copy()


def _world(case: CableCase) -> World:
    world = World(500.0)
    world.current = _UniformCurrent(np.array([0.0, case.current_east_m_s, 0.0]))
    return world


def settle_on_curve(case: CableCase, points: np.ndarray, seconds: float, dt: float = 0.01) -> Tether:
    """Lay ``points`` (spool to gland), then hold both ends for ``seconds``."""
    spool, gland = ends(case)
    tether = Tether(_world(case), spool, gland, case.length_m, gland_body=np.zeros(3))
    tether.layout(points)
    tether.length = case.length_m
    tether.reel_command("hold")
    steps = int(round(seconds / dt))
    for index in range(steps):
        tether.step(dt, index * dt, gland, IDENTITY, np.zeros(3))
    return tether


def run_from_bight(case: CableCase, seconds: float, dt: float = 0.01) -> Tether:
    """Pay out ``case.length_m`` on the solver's own slack bight and hold the ends."""
    spool, gland = ends(case)
    tether = Tether(_world(case), spool, gland, case.length_m, gland_body=np.zeros(3))
    tether.reel_command("hold")
    steps = int(round(seconds / dt))
    for index in range(steps):
        tether.step(dt, index * dt, gland, IDENTITY, np.zeros(3))
    return tether
