"""B2C Steam Offline Speedrun Leaderboard & Profile Settings Persistence (`rov01sim.steam_profile`).

Provides deterministic local JSON persistence (`user_profile_save.json`) for:
1. Personal Best (PB) speedrun times, SOP scores, and medal ratings (`GOLD` / `SILVER` / `BRONZE`) across `M1..M4`.
2. Controller bindings, radial deadzone (`0.08`), continuous expo (`0.35`), HUD theme preference
   (`INDUSTRIAL_P260` / `TACTICAL_SONAR` / `STEAM_DIEGETIC`), and non-orange hull livery
   (`cyber_cyan` / `arctic_white` / `stealth_titanium`).
3. Steam Achievement sync table (`M1_POOL_CLEAR`, `M2_UT_CERTIFIED`, `M3_T3_FAULT_SURVIVOR`, `M4_PIPE_GOLD`).
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SAVE_FILENAME = "user_profile_save.json"

VALID_MISSIONS: tuple[str, ...] = ("M1", "M2", "M3", "M4")

MISSION_ALIASES: dict[str, str] = {
    "M1": "M1",
    "m1": "M1",
    "mission_1_pool": "M1",
    "M2": "M2",
    "m2": "M2",
    "mission_2_hull_ut": "M2",
    "M3": "M3",
    "m3": "M3",
    "mission_3_sar_fault": "M3",
    "M4": "M4",
    "m4": "M4",
    "mission_4_pipeline": "M4",
}

CANONICAL_MISSION_NAMES: dict[str, str] = {
    "M1": "mission_1_pool",
    "M2": "mission_2_hull_ut",
    "M3": "mission_3_sar_fault",
    "M4": "mission_4_pipeline",
}

MEDAL_TIERS: tuple[str, ...] = ("GOLD", "SILVER", "BRONZE", "NONE")
MEDAL_RANK: dict[str, int] = {"GOLD": 3, "SILVER": 2, "BRONZE": 1, "NONE": 0}

# Mission speedrun time par thresholds (seconds) & minimum score thresholds for GOLD / SILVER / BRONZE
MISSION_MEDAL_RULES: dict[str, dict[str, dict[str, float]]] = {
    "M1": {
        "GOLD": {"max_time_sec": 95.0, "min_score": 90.0},
        "SILVER": {"max_time_sec": 140.0, "min_score": 80.0},
        "BRONZE": {"max_time_sec": 210.0, "min_score": 65.0},
    },
    "M2": {
        "GOLD": {"max_time_sec": 135.0, "min_score": 90.0},
        "SILVER": {"max_time_sec": 190.0, "min_score": 80.0},
        "BRONZE": {"max_time_sec": 260.0, "min_score": 65.0},
    },
    "M3": {
        "GOLD": {"max_time_sec": 125.0, "min_score": 88.0},
        "SILVER": {"max_time_sec": 180.0, "min_score": 78.0},
        "BRONZE": {"max_time_sec": 250.0, "min_score": 60.0},
    },
    "M4": {
        "GOLD": {"max_time_sec": 150.0, "min_score": 85.0},
        "SILVER": {"max_time_sec": 210.0, "min_score": 75.0},
        "BRONZE": {"max_time_sec": 300.0, "min_score": 60.0},
    },
}

VALID_HUD_THEMES: tuple[str, ...] = (
    "INDUSTRIAL_P260",
    "TACTICAL_SONAR",
    "STEAM_DIEGETIC",
)

# Strictly non-orange hull liveries (Deep-Sea Cyber Cyan, Arctic White, Stealth Titanium)
VALID_HULL_LIVERIES: tuple[str, ...] = (
    "cyber_cyan",
    "arctic_white",
    "stealth_titanium",
)

HULL_LIVERY_PALETTES: dict[str, dict[str, str]] = {
    "cyber_cyan": {
        "buoyancy_foam": "#06B6D4",
        "buoyancy_highlight": "#22D3EE",
        "anodized_trim": "#38BDF8",
        "open_frame": "#1E293B",
        "pressure_hull": "#0F172A",
        "reflective_strips": "#F8FAFC",
    },
    "arctic_white": {
        "buoyancy_foam": "#F8FAFC",
        "buoyancy_highlight": "#38BDF8",
        "anodized_trim": "#06B6D4",
        "open_frame": "#1E293B",
        "pressure_hull": "#0F172A",
        "reflective_strips": "#22D3EE",
    },
    "stealth_titanium": {
        "buoyancy_foam": "#1E293B",
        "buoyancy_highlight": "#06B6D4",
        "anodized_trim": "#22D3EE",
        "open_frame": "#0F172A",
        "pressure_hull": "#020617",
        "reflective_strips": "#F8FAFC",
    },
}

STEAM_ACHIEVEMENTS: dict[str, dict[str, str]] = {
    "M1_POOL_CLEAR": {
        "id": "M1_POOL_CLEAR",
        "mission": "M1",
        "title": "Pool Qualification Complete",
        "desc": "Complete Mission 1 6DoF Pool Qualification with all waypoints cleared.",
    },
    "M2_UT_CERTIFIED": {
        "id": "M2_UT_CERTIFIED",
        "mission": "M2",
        "title": "UT NDT Level-II Certified",
        "desc": "Acquire valid <3 deg perpendicular Ultrasonic Thickness readings for 3.0s.",
    },
    "M3_T3_FAULT_SURVIVOR": {
        "id": "M3_T3_FAULT_SURVIVOR",
        "mission": "M3",
        "title": "5-Thruster Degraded Recovery",
        "desc": "Return ROV-01 safely to the recovery cage under T3 thruster loss and cross-current.",
    },
    "M4_PIPE_GOLD": {
        "id": "M4_PIPE_GOLD",
        "mission": "M4",
        "title": "Subsea Pipeline Gold Inspector",
        "desc": "Complete Mission 4 Pipeline Trial with a GOLD medal (score >= 85) and zero tether entanglement.",
    },
}

DEFAULT_CONTROLLER_BINDINGS: dict[str, str] = {
    "LeftStick_SurgeSway": "gamepad_left_stick_xy",
    "RightStick_HeaveYaw": "gamepad_right_stick_xy",
    "Depth_Hold": "button_a_or_key_z",
    "Heading_Hold": "button_x_or_key_x",
    "Emergency_Surface": "button_y_or_key_e",
    "UT_Sample": "right_trigger_or_space",
    "Camera_Tilt": "dpad_up_down",
    "HUD_Cycle": "button_back_or_f2",
}

DEFAULT_RADIAL_DEADZONE = 0.08
DEFAULT_CONTINUOUS_EXPO = 0.35
DEFAULT_HUD_THEME = "INDUSTRIAL_P260"
DEFAULT_HULL_LIVERY = "cyber_cyan"
MAX_LEADERBOARD_ENTRIES_PER_MISSION = 10


def normalize_mission_key(mission_id: str) -> str:
    key = str(mission_id or "").strip()
    if key not in MISSION_ALIASES:
        raise ValueError(f"Unsupported mission identifier: {mission_id!r}. Expected one of {VALID_MISSIONS}.")
    return MISSION_ALIASES[key]


def evaluate_medal(
    mission_id: str,
    completion_time_sec: float,
    score: float,
    hull_integrity: float = 100.0,
) -> str:
    """Evaluate speedrun medal (`GOLD` / `SILVER` / `BRONZE` / `NONE`) for a completed mission."""
    mkey = normalize_mission_key(mission_id)
    if completion_time_sec <= 0.0 or hull_integrity <= 0.0 or score < 60.0:
        return "NONE"
    rules = MISSION_MEDAL_RULES[mkey]
    if (
        hull_integrity >= 80.0
        and score >= rules["GOLD"]["min_score"]
        and completion_time_sec <= rules["GOLD"]["max_time_sec"]
    ):
        return "GOLD"
    if (
        hull_integrity >= 80.0
        and score >= rules["SILVER"]["min_score"]
        and completion_time_sec <= rules["SILVER"]["max_time_sec"]
    ):
        return "SILVER"
    if score >= rules["BRONZE"]["min_score"] and completion_time_sec <= rules["BRONZE"]["max_time_sec"]:
        return "BRONZE"
    return "NONE"


def create_default_profile() -> dict[str, Any]:
    """Return a clean default `user_profile_save.json` dictionary."""
    missions: dict[str, Any] = {}
    for mkey in VALID_MISSIONS:
        missions[mkey] = {
            "mission_id": mkey,
            "canonical_id": CANONICAL_MISSION_NAMES[mkey],
            "pb_time_sec": None,
            "best_score": 0.0,
            "best_medal": "NONE",
            "attempts": 0,
            "clears": 0,
            "leaderboard": [],
        }

    achievements: dict[str, Any] = {}
    for ach_id, meta in STEAM_ACHIEVEMENTS.items():
        achievements[ach_id] = {
            "id": ach_id,
            "mission": meta["mission"],
            "title": meta["title"],
            "desc": meta["desc"],
            "unlocked": False,
            "unlocked_at": None,
            "synced_to_steamworks": False,
        }

    return {
        "schema_version": 1,
        "product_id": "CORR-ROV-01",
        "updated_at": int(time.time()),
        "settings": {
            "radial_deadzone": DEFAULT_RADIAL_DEADZONE,
            "continuous_expo": DEFAULT_CONTINUOUS_EXPO,
            "hud_theme": DEFAULT_HUD_THEME,
            "hull_livery": DEFAULT_HULL_LIVERY,
            "hull_palette": copy.deepcopy(HULL_LIVERY_PALETTES[DEFAULT_HULL_LIVERY]),
            "controller_bindings": copy.deepcopy(DEFAULT_CONTROLLER_BINDINGS),
        },
        "missions": missions,
        "achievements": achievements,
    }


@dataclass
class MissionRunResult:
    mission_id: str
    completion_time_sec: float
    score: float
    medal: str
    is_new_pb: bool
    newly_unlocked_achievements: list[str]


class SteamProfileManager:
    """Manages local JSON persistence (`user_profile_save.json`) for B2C Steam & standalone runs."""

    def __init__(self, save_path: str | Path | None = None, auto_load: bool = True) -> None:
        if save_path is None:
            base_dir = Path(os.environ.get("ROV01_PROFILE_DIR", Path.cwd()))
            self.save_path = base_dir / DEFAULT_SAVE_FILENAME
        else:
            self.save_path = Path(save_path)
        self.data: dict[str, Any] = create_default_profile()
        if auto_load and self.save_path.exists():
            self.load()

    def load(self) -> dict[str, Any]:
        """Load profile state from `user_profile_save.json`, merging safely with defaults."""
        if not self.save_path.exists():
            self.data = create_default_profile()
            return self.data

        raw = json.loads(self.save_path.read_text(encoding="utf-8"))
        merged = create_default_profile()
        if isinstance(raw, dict):
            raw_settings = raw.get("settings")
            if isinstance(raw_settings, dict):
                self._apply_settings_dict(merged["settings"], raw_settings)

            raw_missions = raw.get("missions")
            if isinstance(raw_missions, dict):
                for mkey in VALID_MISSIONS:
                    mdata = raw_missions.get(mkey)
                    if isinstance(mdata, dict):
                        entry = merged["missions"][mkey]
                        pb = mdata.get("pb_time_sec")
                        entry["pb_time_sec"] = round(float(pb), 3) if isinstance(pb, (int, float)) and pb > 0 else None
                        entry["best_score"] = round(float(mdata.get("best_score", 0.0)), 2)
                        medal = str(mdata.get("best_medal", "NONE")).upper()
                        entry["best_medal"] = medal if medal in MEDAL_TIERS else "NONE"
                        entry["attempts"] = max(0, int(mdata.get("attempts", 0)))
                        entry["clears"] = max(0, int(mdata.get("clears", 0)))
                        if isinstance(mdata.get("leaderboard"), list):
                            entry["leaderboard"] = mdata["leaderboard"][:MAX_LEADERBOARD_ENTRIES_PER_MISSION]

            raw_achievements = raw.get("achievements")
            if isinstance(raw_achievements, dict):
                for ach_id in STEAM_ACHIEVEMENTS:
                    adata = raw_achievements.get(ach_id)
                    if isinstance(adata, dict):
                        target = merged["achievements"][ach_id]
                        target["unlocked"] = bool(adata.get("unlocked", False))
                        target["unlocked_at"] = adata.get("unlocked_at")
                        target["synced_to_steamworks"] = bool(adata.get("synced_to_steamworks", False))

        self.data = merged
        return self.data

    def save(self) -> Path:
        """Atomically persist `self.data` to `user_profile_save.json`."""
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = int(time.time())
        payload = json.dumps(self.data, indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".user_profile_save_",
            suffix=".tmp",
            dir=str(self.save_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.save_path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
        return self.save_path

    def _apply_settings_dict(self, target_settings: dict[str, Any], updates: dict[str, Any]) -> None:
        if "radial_deadzone" in updates:
            dz = float(updates["radial_deadzone"])
            if not (0.0 <= dz <= 0.35):
                raise ValueError(f"radial_deadzone must be between 0.0 and 0.35, got {dz}")
            target_settings["radial_deadzone"] = round(dz, 4)

        if "continuous_expo" in updates:
            expo = float(updates["continuous_expo"])
            if not (0.0 <= expo <= 1.0):
                raise ValueError(f"continuous_expo must be between 0.0 and 1.0, got {expo}")
            target_settings["continuous_expo"] = round(expo, 4)

        if "hud_theme" in updates:
            theme = str(updates["hud_theme"]).strip().upper()
            if theme not in VALID_HUD_THEMES:
                raise ValueError(f"Unsupported HUD theme: {theme!r}. Expected one of {VALID_HUD_THEMES}.")
            target_settings["hud_theme"] = theme

        if "hull_livery" in updates:
            livery = str(updates["hull_livery"]).strip().lower()
            if livery not in VALID_HULL_LIVERIES:
                raise ValueError(
                    f"Unsupported or prohibited hull livery: {livery!r}. "
                    f"Only non-orange liveries {VALID_HULL_LIVERIES} are allowed."
                )
            target_settings["hull_livery"] = livery
            target_settings["hull_palette"] = copy.deepcopy(HULL_LIVERY_PALETTES[livery])

        if "controller_bindings" in updates:
            bindings = updates["controller_bindings"]
            if not isinstance(bindings, dict):
                raise ValueError("controller_bindings must be a dict of action -> binding.")
            for action, key_binding in bindings.items():
                if not isinstance(action, str) or not isinstance(key_binding, str) or not key_binding.strip():
                    raise ValueError(f"Invalid controller binding for {action!r}: {key_binding!r}")
                target_settings["controller_bindings"][action] = key_binding.strip()

    def update_settings(
        self,
        *,
        radial_deadzone: float | None = None,
        continuous_expo: float | None = None,
        hud_theme: str | None = None,
        hull_livery: str | None = None,
        controller_bindings: dict[str, str] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Validate and update pilot profile settings, enforcing non-orange hull livery rules."""
        updates: dict[str, Any] = {}
        if radial_deadzone is not None:
            updates["radial_deadzone"] = radial_deadzone
        if continuous_expo is not None:
            updates["continuous_expo"] = continuous_expo
        if hud_theme is not None:
            updates["hud_theme"] = hud_theme
        if hull_livery is not None:
            updates["hull_livery"] = hull_livery
        if controller_bindings is not None:
            updates["controller_bindings"] = controller_bindings

        self._apply_settings_dict(self.data["settings"], updates)
        if persist:
            self.save()
        return copy.deepcopy(self.data["settings"])

    def record_mission_run(
        self,
        mission_id: str,
        completion_time_sec: float,
        score: float,
        *,
        cleared: bool = True,
        hull_integrity: float = 100.0,
        ut_certified: bool = False,
        t3_fault_recovered: bool = False,
        tether_entangled: bool = False,
        pilot_tag: str = "PILOT-01",
        persist: bool = True,
    ) -> MissionRunResult:
        """Record a mission speedrun attempt, update PB & medals, and evaluate Steam achievements."""
        mkey = normalize_mission_key(mission_id)
        if completion_time_sec <= 0.0:
            raise ValueError(f"completion_time_sec must be > 0, got {completion_time_sec}")

        entry = self.data["missions"][mkey]
        entry["attempts"] += 1

        if not cleared or hull_integrity <= 0.0:
            if persist:
                self.save()
            return MissionRunResult(
                mission_id=mkey,
                completion_time_sec=round(float(completion_time_sec), 3),
                score=round(float(score), 2),
                medal="NONE",
                is_new_pb=False,
                newly_unlocked_achievements=[],
            )

        entry["clears"] += 1
        rounded_time = round(float(completion_time_sec), 3)
        rounded_score = round(float(score), 2)
        medal = evaluate_medal(mkey, rounded_time, rounded_score, hull_integrity=hull_integrity)

        prev_pb = entry["pb_time_sec"]
        is_new_pb = prev_pb is None or rounded_time < float(prev_pb)
        if is_new_pb:
            entry["pb_time_sec"] = rounded_time

        if rounded_score > float(entry["best_score"]):
            entry["best_score"] = rounded_score

        if MEDAL_RANK[medal] > MEDAL_RANK.get(entry["best_medal"], 0):
            entry["best_medal"] = medal

        run_record = {
            "pilot_tag": str(pilot_tag or "PILOT-01").strip()[:24],
            "time_sec": rounded_time,
            "score": rounded_score,
            "medal": medal,
            "hull_integrity": round(float(hull_integrity), 1),
            "timestamp": int(time.time()),
        }
        leaderboard: list[dict[str, Any]] = list(entry.get("leaderboard", []))
        leaderboard.append(run_record)
        leaderboard.sort(
            key=lambda r: (
                -MEDAL_RANK.get(str(r.get("medal", "NONE")), 0),
                -float(r.get("score", 0.0)),
                float(r.get("time_sec", 999999.0)),
            )
        )
        entry["leaderboard"] = leaderboard[:MAX_LEADERBOARD_ENTRIES_PER_MISSION]

        newly_unlocked: list[str] = []
        if mkey == "M1" and rounded_score >= 60.0:
            if self.unlock_achievement("M1_POOL_CLEAR", persist=False):
                newly_unlocked.append("M1_POOL_CLEAR")
        if mkey == "M2" and (ut_certified or rounded_score >= 80.0):
            if self.unlock_achievement("M2_UT_CERTIFIED", persist=False):
                newly_unlocked.append("M2_UT_CERTIFIED")
        if mkey == "M3" and (t3_fault_recovered or rounded_score >= 75.0):
            if self.unlock_achievement("M3_T3_FAULT_SURVIVOR", persist=False):
                newly_unlocked.append("M3_T3_FAULT_SURVIVOR")
        if mkey == "M4" and rounded_score >= 85.0 and not tether_entangled and medal == "GOLD":
            if self.unlock_achievement("M4_PIPE_GOLD", persist=False):
                newly_unlocked.append("M4_PIPE_GOLD")

        if persist:
            self.save()

        return MissionRunResult(
            mission_id=mkey,
            completion_time_sec=rounded_time,
            score=rounded_score,
            medal=medal,
            is_new_pb=is_new_pb,
            newly_unlocked_achievements=newly_unlocked,
        )

    def unlock_achievement(self, achievement_id: str, *, persist: bool = True) -> bool:
        """Unlock one of the 4 Steam achievements; returns True if newly unlocked."""
        ach_key = str(achievement_id or "").strip()
        if ach_key not in STEAM_ACHIEVEMENTS:
            raise ValueError(f"Unknown Steam achievement ID: {ach_key!r}. Expected one of {tuple(STEAM_ACHIEVEMENTS)}.")
        ach_entry = self.data["achievements"][ach_key]
        if ach_entry["unlocked"]:
            return False
        ach_entry["unlocked"] = True
        ach_entry["unlocked_at"] = int(time.time())
        ach_entry["synced_to_steamworks"] = False
        if persist:
            self.save()
        return True

    def mark_achievements_synced(self, achievement_ids: list[str] | tuple[str, ...], *, persist: bool = True) -> None:
        """Mark unlocked achievements as synced with the Steamworks native client."""
        for ach_id in achievement_ids:
            if ach_id in self.data["achievements"] and self.data["achievements"][ach_id]["unlocked"]:
                self.data["achievements"][ach_id]["synced_to_steamworks"] = True
        if persist:
            self.save()

    def get_unsynced_achievements(self) -> list[str]:
        """Return list of unlocked achievement IDs not yet synced to Steamworks."""
        return [
            ach_id
            for ach_id, meta in self.data["achievements"].items()
            if meta.get("unlocked") and not meta.get("synced_to_steamworks")
        ]

    def get_leaderboard_summary(self) -> dict[str, dict[str, Any]]:
        """Return PB times, best scores, and medal ratings across M1..M4."""
        summary: dict[str, dict[str, Any]] = {}
        for mkey in VALID_MISSIONS:
            mdata = self.data["missions"][mkey]
            summary[mkey] = {
                "mission_id": mkey,
                "canonical_id": mdata["canonical_id"],
                "pb_time_sec": mdata["pb_time_sec"],
                "best_score": mdata["best_score"],
                "best_medal": mdata["best_medal"],
                "attempts": mdata["attempts"],
                "clears": mdata["clears"],
                "top_runs": copy.deepcopy(mdata["leaderboard"]),
            }
        return summary
