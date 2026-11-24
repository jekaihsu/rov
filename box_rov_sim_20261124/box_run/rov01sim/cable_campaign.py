"""Operation: Deep Link — 海底電纜搶修與維護連貫戰役 (Seamless 4-Stage Cohesive Subsea Cable Campaign).

Implements JK's priority gameplay direction (`t949u`, `t950u`):
  1. Subsea cable recovery, maintenance, and splice repair (`SR-IND-06` Power Junction Skid,
     `SR-IND-03` High-Pressure Clamp Manifold, `SR-IND-05` Articulated Manipulator Arm,
     `SR-IND-01` Industrial Rack Debris).
  2. Cohesive 4-Stage continuous campaign flow on one seamless seabed map:
     - Stage 1 (LOCATE): 下潛與聲納尋纜 — Dive through glowing 3D waypoint rings & sonar pulses to the fault zone.
     - Stage 2 (RETRIEVE & CLEAR): 障礙清除與機械手臂撿電纜 — Clear industrial rack debris, lock & grab the dislodged
       subsea cable with ROV-01's manipulator arm, and tow the live catenary cable to the Splice Saddle.
     - Stage 3 (REPAIR & SECURE): 強流下接頭盒維修與管夾鎖固 — Hold station in 1.2 kn cross-current and execute the
       3-step repair sequence (Bio-fouling Jet Clean -> SimReady Clamp Torque Lock -> 400kV/100Gbps Continuity Test).
     - Stage 4 (ENERGIZE & EXTRACT): 海纜全線通電脈衝與母船吊籠回收 — Trigger the full-seabed cable re-energized
       light pulse and return to the TMS Recovery Cage for S-Rank campaign completion & Steam achievement unlock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable

import numpy as np


STAGE_1_LOCATE = "STAGE_1_LOCATE"
STAGE_2_RETRIEVE = "STAGE_2_RETRIEVE"
STAGE_3_REPAIR = "STAGE_3_REPAIR"
STAGE_4_EXTRACT = "STAGE_4_EXTRACT"

CAMPAIGN_STAGES: list[dict[str, Any]] = [
    {
        "stage_num": 1,
        "stage_code": "STAGE_1_LOCATE",
        "title_zh": "STAGE 1/4：下潛與聲納尋纜 (LOCATE)",
        "objective_zh": "穿越 3 座聲納導引光圈，下潛定位 B 區海底主幹光電複合纜斷訊點",
        "objective_en": "Dive through 3 sonar guidance rings to locate the severed subsea trunk cable fault zone",
        "target_ned": [4.5, -1.5, 5.2],
        "simready_focus": "SR-IND-01",
        "comms_speaker": "母船指揮官 CH-16 (Mother Vessel Bridge)",
        "comms_text": "「ROV-01 注意，B 區海底主幹複合電纜訊號中斷！請順著聲納導引光圈下潛至 5.2m 斷纜座標！」",
    },
    {
        "stage_num": 2,
        "stage_code": "STAGE_2_RETRIEVE",
        "title_zh": "STAGE 2/4：障礙清除與機械手臂撿電纜 (RETRIEVE & TOW)",
        "objective_zh": "使用機械手臂移開壓纜鋼架 (SR-IND-01)、夾取斷落海纜端頭並拖曳至搶修鞍座 (SR-IND-06)",
        "objective_en": "Clear fallen rack debris, grab the dislodged subsea cable with manipulator [E], and tow to splice saddle",
        "target_ned": [6.8, 1.2, 6.4],
        "saddle_ned": [9.2, -1.8, 6.8],
        "simready_focus": "SR-IND-05",
        "comms_speaker": "ROV 領航官 (Subsea Pilot Lead)",
        "comms_text": "「已抵達斷纜區！電纜被落石與鋼架壓住，靠近至 3m 內按 [E] 啟動機械手臂移開障礙並夾起海纜，注意懸鏈拖曳張力！」",
    },
    {
        "stage_num": 3,
        "stage_code": "STAGE_3_REPAIR",
        "title_zh": "STAGE 3/4：強流下接頭盒維修與管夾鎖固 (REPAIR & SECURE)",
        "objective_zh": "啟動定深/定艏向抗 1.2 kn 海流，完成三段式海纜搶修：高壓水刀清淤 → SimReady 管夾鎖固 → 絕緣檢測",
        "objective_en": "Engage Depth/Heading Hold in 1.2 kn current and complete 3-step splice box repair & clamp torque lock",
        "target_ned": [9.2, -1.8, 6.8],
        "simready_focus": "SR-IND-06",
        "comms_speaker": "水下工程總監 (Subsea Chief Engineer)",
        "comms_text": "「海纜已就位！側向海流增強至 1.2 kn，請鎖定定深 PID 並執行三段式水下接頭盒搶修與扭力鎖固！」",
    },
    {
        "stage_num": 4,
        "stage_code": "STAGE_4_EXTRACT",
        "title_zh": "STAGE 4/4：海纜全線通電脈衝與吊籠回收 (ENERGIZE & EXTRACT)",
        "objective_zh": "確認 400kV/100Gbps 全線通電脈衝亮起，循回收信標返航進入母船水下 TMS 吊籠完成結算",
        "objective_en": "Verify 400kV/100Gbps cable re-energized pulse and dock into the Subsea TMS Recovery Cage",
        "target_ned": [0.0, 0.0, 2.2],
        "simready_focus": "SR-IND-07",
        "comms_speaker": "母船指揮官 CH-16 (Mother Vessel Bridge)",
        "comms_text": "「接頭鎖固完成，正在送電——全線光電訊號恢復 100%！幹得好 ROV-01，請循綠色信標返航進入 TMS 吊籠！」",
    },
]

REPAIR_SUBSTEPS: list[dict[str, Any]] = [
    {
        "step_index": 1,
        "step_id": "jet_clean",
        "title_zh": "Step 1/3：高壓水刀海生物與除鏽清理",
        "title_en": "Bio-fouling & Rust Cavitation Jet Cleaning",
        "simready_asset": "SR-IND-03",
        "progress_target_pct": 34.0,
    },
    {
        "step_index": 2,
        "step_id": "clamp_torque",
        "title_zh": "Step 2/3：光電接頭盒對接與 SimReady 保護管夾鎖固",
        "title_en": "Splice Box Alignment & SimReady Clamp Torque Lock",
        "simready_asset": "SR-IND-06",
        "progress_target_pct": 68.0,
    },
    {
        "step_index": 3,
        "step_id": "continuity_test",
        "title_zh": "Step 3/3：400kV 高壓絕緣與光纖通電測試",
        "title_en": "400kV / 100Gbps Insulation & Optical Continuity Test",
        "simready_asset": "SR-IND-05",
        "progress_target_pct": 100.0,
    },
]


def compute_catenary_curve_ned(
    start_ned: list[float] | tuple[float, float, float],
    end_ned: list[float] | tuple[float, float, float],
    num_points: int = 16,
    sag_m: float = 0.85,
    seabed_depth_m: float = 7.4,
) -> list[list[float]]:
    """Compute a 3D subsea catenary curve between seabed anchor and ROV-01 gripper/saddle."""
    p0 = np.asarray(start_ned, dtype=float)
    p1 = np.asarray(end_ned, dtype=float)
    n = max(4, int(num_points))
    pts: list[list[float]] = []
    for i in range(n):
        u = i / float(n - 1)
        lin = (1.0 - u) * p0 + u * p1
        # Parabolic/catenary sag in NED Down (+Z) clamped to seabed floor
        sag_offset = 4.0 * u * (1.0 - u) * float(sag_m)
        z_ned = min(float(seabed_depth_m), float(lin[2] + sag_offset))
        pts.append([round(float(lin[0]), 3), round(float(lin[1]), 3), round(z_ned, 3)])
    return pts


# ── Towed-cable physics (deterministic, bounded) ─────────────────────────────
# Armoured trunk cable, sea-water numbers.  All forces are bounded so a bad input can never poison
# the vehicle integrator.  Force on the ROV = catenary/axial pull toward the seabed anchor
#   + seabed Coulomb friction of the dragged length + quadratic hydrodynamic drag of the lifted
#   span (water-relative, so a cross-current loads the tow) + half the lifted span's wet weight.
CABLE_FREE_LENGTH_M = 8.6        # paid-out cable between seabed anchor and the gripper
CABLE_WET_WEIGHT_N_PER_M = 5.5   # submerged weight
CABLE_DIAMETER_M = 0.04
CABLE_CD = 1.2
CABLE_SEABED_MU = 0.6
CABLE_H0_N = 38.0                # catenary pre-tension when the slack is fully removed
CABLE_AXIAL_K_N_PER_M = 1500.0   # elastic stiffness once the cable runs taut (span > free length)
CABLE_FORCE_CAP_N = 260.0        # hard bound on the force applied to the vehicle
CABLE_TENSION_WARN_N = 120.0     # HUD warning: tow tension high
CABLE_TENSION_SLIP_N = 200.0     # gripper holding limit
CABLE_SLIP_HOLD_S = 0.4          # time above the limit before the jaws slip (rejects 1-tick spikes)
SEAWATER_RHO = 1025.0


def compute_cable_tow_load(
    tip_ned: list[float] | np.ndarray,
    anchor_ned: list[float] | np.ndarray,
    free_length_m: float = CABLE_FREE_LENGTH_M,
    tip_vel_ned: list[float] | np.ndarray | None = None,
    current_ned: list[float] | np.ndarray | None = None,
) -> dict[str, Any]:
    """Load of the towed trunk cable on the ROV gripper. Returns force ON the ROV (NED, N), tension and slack."""
    tip = np.asarray(tip_ned, dtype=float)
    anchor = np.asarray(anchor_ned, dtype=float)
    vel = np.zeros(3) if tip_vel_ned is None else np.asarray(tip_vel_ned, dtype=float)
    cur = np.zeros(3) if current_ned is None else np.asarray(current_ned, dtype=float)
    if not (np.all(np.isfinite(tip)) and np.all(np.isfinite(anchor)) and np.all(np.isfinite(vel)) and np.all(np.isfinite(cur))):
        return {"force_ned": [0.0, 0.0, 0.0], "tension_n": 0.0, "span_m": 0.0, "slack_m": float(free_length_m),
                "pull_n": 0.0, "friction_n": 0.0, "drag_n": 0.0}
    L = max(0.5, float(free_length_m))
    vel = np.clip(vel, -4.0, 4.0)
    rel = np.clip(vel - cur, -4.0, 4.0)
    d = anchor - tip
    span = float(np.linalg.norm(d))
    u = d / span if span > 1e-6 else np.zeros(3)
    ratio = min(span / L, 1.0)
    pull = CABLE_H0_N * ratio ** 3 + CABLE_AXIAL_K_N_PER_M * max(0.0, span - L)
    # seabed friction on the dragged half-span, horizontal, smooth sign (no chatter at rest)
    vh = np.array([vel[0], vel[1], 0.0])
    vh_n = float(np.linalg.norm(vh))
    mu_force = CABLE_SEABED_MU * CABLE_WET_WEIGHT_N_PER_M * 0.5 * min(span, L)
    friction = -(vh / vh_n if vh_n > 1e-9 else np.zeros(3)) * mu_force * math.tanh(vh_n / 0.05)
    # lifted span ~30 % of the chord: quadratic drag on the water-relative velocity + half its wet weight
    l_susp = 0.3 * min(span, L)
    rel_n = float(np.linalg.norm(rel))
    drag = -0.5 * SEAWATER_RHO * CABLE_CD * CABLE_DIAMETER_M * l_susp * rel_n * rel
    weight = np.array([0.0, 0.0, 0.5 * CABLE_WET_WEIGHT_N_PER_M * l_susp])
    force = u * pull + friction + drag + weight
    f_n = float(np.linalg.norm(force))
    if f_n > CABLE_FORCE_CAP_N:
        force = force * (CABLE_FORCE_CAP_N / f_n)
        f_n = CABLE_FORCE_CAP_N
    return {
        "force_ned": [float(x) for x in force],
        "tension_n": round(min(float(pull + np.linalg.norm(friction) + np.linalg.norm(drag)), 400.0), 1),
        "span_m": round(span, 3),
        "slack_m": round(L - span, 3),
        "pull_n": round(float(pull), 1),
        "friction_n": round(float(np.linalg.norm(friction)), 1),
        "drag_n": round(float(np.linalg.norm(drag)), 1),
    }


def push_out_of_obstacles(
    point: list[float] | np.ndarray,
    sdf_fn: Callable[[np.ndarray], tuple[float, np.ndarray]] | None,
    clearance_m: float,
    max_iter: int = 8,
    max_depth_m: float | None = None,
) -> list[float]:
    """Deterministically move ``point`` along the world SDF normal until it is >= ``clearance_m`` from every
    obstacle and the seabed. Points already clear are returned unchanged (so open water is a no-op)."""
    p = np.asarray(point, dtype=float).copy()
    if sdf_fn is None or p.shape != (3,) or not np.all(np.isfinite(p)):
        return [float(x) for x in p]
    for _ in range(max_iter):
        d, n = sdf_fn(p)
        if not math.isfinite(d) or d >= clearance_m - 1e-6:
            break
        n = np.asarray(n, dtype=float)
        nn = float(np.linalg.norm(n))
        if nn < 1e-9:
            break
        p = p + n / nn * (clearance_m - d + 1e-3)
        p[2] = max(0.3, p[2])
        if max_depth_m is not None:
            p[2] = min(max_depth_m, p[2])
    return [round(float(x), 3) for x in p]


# Cleanly outside every obstacle: a manipulator reach point / spawn point must sit this far from a surface.
REACH_STANDOFF_M = 0.9

# Single source for interaction radii: used by both the HUD prompt (to_dict.can_interact)
# and the server-side action gates, so the UI can never offer an action the server refuses.
INTERACT_RADIUS_M: dict[int, float] = {1: 3.2, 2: 3.2, 3: 3.5, 4: 3.5}
DRILL_RANK = "DRILL (訓練跳關 · 不計排名)"


@dataclass
class SubseaCableCampaign:
    """Seamless 4-Stage Cohesive Gameplay Campaign state machine attached to Wave1Manager."""

    campaign_id: str = "operation_deep_link"
    campaign_title_zh: str = "深海連線：海底主幹電纜緊急搶修戰役 (Operation: Deep Link)"
    active: bool = True
    stage_num: int = 1
    waypoint_rings_cleared: int = 0
    waypoint_rings_total: int = 3
    debris_cleared: bool = False
    cable_grabbed: bool = False
    cable_seated_in_saddle: bool = False
    cable_anchor_ned: list[float] = field(default_factory=lambda: [3.2, 2.8, 6.9])
    cable_tip_ned: list[float] = field(default_factory=lambda: [6.8, 1.2, 6.4])
    splice_saddle_ned: list[float] = field(default_factory=lambda: [9.2, -1.8, 6.8])
    tms_cage_ned: list[float] = field(default_factory=lambda: [0.0, 0.0, 2.2])
    cable_tension_n: float = 42.0
    cable_free_length_m: float = CABLE_FREE_LENGTH_M
    cable_tow_force_ned: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    cable_tension_warning: str = "OK"       # OK | HIGH | CRITICAL | SLIPPED
    cable_slip_count: int = 0
    cable_over_limit_s: float = 0.0
    cable_load: dict[str, Any] = field(default_factory=dict)
    clearance_fn: Any = field(default=None, repr=False, compare=False)  # world SDF: p -> (dist, outward normal)
    repair_step_index: int = 0  # 0..3
    repair_progress_pct: float = 0.0
    cable_energized: bool = False
    energized_pulse_phase: float = 0.0
    tms_extracted: bool = False
    campaign_completed: bool = False
    campaign_rank: str = "IN_PROGRESS"
    campaign_score: float = 0.0
    drill_mode: bool = False
    last_rejection: str = ""
    comms_history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.comms_history:
            self._push_stage_comms(1)

    def _push_stage_comms(self, stage_num: int, custom_speaker: str | None = None, custom_text: str | None = None) -> None:
        st = next((s for s in CAMPAIGN_STAGES if s["stage_num"] == stage_num), CAMPAIGN_STAGES[0])
        entry = {
            "stage_num": stage_num,
            "speaker": custom_speaker or st["comms_speaker"],
            "text": custom_text or st["comms_text"],
        }
        self.comms_history.append(entry)
        self.comms_history = self.comms_history[-8:]

    def current_stage_meta(self) -> dict[str, Any]:
        idx = max(1, min(4, int(self.stage_num))) - 1
        return CAMPAIGN_STAGES[idx]

    def current_target_ned(self) -> list[float]:
        if self.stage_num == 1:
            ring_coords = [
                [2.2, -0.6, 3.0],
                [3.4, -1.1, 4.2],
                [4.5, -1.5, 5.2],
            ]
            idx = min(len(ring_coords) - 1, self.waypoint_rings_cleared)
            return list(ring_coords[idx])
        if self.stage_num == 2:
            if not self.cable_grabbed:
                return list(self.cable_tip_ned)
            return list(self.splice_saddle_ned)
        if self.stage_num == 3:
            return list(self.splice_saddle_ned)
        return list(self.tms_cage_ned)

    def reset_campaign(self) -> dict[str, Any]:
        self.active = True
        self.stage_num = 1
        self.waypoint_rings_cleared = 0
        self.debris_cleared = False
        self.cable_grabbed = False
        self.cable_seated_in_saddle = False
        self.cable_anchor_ned = [3.2, 2.8, 6.9]
        self.cable_tip_ned = [6.8, 1.2, 6.4]
        self.cable_tension_n = 42.0
        self._clear_cable_load()
        self.cable_slip_count = 0
        self.repair_step_index = 0
        self.repair_progress_pct = 0.0
        self.cable_energized = False
        self.energized_pulse_phase = 0.0
        self.tms_extracted = False
        self.campaign_completed = False
        self.campaign_rank = "IN_PROGRESS"
        self.campaign_score = 0.0
        self.drill_mode = False
        self.last_rejection = ""
        self.comms_history.clear()
        self._push_stage_comms(1)
        return self.to_dict()

    def _clear_cable_load(self) -> None:
        self.cable_free_length_m = CABLE_FREE_LENGTH_M
        self.cable_tow_force_ned = [0.0, 0.0, 0.0]
        self.cable_tension_warning = "OK"
        self.cable_over_limit_s = 0.0
        self.cable_load = {}

    def reach_point_ned(self, nominal_ned: list[float] | np.ndarray) -> list[float]:
        """Where the manipulator can actually reach for ``nominal_ned``.

        Campaign coordinates are authored for open water. In a scenario whose scenery covers a target
        (Mission 2: the ship hull encloses the rings, saddle and TMS cage), the ROV can never get closer
        than hull surface + body radius, so the interaction distance is measured to the nearest reachable
        point on the obstacle surface (``REACH_STANDOFF_M`` clear of it) instead of the buried nominal
        point. Open water is an exact no-op."""
        return push_out_of_obstacles(nominal_ned, self.clearance_fn, REACH_STANDOFF_M)

    def reach_target_ned(self) -> list[float]:
        return self.reach_point_ned(self.current_target_ned())

    def _distance_to_target(self, rov_pos_ned: list[float] | np.ndarray | None) -> float | None:
        if rov_pos_ned is None:
            return None
        p = np.asarray(rov_pos_ned, dtype=float)
        if p.shape != (3,) or not np.all(np.isfinite(p)):
            return None
        return float(np.linalg.norm(p - np.asarray(self.reach_target_ned(), dtype=float)))

    def _reject(self, reason: str, rov_pos_ned: list[float] | np.ndarray | None) -> dict[str, Any]:
        self.last_rejection = reason
        return self.to_dict(rov_pos_ned)

    def _gate(self, stage_ok: bool, rov_pos_ned: list[float] | np.ndarray | None, require_pos: bool = False) -> str:
        """Return a rejection reason, or "" when the action is allowed (M_09 fixed model)."""
        if self.campaign_completed:
            return "CAMPAIGN_ALREADY_COMPLETED"
        if not stage_ok:
            return f"WRONG_STAGE_{self.stage_num}"
        d = self._distance_to_target(rov_pos_ned)
        if d is None:
            return "ROV_POSITION_REQUIRED" if require_pos else ""
        if d > INTERACT_RADIUS_M[self.stage_num]:
            return f"OUT_OF_RANGE_{d:.2f}m>{INTERACT_RADIUS_M[self.stage_num]}m"
        return ""

    def advance_sonar_ring(self, rov_pos_ned: list[float] | np.ndarray | None = None) -> dict[str, Any]:
        """Clear a Stage 1 sonar guidance waypoint ring and auto-transition to Stage 2 when all 3 are cleared."""
        why = self._gate(self.stage_num == 1, rov_pos_ned)
        if why:
            return self._reject(why, rov_pos_ned)
        self.last_rejection = ""
        self.waypoint_rings_cleared = min(self.waypoint_rings_total, self.waypoint_rings_cleared + 1)
        if self.waypoint_rings_cleared >= self.waypoint_rings_total:
            self.stage_num = 2
            self._push_stage_comms(2)
        else:
            self._push_stage_comms(
                1,
                "聲納導航官 (Sonar Nav)",
                f"「已通過聲納導引光圈 {self.waypoint_rings_cleared}/{self.waypoint_rings_total}！繼續下潛逼近斷纜主座標！」",
            )
        return self.to_dict(rov_pos_ned)

    def grab_or_tow_cable(self, rov_pos_ned: list[float] | np.ndarray | None = None, place_in_saddle: bool = False) -> dict[str, Any]:
        """Stage 2 action: clear debris, grab the dislodged subsea cable with manipulator, or seat it into the splice saddle."""
        why = self._gate(self.stage_num == 2, rov_pos_ned)
        if why:
            return self._reject(why, rov_pos_ned)
        self.last_rejection = ""

        if not self.debris_cleared:
            self.debris_cleared = True

        if not self.cable_grabbed and not place_in_saddle:
            self.cable_grabbed = True
            if rov_pos_ned is not None:
                p = np.asarray(rov_pos_ned, dtype=float)
                if p.shape == (3,) and np.all(np.isfinite(p)):
                    self.cable_tip_ned = [round(float(p[0]), 2), round(float(p[1]), 2), round(float(p[2]), 2)]
            self.cable_tension_n = 128.5
            self.cable_tension_warning = "OK"
            self.cable_over_limit_s = 0.0
            self._push_stage_comms(
                2,
                "ROV 領航官 (Subsea Pilot Lead)",
                "「機械手臂夾爪已咬合海底主幹電纜！注意懸鏈張力 (128.5 N)，請拖曳海纜前往搶修接頭鞍座 (SR-IND-06)！」",
            )
            return self.to_dict(rov_pos_ned)

        # Seat cable into splice saddle -> auto-transition to Stage 3 (only a cable actually held can be seated)
        if not self.cable_grabbed:
            return self._reject("CABLE_NOT_GRABBED", rov_pos_ned)
        self.cable_grabbed = False
        self.cable_seated_in_saddle = True
        self.cable_tip_ned = list(self.splice_saddle_ned)
        self.cable_tension_n = 64.0
        self.cable_tow_force_ned = [0.0, 0.0, 0.0]
        self.cable_tension_warning = "OK"
        self.stage_num = 3
        self._push_stage_comms(3)
        return self.to_dict(rov_pos_ned)

    def perform_repair_step(self, step_delta_pct: float = 34.0, rov_pos_ned: list[float] | np.ndarray | None = None) -> dict[str, Any]:
        """Stage 3 action: advance the 3-step subsea splice box repair & SimReady clamp lock."""
        why = self._gate(self.stage_num == 3 and self.cable_seated_in_saddle, rov_pos_ned)
        if why:
            return self._reject(why, rov_pos_ned)
        self.last_rejection = ""

        self.repair_progress_pct = round(min(100.0, self.repair_progress_pct + max(5.0, float(step_delta_pct))), 1)
        if self.repair_progress_pct >= 99.5:
            self.repair_progress_pct = 100.0
            self.repair_step_index = 3
            self.cable_energized = True
            self.stage_num = 4
            self._push_stage_comms(4)
        elif self.repair_progress_pct >= 66.0:
            self.repair_step_index = 2
            self._push_stage_comms(
                3,
                "水下工程總監 (Subsea Chief Engineer)",
                "「Step 2/3 SimReady 保護管夾扭力鎖固完成 (240 N·m)！準備執行 Step 3/3 400kV 高壓絕緣與光纖導通測試！」",
            )
        else:
            self.repair_step_index = 1
            self._push_stage_comms(
                3,
                "水下工程總監 (Subsea Chief Engineer)",
                "「Step 1/3 高壓空化水刀海生物與除鏽清理完成！請對準接頭盒執行 Step 2/3 保護管夾鎖固！」",
            )
        return self.to_dict(rov_pos_ned)

    def complete_extraction(
        self,
        hull_integrity_pct: float = 100.0,
        elapsed_s: float = 142.0,
        rov_pos_ned: list[float] | np.ndarray | None = None,
    ) -> dict[str, Any]:
        """Stage 4 action: dock into TMS Recovery Cage and compute final S/A/B Campaign Victory Rank.

        Only legal at Stage 4 with the cable energized and ROV-01 inside the TMS cage radius;
        earlier stages can no longer be skipped straight to an S rank (M_09 Inv_RankedRequiresFullRun).
        """
        why = self._gate(
            self.stage_num == 4 and self.cable_energized and self.repair_progress_pct >= 100.0,
            rov_pos_ned,
            require_pos=True,
        )
        if why:
            return self._reject(why, rov_pos_ned)
        self.last_rejection = ""
        self.tms_extracted = True
        self.campaign_completed = True

        hull = max(0.0, min(100.0, float(hull_integrity_pct)))
        score = round(min(100.0, 45.0 + 0.35 * hull + (20.0 if self.cable_energized else 0.0)), 1)
        if hull <= 0.0:
            score = 0.0
            rank = "F (任務失敗 · 機體損毀)"
        elif self.drill_mode:
            rank = DRILL_RANK
        elif score >= 92.0 and hull >= 90.0:
            rank = "S (傳奇深海領航員 · 零失誤完美搶修)"
        elif score >= 82.0 and hull >= 80.0:
            rank = "A (資深海纜工程師 · 符合 B2B 認證標準)"
        else:
            rank = "B (合格完成 · 建議加強抗流穩定度)"

        self.campaign_score = score
        self.campaign_rank = rank
        self._push_stage_comms(
            4,
            "母船指揮官 CH-16 (Mother Vessel Bridge)",
            f"「ROV-01 已安全鎖入水下 TMS 吊籠！海底主幹電纜 400kV/100Gbps 全線暢通，戰役總評：{rank} ({score} 分)！」",
        )
        return self.to_dict(rov_pos_ned)

    def set_stage(self, stage_num: int, rov_pos_ned: list[float] | np.ndarray | None = None) -> dict[str, Any]:
        """Jump directly to Stage 1..4 for training drills or verification."""
        st = max(1, min(4, int(stage_num)))
        self.reset_campaign()
        self.drill_mode = st >= 2  # any jump past Stage 1 is a training drill: never ranked
        if st >= 2:
            self.waypoint_rings_cleared = self.waypoint_rings_total
            self.stage_num = 2
            self.debris_cleared = True
            self.cable_grabbed = True
            self.cable_tip_ned = [7.6, -0.2, 6.1]
            self.cable_tension_n = 134.0
            self._push_stage_comms(2)
        if st >= 3:
            self.cable_grabbed = False
            self.cable_seated_in_saddle = True
            self.cable_tip_ned = list(self.splice_saddle_ned)
            self.cable_tension_n = 68.0
            self.stage_num = 3
            self.repair_step_index = 2
            self.repair_progress_pct = 68.0
            self._push_stage_comms(3)
        if st >= 4:
            self.repair_step_index = 3
            self.repair_progress_pct = 100.0
            self.cable_energized = True
            self.stage_num = 4
            self._push_stage_comms(4)
        return self.to_dict(rov_pos_ned)

    def step(
        self,
        dt: float,
        rov_pos_ned: list[float] | np.ndarray,
        hull_integrity_pct: float = 100.0,
        rov_vel_ned: list[float] | np.ndarray | None = None,
        current_ned: list[float] | np.ndarray | None = None,
    ) -> None:
        """Continuous per-tick campaign physics & proximity progression.

        While the cable is held, the towed-cable load (``compute_cable_tow_load``) is recomputed every tick and
        published as ``cable_tow_force_ned`` for the vehicle dynamics. Tension above ``CABLE_TENSION_WARN_N``
        raises HIGH, above ``CABLE_TENSION_SLIP_N`` CRITICAL; holding CRITICAL for ``CABLE_SLIP_HOLD_S`` makes the
        gripper slip (cable dropped, must be re-grabbed)."""
        p = np.asarray(rov_pos_ned, dtype=float)
        if p.shape != (3,) or not np.all(np.isfinite(p)):
            return
        dt = float(dt) if math.isfinite(float(dt)) and float(dt) > 0.0 else 0.0

        if self.cable_energized:
            self.energized_pulse_phase = round((self.energized_pulse_phase + dt * 1.8) % 10.0, 3)

        # If cable is grabbed by ROV-01's manipulator gripper, update cable tip and the real tow load
        if self.cable_grabbed:
            gripper_ned = [
                round(float(p[0] + 0.55), 3),
                round(float(p[1]), 3),
                round(float(p[2] + 0.15), 3),
            ]
            self.cable_tip_ned = gripper_ned
            load = compute_cable_tow_load(
                gripper_ned, self.cable_anchor_ned, self.cable_free_length_m, rov_vel_ned, current_ned
            )
            self.cable_load = load
            self.cable_tow_force_ned = list(load["force_ned"])
            self.cable_tension_n = float(load["tension_n"])
            if self.cable_tension_n >= CABLE_TENSION_SLIP_N:
                self.cable_tension_warning = "CRITICAL"
                self.cable_over_limit_s += dt
            else:
                self.cable_over_limit_s = max(0.0, self.cable_over_limit_s - 2.0 * dt)
                self.cable_tension_warning = "HIGH" if self.cable_tension_n >= CABLE_TENSION_WARN_N else "OK"
            if self.cable_over_limit_s >= CABLE_SLIP_HOLD_S:
                self._slip_cable()
            else:
                # Auto-seat if towed within 1.35m of the (reachable) Splice Saddle
                saddle = self.reach_point_ned(self.splice_saddle_ned)
                dist_to_saddle = float(np.linalg.norm(np.asarray(gripper_ned) - np.asarray(saddle)))
                if dist_to_saddle <= 1.35:
                    self.grab_or_tow_cable(rov_pos_ned=p, place_in_saddle=True)
        elif self.cable_tow_force_ned != [0.0, 0.0, 0.0]:
            self.cable_tow_force_ned = [0.0, 0.0, 0.0]

        # Stage 1 proximity check for glowing sonar waypoint rings
        if self.stage_num == 1:
            tgt = np.asarray(self.reach_target_ned(), dtype=float)
            if float(np.linalg.norm(p - tgt)) <= 1.65:
                self.advance_sonar_ring(p)

    def _slip_cable(self) -> None:
        """Jaws let go: the tow load exceeded the gripper holding limit for too long."""
        self.cable_grabbed = False
        self.cable_slip_count += 1
        self.cable_tow_force_ned = [0.0, 0.0, 0.0]
        self.cable_tension_warning = "SLIPPED"
        self.cable_over_limit_s = 0.0
        self.cable_tension_n = 42.0
        self.last_rejection = f"CABLE_SLIPPED_TENSION>{CABLE_TENSION_SLIP_N:.0f}N"
        self._push_stage_comms(
            2,
            "ROV 領航官 (Subsea Pilot Lead)",
            f"「警告！懸鏈張力超過夾爪握持極限 ({CABLE_TENSION_SLIP_N:.0f} N)，海纜已脫夾！請回到斷纜端頭重新夾取，拖曳時保持海纜鬆弛。」",
        )

    def to_dict(self, rov_pos_ned: list[float] | np.ndarray | None = None) -> dict[str, Any]:
        meta = self.current_stage_meta()
        tgt = self.current_target_ned()
        dist_m = 0.0
        can_interact = False
        interaction_prompt = ""

        if rov_pos_ned is not None:
            p = np.asarray(rov_pos_ned, dtype=float)
            if p.shape == (3,) and np.all(np.isfinite(p)):
                dist_m = round(float(np.linalg.norm(p - np.asarray(self.reach_point_ned(tgt), dtype=float))), 2)
        else:
            dist_m = 2.1

        if self.stage_num == 1:
            can_interact = dist_m <= INTERACT_RADIUS_M[1]
            interaction_prompt = "[E] 聲納鎖定通過導引光圈 (SONAR WAYPOINT LOCK)"
        elif self.stage_num == 2:
            can_interact = dist_m <= INTERACT_RADIUS_M[2]
            interaction_prompt = (
                "[E] / [Space] 接頭鞍座落位鎖定 (SEAT CABLE IN SADDLE)"
                if self.cable_grabbed
                else "[E] / [Space] 機械手臂夾取斷落海纜 (GRAB SUBSEA CABLE)"
            )
        elif self.stage_num == 3:
            can_interact = dist_m <= INTERACT_RADIUS_M[3]
            sub = REPAIR_SUBSTEPS[min(2, self.repair_step_index)]
            interaction_prompt = f"[E] 執行 {sub['title_zh']}"
        elif self.stage_num == 4:
            can_interact = (dist_m <= INTERACT_RADIUS_M[4]) and not self.campaign_completed
            interaction_prompt = (
                "🏆 戰役已完成 (OPERATION DEEP LINK COMPLETE)"
                if self.campaign_completed
                else "[E] 進入母船水下 TMS 吊籠完成回收結算 (DOCK IN TMS CAGE)"
            )

        catenary_pts = compute_catenary_curve_ned(
            self.cable_anchor_ned,
            self.cable_tip_ned,
            num_points=16,
            sag_m=0.65 if self.cable_grabbed else 0.95,
        )

        overall_pct = round(
            min(
                100.0,
                (self.stage_num - 1) * 25.0
                + (
                    (self.waypoint_rings_cleared / max(1, self.waypoint_rings_total)) * 25.0
                    if self.stage_num == 1
                    else (15.0 if self.cable_grabbed else 5.0)
                    if self.stage_num == 2
                    else (self.repair_progress_pct * 0.25)
                    if self.stage_num == 3
                    else (25.0 if self.campaign_completed else 15.0)
                ),
            ),
            1,
        )

        latest_comms = self.comms_history[-1] if self.comms_history else {
            "stage_num": self.stage_num,
            "speaker": meta["comms_speaker"],
            "text": meta["comms_text"],
        }

        return {
            "campaign_id": self.campaign_id,
            "campaign_title_zh": self.campaign_title_zh,
            "active": self.active,
            "stage_num": self.stage_num,
            "drill_mode": self.drill_mode,
            "last_rejection": self.last_rejection,
            "stage_code": meta["stage_code"],
            "stage_title_zh": meta["title_zh"],
            "objective_zh": meta["objective_zh"],
            "objective_en": meta["objective_en"],
            "simready_focus": meta["simready_focus"],
            "target_ned": tgt,
            "target_distance_m": dist_m,
            "can_interact": can_interact,
            "interaction_prompt": interaction_prompt,
            "overall_progress_pct": overall_pct,
            "waypoint_rings_cleared": self.waypoint_rings_cleared,
            "waypoint_rings_total": self.waypoint_rings_total,
            "debris_cleared": self.debris_cleared,
            "cable_grabbed": self.cable_grabbed,
            "cable_seated_in_saddle": self.cable_seated_in_saddle,
            "cable_anchor_ned": list(self.cable_anchor_ned),
            "cable_tip_ned": list(self.cable_tip_ned),
            "splice_saddle_ned": list(self.splice_saddle_ned),
            "tms_cage_ned": list(self.tms_cage_ned),
            "catenary_points_ned": catenary_pts,
            "cable_tension_n": self.cable_tension_n,
            "cable_tension_warning": self.cable_tension_warning,
            "cable_tension_warn_n": CABLE_TENSION_WARN_N,
            "cable_tension_limit_n": CABLE_TENSION_SLIP_N,
            "cable_free_length_m": self.cable_free_length_m,
            "cable_slack_m": round(self.cable_free_length_m - float(np.linalg.norm(np.asarray(self.cable_tip_ned) - np.asarray(self.cable_anchor_ned))), 2),
            "cable_tow_force_ned": [round(float(x), 2) for x in self.cable_tow_force_ned],
            "cable_slip_count": self.cable_slip_count,
            "cable_load": dict(self.cable_load),
            "reach_ned": self.reach_target_ned(),
            "repair_step_index": self.repair_step_index,
            "repair_progress_pct": self.repair_progress_pct,
            "repair_substeps": REPAIR_SUBSTEPS,
            "cable_energized": self.cable_energized,
            "power_restore_pct": 100.0 if self.cable_energized else round(self.repair_progress_pct * 0.5, 1),
            "energized_pulse_phase": self.energized_pulse_phase,
            "tms_extracted": self.tms_extracted,
            "campaign_completed": self.campaign_completed,
            "campaign_rank": self.campaign_rank,
            "campaign_score": self.campaign_score,
            "latest_comms": latest_comms,
            "comms_history": list(self.comms_history),
            "stages_catalog": CAMPAIGN_STAGES,
        }
