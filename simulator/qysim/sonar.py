"""Read-only vectorized first-return sonar; acoustic parameters are training assumptions."""
import time
import numpy as np
from .physics import q_rot


def scan(world, pos, q, range_m=30.0, noise=0.02, multipath=0.05, seed=None):
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
    distance = np.minimum(distance, range_m)
    intensity = np.clip(strength + rng.normal(0, noise, 256), 0, 1)
    ghost = np.where(rng.random(256) < multipath, np.minimum(range_m, distance * 1.6), range_m)
    return {"timestamp": time.time(), "range_m": range_m, "fov_deg": 120, "beams": 256,
            "distance_m": distance.round(3).tolist(), "intensity": (intensity * 255).astype(int).tolist(),
            "ghost_m": ghost.round(3).tolist()}
