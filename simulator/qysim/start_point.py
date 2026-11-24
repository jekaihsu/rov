"""Optional "start near the work" spawn point for the assisted presentation (PROTOCOL.md, Optional start point).

A real dive starts at the surface; the `real` preset keeps that (and the deployment procedure governs it). The
viewer's assisted preset may instead ask once, before the motors are unlocked, to place a locked vehicle a few
metres short of the scenario's first work point, facing it, so there is something to see in the first minute.
Only the spawn point moves, exactly like the multiplayer spread in room.py: the vehicle, tether and sensor models
are rebuilt the same way a scenario load builds them, and no dynamics or SDK semantics change.
"""
import math

import numpy as np

from .physics import q_from_euler, q_rot
from .tether import Tether

# Scenarios whose first work point is out of view from the surface start. Incident drills already start in the
# situation, the pool is the first-dive tutorial and the sonar search is about finding the target unseen.
SCENARIOS = ("open_water", "jacket_inspection", "monopile_current", "hull_inspection", "wreck_survey",
             "korean_castle", "coral_reef", "seagrass_meadow", "harbor_inspection")
WORK_KINDS = ("inspect", "checkpoint", "station_keep")
MIN_ALTITUDE_M = 2.5      # comfortable working height above the bed; assumed, not a procedure value
MIN_CLEARANCE_M = 1.5     # free water round the hull at the start point
STANDOFF_M = (3.0, 7.0)   # distance short of the work point, bounded by visibility


def _work_point(scenario):
    for objective in scenario.objectives:
        if objective.kind in WORK_KINDS and objective.point is not None:
            return objective
    return None


def near_target_pose(sim):
    """Return {"pos": [n, e, d], "heading": deg} short of the first work point, or None when not offered."""
    scenario = sim.scenario
    if scenario.key not in SCENARIOS:
        return None
    objective = _work_point(scenario)
    if objective is None:
        return None
    goal = np.asarray(objective.point, float)
    face = np.asarray(getattr(objective, "face_point", None) or objective.point, float)
    origin = np.asarray(scenario.start_pos, float)
    direction = goal[:2] - origin[:2]
    distance = float(np.linalg.norm(direction))
    if distance < 1e-6:
        return None
    direction /= distance
    standoff = max(STANDOFF_M[0], min(STANDOFF_M[1], 0.4 * float(scenario.visibility_m)))
    for step in range(16):
        back = standoff + step
        if back >= distance:
            break
        north, east = goal[:2] - direction * back
        bed = float(sim.world.depth_at(np.array([north, east, 0.0])))
        depth = min(float(goal[2]), bed - MIN_ALTITUDE_M)
        if depth < 1.0:
            continue
        point = np.array([north, east, depth])
        if float(sim.world.sdf(point)[0]) <= MIN_CLEARANCE_M:
            continue
        look = face[:2] - point[:2]
        heading = math.degrees(math.atan2(float(look[1]), float(look[0]))) % 360.0
        return {"pos": [round(float(v), 3) for v in point], "heading": round(heading, 1)}
    return None


def apply_near_target_start(sim):
    """Move a locked vehicle that has not opted into the procedure to the near-target pose."""
    if sim.procedure.active:
        raise ValueError("完整下水流程進行中，不能改變出發點")
    if sim.rc.rc_lock != 1:
        raise ValueError("請先上鎖再改變出發點")
    pose = near_target_pose(sim)
    if pose is None:
        return {"type": "start_result", "ok": False, "start": None}
    state = sim.vehicle.s
    state.pos[:] = pose["pos"]
    state.vel[:] = 0
    state.omega[:] = 0
    state.q = q_from_euler(0.0, 0.0, math.radians(pose["heading"]))
    sim.controller.reset_holds(state.q)
    old = sim.tether
    gland = state.pos + q_rot(state.q, old.gland_body)
    sim.tether = Tether(sim.world, old.spool, gland, old.length, old.p, gland_body=old.gland_body)
    sim.tether.settle(2.0, state.pos, state.q)
    sim.sensors.reset(sim)
    return {"type": "start_result", "ok": True, "start": pose}
