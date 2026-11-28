"""Offline comparison functions from Q2 (#111) and Q4 (#112)."""
import numpy as np

GLIDE_FRACTION = 1 - np.exp(-1)

def glide_time(time, position):
    """Time to cover (1 - 1/e) of the recorded coast displacement.

    For linear drag this equals the time constant. With quadratic drag it is the
    equivalent first-order time read from the marks, not mass/linear_drag.
    """
    distance = float(position[-1] - position[0])
    if abs(distance) < 1e-9:
        return None
    target = float(position[0] + GLIDE_FRACTION * distance)
    if distance > 0:
        hits = np.where(position >= target)[0]
    else:
        hits = np.where(position <= target)[0]
    if len(hits) == 0:
        return None
    index = int(hits[0])
    if index == 0:
        return 0.0
    span = float(position[index] - position[index-1])
    if span == 0:
        return float(time[index] - time[0])
    frac = (target - float(position[index-1])) / span
    crossed = float(time[index-1] + frac * (time[index] - time[index-1]))
    return crossed - float(time[0])


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



# External comparators in the metric's units. Run conditions are documented in bench.md.
POOL_SOURCE = "https://doi.org/10.3390/jmse10121898"
COMPARATORS = {
    ("surge", "steady"): (.72, POOL_SOURCE, "Table 4, 85 N"),
    ("sway", "steady"): (.63, POOL_SOURCE, "Table 4, 85 N"),
    ("heave", "steady"): (.71, POOL_SOURCE, "Table 4, speed magnitude at 120 N"),
    ("yaw", "steady"): (3.6, POOL_SOURCE, "Table 4, maximum yaw rate"),
    ("coast", "distance_m"): (.30, POOL_SOURCE, "derived from Table A1, release at 0.72 m/s with zero thrust"),
    ("bollard", "steady_N"): (9 * 9.81, "docs/reference/real-rov-research.md", "catalogue, 9 kgf forward"),
}
