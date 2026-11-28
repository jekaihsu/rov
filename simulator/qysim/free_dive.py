"""A slack-water visit to the fictional wreck; the mission retains its original layout."""
import math

import numpy as np

from .scenarios import korean_castle
from .world import CurrentProfile, Cylinder


def wreck_visit():
    site = korean_castle()
    wreck = site.obstacles[0]
    site.key = "free_dive_wreck"
    site.start_pos = tuple(wreck.world_point((4., 1., 12.3)))
    site.start_heading_deg = 90.
    site.spool_pos = tuple(wreck.world_point((-5., 1., 32.)))
    site.tether_length = 25.
    site.water_type = "oceanic"
    site.visibility_m = 18.
    site.current = CurrentProfile(.15, 30, .12, 35, .08, 40, .05)
    site.objectives = []

    # Detached screw astern. The renderer already builds a pitched blade between paired capsule edges.
    hub = np.array([155., 0., 2.6])
    def part(name, start, end, radius):
        return Cylinder("Wreck propeller " + name, tuple(wreck.world_point(start)),
                        tuple(wreck.world_point(end)), radius, "propeller")

    site.obstacles.append(part("hub", hub - [.4, 0, 0], hub + [.4, 0, 0], .45))
    for index in range(4):
        angle = math.radians(45 + 90 * index)
        radial = np.array([0., math.cos(angle), math.sin(angle)])
        chord = np.array([.5, -.866 * math.sin(angle), .866 * math.cos(angle)])
        for suffix, sign in (("a", -1), ("b", 1)):
            base = hub + sign * .26 * chord
            site.obstacles.append(part(f"blade {index + 1}{suffix}", base, base + 2.3 * radial, .26))
    return site
