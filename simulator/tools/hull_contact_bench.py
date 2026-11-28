"""Measure complete vehicle contact steps at representative surfaces (fixed inputs, warmed geometry)."""
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qysim import scenarios
from qysim.hull_contact import HullContact
from qysim.physics import Vehicle
from qysim.world import ShipHull, World


def run(site, start, end, samples=300):
    sc = scenarios.build(site, 7)
    world = World(sc.seabed_depth)
    world.obstacles = sc.obstacles
    world.configure_habitat(sc.biome, 7, keep_clear=[sc.start_pos, sc.spool_pos])
    vehicle = Vehicle()
    hull = HullContact(vehicle)
    durations = []
    for i in range(samples + 10):
        vehicle.s.pos = end.copy()
        vehicle.s.vel = (end - start) / .01
        vehicle.s.omega.fill(0.)
        hull.active.clear()
        before = time.perf_counter_ns()
        hull.resolve(world, vehicle, start, vehicle.s.q, .01, i * .01, "bench")
        elapsed = (time.perf_counter_ns() - before) / 1e6
        if i >= 10:
            durations.append(elapsed)
    print(f"{site:22} {np.mean(durations):7.3f} {np.percentile(durations, 95):7.3f} "
          f"{max(durations):7.3f}   {world.events[-1].obstacle if world.events else 'clear'}")


def main():
    ship = next(o for o in scenarios.build("hull_inspection", 7).obstacles if isinstance(o, ShipHull))
    side = ship.hp["beam"] / 2
    wreck = scenarios.build("korean_castle", 7).obstacles[0]
    jacket = scenarios.build("jacket_inspection", 7).obstacles[0]
    # Impact at mid-depth from a clear pose; the final case also stresses recovery
    # from a deliberately invalid initial pose below the floor inside the pile.
    middle = (np.array(jacket.p0) + jacket.p1) / 2
    cases = [
        ("open_water", (0, 0, 4), (.01, 0, 4)),
        ("tutorial_pool", (11.55, 0, 4), (11.60, 0, 4)),
        ("jacket_inspection", middle - [1.06, 0., 0.], middle - [.99, 0., 0.]),
        ("aquaculture_pen", (5.56, 1., 4.), (5.66, 1., 4.)),
        ("hull_inspection", ship.world_point((0, side + .35, 2)), ship.world_point((0, side + .25, 2))),
        ("korean_castle", wreck.world_point((75, -9.9, 6)), wreck.world_point((75, -9.6, 6))),
        ("jacket_inspection", jacket.p1, jacket.p1),
    ]
    print("site                   mean ms  p95 ms  max ms   contact")
    for site, start, end in cases:
        run(site, np.asarray(start, float), np.asarray(end, float))


if __name__ == "__main__":
    main()
