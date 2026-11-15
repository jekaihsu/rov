"""Collision shapes for the inspection-site details that the viewer draws on each structure.

Every detail here is something a vehicle or the tether can touch: sacrificial anodes and their straps on
jacket legs, mud mats, a monopile's transition piece, boat landing, J-tubes and scour-protection rock, quay
fenders, ladders, bollards and toe rock, ship bilge keels, propeller and rudder, and the larger seabed debris.
The viewer (viewer/structures.js) dresses each of these obstacles by its ``kind`` and builds its mesh inside
the shape given here, so physics and picture stay the same object. Purely decorative growth (paint, fouling
textures, mussel lumps thinner than the scene tolerance) has no entry here.

Seabed fittings larger than about 0.2 m (enough to hook a 9.5 mm tether) carry ``snag_hold`` for the tether
snag model (tether_snag.py), the same attribute as ``world.SnagFeature`` and the Korean Castle wreck. Fittings in
the near-bed layer and small attachments make no wake in the structure flow (``NO_WAKE_KINDS``, flow.py).
Proportions follow common offshore and harbour practice; they are illustrative, not survey data.
"""

from __future__ import annotations

import math

import numpy as np

from .world import Box, Cylinder, ShipHull, Wall, ship_hull_params

# Fittings on a structure: the tether touches and snags on them like any obstacle, but wrap counting (turns of
# cable round a pile) keeps to the primary members, so a leg's anodes or a monopile's J-tubes do not report turns.
APPURTENANCE_KINDS = frozenset({
    "wind_dry", "wind_paint", "wind_tower",
    "pen_net", "pen_rope", "pen_frame", "pen_sinker", "pen_buoy", "pen_anchor",
    "anode", "anode_strap", "mudmat", "transition_piece", "boat_landing", "j_tube", "cable_protection",
    "scour_rock", "fender", "ladder", "bollard", "toe_rock", "tyre", "debris_block", "debris_pipe",
    "bilge_keel", "shaft", "propeller", "rudder", "deck",
})
# Fittings that sit inside the near-bed log layer (whose roughness length already stands for them) or are too
# small to shed a wake of their own; the structure flow skips them.
NO_WAKE_KINDS = frozenset({
    "wind_dry", "wind_paint", "wind_tower",
    "pen_net", "pen_rope", "pen_frame", "pen_sinker", "pen_buoy", "pen_anchor",
    "scour_rock", "toe_rock", "cable_protection", "debris_pipe", "tyre", "debris_block", "mudmat",
    "anode_strap", "propeller", "bollard", "deck",
})
# Holding force ranges (N) for snaggable seabed fittings. Provisional training settings like SnagFeature's
# default (150-400 N): no published small-ROV snag strength data exists. Rock armour holds harder (assumed).
SNAG_HOLD_DEBRIS = (150.0, 400.0)
SNAG_HOLD_ROCK = (200.0, 500.0)


def snaggable(obstacles: list, hold: tuple) -> list:
    """Mark obstacles as snaggable for the tether (sets ``snag_hold``) and return them."""
    for ob in obstacles:
        ob.snag_hold = tuple(hold)
    return obstacles


ANODE_LENGTH = 2.0          # m, stand-off anode bar
ANODE_RADIUS = 0.13         # m, capsule enclosing the trapezoid bar section
ANODE_STANDOFF = 0.30       # m, anode axis to leg surface
STRAP_RADIUS = 0.035        # m, steel insert cores welded to the leg


def _unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def _tuple(v) -> tuple:
    return tuple(round(float(x), 4) for x in v)


def leg_anode(leg: Cylinder, depth: float, outward_xy, tag: str) -> list:
    """A stand-off anode parallel to ``leg`` at ``depth`` on the side facing ``outward_xy``, with two straps."""
    a, b = np.asarray(leg.p0, float), np.asarray(leg.p1, float)
    axis = _unit(b - a)
    t = (depth - a[2]) / (b[2] - a[2])
    centre = a + (b - a) * t
    out = np.array([outward_xy[0], outward_xy[1], 0.0])
    out = _unit(out - axis * float(out @ axis))
    offset = out * (leg.radius + ANODE_STANDOFF)
    half = axis * (ANODE_LENGTH / 2 - 0.15)
    obs = [Cylinder(f"{leg.name} anode {tag}", _tuple(centre + offset - half), _tuple(centre + offset + half),
                    ANODE_RADIUS, "anode")]
    strap_at = axis * (ANODE_LENGTH / 2 - 0.25)
    for k, sign in enumerate((-1, 1)):
        root = centre + sign * strap_at + out * (leg.radius - 0.05)
        tip = centre + sign * strap_at + offset
        obs.append(Cylinder(f"{leg.name} anode {tag} strap {k + 1}", _tuple(root), _tuple(tip), STRAP_RADIUS,
                            "anode_strap"))
    return obs


def dress_jacket(obs: list, cx: float, cy: float, seabed: float, anode_depths: dict) -> list:
    """Anodes (``anode_depths``: leg name -> depths) and mud mats for a jacket built by scenarios.jacket."""
    extra = []
    for leg in (o for o in obs if o.kind == "jacket_leg"):
        p1 = np.asarray(leg.p1, float)
        outward = p1[:2] - np.array([cx, cy])
        for depth in anode_depths.get(leg.name, ()):
            extra += leg_anode(leg, float(depth), outward, f"{depth:.0f}m")
        foot = _leg_point(leg, seabed)
        yaw = math.degrees(math.atan2(outward[1], outward[0]))
        extra += snaggable([Box(f"{leg.name} mud mat", _tuple((foot[0], foot[1], seabed - 0.2)), (1.6, 1.6, 0.2),
                                yaw, "mudmat")], SNAG_HOLD_DEBRIS)
    return extra


def _leg_point(leg: Cylinder, depth: float) -> np.ndarray:
    a, b = np.asarray(leg.p0, float), np.asarray(leg.p1, float)
    return a + (b - a) * (depth - a[2]) / (b[2] - a[2])


def _ring(prefix: str, cx: float, cy: float, radius: float, depth: float, rock: float, kind: str) -> list:
    """Horizontal capsules round a circle: one band of rock armour (its crown sits ``rock - (depth - seabed)``)."""
    n = max(6, math.ceil(2 * math.pi * radius / 2.0))
    out = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = (cx + radius * math.cos(a0), cy + radius * math.sin(a0), depth)
        p1 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), depth)
        out.append(Cylinder(f"{prefix} {i + 1}", _tuple(p0), _tuple(p1), rock, kind))
    return out


def dress_monopile(pile: Cylinder, seabed: float, landing_deg: float = 90.0, jtube_deg: float = 0.0) -> list:
    """Transition piece, boat landing, two J-tubes with clamps and cable protection, scour-protection rock.

    Bearings are compass degrees from the pile axis: the boat landing faces ``landing_deg`` and the J-tubes sit
    either side of ``jtube_deg``.
    """
    c = np.asarray(pile.p0, float)
    r = pile.radius
    top = min(float(pile.p0[2]), float(pile.p1[2]))
    obs = []
    tp_r = r + 0.30
    # transition piece over the pile top; the capsule's lower cap is drawn as the grouted skirt taper
    obs.append(Cylinder(f"{pile.name} transition piece", _tuple((c[0], c[1], top)), _tuple((c[0], c[1], 4.0)),
                        tp_r, "transition_piece"))
    a = math.radians(landing_deg)
    out, side = np.array([math.cos(a), math.sin(a), 0.0]), np.array([-math.sin(a), math.cos(a), 0.0])
    for k, s in enumerate((-0.75, 0.75)):
        base = c + out * (tp_r + 1.0) + side * s
        obs.append(Cylinder(f"{pile.name} boat landing {k + 1}", _tuple((base[0], base[1], top + 0.5)),
                            _tuple((base[0], base[1], 3.0)), 0.20, "boat_landing"))
        for z in (-1.0, 2.5):
            root = c + out * (tp_r - 0.1) + side * s
            obs.append(Cylinder(f"{pile.name} boat landing {k + 1} arm {z:+.0f}", _tuple((root[0], root[1], z)),
                                _tuple((base[0], base[1], z)), 0.11, "boat_landing"))
    for k, off in enumerate((-22.0, 22.0)):
        a = math.radians(jtube_deg + off)
        out = np.array([math.cos(a), math.sin(a), 0.0])
        x0 = c + out * (r + 0.55)
        bend = seabed - 3.0
        x1 = c + out * (r + 1.6)
        x2 = c + out * (r + 3.4)
        name = f"{pile.name} J-tube {k + 1}"
        obs.append(Cylinder(name, _tuple((x0[0], x0[1], 3.5)), _tuple((x0[0], x0[1], bend)), 0.2, "j_tube"))
        obs.append(Cylinder(f"{name} bend", _tuple((x0[0], x0[1], bend)), _tuple((x1[0], x1[1], seabed - 1.2)), 0.2,
                            "j_tube"))
        obs.append(Cylinder(f"{name} bellmouth", _tuple((x1[0], x1[1], seabed - 1.2)),
                            _tuple((x2[0], x2[1], seabed - 0.35)), 0.3, "j_tube"))
        far = c + out * (r + 12.0)
        obs += snaggable([Cylinder(f"{name} cable protection", _tuple((x2[0], x2[1], seabed - 0.35)),
                                   _tuple((far[0], far[1], seabed - 0.15)), 0.15, "cable_protection")],
                         SNAG_HOLD_DEBRIS)
        for z in (8.0, 16.0):
            if z < bend - 1:
                root = c + out * (r - 0.05)
                obs.append(Cylinder(f"{name} clamp {z:.0f}m", _tuple((root[0], root[1], z)),
                                    _tuple((x0[0], x0[1], z)), 0.08, "j_tube"))
    # rock armour: three overlapping bands, highest next to the pile, buried 0.35-0.5 m in the seabed
    for k, (radius, rock, bury) in enumerate(((r + 1.0, 0.95, 0.35), (r + 2.8, 0.95, 0.4), (r + 4.5, 0.75, 0.5))):
        obs += snaggable(_ring(f"{pile.name} scour rock {k + 1}", c[0], c[1], radius, seabed + bury, rock,
                               "scour_rock"), SNAG_HOLD_ROCK)
    return obs


def dress_quay(wall: Wall, seabed: float, keep_clear=()) -> list:
    """Fenders, ladders, bollards on the cope, toe rock along the base and a tyre/block/pipe at the base.

    ``keep_clear`` holds positions along the face (metres from ``wall.point``) where the inspection lane runs.
    """
    a = math.radians(wall.normal_deg)
    n = np.array([math.cos(a), math.sin(a), 0.0])
    t = np.array([-n[1], n[0], 0.0])
    p = np.asarray(wall.point, float)
    half = wall.width / 2
    obs = []

    def face(along, off, z):
        q = p + t * along + n * off
        return (q[0], q[1], z)

    def clear(along, gap=4.0):
        return all(abs(along - k) > gap for k in keep_clear)

    for i, s in enumerate(np.arange(-half + 6.0, half - 3.0, 12.0)):
        if not clear(s):
            continue
        obs.append(Cylinder(f"{wall.name} fender {i + 1}", _tuple(face(s, 0.45, wall.top + 0.6)),
                            _tuple(face(s, 0.45, 1.6)), 0.42, "fender"))
    for i, s in enumerate((-half + 12.0, half - 12.0)):
        if not clear(s):
            continue
        obs.append(Box(f"{wall.name} ladder {i + 1}", _tuple(face(s, 0.11, 0.6)), (0.11, 0.3, 2.6),
                       wall.normal_deg, "ladder"))
    for i, s in enumerate(np.arange(-half + 3.0, half, 9.0)):
        obs.append(Cylinder(f"{wall.name} bollard {i + 1}", _tuple(face(s, -0.9, wall.top - 0.2)),
                            _tuple(face(s, -0.9, wall.top - 0.65)), 0.22, "bollard"))
    obs += snaggable([Cylinder(f"{wall.name} toe rock", _tuple(face(-half + 1.0, 0.6, seabed + 0.45)),
                               _tuple(face(half - 1.0, 0.6, seabed + 0.45)), 1.05, "toe_rock")], SNAG_HOLD_ROCK)
    return obs


def quay_debris(wall: Wall, seabed: float) -> list:
    """Tyre, broken concrete block and a pipe length lying off the quay toe (collision boxes/capsules)."""
    a = math.radians(wall.normal_deg)
    n = np.array([math.cos(a), math.sin(a), 0.0])
    t = np.array([-n[1], n[0], 0.0])
    p = np.asarray(wall.point, float)
    obs = []
    tyre = p + n * 3.2 + t * (-6.5)
    obs.append(Box(f"{wall.name} tyre", _tuple((tyre[0], tyre[1], seabed - 0.13)), (0.45, 0.45, 0.13),
                   wall.normal_deg + 20, "tyre"))
    block = p + n * 3.6 + t * 9.0
    obs.append(Box(f"{wall.name} concrete block", _tuple((block[0], block[1], seabed - 0.35)), (0.7, 0.5, 0.35),
                   wall.normal_deg - 25, "debris_block"))
    pipe0, pipe1 = p + n * 4.6 + t * (-14.0), p + n * 3.4 + t * (-18.5)
    obs.append(Cylinder(f"{wall.name} pipe", _tuple((pipe0[0], pipe0[1], seabed - 0.18)),
                        _tuple((pipe1[0], pipe1[1], seabed - 0.18)), 0.18, "debris_pipe"))
    return snaggable(obs, SNAG_HOLD_DEBRIS)


def ship_hull(name: str, center_xy, yaw_deg: float, length: float, beam: float, draft: float) -> list:
    """A ShipHull plus its bilge keels, shaft, hub, four blades and rudder, in that order."""
    hull = ShipHull(name, (center_xy[0], center_xy[1], 0.0), yaw_deg, length, beam, draft)
    hp = ship_hull_params(length, beam, draft)
    W = hull.world_point
    obs = [hull]
    rb, T, B, L = hp["bilge"], draft, beam, length
    reach = rb + 0.22
    for side, label in ((1, "starboard"), (-1, "port")):
        cy, cz = side * (B / 2 - rb), T - rb
        oy, oz = cy + side * reach * math.sqrt(0.5), cz + reach * math.sqrt(0.5)
        obs.append(Cylinder(f"{name} bilge keel {label}", _tuple(W((-0.15 * L, oy, oz))),
                            _tuple(W((0.12 * L, oy, oz))), 0.22, "bilge_keel"))
    prop = propeller_layout(hp)
    xp, zp, radius = prop["x"], prop["z"], prop["radius"]
    obs.append(Cylinder(f"{name} shaft", _tuple(W((-L / 2 + hp["aperture"] + 1.0, 0, zp))),
                        _tuple(W((xp + 0.2, 0, zp))), 0.25, "shaft"))
    obs.append(Cylinder(f"{name} propeller hub", _tuple(W((xp + 0.35, 0, zp))), _tuple(W((xp - 0.45, 0, zp))),
                        prop["hub"], "propeller"))
    # each blade: two thin capsules side by side along the pitched chord, enclosing the flat blade
    r_edge = prop["blade"]
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        radial = np.array([0.0, math.cos(ang), math.sin(ang)])
        chord = np.array([math.sin(prop["pitch"]), -math.sin(ang) * math.cos(prop["pitch"]),
                          math.cos(ang) * math.cos(prop["pitch"])])
        hub = np.array([xp, 0.0, zp])
        tip = hub + radial * (radius - r_edge)
        for edge, sign in (("a", -1), ("b", 1)):
            offset = chord * sign * r_edge
            obs.append(Cylinder(f"{name} propeller blade {k + 1}{edge}", _tuple(W(hub + offset)),
                                _tuple(W(tip + offset)), r_edge, "propeller"))
    rud = rudder_layout(hp)
    obs.append(Box(f"{name} rudder", _tuple(W((rud["x"], 0, rud["z"]))), (rud["half_chord"], rud["half_thick"],
                                                                           rud["half_height"]), yaw_deg, "rudder"))
    return obs


def propeller_layout(hp: dict) -> dict:
    radius = 0.28 * hp["draft"]
    return {"x": -hp["length"] / 2 + hp["aperture"] - 1.6 / 6.0 * hp["aperture"], "z": hp["draft"] - radius - 0.2,
            "radius": radius, "hub": 0.5, "blade": 0.14, "pitch": 0.6}


def rudder_layout(hp: dict) -> dict:
    top, bottom = hp["counter"] - 0.05, hp["draft"] - 0.3
    return {"x": -hp["length"] / 2 + 0.3 * hp["aperture"], "z": (top + bottom) / 2, "half_chord": 0.2 * hp["aperture"],
            "half_thick": 0.3, "half_height": (bottom - top) / 2}


def wind_jacket_fittings(structure: list, cx: float, cy: float, seabed: float) -> list:
    """Original generic wind foundation; NED metres, illustrative proportions, no site identifiers.

    Every rigid fitting is a standard cylinder or box, shared by rendering, sonar and tether contact.
    The inspection anodes remain on their leg-derived outward bearings.
    """
    obs = []

    def tube(name, a, b, radius=0.06, kind="boat_landing"):
        if max(a[2], b[2]) + radius < 0 and kind == "boat_landing":
            kind = "wind_dry"
        obs.append(Cylinder(f"Wind {cx:g} {cy:g} {name}",
                            (cx + a[0], cy + a[1], a[2]),
                            (cx + b[0], cy + b[1], b[2]), radius, kind))

    def box(name, center, half, kind="wind_paint"):
        obs.append(Box(f"Wind {cx:g} {cy:g} {name}",
                       (cx + center[0], cy + center[1], center[2]), half, 0, kind))

    # Square transition deck, underside grillage, edge rails and stanchions.
    box("platform", (0, 0, -12.3), (7.3, 7.3, 0.16))
    for i in range(-7, 8):
        box(f"grillage x {i}", (i, 0, -11.95), (0.055, 7.2, 0.2))
        box(f"grillage y {i}", (0, i, -11.95), (7.2, 0.055, 0.2))
    for side in (-1, 1):
        for height in (-12.8, -13.5):
            tube(f"rail x {side} {height}", (-7.2, side * 7.2, height), (7.2, side * 7.2, height))
            tube(f"rail y {side} {height}", (side * 7.2, -7.2, height), (side * 7.2, 7.2, height))
        for i in range(-7, 8, 2):
            tube(f"post x {side} {i}", (i, side * 7.2, -12.5), (i, side * 7.2, -13.5))
            tube(f"post y {side} {i}", (side * 7.2, i, -12.5), (side * 7.2, i, -13.5))
    tube("tower base", (0, 0, -12.5), (0, 0, -29), 2.3, "wind_tower")
    # Two flights switch direction at a landing outside the southern face.
    for flight in range(2):
        z0 = -3.0 - flight * 4.5
        sign = 1 if flight == 0 else -1
        x0 = -4.5 * sign
        for i in range(19):
            t = i / 18
            box(f"stair {flight} tread {i}", (x0 + sign * 9 * t, -6.4, z0 - 4.5 * t),
                (0.25, 0.65, 0.055))
        for y in (-7.05, -5.75):
            tube(f"stair {flight} stringer {y}", (x0, y, z0), (-x0, y, z0 - 4.5), 0.09)
            tube(f"stair {flight} handrail {y}", (x0, y, z0 - 1.1), (-x0, y, z0 - 5.6))
            for i in range(0, 19, 3):
                x, z = x0 + sign * i / 2, z0 - i / 4
                tube(f"stair {flight} post {y} {i}", (x, y, z), (x, y, z - 1.1))
        box(f"stair landing {flight}", (-x0, -6.4, z0 - 4.5), (1, 0.9, 0.08))
    tube("davit mast", (5.8, 4.5, -12.5), (5.8, 4.5, -15.5), 0.12)
    tube("davit jib", (5.8, 4.5, -15.5), (8.2, 4.5, -15.5), 0.12)
    tube("davit wire", (8.2, 4.5, -15.5), (8.2, 4.5, -13.5), 0.025)
    # Boat landing is away from the radial anode approaches.
    for x in (-0.8, 0.8):
        tube(f"landing column {x}", (x, -7.4, -4), (x, -7.4, 3), 0.23)
        tube(f"rubber strip {x}", (x, -7.4, -0.7), (x, -7.4, 2), 0.245, "fender")
        tube(f"ladder stile {x}", (x * 0.5, -7.15, -4), (x * 0.5, -7.15, 2.6), 0.045)
    for i in range(22):
        z = -3.8 + i * 0.3
        tube(f"ladder rung {i}", (-0.4, -7.15, z), (0.4, -7.15, z), 0.035)
    box("landing deck", (0, -6.7, -3), (1.2, 1, 0.12))
    for side in (-1, 1):
        tube(f"landing support {side}", (side * 5, -5, -3), (side * 0.8, -7.4, -3), 0.13)
    box("symbol plate", (0, -7.3, -4.05), (0.45, 0.035, 0.45))
    vertices = [(-0.32, -7.35, -3.8), (0.32, -7.35, -3.8), (0, -7.35, -4.38)]
    for i in range(3):
        tube(f"warning triangle {i}", vertices[i], vertices[(i + 1) % 3], 0.025, "fender")
    # Grout sleeves and segmented J-tubes follow the legs without blocking the inspection faces.
    legs = [ob for ob in structure if ob.kind == "jacket_leg"]
    for i, leg in enumerate(legs):
        a, b = _leg_point(leg, seabed - 2), _leg_point(leg, seabed)
        obs.append(Cylinder(f"{leg.name} grout sleeve", _tuple(a), _tuple(b), leg.radius + 0.16, "j_tube"))
        foot = _leg_point(leg, seabed)
        obs += snaggable(_ring(f"{leg.name} armour", foot[0], foot[1], 2.5,
                               seabed + 0.32, 0.65, "scour_rock"), SNAG_HOLD_ROCK)
        if i >= 2:
            continue
        points = [_leg_point(leg, d) + np.array([-0.9, 0, 0]) for d in (-2, 8, 18, seabed - 3)]
        points += [points[-1] + np.array([-1, 0, 1.6]), points[-1] + np.array([-2.5, 0, 2.5])]
        for j, (a, b) in enumerate(zip(points, points[1:])):
            obs.append(Cylinder(f"{leg.name} J section {j}", _tuple(a), _tuple(b), 0.16, "j_tube"))
        for d in (4, 14, 24):
            root = _leg_point(leg, d)
            tip = root + np.array([-0.9, 0, 0])
            obs.append(Cylinder(f"{leg.name} clamp {d}", _tuple(root), _tuple(tip), 0.07, "j_tube"))
    return obs
