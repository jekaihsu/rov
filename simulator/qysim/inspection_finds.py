"""Photographable survey subjects as habitat entities, in world NED metres.

Hull and pen placements follow the R6 inspection routes. Other outdoor sites get a
small authored set (about eight) near the launch pose or the first working face so
the first medium-quality look already shows something real to fly toward.
"""
from __future__ import annotations

import math

import numpy as np

from .ecology import placed_schools

# Photo capture radii (metres) used by expedition observation_photo.
SUBJECT_RADIUS = {
    "grate_fish": .15, "barnacle": 1.6, "scuff": 1.6, "shackle": .4, "feed": .55,
    "anemone_clump": .55, "rope_coil": .45, "shell_bed": .7, "rust_panel": .9,
}


def _place(world, kind, pos, scale, yaw=0):
    entities = world.habitat_entities
    entities.append(dict(
        id=f"inspection-{kind}-{len(entities)}",
        kind=kind,
        pos=list(np.asarray(pos, float).round(4)),
        scale=float(scale),
        yaw=float(yaw),
        variant=0,
    ))


def _hull(world):
    for n in (40, 44, 49, 54):
        _place(world, "barnacle", (n, -9.03, .85), 1)
    for n in (41, 45, 49):
        _place(world, "barnacle", (n, -8.64, 7.50), .58)
    for n, depth in ((42.7, 5.50), (43.14, 5.38), (43.4, 5.57)):
        _place(world, "grate_fish", (n, -9.028, depth), .9)
    for n in (31, 51, 62):
        _place(world, "scuff", (n, -.55, 8.025), 1)
    for n, e in ((12, -4), (37, -12)):
        _place(world, "shackle", (n, e, world.seabed_depth), .85)
    schools = placed_schools([dict(home=(2, 0, 4), count=16)], np.random.default_rng(world.world_seed), world)
    schools[0].update(id="approach-school", home=np.array([-2., .2, 3.6]),
                      pos=np.array([3., .2, 3.6]), phase=0.)
    if world.fish_schools:
        world.fish_schools[0].update(home=np.array([2., -.5, 4.4]),
                                     pos=np.array([7., -.5, 4.4]), phase=0.)
    if len(world.fish_schools) >= 2:
        world.fish_schools[1].update(home=np.array([12.5, -1.3, 8.4]),
                                     pos=np.array([17.5, -1.3, 8.4]), phase=0.)
    world.fish_schools.extend(schools)


def _pen(world):
    for cable in world.obstacles:
        if cable.kind == "pen_rope" and cable.name.endswith("-0"):
            pos = .52 * np.asarray(cable.p0) + .48 * np.asarray(cable.p1)
            _place(world, "kelp", pos, .72, 65)
    for e, depth, scale in ((1.1, 8.02, .85), (3.6, 7.6, .7), (6, 7.3, .78),
                            (8.5, 6.2, .64), (10.7, 5.1, .82), (12.8, 4.0, .66)):
        n = 24 - math.sqrt(18.02 ** 2 - e ** 2)
        _place(world, "kelp", (n, e, depth), scale, e * 31)
    for n, e in ((8, 2), (18, -8), (30, -4)):
        _place(world, "feed", (n, e, world.seabed_depth), .8)
    schools = placed_schools([dict(home=(-2, 2, 7), count=16)], np.random.default_rng(world.world_seed), world)
    schools[0].update(id="wild-school-1", wild=True, home=np.array([.0, .6, 7.1]),
                      pos=np.array([5., .6, 7.1]), phase=0.)
    world.fish_schools.extend(schools)


def _open_water(world):
    def floor(n, e):
        return float(world.depth_at(np.array([n, e, 0.])))

    # First look (vis 12 m): mid-water colony 2–3 m ahead of spawn, then the recovery lane.
    _place(world, "anemone_clump", (2.2, .35, 2.4), 1.25, 18)
    _place(world, "barnacle", (2.8, 1.1, 2.7), 1.05, 40)
    _place(world, "rope_coil", (3.4, -.2, 3.1), .95, 8)
    _place(world, "shackle", (4.2, .7, 3.6), .8, 55)
    _place(world, "anemone_clump", (5.5, 1.4, 4.2), 1.0, 22)
    _place(world, "shell_bed", (9.2, 4.4, floor(9.2, 4.4)), .95, 12)
    _place(world, "barnacle", (12.4, .6, 5.1), .85, 20)
    _place(world, "seastar", (8.8, 1.2, floor(8.8, 1.2)), .22, 95)


def _jacket(world, key):
    # Keep the first four finds inside ~half the site visibility so the spawn look is not empty fog.
    if key == "cold_open_jacket":
        # start (−12, −9, 11.5), vis 22 m — face the near C leg
        roots = (
            (-10.2, -8.2, 11.7), (-9.4, -7.4, 12.0), (-8.6, -6.6, 11.4), (-7.8, -7.8, 12.3),
            (-7.2, -6.4, 11.6), (-6.0, -7.2, 12.2), (-5.2, -5.5, 11.0), (-4.4, -7.8, 10.8),
        )
    elif key == "incident_jacket":
        # start (0, 0, 12), vis 12 m
        roots = (
            (2.0, -.6, 12.2), (2.8, .8, 11.8), (3.6, -1.2, 12.5), (4.4, .4, 11.5),
            (-7.2, -6.4, 11.6), (-6.0, -7.2, 12.2), (-5.2, -5.5, 11.0), (-4.4, -7.8, 10.8),
        )
    elif key == "tether_untangle":
        # start (8, 2.8, 10), vis 9 m — hang mid-water near the wrap
        roots = (
            (7.2, 1.6, 10.2), (6.4, 2.2, 9.8), (6.8, 3.6, 10.4), (5.5, 2.0, 9.5),
            (4.2, 1.0, 9.0), (3.0, 2.5, 8.5), (2.0, .5, 8.0), (1.0, 3.0, 7.5),
        )
    else:
        # jacket_inspection start (0, 0, 3), vis 8 m — jacket legs sit past the fog wall
        roots = (
            (2.1, .4, 3.2), (2.8, -.7, 3.5), (3.5, .9, 3.9), (4.2, -.3, 4.3),
            (5.0, .6, 4.8), (6.0, -1.0, 5.4), (8.5, -1.2, 6.5), (12.0, -2.0, 8.0),
        )
    kinds = ("anemone_clump", "barnacle", "rope_coil", "anemone_clump",
             "barnacle", "shackle", "anemone_clump", "rope_coil")
    for kind, pos in zip(kinds, roots):
        _place(world, kind, pos, 1.15 if kind == "anemone_clump" else .9 if kind != "shackle" else .7,
               pos[0] * 9)


def _wreck(world, key):
    bed = world.seabed_depth
    if key == "incident_wreck":
        # start (8, 2.8, 128), vis 4 m
        items = (
            ("rust_panel", (8.8, 2.5, 128.3), 1.2),
            ("shackle", (9.4, 2.0, 128.6), .8),
            ("rope_coil", (9.8, 3.2, 128.5), .95),
            ("barnacle", (10.2, 2.4, 128.9), 1.0),
            ("anemone_clump", (10.8, 1.6, 129.2), .9),
            ("shell_bed", (15.0, -2.5, bed), .85),
            ("rust_panel", (20.5, -4.0, bed - .1), 1.05),
            ("shackle", (6.2, -1.5, 127.2), .6),
        )
    elif key == "korean_castle":
        # start (0, 0, 4), vis 10 m
        items = (
            ("rust_panel", (2.0, .6, 4.3), 1.2),
            ("shackle", (2.6, -.5, 4.6), .8),
            ("rope_coil", (3.2, .9, 5.0), .95),
            ("barnacle", (4.0, -.2, 5.4), 1.0),
            ("anemone_clump", (5.0, 1.2, 5.8), .95),
            ("shell_bed", (44.0, 14.0, bed), .9),
            ("rust_panel", (48.5, 18.2, 24.0), 1.05),
            ("shackle", (49.2, 20.4, 24.2), .65),
        )
    else:
        # wreck_survey start (0, 0, 3), vis 4 m — subjects must sit inside the murk
        items = (
            ("rust_panel", (1.6, .4, 3.3), 1.25),
            ("shackle", (2.1, -.5, 3.5), .85),
            ("rope_coil", (2.5, .7, 3.7), 1.0),
            ("barnacle", (2.9, -.2, 3.9), 1.05),
            ("anemone_clump", (3.3, .5, 4.1), 1.0),
            ("shell_bed", (44.0, 14.0, bed), .9),
            ("rust_panel", (48.5, 18.2, 24.0), 1.05),
            ("shackle", (49.2, 20.4, 24.2), .65),
        )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, pos[0] * 7)


def _reef(world, key):
    if key == "seagrass_meadow":
        # start (0, 0, 2), vis 12 m — mid-water colour first, bed subjects later
        items = (
            ("anemone_clump", (2.2, .5, 2.6), 1.15),
            ("rope_coil", (2.8, -.6, 3.0), .95),
            ("shackle", (3.4, .8, 3.4), .7),
            ("barnacle", (4.0, -.3, 3.8), .9),
            ("shell_bed", (5.2, -1.4, 7.6), .9),
            ("seastar", (6.4, -2.8, 7.9), .2),
            ("anemone_clump", (10.5, -6.0, 7.1), .85),
            ("shell_bed", (24.0, 7.5, 7.4), .85),
        )
    else:
        # coral_reef start (0, 0, 3), vis 18 m
        items = (
            ("anemone_clump", (2.2, -.5, 3.4), 1.3),
            ("barnacle", (2.8, .7, 3.7), 1.05),
            ("seastar", (3.3, -.9, 4.0), .28),
            ("shell_bed", (3.8, .4, 4.3), 1.05),
            ("anemone_clump", (5.5, -1.8, 5.2), 1.1),
            ("shackle", (6.5, .6, 5.8), .75),
            ("barnacle", (11.0, -4.5, 9.0), .85),
            ("seastar", (19.5, -13.0, 11.0), .18),
        )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, pos[1] * 11)


def _monopile(world):
    # start (0, 0, 3), vis 10 m — pile is 15 m out; put colour in the launch cone
    items = (
        ("anemone_clump", (2.3, .4, 3.3), 1.2),
        ("barnacle", (3.0, -.8, 3.7), 1.0),
        ("rope_coil", (3.6, .9, 4.1), .95),
        ("shackle", (4.2, -.3, 4.5), .75),
        ("anemone_clump", (5.5, -1.2, 5.2), 1.0),
        ("barnacle", (7.0, 1.0, 6.0), .9),
        ("rope_coil", (10.0, -2.0, 8.0), .8),
        ("shell_bed", (2.5, -1.5, world.seabed_depth), .8),
    )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, pos[0] * 5)


def _sonar(world):
    bed = world.seabed_depth
    # start (0, 0, 13), vis 0.8 m — only arm's-length subjects read without sonar
    items = (
        ("rust_panel", (.45, .2, 13.15), 1.1),
        ("shackle", (.55, -.25, 13.05), .7),
        ("rope_coil", (.35, .35, 13.25), .85),
        ("barnacle", (.6, .05, 12.95), .9),
        ("anemone_clump", (5.8, 5.5, 14.6), .85),
        ("shell_bed", (3.0, 1.0, bed), .8),
        ("shackle", (16.4, 5.2, 12.6), .55),
        ("shell_bed", (20.0, 6.5, bed), .85),
    )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, 30)


def _incident_shallow(world, key):
    bed = world.seabed_depth
    table = {
        # start (8, 0, 11.55), vis 3 m
        "incident_silt": (
            ("rope_coil", (8.4, .3, 11.4), 1.0),
            ("anemone_clump", (8.7, -.5, 11.6), 1.05),
            ("shackle", (8.2, .7, 11.2), .7),
            ("barnacle", (7.6, -.3, 11.0), .9),
            ("shell_bed", (7.5, .5, bed), .9),
            ("rope_coil", (5.2, -2.4, bed), .75),
            ("shell_bed", (1.5, -1.5, bed), .8),
            ("shackle", (6.0, 2.5, bed), .5),
        ),
        # start (7, 0, 10), vis 6 m
        "incident_compass": (
            ("barnacle", (7.8, .5, 10.2), 1.0),
            ("anemone_clump", (8.2, -.6, 10.4), 1.05),
            ("rope_coil", (8.6, .8, 10.6), .9),
            ("shackle", (7.4, -.4, 9.8), .7),
            ("barnacle", (9.5, -2.0, 12.0), .85),
            ("anemone_clump", (4.0, 2.0, 8.5), .8),
            ("shell_bed", (2.0, -1.5, bed), .8),
            ("shackle", (8.0, -5.0, 15.2), .55),
        ),
        # start (6, 0, 8), vis 8 m
        "incident_current": (
            ("barnacle", (6.6, .4, 8.2), 1.0),
            ("anemone_clump", (7.0, -.5, 8.4), 1.05),
            ("rope_coil", (7.4, .7, 8.6), .9),
            ("shackle", (6.2, -.3, 7.9), .7),
            ("anemone_clump", (1.9, -.6, 8.9), .8),
            ("shell_bed", (11.0, -1.0, bed), .85),
            ("barnacle", (0.8, 2.0, 12.5), .75),
            ("shackle", (4.5, -2.5, bed), .55),
        ),
    }
    for kind, pos, scale in table[key]:
        _place(world, kind, pos, scale, pos[0] * 6)


def populate(world, scenario):
    if scenario == "hull_inspection":
        _hull(world)
    elif scenario.startswith("aquaculture_pen"):
        _pen(world)
    elif scenario == "open_water":
        _open_water(world)
    elif scenario in ("jacket_inspection", "cold_open_jacket", "incident_jacket", "tether_untangle"):
        _jacket(world, scenario)
    elif scenario in ("wreck_survey", "korean_castle", "incident_wreck"):
        _wreck(world, scenario)
    elif scenario in ("coral_reef", "seagrass_meadow"):
        _reef(world, scenario)
    elif scenario == "monopile_current":
        _monopile(world)
    elif scenario == "sonar_search":
        _sonar(world)
    elif scenario in ("incident_silt", "incident_compass", "incident_current"):
        _incident_shallow(world, scenario)
