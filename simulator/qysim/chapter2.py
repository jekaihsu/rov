"""Chapter 2 aquaculture turning points as ordinary scenario data (docs/prompts/R3-chapter2.md).

Nothing here changes the vehicle, tether, silt or snag models. Each mission's crisis is arranged by
where the site sits: current direction (lee-side net billow + snag risk), seabed type under the net
floor (stirred turbidity), and the escape-hole attractor already published by aquaculture_pen_escape.

Site numbers are provisional presentation choices, like every other scenario value (AGENTS.md).
"""
from __future__ import annotations

import math

from .aquaculture import CENTER, DEPTH, RADIUS, hole_truth, layout

# Current flows toward east (90°). The lee / downstream face is the east arc; panels there bow out into
# the fairway when the water pushes through the net (C2-1 turning point).
CURRENT_DIR_DEG = 90.0
# East-facing arc in clock hours on the pen (12 = +N, 3 = +E). Director and tests use this band.
BILLOW_CLOCK = (1.5, 4.5)
BILLOW_RADIUS = (19.0, 22.8)
BILLOW_DEPTH = (4.0, 14.0)
# Outer-arc path a scripted pilot flies along the lee (east, +E) face to prove a net snag.
# Pen layout: angle 0 is +N, angle π/2 is +E (aquaculture.point).
LEE_SNAG_START = (36.0, 21.0, 7.0)
LEE_SNAG_TARGET = (12.0, 21.0, 7.0)
LEE_SNAG_YAW_DEG = 180.0  # south along the east face

# C2-2: morts sit on the net floor. The inside variant drops the seabed to that floor and removes the
# polygonal floor panels so thruster jets reach the fluff bed (incident_silt pattern). Floor panels
# otherwise sit on the bed and swallow the jet before silt can erode.
INSIDE_SEABED = DEPTH
INSIDE_SEABED_TYPE = "fluff"
INSIDE_BNL_HEIGHT_M = 0.0
INSIDE_BNL_MG_L = 0.0

# C2-3 window (seconds) published on aquaculture.escape; matches the radio "十二分窗口".
ESCAPE_WINDOW_S = 720


def clock_on_pen(pos, center=CENTER) -> float:
    """Clock face on the pen: 12 = north (+N), 3 = east (+E). Returns 1–12."""
    north = float(pos[0]) - center[0]
    east = float(pos[1]) - center[1]
    deg = math.degrees(math.atan2(east, north)) % 360.0
    clock = deg / 30.0
    if clock < 0.5:
        return 12.0
    return 12.0 if clock > 12.0 else clock


def in_billow_zone(pos) -> bool:
    """True when the vehicle is on the lee outer arc where the net bows out into the fairway."""
    dn = float(pos[0]) - CENTER[0]
    de = float(pos[1]) - CENTER[1]
    radius = math.hypot(dn, de)
    if radius < BILLOW_RADIUS[0] or radius > BILLOW_RADIUS[1]:
        return False
    depth = float(pos[2])
    if depth < BILLOW_DEPTH[0] or depth > BILLOW_DEPTH[1]:
        return False
    clock = clock_on_pen(pos)
    lo, hi = BILLOW_CLOCK
    if lo <= hi:
        return lo <= clock <= hi
    return clock >= lo or clock <= hi


def chapter2_summary(key: str) -> dict:
    """Presentation metadata for the three Chapter 2 variants; empty for unrelated sites."""
    key = str(key)
    if not key.startswith("aquaculture_pen"):
        return {}
    data = {
        "current_dir_deg": CURRENT_DIR_DEG,
        "billow": {
            "clock": list(BILLOW_CLOCK),
            "radius_m": list(BILLOW_RADIUS),
            "depth_m": list(BILLOW_DEPTH),
            "center": list(CENTER),
        },
    }
    if key == "aquaculture_pen_slack":
        data["mission"] = "net_inspection"
        data["lee_snag"] = {
            "start": list(LEE_SNAG_START),
            "target": list(LEE_SNAG_TARGET),
            "yaw_deg": LEE_SNAG_YAW_DEG,
        }
    elif key == "aquaculture_pen_inside":
        data["mission"] = "mort_recovery"
        data["silt"] = {
            "seabed_type": INSIDE_SEABED_TYPE,
            "seabed_depth_m": INSIDE_SEABED,
            "bnl_height_m": INSIDE_BNL_HEIGHT_M,
            "bnl_mg_l": INSIDE_BNL_MG_L,
        }
    elif key == "aquaculture_pen_escape":
        data["mission"] = "escape"
        holes = layout()[1]["holes"]
        primary = holes[0]
        data["escape"] = {
            "hole_id": primary["id"],
            "priority": True,
            "window_s": ESCAPE_WINDOW_S,
            "truth": hole_truth(primary),
        }
    return data
