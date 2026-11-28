"""Read-only vectorized first-return sonar; acoustic parameters are training assumptions."""
import time
import numpy as np
from .physics import q_rot


# X1 暫定 engineering assumptions for the existing 120 degree training fan.
DEFAULT_RANGE_M = 30.0
DEFAULT_NOISE = 0.02
DEFAULT_MULTIPATH = 0.05
RANGE_BIN_M = 0.05
SIDELOBE_OFFSET_BEAMS = 4
SIDELOBE_GAIN = 0.12


def scan(world, pos, q, range_m=DEFAULT_RANGE_M, noise=DEFAULT_NOISE, multipath=DEFAULT_MULTIPATH,
         seed=None, ideal=False):
    """120 degree, 256 beam fan. First surfaces occlude all objects behind them."""
    range_m = float(range_m)
    if not 2 <= range_m <= 50 or not 0 <= noise <= 1 or not 0 <= multipath <= 1:
        raise ValueError("invalid sonar settings")
    rng = np.random.default_rng(seed)
    angles = np.linspace(-np.pi / 3, np.pi / 3, 256)
    rotation = np.column_stack([q_rot(q, axis) for axis in np.eye(3)])
    directions = np.column_stack((np.cos(angles), np.sin(angles), np.zeros(256))) @ rotation.T
    distance = np.full(256, 0.45)
    strength = np.zeros(256)
    active = np.ones(256, dtype=bool)
    candidates = world.near(pos - range_m, pos + range_m)
    for _ in range(256):
        ids = np.flatnonzero(active)
        if not len(ids):
            break
        points = pos + directions[ids] * distance[ids, None]
        gap, normals, _ = world.sdf_many(points, candidates)
        hit = gap < 0.03
        found = ids[hit]
        incidence = np.abs(np.sum(normals[hit] * directions[found], axis=1))
        strength[found] = incidence * np.exp(-distance[found] / 35)
        active[found] = False
        moving = ids[~hit]
        distance[moving] += np.maximum(0.02, gap[~hit] * 0.8)
        active[distance >= range_m] = False
    distance[active] = range_m
    distance = np.minimum(distance, range_m)
    extras = {}
    if not ideal:
        hit = distance < range_m
        distance[hit] = np.minimum(range_m, np.rint(distance[hit] / RANGE_BIN_M) * RANGE_BIN_M)
        # Display the stronger of two off-axis echoes at its own range. Never wrap fan edges.
        offset = SIDELOBE_OFFSET_BEAMS
        padded = np.pad(strength, offset)
        left = padded[:-2 * offset]
        right = padded[2 * offset:]
        source = np.arange(len(distance)) + np.where(left > right, -offset, offset)
        level = np.maximum(left, right) * SIDELOBE_GAIN
        side = np.where(level > 0, distance[source.clip(0, len(distance) - 1)], range_m)
        extras = {"sidelobe_m": side.round(3).tolist(), "sidelobe_intensity": (255 * level).astype(int).tolist()}
    intensity = np.clip(strength + rng.normal(0, noise, 256), 0, 1)
    ghost = np.where(rng.random(256) < multipath, np.minimum(range_m, distance * 1.6), range_m)
    return {**extras, "timestamp": time.time(), "range_m": range_m, "fov_deg": 120, "beams": 256,
            "distance_m": distance.round(3).tolist(), "intensity": (intensity * 255).astype(int).tolist(),
            "ghost_m": ghost.round(3).tolist()}


def snapshot(room, sim):
    """Freeze dynamic targets before yielding; static fields remain shared read-only."""
    from .world import Cylinder, World
    world = World(sim.world.seabed_depth)
    world.terrain = sim.world.terrain
    world.obstacles = list(sim.world.obstacles)
    world._obstacle_bounds = None
    for other in room.vehicles.values():
        if other is not sim:
            p = other.vehicle.s.pos.copy()
            world.obstacles.append(Cylinder("vehicle", p, p, 0.4))
        points = other.tether.x.copy()
        for a, b in zip(points[:-1], points[1:]):
            if np.linalg.norm(a - sim.vehicle.s.pos) > 0.8:
                world.obstacles.append(Cylinder("tether", a, b, 0.015))
    for obj in getattr(sim.world, "work_objects", {}).values():
        p = obj["pos"].copy()
        world.obstacles.append(Cylinder("work", p, p, obj["radius"]))
    for fish in sim.world.fish_schools:
        p = fish["pos"].copy()
        world.obstacles.append(Cylinder("fish", p, p, 0.15))
    return world, sim.vehicle.s.pos.copy(), sim.vehicle.s.q.copy()


_EXECUTOR = None


def submit_scan(world, pos, q, settings):
    """Separate processes prevent scan work from contending for the physics GIL."""
    import asyncio
    import functools
    from concurrent.futures import ProcessPoolExecutor
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ProcessPoolExecutor(max_workers=3)
    return asyncio.get_running_loop().run_in_executor(
        _EXECUTOR, functools.partial(scan, world, pos, q, **settings))
