"""Persistent photo subjects for the two inspection routes, in world NED metres."""
import math
import numpy as np
from .ecology import placed_schools


def populate(world, scenario):
    def place(kind, pos, scale, yaw=0):
        entities = world.habitat_entities
        entities.append(dict(id=f"inspection-{kind}-{len(entities)}", kind=kind,
                             pos=list(pos), scale=scale, yaw=yaw, variant=0))

    if scenario == "hull_inspection":
        for n in (40, 44, 49, 54):
            place("barnacle", (n, -9.03, .85), 1)
        for n in (41, 45, 49):
            place("barnacle", (n, -8.64, 7.50), .58)
        for n, depth in ((42.7, 5.50), (43.14, 5.38), (43.4, 5.57)):
            place("grate_fish", (n, -9.028, depth), .9)
        for n in (31, 51, 62):
            place("scuff", (n, -.55, 8.025), 1)
        for n, e in ((12, -4), (37, -12)):
            place("shackle", (n, e, world.seabed_depth), .85)
        schools = placed_schools([dict(home=(2, 0, 4), count=16)], np.random.default_rng(world.world_seed))
        # Start the orbit across the vehicle's bow, just inside visibility at deployment.
        schools[0].update(id="approach-school", home=np.array([-2., .2, 3.6]),
                          pos=np.array([3., .2, 3.6]), phase=0.)
        if world.fish_schools:
            world.fish_schools[0].update(home=np.array([2., -.5, 4.4]),
                                         pos=np.array([7., -.5, 4.4]), phase=0.)
        if len(world.fish_schools) >= 2:
            world.fish_schools[1].update(home=np.array([12.5, -1.3, 8.4]),
                                         pos=np.array([17.5, -1.3, 8.4]), phase=0.)
        world.fish_schools.extend(schools)
    elif scenario.startswith("aquaculture_pen"):
        for cable in world.obstacles:
            if cable.kind == "pen_rope" and cable.name.endswith("-0"):
                pos = .52 * np.asarray(cable.p0) + .48 * np.asarray(cable.p1)
                place("kelp", pos, .72, 65)
        # Holdfasts follow the outside face. The first frond is rooted on the lower lip of the opening.
        for e, depth, scale in ((1.1, 8.02, .85), (3.6, 7.6, .7), (6, 7.3, .78),
                                (8.5, 6.2, .64), (10.7, 5.1, .82), (12.8, 4.0, .66)):
            n = 24 - math.sqrt(18.02 ** 2 - e ** 2)
            place("kelp", (n, e, depth), scale, e * 31)
        for n, e in ((8, 2), (18, -8), (30, -4)):
            place("feed", (n, e, world.seabed_depth), .8)
        schools = placed_schools([dict(home=(-2, 2, 7), count=16)], np.random.default_rng(world.world_seed))
        schools[0].update(id="wild-school-1", wild=True, home=np.array([.0, .6, 7.1]),
                          pos=np.array([5., .6, 7.1]), phase=0.)
        world.fish_schools.extend(schools)
