"""Chapter-1 physics turns: scene data only for the four harbour career sites.

Each C1 mission keeps the base site builders (harbor piles / hull / sonar box) and only adjusts
spawn, current, tether layout, snag marks, visibility and echo props so one existing physics
effect happens reliably. Nothing in the vehicle, tether solver, snag model or SDK changes:

* C1-1 ``harbor_inspection_turbid`` — 1.5 m vis; start near pile A so a 0.7×visibility standoff is
  reachable without contact, while driving into the pile still contacts (AGENTS.md provisional);
* C1-2 ``hull_inspection_berth`` — 3.0 m vis; stronger mid/bottom current toward the prop hub
  approximates suction on the aft approach (provisional knots; not a measured berth profile);
* C1-3 ``sonar_search_echoes`` — three solid returns in a line (two decoy rocks + one instrument);
  only the instrument is the objective;
* C1-4 ``harbor_inspection_signoff`` — 4.0 m vis; A3 marked snaggable and the spool / tether /
  current set so a rushed B3→quay transit wraps (cold_open.py pattern).

Site values are presentation choices for training, provisional like every other scenario value.
"""
from __future__ import annotations

import math

from . import site_dressing as dressing
from .scenarios import (
    HARBOR_VARIANT_STRINGS,
    HULL_VARIANT_STRINGS,
    Objective,
    Scenario,
    TI_SHELTERED,
    harbor_inspection,
    hull_inspection,
    sonar_search,
)
from .world import Box, CurrentProfile

STRINGS = {
    "echoes_name": "聲納搜尋（三回波）",
    "echoes_brief": "濁水港池：聲納可見三個回波，只有測量儀是目標；先辨位再以攝影機確認。",
    "instrument": "掉落測量儀",
    "rock_west": "誘餌礁石西",
    "rock_east": "誘餌礁石東",
    "confirm": "接近並確認測量儀",
}

# ── C1-1 turbid harbour (Level II standoff) ───────────────────────────────
TURBID_VIS_M = 1.5
# 0.7× visibility from the pile face (brief / chapter1.md). Provisional training standoff.
TURBID_STANDOFF_M = 0.7 * TURBID_VIS_M
PILE_A_NAME = "Harbor pile A"
PILE_A_CENTER = (21.0, -10.0)
PILE_A_RADIUS = 0.65
# West of pile A at the standoff range; first inspect objective faces the pile.
TURBID_APPROACH = (
    PILE_A_CENTER[0] - (PILE_A_RADIUS + TURBID_STANDOFF_M),
    PILE_A_CENTER[1],
    8.0,
)
# Closer start for smoke / short approach (provisional; not a measured launch point).
TURBID_START = (16.0, -10.0, 8.0)
TURBID_HEADING_DEG = 0.0

# ── C1-2 berth hull (prop suction via CurrentProfile) ─────────────────────
BERTH_VIS_M = 3.0
# Prop hub on the existing 80 m hull at center (50, 0), yaw 0 — see site_dressing.propeller_layout.
PROP_HUB = (14.4, 0.0, 5.56)
PROP_HUB_NAME = "Hull 貨輪船殼 propeller hub"
# Stronger mid/bottom flow toward +N (0°) so an approach from the start is pushed toward the prop.
# Provisional berth suction stand-in; not a measured wake or thruster wash.
SUCTION_CURRENT_KN = (0.25, 1.8, 1.4)          # surface, mid, bottom
SUCTION_CURRENT_DIR = (0.0, 0.0, 0.0)
# Corridor sample just clear of the hub solid (world.current_at is zero inside solids).
PROP_APPROACH_SAMPLE = (9.0, 0.0, 5.56)
PROP_FAR_SAMPLE = (9.0, -40.0, 5.56)

# ── C1-3 sonar echoes ─────────────────────────────────────────────────────
INSTRUMENT_NAME = STRINGS["instrument"]
INSTRUMENT_POS = (18.0, 5.0, 13.0)
ROCK_WEST_POS = (14.0, 5.0, 13.0)
ROCK_EAST_POS = (22.0, 5.0, 13.0)
ECHO_HALF = (0.6, 0.6, 0.8)
INSTRUMENT_HALF = (1.0, 1.0, 2.0)
# Checkpoint just west of the instrument, same pattern as sonar_search.
INSTRUMENT_CHECKPOINT = (16.0, 5.0, 13.0)

# ── C1-4 sign-off rush (tether wrap / snag) ────────────────────────────────
SIGNOFF_VIS_M = 4.0
SNAG_PILE = "Harbor pile A3"                   # task example; snaggable via site_dressing.snaggable
SNAG_HOLD = (150.0, 260.0)                     # N, like cold_open / SnagFeature training default
# Spool west of the B-row so a rushed B3→quay transit wraps the B-row (often B3). Provisional.
SIGNOFF_SPOOL = (8.0, 10.0, 0.0)
SIGNOFF_TETHER_LENGTH = 55.0
SIGNOFF_CURRENT_KN = (0.35, 0.25, 0.12)
SIGNOFF_CURRENT_DIR = (90.0, 95.0, 100.0)
# Scripted rush endpoints (career deliverable points for anomalies 2 and 3).
SIGNOFF_B3 = (33.0, 12.0, 14.0)                # north of B3 pile
SIGNOFF_QUAY = (42.0, -6.0, 12.0)


def harbor_inspection_turbid() -> Scenario:
    """Same harbour at ~1.5 m visibility; start near pile A for the Level II standoff turn."""
    sc = harbor_inspection()
    sc.key = "harbor_inspection_turbid"
    sc.name = HARBOR_VARIANT_STRINGS["turbid_name"]
    sc.brief = HARBOR_VARIANT_STRINGS["turbid_brief"]
    sc.visibility_m = TURBID_VIS_M
    sc.start_pos = TURBID_START
    sc.start_heading_deg = TURBID_HEADING_DEG
    face = (PILE_A_CENTER[0], PILE_A_CENTER[1], TURBID_APPROACH[2])
    # Keep the other harbour objectives; only the first pile uses the 0.7×vis standoff point.
    rest = [o for o in sc.objectives if o.label != "港樁 A"]
    sc.objectives = [
        Objective("inspect", "港樁 A", TURBID_APPROACH, 1.5, hold_s=6.0, face_point=face,
                  standoff=(TURBID_STANDOFF_M * 0.7, TURBID_STANDOFF_M * 1.4)),
        *rest,
    ]
    return sc


def hull_inspection_berth() -> Scenario:
    """Same hull at ~3 m visibility with a provisional northward mid/bottom suction current."""
    sc = hull_inspection()
    sc.key = "hull_inspection_berth"
    sc.name = HULL_VARIANT_STRINGS["berth_name"]
    sc.brief = HULL_VARIANT_STRINGS["berth_brief"]
    sc.visibility_m = BERTH_VIS_M
    s_kn, m_kn, b_kn = SUCTION_CURRENT_KN
    s_dir, m_dir, b_dir = SUCTION_CURRENT_DIR
    sc.current = CurrentProfile(s_kn, s_dir, m_kn, m_dir, b_kn, b_dir, TI_SHELTERED)
    return sc


def sonar_search_echoes() -> Scenario:
    """Low-vis acoustic search with three solid returns; only the instrument is the objective."""
    sc = sonar_search()
    sc.key = "sonar_search_echoes"
    sc.name = STRINGS["echoes_name"]
    sc.brief = STRINGS["echoes_brief"]
    sc.obstacles = [
        Box(STRINGS["rock_west"], ROCK_WEST_POS, ECHO_HALF),
        Box(INSTRUMENT_NAME, INSTRUMENT_POS, INSTRUMENT_HALF),
        Box(STRINGS["rock_east"], ROCK_EAST_POS, ECHO_HALF),
    ]
    sc.objectives = [
        Objective("checkpoint", STRINGS["confirm"], INSTRUMENT_CHECKPOINT, radius=1.5,
                  target=INSTRUMENT_NAME),
    ]
    return sc


def harbor_inspection_signoff() -> Scenario:
    """Same harbour at ~4 m vis; A3 snaggable and spool/current set for a B3→quay wrap."""
    sc = harbor_inspection()
    sc.key = "harbor_inspection_signoff"
    sc.name = HARBOR_VARIANT_STRINGS["signoff_name"]
    sc.brief = HARBOR_VARIANT_STRINGS["signoff_brief"]
    sc.visibility_m = SIGNOFF_VIS_M
    sc.spool_pos = SIGNOFF_SPOOL
    sc.tether_length = SIGNOFF_TETHER_LENGTH
    s_kn, m_kn, b_kn = SIGNOFF_CURRENT_KN
    s_dir, m_dir, b_dir = SIGNOFF_CURRENT_DIR
    sc.current = CurrentProfile(s_kn, s_dir, m_kn, m_dir, b_kn, b_dir, TI_SHELTERED)
    snag = [o for o in sc.obstacles if o.name == SNAG_PILE]
    dressing.snaggable(snag, SNAG_HOLD)
    return sc


def pile_a_surface_distance(pos) -> float:
    """Horizontal clearance from ``pos`` to the face of harbour pile A."""
    dx = float(pos[0]) - PILE_A_CENTER[0]
    dy = float(pos[1]) - PILE_A_CENTER[1]
    return math.hypot(dx, dy) - PILE_A_RADIUS
