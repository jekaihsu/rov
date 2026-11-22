"""Place photographable, low-relief organisms and fragments on existing site surfaces (NED metres)."""
from __future__ import annotations

import math
import numpy as np


# Three six-subject transects per dive. A depth targets a working face; None follows the actual seabed.
# Wreck transects run along the debris apron, outside the hull's distance-field envelope.
TRANSECTS = {
    "open_water": ((4, 1, None), (9, 5, None), (0, 10, None)),
    "cold_open_jacket": ((-8, -7, 12), (4, -8, 12), (-5, 6, 11)),
    "jacket_inspection": ((13, -6, 13), (27, 6, 7), (27, -6, 13)),
    "monopile_current": ((11, -1, 12), (14, -4, 8), (1, -2, None)),
    "tether_untangle": ((8, 3, 10), (9, -1, 15), (3, 0, None)),
    "hull_inspection": ((24, 0, 8.3), (44, 2, 8.3), (52, -9, 5)),
    "wreck_survey": ((7, -9, None), (18, 12, None), (40, 6, None)),
    "korean_castle": ((13, -25, None), (13, -5, None), (45, 37, None)),
    "coral_reef": ((9, -6, None), (19, -13, None), (34, 10, None)),
    "seagrass_meadow": ((5, -2, None), (16, -9, None), (30, 7, None)),
    "harbor_inspection": ((8, -5, None), (20, -10, 8), (37, 4, None)),
    "sonar_search": ((2, 0, None), (10, 3, None), (17, 5, 13)),
    "incident_jacket": ((-5, -5, 12), (6, -6, 10), (-8, 6, 16)),
    "incident_wreck": ((8, 2, 128), (13, 2, None), (23, -6, None)),
    "incident_silt": ((8, 0, None), (5, -3, None), (1, 1, None)),
    "incident_compass": ((9, 2, 10), (8, -5, 15), (3, 1, None)),
    "incident_current": ((7, 1, None), (0, -4, None), (2, 3, None)),
}

MEADOW = ("shell_hash", "brittle_star", "crab_molt", "shell_hash", "anemones", "brittle_star")
WRECK = ("rust_flake", "ceramic_shard", "shackle", "brittle_star", "rope_offcut", "crab_molt")
HARBOR = ("bottle_glass", "shackle", "ceramic_shard", "rope_offcut", "shell_hash", "net_patch")
OFFSHORE = ("brittle_star", "shell_hash", "rope_offcut", "shackle", "crab_molt", "shell_hash")
FOULING = ("mussels", "anemones", "limpet", "barnacles", "mussels", "barnacles")
SUPPORTS = {"jacket_leg", "monopile", "pile", "hull", "quay", "pen_net", "reef_outcrop", "mudmat", "wreck"}


def _marker(key, index, kind, p, normal, rng):
    return {"id": f"detail-{key}-{index:02}", "kind": kind, "pos": np.asarray(p).round(4).tolist(),
            "normal": np.asarray(normal).round(5).tolist(), "yaw": round(float(rng.uniform(0, 360)), 2)}


def _pen_markers(scenario, rng):
    # Sample the middle of intact panels, avoiding repair targets and holes. Inside launches can
    # approach their samples from inside the net, without crossing the physical enclosure.
    panels = {ob.name: ob for ob in scenario.obstacles if ob.kind == "pen_net"}
    inside = scenario.key == "aquaculture_pen_inside"
    markers = []
    for i, panel in enumerate((22, 21, 20, 19, 18, 17, 26, 27, 28, 29, 30, 31, 33, 34, 35, 37, 39, 41)):
        host = panels[f"pen-net-{panel}-0"]
        point = np.array(host.center, dtype=float)
        radial = point - [24, 0, point[2]]
        normal = radial / np.linalg.norm(radial)
        if inside:
            normal = -normal
        point += normal * host.half[1]
        point[2] = (7, 4.5, 12, 8, 5, 14)[i % 6]
        kinds = ("net_patch", "mussels", "barnacles", "rope_offcut", "anemones", "mussels")
        markers.append(_marker(scenario.key, i, kinds[i % 6], point, normal, rng))
    return markers


def place_discoveries(scenario, world):
    """Seeds are independent of physics and ecology; all viewers use the host's attachment coordinates."""
    if scenario.enclosed:
        return []
    rng = np.random.default_rng([world.world_seed, 83729])
    key = scenario.key
    if key.startswith("aquaculture_pen"):
        return _pen_markers(scenario, rng)
    stations = TRANSECTS.get(key)
    if stations is None:
        stations = [o.point for o in scenario.objectives if o.point is not None][:3]
    floor_kinds = OFFSHORE
    if key in {"coral_reef", "seagrass_meadow", "incident_silt", "open_water"}:
        floor_kinds = MEADOW
    elif "wreck" in key or key == "korean_castle":
        floor_kinds = WRECK
    elif key == "harbor_inspection" or scenario.seabed_type == "mud":
        floor_kinds = HARBOR

    supports = {ob.name for ob in world.obstacles if ob.kind in SUPPORTS}
    roots = []
    markers = []
    if scenario.prewrap:
        # Sheltered patches on alternating sides of the fouling band are visible while inspecting a wrap.
        wrap = scenario.prewrap
        pole = next(ob for ob in scenario.obstacles if ob.name == wrap["pile"])
        for i in range(6):
            angle = math.radians(20 + 60 * i)
            normal = np.array([math.cos(angle), math.sin(angle), 0.])
            root = np.array([*pole.p0[:2], wrap["depth"] + (.23 if i % 2 else -.27)]) + pole.radius * normal
            kind = ("anemones", "barnacles", "brittle_star")[i % 3] if wrap["depth"] > 50 else FOULING[i]
            markers.append(_marker(key, i, kind, root, normal, rng))
            roots.append(root)
        stations = stations[1:]
    spool = np.asarray(scenario.spool_pos, float)
    for n, e, d in stations:
        placed = 0
        for attempt in range(100):
            # Spread outward when a large anchor block occupies part of a transect.
            spread = 2.8 + .06 * attempt
            point = np.array([n, e, d or 0.]) + rng.uniform(-spread, spread, 3)
            if attempt >= 65:
                point[:2] = spool[:2] + rng.uniform(-4, 4, 2)
            if d is None or attempt >= 45:
                point[2] = world.depth_at(point)
            distance, normal, host = world.sdf(point)
            if host != "seabed" and host not in supports:
                continue
            root = point - distance * normal
            gap, normal, host = world.sdf(root)
            if np.linalg.norm(root - spool) >= scenario.tether_length:
                continue
            if abs(gap) > .025 or root[2] < 1.0:
                continue
            if any(np.linalg.norm(root - other) < .65 for other in roots):
                continue
            if world.sdf(root + normal * .85)[0] < .55:
                continue
            kinds = floor_kinds if host == "seabed" else FOULING
            markers.append(_marker(key, len(markers), kinds[placed % len(kinds)], root, normal, rng))
            roots.append(root)
            placed += 1
            if placed == 6:
                break
    return markers
