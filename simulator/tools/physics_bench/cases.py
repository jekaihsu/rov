"""Offline 100 Hz trials using production hull, allocator, controller, cable and contact solvers."""
from dataclasses import dataclass
from time import perf_counter_ns, thread_time_ns

import numpy as np

from qysim.controller import FlightController
from qysim.engine import Simulator
from qysim.physics import KNOT, Vehicle
from qysim.sensors import SensorConfig
from qysim.tether import Tether
from qysim.world import CurrentProfile, Cylinder, World
from .reference import glide_time, scalar_response

DT = 0.01
SEED = 1947


@dataclass
class Trace:
    name: str
    columns: tuple
    rows: np.ndarray
    metrics: dict


def trace(name, columns, rows, **metrics):
    rows = np.asarray(rows)
    if not np.isfinite(rows).all() or not np.isfinite(list(metrics.values())).all():
        raise ValueError(f"{name}: non-finite observation")
    return Trace(name, columns, rows, metrics)


def hull():
    v = Vehicle()
    v.s.pos[2] = 20
    v.seabed_depth = 100
    return v


def kinetic(v):
    return 0.5 * (v.M @ (v.s.vel ** 2) + v.I @ (v.s.omega ** 2))


def steps():
    # von Benzon 2022 Table A1; Eq. 19 dominant pole approximation from Q2.
    for axis, name, force, linear, quad, mass in (
        (0, "surge", 85, 13.7, 141, 19.86), (1, "sway", 85, 0, 217, 20.62),
        (2, "heave", 120, 33, 190, 32.18), (5, "yaw", 20, 0, 1.5, .592)
    ):
        v = hull()
        motors = v.allocate(np.eye(6)[axis])
        rows = []
        for i, analogue in enumerate(scalar_response(force, linear, quad, mass, .076, 8, DT)):
            v.step(DT, motors)
            speed = v.s.vel[axis] if axis < 3 else v.s.omega[2]
            rows.append(((i + 1) * DT, speed, analogue))
        values = np.array(rows)[:, 1]
        steady = values[-100:].mean()
        rise = (np.flatnonzero(values >= 0.632 * steady)[0] + 1) * DT
        unit = "rad_s" if axis == 5 else "m_s"
        yield trace(name, ("time_s", "body_" + unit, "analogue_" + unit), rows, steady=steady, rise63_s=rise)
        if axis == 0:
            x = v.s.pos[0]
            coast = [(0., v.s.vel[0], 0.)]
            for i in range(2000):
                v.step(DT, np.zeros_like(motors))
                coast.append(((i + 1) * DT, v.s.vel[0], v.s.pos[0] - x))
            t, speed, distance = np.asarray(coast).T
            yield trace("coast", ("time_s", "speed_m_s", "distance_m"), coast, distance_m=distance[-1],
                        glide_s=glide_time(t, distance), speed_1s=speed[100])


def controlled(name):
    v = hull()
    c = FlightController(v)
    target = 1 if name == "depth" else np.pi / 4
    c.depth_hold = 21 if name == "depth" else 20
    if name == "station":
        v.current_ned[1] = 0.4
    rows = []
    for i in range(1500):
        motors = c.update(DT, {}, "A", False, True, target if name == "heading" else 0,
                          assist=2 if name == "station" else 0, dvl_valid=True)
        v.step(DT, motors)
        if name == "station":
            value = np.linalg.norm(v.s.pos[:2])
        elif name == "depth":
            value = v.s.pos[2] - 20
        else:
            value = v.euler[2]
        rows.append(((i + 1) * DT, value))
    values = np.asarray(rows)[:, 1]
    if name == "station":
        return trace(name, ("time_s", "horizontal_error_m"), rows, peak_m=max(values),
                     rms_m=np.sqrt(np.mean(values ** 2)), final_m=values[-1])
    outside = np.flatnonzero(abs(values - target) > .05 * target)
    settled = (outside[-1] + 2) * DT if outside.size else DT
    if settled > rows[-1][0] - 1:
        raise ValueError(f"{name}: did not remain within 5% for the last second")
    return trace(name, ("time_s", "displacement_m" if name == "depth" else "heading_rad"), rows,
                 overshoot_pct=max(0., 100 * (max(values) / target - 1)), settling_s=settled,
                 final_error=target - values[-1])


def turning():
    v = hull()
    c = FlightController(v)
    rows = []
    for i in range(1600):
        pilot = {"yaw": .6, "surge": 0 if i < 800 else .5}
        motors = c.update(DT, pilot, "A", False, True)
        v.step(DT, motors)
        rows.append(((i + 1) * DT, *v.s.pos[:2], v.euler[2]))
    t, n, e, heading = np.asarray(rows).T
    rate = np.gradient(np.unwrap(heading), DT)
    radius = np.hypot(np.gradient(n, DT), np.gradient(e, DT))[-100:] / abs(rate[-100:])
    return trace("turn", ("time_s", "north_m", "east_m", "heading_rad"), rows,
                 pivot_rad_s=rate[699:799].mean(), underway_radius_m=radius.mean())


def bollard():
    v = hull()
    motors = v.allocate(np.eye(6)[0])
    rows = []
    for i in range(200):
        v.step(DT, motors)
        rows.append(((i + 1) * DT, (v.B @ v.s.thrust)[0]))
        v.s.pos[:] = (0, 0, 20)
        v.s.q[:] = (1, 0, 0, 0)
        v.s.vel.fill(0)
        v.s.omega.fill(0)
    return trace("bollard", ("time_s", "surge_reaction_N"), rows, steady_N=rows[-1][1])


def cable(length, current):
    v = hull()
    v.s.pos[:] = (4, 0, 3)
    w = World()
    knots = current / KNOT
    w.current = CurrentProfile(surface_kn=knots, mid_kn=knots, bottom_kn=knots, seed=SEED)
    gland = np.array(v.definition.gland_body)
    line = Tether(w, np.zeros(3), v.s.pos + gland, length, gland_body=gland)
    line.settle(2, v.s.pos, v.s.q)
    rows = []
    for i in range(1000):
        w.current.step_gust(DT)
        v.current_ned = w.current_at(v.s.pos)
        wrench = line.step(DT, i * DT, v.s.pos, v.s.q, v.world_velocity())
        v.step(DT, np.zeros_like(v.s.thrust), wrench)
        rows.append(((i + 1) * DT, line.tension_rov, np.hypot(v.s.pos[0] - 4, v.s.pos[1])))
    if line.broken:
        raise ValueError("cable broke")
    data = np.asarray(rows)
    return trace(f"cable_{length}m_{current}ms", ("time_s", "gland_N", "drift_m"), rows,
                 peak_N=max(data[:, 1]), mean_N=data[:, 1].mean(), drift_m=data[-1, 2])


def impact(speed):
    v = hull()
    w = World()
    w.obstacles = [Cylinder("pile", (1, 0, 0), (1, 0, 30), .4)]
    v.s.vel[0] = speed
    s = v.s
    spheres = [(centre, v.definition.hull_radius) for centre in v.definition.hull_centres]
    incident = None
    rebound = None
    rows = []
    for i in range(200):
        wrench = w.vehicle_contact(i * DT, s.pos, s.q, s.vel, s.omega, hull_spheres=spheres)
        if np.any(wrench) and incident is None:
            incident = kinetic(v)
        if incident is not None and rebound is None and not np.any(wrench):
            rebound = -v.world_velocity()[0]
            loss = 1 - kinetic(v) / incident
        v.step(DT, np.zeros_like(s.thrust), wrench)
        rows.append(((i + 1) * DT, v.world_velocity()[0], kinetic(v), wrench[0]))
    if rebound is None or rebound <= 0:
        raise ValueError("no completed rebound")
    return trace(f"pile_{speed}ms", ("time_s", "north_m_s", "kinetic_J", "contact_N"), rows,
                 rebound_m_s=rebound, loss_fraction=loss)


def stability():
    v = hull()
    v.s.vel[0] = 1.5
    v.p.net_buoyancy = 0  # unforced horizontal coast; no gravitational work
    rows = []
    energy0 = kinetic(v)
    last = energy0
    growth = 0.
    zeros = np.zeros_like(v.s.thrust)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for i in range(60000):
            v.step(DT, zeros)
            state = v.s
            if not np.isfinite(np.r_[state.pos, state.q, state.vel, state.omega, state.accel, state.thrust]).all():
                raise ValueError(f"non-finite state at step {i}")
            energy = kinetic(v)
            growth = max(growth, energy - last)
            last = energy
            rows.append(((i + 1) * DT, energy, state.pos[0]))
    return trace("stability", ("time_s", "kinetic_J", "north_m"), rows, max_gain_J=growth,
                 residual_fraction=last / energy0, distance_m=state.pos[0])


def open_water():
    sim = Simulator(seed=SEED, sensor_config=SensorConfig(ideal=False))
    sim.apply_viewer_rc({"rc_lock": 0, "keep_depth": 1, "assist": 2})
    return sim


def coupled_stability():
    sim = open_water()
    rows = np.empty((60000, 5))
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for i, row in enumerate(rows):
            # Four seconds of thrust alternating with six seconds holding in current.
            if i % 1000 in (0, 400):
                channel = 1600 if i % 2000 < 1000 else 1400
                sim.apply_viewer_rc({"right_ud": channel if i % 1000 == 0 else 1500}, partial=True)
            sim.step()
            s = sim.vehicle.s
            cable = sim.tether
            if not (np.isfinite(cable.x).all() and np.isfinite(cable.v).all() and
                    np.isfinite(np.r_[s.pos, s.vel, s.omega, s.accel, s.q, s.thrust]).all()):
                raise ValueError(f"non-finite coupled state at step {i}")
            if cable.broken or abs(np.linalg.norm(s.q) - 1) > 1e-8:
                raise ValueError(f"invalid coupled state at step {i}")
            row[:] = ((i + 1) * DT, kinetic(sim.vehicle), s.pos[2], np.linalg.norm(s.pos[:2]), cable.tension_rov)
    return trace("coupled_stability", ("time_s", "hull_kinetic_J", "depth_m", "excursion_m", "gland_N"),
                 rows, peak_J=max(rows[:, 1]), max_excursion_m=max(rows[:, 3]), peak_N=max(rows[:, 4]))


def timing():
    sim = open_water()
    for _ in range(100):
        sim.step()
    rows = []
    for i in range(500):
        wall = perf_counter_ns()
        cpu = thread_time_ns()
        sim.step()
        rows.append(((i + 1) * DT, (thread_time_ns() - cpu) / 1e6, (perf_counter_ns() - wall) / 1e6))
    return trace("timing", ("time_s", "thread_ms", "wall_ms"), rows,
                 mean_cpu_ms=np.mean(np.asarray(rows)[:, 1]))


def cases():
    yield from steps()
    yield turning()
    for name in ("depth", "heading", "station"):
        yield controlled(name)
    yield bollard()
    for length in (6, 10):
        for current in (.25, .5):
            yield cable(length, current)
    for speed in (.6, 1.2):
        yield impact(speed)
    yield stability()
    yield coupled_stability()
    yield timing()
