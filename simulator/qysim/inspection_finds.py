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

    # First look faces the north drop and the nearby bank colony.
    _place(world, "anemone_clump", (12.4, .6, 5.1), .9, 20)
    _place(world, "barnacle", (13.05, 1.15, 6.8), .75, 40)
    _place(world, "shell_bed", (9.2, 4.4, floor(9.2, 4.4)), .95, 12)
    _place(world, "shackle", (10.6, 9.4, floor(10.6, 9.4)), .7, 55)
    _place(world, "rope_coil", (1.8, 9.6, floor(1.8, 9.6)), .8, 8)
    _place(world, "anemone_clump", (11.8, 18.5, floor(11.8, 18.5) - .2), 1.0, 70)
    _place(world, "barnacle", (12.6, -15.2, floor(12.6, -15.2) - .15), .95, 210)
    _place(world, "seastar", (8.8, 1.2, floor(8.8, 1.2)), .18, 95)


def _jacket(world, key):
    # Anodes and the near face of C/A legs sit in the launch cone for cold open and jacket work.
    roots = (
        (-8.2, -7.1, 12.0), (-6.4, -8.0, 11.4), (4.2, -7.6, 12.2), (6.1, -5.8, 10.8),
        (-5.1, 5.4, 11.2), (3.8, 6.2, 9.6), (-1.2, -1.4, 7.5), (8.4, -2.2, 13.5),
    )
    kinds = ("barnacle", "anemone_clump", "barnacle", "anemone_clump",
             "barnacle", "anemone_clump", "shackle", "rope_coil")
    for kind, pos in zip(kinds, roots):
        _place(world, kind, pos, .85 if kind != "shackle" else .65, pos[0] * 9)


def _wreck(world, key):
    bed = world.seabed_depth
    if key == "incident_wreck":
        items = (
            ("rust_panel", (9.2, 1.4, 128.4), 1.0),
            ("shackle", (11.0, -.8, 129.1), .7),
            ("rope_coil", (7.4, 2.2, 128.8), .8),
            ("barnacle", (8.1, -.2, 127.6), .9),
            ("anemone_clump", (13.5, 1.6, 130.2), .75),
            ("shell_bed", (15.0, -2.5, bed), .85),
            ("rust_panel", (20.5, -4.0, bed - .1), 1.05),
            ("shackle", (6.2, -1.5, 127.2), .6),
        )
    else:
        items = (
            ("rust_panel", (8.5, 2.0, 8.2), 1.0),
            ("shackle", (14.2, 9.5, 12.4), .7),
            ("rope_coil", (18.6, 12.8, 14.0), .85),
            ("barnacle", (27.0, 18.2, 16.5), .9),
            ("anemone_clump", (33.0, 20.0, 18.8), .8),
            ("shell_bed", (44.0, 14.0, bed), .9),
            ("rust_panel", (48.5, 18.2, 24.0), 1.05),
            ("shackle", (49.2, 20.4, 24.2), .65),
        )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, pos[0] * 7)


def _reef(world, key):
    if key == "seagrass_meadow":
        items = (
            ("shell_bed", (5.2, -1.4, 7.6), .9),
            ("seastar", (6.4, -2.8, 7.9), .16),
            ("anemone_clump", (10.5, -6.0, 7.1), .8),
            ("barnacle", (17.8, -10.2, 6.6), .7),
            ("shell_bed", (24.0, 7.5, 7.4), .85),
            ("seastar", (30.5, 6.2, 6.9), .15),
            ("rope_coil", (8.2, 2.8, 4.4), .7),
            ("shackle", (4.0, 2.2, 7.8), .55),
        )
    else:
        items = (
            ("anemone_clump", (8.2, -4.5, 10.2), .9),
            ("barnacle", (11.0, -3.2, 9.4), .8),
            ("seastar", (12.5, -6.0, 12.8), .18),
            ("shell_bed", (14.0, 5.5, 12.5), .85),
            ("anemone_clump", (19.5, -13.0, 11.0), .75),
            ("barnacle", (28.5, 10.0, 11.5), .85),
            ("seastar", (34.0, 9.5, 12.0), .16),
            ("shackle", (9.5, -1.5, 8.8), .6),
        )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, pos[1] * 11)


def _monopile(world):
    items = (
        ("barnacle", (10.6, -.8, 11.5), .9),
        ("anemone_clump", (11.2, -2.4, 9.2), .8),
        ("barnacle", (12.8, 1.5, 14.0), .85),
        ("shackle", (8.4, 4.2, world.seabed_depth), .65),
        ("rope_coil", (14.5, -3.5, 7.5), .75),
        ("shell_bed", (2.5, -1.5, world.seabed_depth), .8),
        ("anemone_clump", (13.5, -4.2, 12.5), .7),
        ("barnacle", (9.5, 3.0, 16.0), .8),
    )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, pos[0] * 5)


def _sonar(world):
    bed = world.seabed_depth
    items = (
        ("rust_panel", (5.8, 5.5, 14.6), .9),
        ("shackle", (9.0, 4.2, 13.6), .6),
        ("rope_coil", (15.5, 5.5, 13.6), .7),
        ("shell_bed", (3.0, 1.0, bed), .8),
        ("barnacle", (16.4, 5.2, 12.6), .75),
        ("anemone_clump", (12.0, 5.8, 14.5), .7),
        ("shackle", (17.2, 4.6, 12.4), .55),
        ("shell_bed", (20.0, 6.5, bed), .85),
    )
    for kind, pos, scale in items:
        _place(world, kind, pos, scale, 30)


def _incident_shallow(world, key):
    bed = world.seabed_depth
    table = {
        "incident_silt": (
            ("shell_bed", (7.5, .5, bed), .9),
            ("rope_coil", (5.2, -2.4, bed), .75),
            ("shackle", (4.2, 2.1, 9.4), .55),
            ("anemone_clump", (8.8, -1.0, bed - .2), .7),
            ("barnacle", (2.4, 1.2, 6.5), .65),
            ("shell_bed", (1.5, -1.5, bed), .8),
            ("rope_coil", (10.5, .8, bed), .7),
            ("shackle", (6.0, 2.5, bed), .5),
        ),
        "incident_compass": (
            ("barnacle", (8.5, 1.5, 10.2), .85),
            ("anemone_clump", (7.5, -4.2, 14.5), .75),
            ("shackle", (3.5, 1.2, bed), .6),
            ("rope_coil", (9.5, -2.0, 12.0), .7),
            ("shell_bed", (2.0, -1.5, bed), .8),
            ("barnacle", (11.0, 6.5, 13.0), .8),
            ("anemone_clump", (4.0, 2.0, 8.5), .7),
            ("shackle", (8.0, -5.0, 15.2), .55),
        ),
        "incident_current": (
            ("barnacle", (6.5, .8, 8.2), .85),
            ("anemone_clump", (1.9, -.6, 8.9), .7),
            ("shackle", (8.2, -4.0, bed), .6),
            ("rope_coil", (2.5, 3.2, bed), .75),
            ("shell_bed", (11.0, -1.0, bed), .85),
            ("barnacle", (0.8, 2.0, 12.5), .75),
            ("anemone_clump", (14.5, 5.5, 11.0), .7),
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
