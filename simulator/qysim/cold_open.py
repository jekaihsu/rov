"""Site of the cold open: one leg of a four-legged offshore wind jacket at slack water, tens of metres down.

The cold open (docs/design/cold-open/README.md) drops a new player into a working dive at this jacket: photograph
the 12 m anode on leg C (south-west corner), head north along the west face to leg B, and the tether catches on
leg C's stand-off anode on the way. Everything here is ordinary scenario data for the existing physics; nothing
in the vehicle, tether or snag model changes:

* the jacket, anodes and mud mats are the same builders as ``jacket_inspection`` (scenarios.jacket,
  site_dressing.dress_jacket);
* leg C's 12 m anode and its two straps carry ``snag_hold`` (site_dressing.snaggable), so the tether snag model
  (tether_snag.py) can hook on them like on any other snaggable fitting. Stand-off anodes are a classic place for
  a small ROV's tether to catch on a jacket (VideoRay snag response and operations notes in
  research_notes/真实 ROV 操作体验研究/operations_tether_sonar.md);
* the incident is set up by where the tether lies, not by chance. The support boat (spool) stands off to the
  south-east with about ten metres more tether out than the straight run to the vehicle. The slack-water current
  sets north-north-west, so that spare tether streams against the outside of the jacket's south face and reaches
  the vehicle from the east, past the south side of leg C, a little below the vehicle. A vehicle that leaves the
  anode northwards along the west face pulls it round the south-west corner of leg C, across the anode, through
  most of a right angle, and it hooks there within a few metres. The hook only opens when that bend is gone
  (tether_snag.py "release"), which needs the vehicle back south, abeam of the anode: the way it came. Letting
  go of the sticks does not do it: the same current carries a drifting vehicle further round the snagged side;
* the tether hand keeps the slack short on purpose (``TETHER_LENGTH``). With 60 m out and the current setting
  east, the spare tether hung in a deep bight on the far side of the boat, the tether reached the anode from
  whichever way that bight happened to lie, and the hook opened by itself or never opened (see
  docs/design/cold-open/README.md §5);
* the fish schools are placed round the legs (a jacket works as an artificial reef) instead of the biome's
  random schools.

Site values are presentation choices for a slack-water dive on a clear day, provisional like every other
scenario value (AGENTS.md): current, visibility and holding forces are not measurements of any real site.
"""
from __future__ import annotations

import math

from . import site_dressing as dressing
from .scenarios import TI_OFFSHORE, Objective, Scenario, jacket
from .world import CurrentProfile

STRINGS = {
    "name": "離岸風場導管架",
    "brief": "平潮時段的導管架巡檢：拍下 C 腿 12 m 陽極，再沿西面往北到 B 腿。",
    "anode_c": "C 腿陽極 @12m",
    "anode_b": "B 腿陽極 @12m",
    "surface": "回收上浮",
}

SEABED = 32.0
PREFIX = "J"
ANODE_DEPTH = 12.0
# Anode depths per leg (m): every leg has a 12 m anode; the deeper row is for the seabed views.
ANODE_DEPTHS = {f"{PREFIX} leg {leg}": (ANODE_DEPTH, 24.0) for leg in "ABCD"}
SNAG_HOLD = (150.0, 260.0)          # N, like SnagFeature's training default; no published data exists
SNAG_ANODE = f"{PREFIX} leg C anode {ANODE_DEPTH:.0f}m"
SNAG_NAMES = (SNAG_ANODE, SNAG_ANODE + " strap 1", SNAG_ANODE + " strap 2")
# Vehicle start: south-west of leg C, just above the anode's depth, the anode a little right of the bow.
START = (-12.0, -9.0, ANODE_DEPTH - 0.5)
START_HEADING = 33.0
SPOOL = (-26.0, 20.0, 0.0)
TETHER_LENGTH = 45.0
CURRENT_KN = 0.15
CURRENT_DIR = (345.0, 345.0, 345.0)
# Schools at home positions round the legs, at least 3 m off the steel (ecology.step_schools keeps them clear).
FISH = (
    {"home": (-5.6, -9.6, 11.6), "count": 64},     # front left of the start view, between the vehicle and leg C
    {"home": (-6.6, -0.7, 10.5), "count": 72},     # beyond leg C, framed through the west face
    {"home": (0.0, 0.0, 14.0), "count": 56},       # inside the jacket
    {"home": (0.0, -11.0, 11.0), "count": 48},     # off the west face, on the way to leg B
    {"home": (8.0, -10.0, 12.0), "count": 40},     # by leg B
)


def _photo_spot(leg, standoff: float = 1.4) -> tuple:
    """Inspection objective for a leg's 12 m anode, faced from outside the jacket."""
    a, b = leg.p0, leg.p1
    t = (ANODE_DEPTH - a[2]) / (b[2] - a[2])
    centre = [a[k] + (b[k] - a[k]) * t for k in range(3)]
    norm = math.hypot(centre[0], centre[1])
    out = (centre[0] / norm, centre[1] / norm)
    reach = leg.radius + dressing.ANODE_STANDOFF + standoff
    stand = (centre[0] + out[0] * reach, centre[1] + out[1] * reach, ANODE_DEPTH)
    return stand, tuple(centre)


def cold_open_jacket() -> Scenario:
    obstacles = jacket(0.0, 0.0, SEABED, prefix=PREFIX)
    obstacles += dressing.dress_jacket(obstacles, 0.0, 0.0, SEABED, ANODE_DEPTHS)
    snaggable = [o for o in obstacles if o.name in SNAG_NAMES]
    dressing.snaggable(snaggable, SNAG_HOLD)
    legs = {o.name[-1]: o for o in obstacles if o.kind == "jacket_leg"}
    objectives = []
    for leg, label in (("C", STRINGS["anode_c"]), ("B", STRINGS["anode_b"])):
        stand, face = _photo_spot(legs[leg])
        objectives.append(Objective("inspect", label, stand, radius=1.5, hold_s=2.0, face_point=face,
                                    standoff=(0.8, 3.0)))
    objectives.append(Objective("surface", STRINGS["surface"], (SPOOL[0] + 3.0, SPOOL[1], 0.5), radius=3.0))
    return Scenario(
        "cold_open_jacket", STRINGS["name"], STRINGS["brief"], seabed_depth=SEABED, obstacles=obstacles,
        current=CurrentProfile(CURRENT_KN, CURRENT_DIR[0], CURRENT_KN * 2 / 3, CURRENT_DIR[1], CURRENT_KN / 3,
                               CURRENT_DIR[2], TI_OFFSHORE),
        visibility_m=22.0, start_pos=START, start_heading_deg=START_HEADING, spool_pos=SPOOL,
        tether_length=TETHER_LENGTH, objectives=objectives, time_limit_s=1200, water_type="oceanic",
        fish_schools=[dict(spec) for spec in FISH])
