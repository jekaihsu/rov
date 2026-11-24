"""Survey-site landmarks in NED metres. All dimensions and layouts are fictional.

The ropes, floats, broken hull plating and submerged rock faces are ordinary world
obstacles, shared by sonar, vehicle contact, tether contact and the viewer.
"""

import math

from .site_dressing import SNAG_HOLD_DEBRIS, snaggable
from .site_habitat import channel_relief
from .world import Box, Cylinder


def sounding_mooring(label, anchor, top, float_depths):
    """A taut, weighted survey line; flotation lies on the line between the sinker and the head float."""
    n, e, bed = anchor
    tn, te, td = top
    obstacles = snaggable([
        Box(f"{label} clump weight", (n, e, bed - .19), (.60, .48, .22), 17, "survey_weight"),
        Cylinder(f"{label} riser", (n, e, bed - .4), top, .024, "survey_line"),
    ], SNAG_HOLD_DEBRIS)
    for i, d in enumerate((td, *float_depths)):
        t = (d - td) / (bed - .4 - td)
        x = tn + (n - tn) * t
        y = te + (e - te) * t
        radius = .29 if i == 0 else .19
        obstacles.append(Cylinder(f"{label} float {i + 1}", (x, y, d - .16), (x, y, d + .16),
                                  radius, "survey_float"))
    return obstacles


# Pairs of coordinates let the survey riser rake with the local current. Choose the
# offset side so it doesn't cross the inspection lane or interfere with a prewrap.
# Harbor, hull and aquaculture landmarks belong to R5/R6. This module only dresses T1 sites.
MOORINGS = {
    "jacket_inspection": ("Service mooring", (10.1, 7.2), (8.1, 5.7, .15), (3.6, 9.4)),
    "monopile_current": ("Scour survey", (8, 5), (6, 3, .2), (3.6, 11.5)),
    "tether_untangle": ("Outer mooring", (-3.6, 2.2), (-2.8, 1.8, .2), (4.4, 6.7, 10.5)),
    "incident_wreck": ("Recovery shot", (5.0, -.10), (-42.3, -.10, .18), (26, 51, 76, 101, 117.4, 120.3, 123.1, 125.6)),
    "incident_silt": ("Sediment station", (2.1, 2), (-1.9, .52, .26), (3.3, 6.6, 9.5)),
    "incident_jacket": ("Recovery shot", (-10.8, -3.9), (-12.9, -1.8, .18), (4, 9, 12)),
    "incident_compass": ("Reference mooring", (-2, 2.5), (-2.3, .39, .18), (4.6, 9.7)),
    "incident_current": ("Current mooring", (2.3, -1.85), (1.4, -.3, .18), (3.4, 9.2, 14.8)),
    "random": ("Survey mooring", (5, -4.6), (4, -2.8, .2), (3.6,)),
}

OWNED = {
    "open_water", "jacket_inspection", "monopile_current", "tether_untangle",
    "wreck_survey", "korean_castle", "coral_reef", "seagrass_meadow", "sonar_search",
    "incident_jacket", "incident_wreck", "incident_silt", "incident_compass", "incident_current",
    "cold_open_jacket", "random",
}


def training_stations(bed):
    """The four corners of the open-water box have separate marker lines outside the flight lane."""
    # Keep the head float (capsule radius 0.29 m) fully submerged so a 0.1 m hover stays clear.
    recovery_head = (-3.6, -2.7, .55)
    stations = [
        ("North drop", (13, 1.5), (13.2, 1, 2.7), (5., 9.)),
        ("East drop", (8.6, 14), (10.3, 13.4, 5.7), (7.9, 10.7)),
        ("Deep drop", (-3.8, 8), (-3.1, 9.4, 8.6), (11.4, 13.6)),
        ("Recovery drop", (-3, -3), recovery_head, (2.8, 6.1, 9.)),
    ]
    obstacles = []
    for label, foot, head, depths in stations:
        floor = bed - float(channel_relief(foot[1]))
        obstacles.extend(sounding_mooring(label, (*foot, floor), head, depths))
    # A short pickup pendant trails the recovery buoy toward the deployment side.
    # Keep the painter and fender fully below ~0.7 m so a 0.1 m hover does not sit inside the tube.
    pickup = (4.55, 1.95, .95)
    obstacles.extend([
        Cylinder("Recovery pickup painter", recovery_head, pickup, .031, "survey_line"),
        Cylinder("Recovery pickup fender", pickup, (4.55, 1.95, 1.45), .30, "survey_float"),
        Cylinder("Recovery hand line", (4.55, 1.95, 1.4), (4.65, 2.06, 2.63), .039, "survey_line"),
        Cylinder("Recovery stopper float", (4.61, 2.02, 1.87), (4.61, 2.02, 2.08), .19, "survey_float"),
    ])
    return obstacles


def instrument_mount(riser, name, depth):
    """Suspended pressure housing with a triangular guard below it, mounted to the taut riser."""
    lo, hi = riser.p0, riser.p1
    t = (depth - lo[2]) / (hi[2] - lo[2])
    n = lo[0] + (hi[0] - lo[0]) * t
    e = lo[1] + (hi[1] - lo[1]) * t
    axis = (n + .18, e, depth)
    crown = (n + .18, e, depth + .84)
    parts = [
        Cylinder(f"{name} pressure case", (n + .18, e, depth - .56), axis, .16, "instrument_case"),
        Cylinder(f"{name} probe", axis, (n + .18, e, depth + .49), .069, "survey_line"),
    ]
    for i, (dn, de) in enumerate(((.42, .05), (.02, .24), (.02, -.24))):
        joint = (n + dn, e + de, depth + .73)
        parts.append(Cylinder(f"{name} guard {i}", axis, joint, .027, "survey_line"))
        parts.append(Cylinder(f"{name} guard heel {i}", joint, crown, .027, "survey_line"))
    return parts


def marked_guide(name, path):
    """A survey guideline with closed-cell markers threaded on its spliced sections."""
    parts = []
    for i, (a, b) in enumerate(zip(path, path[1:])):
        parts.append(Cylinder(f"{name} span {i + 1}", a, b, .035, "survey_line"))
        for j, fraction in enumerate((.48, .93)):
            n, e, d = (lo + fraction * (hi - lo) for lo, hi in zip(a, b))
            parts.append(Cylinder(f"{name} splice {i}-{j}", (n, e, d - .085), (n, e, d + .085),
                                  .15 if j else .12, "survey_float"))
    return snaggable(parts, SNAG_HOLD_DEBRIS)


def wreck_descent_line(sea):
    """The upper rope trails south-west in the strongest current and the last metres hang nearly plumb."""
    path = ((-5.4, -3.3, .18), (14.1, 10.8, 8.7), (27.6, 18.4, 13.7), (33.8, 21., 16.1),
            (48.2, 21.5, 21.4), (50.3, 21.5, 24.), (50.1, 21.4, sea - .40))
    weight = Box("Bow shot weight", (50.1, 21.4, sea - .19), (.60, .48, .22), 17, "survey_weight")
    return [weight, *marked_guide("Bow shot", path)]


def cargo_hold_transect(sea):
    """A marked descent to the bow fracture and a photo baseline held between the two survey stations."""
    bow = (16.3, -24.8, 25.3)
    mid = (33., -6., 17.6)
    descent = ((-1., 3., .18), (6.2, -10., 6.4), (10.7, -19., 8.8), (16.5, -24.1, 12.),
               bow, (16.3, -24.8, sea - .4))
    # Keep the jackstay outside the open hatch. The second riser is seated in the open hold.
    parts = marked_guide("Bow break survey line", descent)
    parts.extend(marked_guide("Hold photo baseline", (bow, mid)))
    parts.extend(sounding_mooring("Hold survey station", (33., -6., sea), mid, (21., 26.)))
    parts.append(Box("Bow break shot weight", (16.3, -24.8, sea - .19), (.6, .48, .22), 17, "survey_weight"))
    return parts


def hull_berth(hull, site):
    """Tubular rubbing wale and four supporting piles outside the generated ship's stern quarter."""
    length = hull.hp["length"]
    beam = hull.hp["beam"]
    side = 1 if hull.yaw_deg >= 0 else -1
    samples = [o.point for o in site.objectives if o.point is not None] + [site.start_pos, site.spool_pos]
    # Keep one continuous berth edge parallel to its original layout; move the entire row outboard
    # when a random survey station happens to be beside it.
    shift = 0.
    stations = ((-.47, .81), (-.39, .69), (-.31, .57), (-.23, .57))
    while True:
        heads = [hull.world_point((length * x, (beam * offset + shift) * side, -.45)) for x, offset in stations]
        if all(math.dist(head[:2], point[:2]) >= 2.2 for head in heads for point in samples):
            break
        shift += 3.
    piles = []
    rails = []
    for i, (n, e, d) in enumerate(heads):
        head = (n, e, d)
        piles.append(Cylinder(f"Berth pile {i + 1}", (n, e, site.seabed_depth), head, .32, "pile"))
        rails.append((n, e, .95))
    for i, (a, b) in enumerate(zip(rails, rails[1:])):
        piles.append(Cylinder(f"Berth rubbing wale {i + 1}", a, b, .19, "pile"))
    # A submerged inspection jackstay runs from the landing piles beneath the stationary hull to a
    # buoyed clump by the furthest work station. The scale bars hang below it for repeat photographs.
    draft = hull.hp["draft"]
    working_depth = draft + 2.52
    end = max((o.point for o in site.objectives), key=lambda p: hull.to_local(p)[0, 0])
    last = (end[0] + 3., end[1] - 1.8 * side, working_depth)
    n, e, _ = heads[-1]
    path = [(x, y, working_depth) for x, y, _ in heads]
    for i in range(1, 6):
        t = i / 5
        # Buoyed spans bow gently with the current between the berth and clump.
        path.append((n + (last[0] - n) * t, e + (last[1] - e) * t + side * 2.65 * math.sin(math.pi * t),
                     working_depth + .25 * math.sin(math.pi * t)))
    guide = marked_guide("Hull photographic jackstay", path)
    for i in (1, 3, 5, 7):
        x, y, z = path[i]
        # Rigid inverted T with a half-metre measuring arm and a weighted centre stem.
        guide.append(Cylinder(f"Survey scale {i} stem", (x, y, z), (x, y, z + .43), .035, "instrument_case"))
        guide.append(Cylinder(f"Survey scale {i} bar", (x, y - .34, z + .43), (x, y + .34, z + .43),
                              .042, "valve_guard"))
    guide.extend(sounding_mooring("Jackstay end", (*last[:2], site.seabed_depth), last, (working_depth + .7,)))
    return piles + guide


def reef_outcrops():
    # An eroded lintel across a notch, with a lower fallen slab and a second
    # ridge beyond it. The open passage is genuine free water between colliders.
    pieces = (
        ("West arch north buttress", (11.6, -5.1, 14), (10.7, -4.9, 6.6), 1.25),
        ("West arch south buttress", (11.6, .7, 14), (11.4, -.4, 6.9), 1.38),
        ("West arch lintel", (10.7, -4.8, 6.4), (11.5, -.5, 6.7), 1.05),
        ("West arch fallen lip", (12, -5.1, 13.1), (16, -3.4, 12.6), 1.25),
        ("West notch projecting toe", (21.4, -16.2, 13.6), (20.1, -14.4, 9.2), 1.65),
        ("West notch upper lip", (20.3, -14.6, 9.2), (19.4, -13.1, 8.7), .93),
        ("West notch sill", (18.6, -15, 12.9), (21.5, -12.5, 11.9), 1.25),
        ("Lagoon pinnacle talus", (14.3, 6.1, 13.6), (10.1, 5.5, 5.9), 2.05),
        ("Lagoon pinnacle crest", (10.4, 5.7, 6.1), (8.7, 5.6, 2.2), 1.25),
        ("Lagoon pinnacle ledge", (8.3, 5.3, 3.2), (10.5, 7.6, 4.6), .95),
        ("East reef spur", (29.5, 10.8, 14), (28.8, 9.8, 8.7), 1.52),
        ("East reef high crest", (39.6, 17.5, 13.6), (38.6, 15.7, 8.4), 1.49),
        ("East reef plinth", (35.8, 17.5, 13.3), (40.2, 16.6, 11.8), 1.55),
        ("East reef split stack", (28.7, 13.8, 14), (29.4, 13.1, 10.1), 1.05),
    )
    return [Cylinder(name, start, end, radius, "reef_outcrop") for name, start, end, radius in pieces]


def grass_outcrops():
    return [
        Cylinder("Shell bank ridge", (7, -7.2, 8.8), (11.6, -6.3, 7.2), 1.26, "reef_outcrop"),
        Cylinder("Shell bank toe", (8, -6.7, 8.8), (12.3, -4.9, 8.4), .82, "reef_outcrop"),
        Cylinder("Shell bank shelf", (17.2, -11.5, 8.6), (18.3, -10.8, 6.35), 1.21, "reef_outcrop"),
        Cylinder("Shell bank crest", (18.1, -10.4, 6.5), (19.6, -12.2, 6.7), .65, "reef_outcrop"),
        Cylinder("Meadow reef crest", (36.5, 11.2, 8.6), (35.6, 9.8, 6.2), 1.18, "reef_outcrop"),
        Cylinder("Meadow reef scree", (35.2, 10.3, 7.9), (38.1, 8.9, 8.5), 1.04, "reef_outcrop"),
        Cylinder("Meadow reef", (22.8, 10.2, 8.8), (25.3, 11.2, 6.8), 1.54, "reef_outcrop"),
        Cylinder("Meadow reef shelf", (23.3, 13, 8.7), (27.4, 12.6, 8.2), 1.0, "reef_outcrop"),
    ]


def detached_ribs(prefix, n, e, bed):
    """Half-buried sheared frames, trailing away from the wreck's impact scar."""
    return [
        Cylinder(f"{prefix} web", (n, e, bed), (n + 2.3, e + .6, bed - 2.6), .21, "mast"),
        Cylinder(f"{prefix} bent flange", (n + 2.3, e + .6, bed - 2.6), (n + 3.4, e + 2.7, bed - 2.2), .17, "mast"),
        Box(f"{prefix} plate", (n + 2, e - 1.1, bed - .13), (1.7, .84, .14), 27, "wreck"),
    ]


def add_landmarks(site):
    """Extend the authored scene without changing controls, missions, water or spawn poses."""
    key = site.key
    if key not in OWNED:
        return site
    sea = site.seabed_depth
    obs = site.obstacles
    if key in MOORINGS:
        label, foot, head, depths = MOORINGS[key]
        mooring = sounding_mooring(label, (*foot, sea), head, depths)
        obs.extend(mooring)
        if key in ("incident_silt", "incident_current", "incident_compass"):
            obs.extend(instrument_mount(mooring[1], f"{label} instrument", depths[1] - .52))
        if key == "jacket_inspection":
            obs.extend(instrument_mount(mooring[1], "Service current logger", 4.35))
    if key == "open_water":
        obs.extend(training_stations(sea))
    elif key == "coral_reef":
        obs.extend(reef_outcrops())
    elif key == "seagrass_meadow":
        obs.extend(grass_outcrops())
        obs.extend(sounding_mooring("Meadow transect", (7.8, 3.5, sea), (8.7, 3.3, .24), (2.2, 4.6)))
        obs.extend(sounding_mooring("Transect end", (4.2, 2.8, sea), (3.7, 2.5, .24), (1.7,)))
        obs.append(Cylinder("Transect floatline", (3.7, 2.5, .24), (8.7, 3.3, .24), .031, "survey_line"))
    elif key == "sonar_search":
        # Acoustic target stays in its original bearing. The pipe partly buried
        # off the search lane makes a second return at a different range.
        obs.append(Cylinder("Exposed drain", (5.2, 5.9, 15.6), (16.1, 6.05, 14.8), .42, "debris_pipe"))
        obs.append(Box("Drain headwall", (16.1, 6.05, 14.4), (.38, .75, .78), 0, "debris_block"))
        for n, e, d in ((9.04, 4.13, 13.48), (15.94, 5.40, 13.48)):
            obs.append(Cylinder(f"Drain manifold branch {n}", (n, 5.98, 14.8), (n, e, 14.8), .14, "debris_pipe"))
            obs.append(Cylinder(f"Drain valve neck {n}", (n, e, sea), (n, e, d), .13, "mast"))
            obs.append(Cylinder(f"Drain valve bonnet {n}", (n, e, d), (n, e, d + .08), .19, "valve_bonnet"))
            obs.append(Cylinder(f"Drain valve handle {n}", (n - .18, e, d - .22), (n + .18, e, d - .22),
                                .036, "mast"))
            obs.append(Cylinder(f"Drain valve spindle {n}", (n, e, d - .22), (n, e, d), .046, "mast"))
        # Stand-off rails protect the two valve spindles from snagging gear.
        # Their pale antifouling sleeves are visible at close range in the silt.
        for a, b in (((8.58, 4.30, 13.04), (9.58, 4.61, 13.04)),
                     ((15.28, 5.32, 13.04), (16.38, 5.59, 13.04))):
            obs.append(Cylinder(f"Manifold top rail {a[0]}", a, b, .067, "valve_guard"))
            for point in (a, b):
                foot = (point[0], point[1], sea)
                obs.append(Cylinder(f"Manifold rail upright {point[0]}", point, foot, .059, "valve_guard"))
        # The near face of the search target is a service cabinet: hinge,
        # raised inspection cover and lifting bail readable in the ROV light.
        obs.append(Box("Access hatch", (17.01, 5, 13.0), (.035, .61, .47), 0, "service_hatch"))
        obs.append(Cylinder("Hatch hinge", (16.96, 4.41, 12.02), (16.96, 4.41, 12.8), .048, "mast"))
        for y in (5.22, 5.52):
            obs.append(Cylinder(f"Bail lug {y}", (16.97, y, 12.30), (16.79, y, 12.30), .044, "mast"))
        obs.append(Cylinder("Hatch bail", (16.79, 5.22, 12.30), (16.79, 5.52, 12.30), .044, "mast"))
    elif key == "random":
        hull = next((ob for ob in obs if hasattr(ob, "hp")), None)
        if hull is not None:
            obs.extend(hull_berth(hull, site))
    elif key == "wreck_survey":
        obs.extend(wreck_descent_line(sea))
        obs.extend(detached_ribs("Detached bow frame", 44, 12, sea))
        # A detached boat davit remains bolted to a torn plate at the end of the bow debris strip.
        obs.append(Box("Davit foundation plate", (49.9, 18.7, sea - .19), (1.33, .82, .22), 24, "wreck"))
        shoulder = (49.2, 19.9, 24.45)
        tip = (49.45, 21.22, 23.96)
        obs.append(Cylinder("Davit column", (49.9, 18.7, sea - .40), shoulder, .20, "mast"))
        obs.append(Cylinder("Davit jib", shoulder, tip, .16, "mast"))
        obs.append(Cylinder("Davit sheave", (49.32, 21.22, 24.14), (49.56, 21.22, 24.14), .27, "shaft"))
        obs.append(Cylinder("Davit pendant", (49.45, 21.45, 24.14), (49.44, 21.49, 25.24), .038, "survey_line"))
    elif key == "korean_castle":
        obs.extend(cargo_hold_transect(sea))
        obs.extend(detached_ribs("Bow debris strip", 47, -22, sea))
        obs.extend(detached_ribs("Stern debris strip", 5, 41, sea))
    elif key == "incident_wreck":
        obs.extend(detached_ribs("Detached deck frame", 14, 5, sea))
        riser = next(ob for ob in obs if ob.name == "Recovery shot riser")
        obs.extend(instrument_mount(riser, "Wreck pressure logger", 125.2))
        # Fallen cargo derrick bolted to the snag post below the prewrapped line.
        obs.append(Cylinder("Derrick boom", (8, 0, 131.7), (11.7, -1.5, 130.5), .19, "mast"))
        obs.append(Cylinder("Derrick stay", (8, 0, 129.6), (11.7, -1.5, 130.5), .052, "mast"))
    elif key == "incident_silt":
        # Pair of sediment traps sample two different heights above the soft bed.
        obs.append(Box("Sediment collector base", (4.4, 2, sea - .12), (.28, .64, .13), 0, "survey_weight"))
        for e, mouth in ((1.65, 9.25), (2.35, 9.65)):
            obs.append(Cylinder(f"Collector tube {e}", (4.4, e, sea - .21), (4.4, e, mouth),
                                .13, "debris_pipe"))
    elif key == "incident_current":
        # A midwater vane's tail streams along the east-going current. Its
        # split metal supports leave the flow aperture and the pilot lane open.
        obs.append(Cylinder("Vane bearing", (1.97, -.90, 8.07), (1.97, -.90, 8.62), .16, "instrument_case"))
        obs.append(Cylinder("Vane boom", (1.97, -.90, 8.6), (1.97, .30, 8.6), .065, "mast"))
        obs.append(Box("Current vane", (1.97, .16, 8.91), (.028, .28, .34), 0, "survey_weight"))
        # A second, subsurface float at the downstream sampling station marks
        # the opposite side of the gate in the strong cross-current.
        obs.extend(sounding_mooring("Downstream logger", (1.1, 2.4, sea), (1.3, 5.7, 6.7), (8.2, 12.6)))
        # Tripod on the bed carries a current meter above the floc layer.
        apex = (8.5, -4.4, sea - 2.1)
        for i, (n, e) in enumerate(((7, -4.9), (9.5, -5.4), (9, -3.4))):
            obs.append(Cylinder(f"Meter frame strut {i + 1}", (n, e, sea), apex, .07, "mast"))
        obs.append(Cylinder("Meter pressure tube", apex, (8.5, -4.4, sea - 2.8), .16, "mast"))
    return site
