"""Seeded, bounded marine habitats shared by physics and all viewers.

These are real-time approximations, not species population or CFD models.
Distances are metres in NED; terrain samples are *depths*, not elevations.
"""
from __future__ import annotations

import math
import numpy as np


class SeabedTerrain:
    def __init__(self, depth: float, seed: int, relief: float = 0.0):
        self.origin = np.array([-100.0, -100.0])
        self.spacing = 5.0
        axis = np.arange(41) * self.spacing - 100
        n, e = np.meshgrid(axis, axis, indexing="ij")
        phase = np.random.default_rng(seed).uniform(0, 2 * math.pi, 3)
        mound = (0.5 + 0.25 * np.sin(n * .065 + phase[0]) + .25 * np.cos(e * .071 + phase[1]))
        # Relief only rises above the old flat-floor safety clamp.
        self.depths = depth - relief * mound
        self.relief = relief

    def sample_many(self, positions):
        xy = np.asarray(positions, float)[:, :2]
        grid = np.clip((xy - self.origin) / self.spacing, 0, 39.999999)
        i = np.floor(grid).astype(int)
        a, b = (grid - i).T
        x, y = i.T
        d00, d10 = self.depths[x, y], self.depths[x + 1, y]
        d01, d11 = self.depths[x, y + 1], self.depths[x + 1, y + 1]
        depth = (1-a)*(1-b)*d00 + a*(1-b)*d10 + (1-a)*b*d01 + a*b*d11
        dn = ((1-b)*(d10-d00) + b*(d11-d01)) / self.spacing
        de = ((1-a)*(d01-d00) + a*(d11-d10)) / self.spacing
        normal = np.column_stack((dn, de, -np.ones(len(x))))
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        return depth, normal

    def as_dict(self):
        return {"origin": self.origin.tolist(), "spacing": self.spacing,
                "size": [41, 41], "depths": self.depths.round(4).tolist()}


def create_habitat(world, biome: str, seed: int, keep_clear=()):
    """Generate once on the server; no cross-language PRNG agreement is needed."""
    from .world import Cylinder
    rng = np.random.default_rng(np.random.SeedSequence([seed, 8271]))
    entities = []
    schools = []
    reef = biome == "reef"
    grass = biome == "seagrass"
    counts = {"rock": 18, "coral": 72 if reef else 0,
              "seastar": 28 if reef else 18, "kelp": 0 if reef or grass else 90,
              "seagrass": 260 if grass else 35 if reef else 0}
    exclusion = [np.asarray(p, float) for p in keep_clear]
    for kind, count in counts.items():
        for _ in range(count):
            for attempt in range(40):
                xy = rng.uniform([-12, -35], [62, 35])
                if any(np.linalg.norm(xy - p[:2]) < 4.0 for p in exclusion):
                    continue
                z = float(world.terrain.sample_many(np.array([[*xy, 0]]))[0][0])
                pos = np.array([*xy, z])
                if any(o.sdf(pos - [0, 0, .5])[0] < 2.0 for o in world.obstacles):
                    continue
                break
            else:
                continue
            scale = float(rng.uniform(.35, 1.0) if kind == "coral" else
                          rng.uniform(.65, 1.6) if kind == "rock" else
                          rng.uniform(.10, .23) if kind == "seastar" else rng.uniform(.5, 1.5))
            eid = f"{kind}-{len(entities)}"
            # Static life is clustered by a common habitat envelope, and rooted to the terrain.
            entities.append({"id": eid, "kind": kind, "pos": pos.round(4).tolist(),
                             "scale": round(scale, 4), "yaw": float(rng.uniform(0, 360)),
                             "variant": int(rng.integers(0, 3))})
            if kind in ("rock", "coral"):
                r = scale * (.6 if kind == "rock" else .45)
                # Capsule proxy kept entirely inside the visible procedural mound/colony envelope.
                world.obstacles.append(Cylinder(eid, tuple(pos - [0, 0, r]),
                                                tuple(pos - [0, 0, max(r, scale-r)]), r, "habitat"))
    for k in range(4):
        for _ in range(100):
            pos = np.array([rng.uniform(6, 48), rng.uniform(-20, 20), rng.uniform(3, max(4, world.seabed_depth - 4))])
            if world.sdf(pos)[0] > 3.0:
                break
        else:
            continue
        schools.append({"id": f"school-{k}", "pos": pos, "home": pos.copy(),
                        "vel": np.array([.3, 0, 0]), "count": 24 + int(rng.integers(0, 16)),
                        "phase": float(rng.uniform(0, 2*math.pi)), "variant": k % 3})
    return entities, schools


def step_schools(world, dt, vehicles):
    for school in world.fish_schools:
        p, phase = school["pos"], school["phase"]
        angle = world.time * .06 + phase
        target = school["home"] + np.array([math.cos(angle)*5, math.sin(angle)*5, math.sin(angle*.7)*.6])
        desired = (target - p) * .25
        desired += world.current.sample(p, world.seabed_depth, world.time) * .35
        for vehicle in vehicles:
            away = p - np.asarray(vehicle["pos"], float)
            distance = np.linalg.norm(away)
            if distance < 5:
                desired += away / max(distance, .1) * (5-distance) * .4
        d, normal, _ = world.sdf(p)
        if d < 3:
            desired += normal * (3-d) * 1.5
        if p[2] < 2:
            desired[2] += 2-p[2]
        speed = np.linalg.norm(desired)
        desired *= min(1.0, 1.4 / max(speed, 1e-9))
        school["vel"] += (desired - school["vel"]) * min(1, dt * 2)
        nxt = p + school["vel"] * dt
        nd, nn, _ = world.sdf(nxt)
        if nd < 2.0:
            nxt += nn * (2.0-nd)
        nxt[2] = max(1.5, nxt[2])
        school["pos"] = nxt
