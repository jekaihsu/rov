"""Survey-site fish refuges and sections of the host's existing bathymetry grid (illustrative NED metres)."""
from __future__ import annotations

import numpy as np


# Homes follow the shot line, the lee of the first structure and then the deeper survey stations.
# Cold open and farm have their own authored schools. The pool keeps its training layout.
_SCHOOL_HOMES = {
    "open_water": [(12, -1, 5), (11, 15, 8), (-4, 9, 12), (-5, -6, 7)],
    "jacket_inspection": [(7, -1, 4), (11, -6, 7), (21, 9, 11), (27, -9, 15)],
    "monopile_current": [(6, 0, 4), (9, -4, 8), (13, 5, 12), (19, -6, 18)],
    "tether_untangle": [(4.8, 1.1, 8.9), (7, -4, 9), (0, -1, 5), (11, 4, 16)],
    "hull_inspection": [(7, -1, 4), (14, -4, 9), (35, -1, 10.6), (61, -4, 10.3)],
    "wreck_survey": [(8, 3.3, 5.2), (19, 12, 9.8), (30, 18, 14.5), (44, 20.5, 19.6)],
    "korean_castle": [(7.4, -9, 6.5), (14.4, -24, 12), (17.5, -24.6, 19), (33, -6.5, 17.4)],
    "coral_reef": [(7, -2, 5), (12, -8, 10), (26, 8, 11), (18, 8.3, 5.3)],
    "seagrass_meadow": [(6, -2, 3), (11, -6, 5), (24, 8, 6), (34, 6, 5)],
    "harbor_inspection": [(5, -2, 4), (13, -7, 6), (22, -6, 9), (31, 7, 10)],
    "sonar_search": [(3, -1, 12), (9, 3, 12), (15, 4, 12), (21, 7, 11)],
    "incident_jacket": [(4, -1, 12), (-8, -4, 11), (-11, 2, 6), (-4, 8, 14)],
    "incident_wreck": [(12, 3, 128), (6, -3, 127), (16, 5, 131), (27, -5, 132)],
    "incident_silt": [(11, 0, 10), (6, -2, 8), (5.4, 2.3, 8.7), (1, -2, 3)],
    "incident_compass": [(8, -3, 10), (3.1, 1.6, 9), (2, -2, 5), (12, 8, 13)],
    "incident_current": [(11, -1, 8), (5, -2, 8), (4.1, 4.6, 8.3), (15, 6, 12)],
}


def school_refuges(scenario):
    homes = _SCHOOL_HOMES.get(scenario.key)
    if scenario.key == "random":
        homes = [(6, -1, 4)] + [o.point for o in scenario.objectives[:3]]
    if homes is None:
        return scenario.fish_schools
    return [dict(home=p, count=count, radius=1.6) for p, count in zip(homes, (10, 14, 9, 12))]


def channel_relief(east):
    """Depth profile across the channel, shared by bathymetry, kelp beds and mooring feet."""
    # The charted 25 m commissioning lane runs north. Its wide level bed covers the
    # survey box and acoustic beam footprints; rocks and kelp colonize its outer shoulders.
    bank = [-100, -50, -35, -25, -20, -15, -10, 15, 20, 25, 30, 40, 55, 100]
    height = [0, 0, 5, 15, 16, 7, 0, 0, 9, 18, 15, 10, 0, 0]
    return np.interp(east, bank, height)


def shape_bed(terrain, key, obstacles, clear):
    """Parallel bedforms are piecewise planar: the collision interpolant and viewer triangles coincide."""
    if not key or key in ("tutorial_pool", "coral_reef", "seagrass_meadow"):
        return
    if key == "open_water":
        east = terrain.origin[1] + np.arange(terrain.depths.shape[1]) * terrain.spacing
        relief = channel_relief(east)
        terrain.depths -= relief[None, :]
        terrain.relief = float(relief.max())
        return
    north = terrain.origin[0] + np.arange(terrain.depths.shape[0]) * terrain.spacing
    # Long, low depositional ridges, including beyond the industrial footprints.
    relief = (0.5 + 0.5 * np.cos(north * 0.23)) * (0.56 + 0.18 * np.sin(north * 0.1))
    relief[relief < .015] = 0
    if key == "harbor_inspection":
        # The dredged launch lane also provides the known-depth turbidity reference.
        relief[np.abs(north) <= terrain.spacing] = 0
    # Preserve the existing floor under solid fixtures and near-bottom work stations.
    # Walls run below the floor; their infinite bounding plane need not flatten the entire map.
    depth = float(terrain.depths.max())
    for ob in obstacles:
        lo, hi = ob.aabb()
        if hi[2] >= depth - 1 and hi[0] - lo[0] < 500:
            relief[(north >= lo[0] - terrain.spacing) & (north <= hi[0] + terrain.spacing)] = 0
    for point in clear:
        if point[2] >= depth - 3:
            relief[np.abs(north - point[0]) <= terrain.spacing] = 0
    terrain.depths -= relief[:, None]
    terrain.relief = float(relief.max())


# Exposed rock lips interrupt both banks of the open-water course. Small colonies on their
# sunlit slopes make the edge legible from the channel. Other sites retain their biome scatter.
_BANK_PATCHES = np.array([(-3, -19), (11, 21), (21, 18), (12, -16), (-6, 19)])


def bank_patch(index, rng):
    return _BANK_PATCHES[index % len(_BANK_PATCHES)] + rng.normal(0, (1.1, 2.1))
