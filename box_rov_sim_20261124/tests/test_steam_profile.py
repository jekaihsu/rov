"""Unit tests for B2C Steam Offline Speedrun Leaderboard, Profile Settings Persistence & Non-Orange Livery (`rov01sim.steam_profile`)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rov01sim.steam_profile import (
    DEFAULT_CONTINUOUS_EXPO,
    DEFAULT_HUD_THEME,
    DEFAULT_HULL_LIVERY,
    DEFAULT_RADIAL_DEADZONE,
    DEFAULT_SAVE_FILENAME,
    HULL_LIVERY_PALETTES,
    STEAM_ACHIEVEMENTS,
    VALID_HUD_THEMES,
    VALID_HULL_LIVERIES,
    SteamProfileManager,
    evaluate_medal,
)


class TestSteamProfileAndLeaderboard(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.save_file = Path(self._tmp.name) / DEFAULT_SAVE_FILENAME

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_profile_values_and_non_orange_livery(self) -> None:
        mgr = SteamProfileManager(save_path=self.save_file)
        settings = mgr.data["settings"]

        self.assertAlmostEqual(settings["radial_deadzone"], DEFAULT_RADIAL_DEADZONE)
        self.assertAlmostEqual(settings["continuous_expo"], DEFAULT_CONTINUOUS_EXPO)
        self.assertEqual(settings["hud_theme"], DEFAULT_HUD_THEME)
        self.assertEqual(settings["hull_livery"], DEFAULT_HULL_LIVERY)
        self.assertEqual(settings["hull_livery"], "cyber_cyan")
        self.assertEqual(settings["hull_palette"]["buoyancy_foam"], "#06B6D4")
        self.assertEqual(settings["hull_palette"]["buoyancy_highlight"], "#22D3EE")
        self.assertEqual(settings["hull_palette"]["anodized_trim"], "#38BDF8")
        self.assertEqual(settings["hull_palette"]["open_frame"], "#1E293B")
        self.assertEqual(settings["hull_palette"]["reflective_strips"], "#F8FAFC")

        for livery_name, palette in HULL_LIVERY_PALETTES.items():
            self.assertIn(livery_name, VALID_HULL_LIVERIES)
            for hex_val in palette.values():
                self.assertNotIn(hex_val.upper(), ("#FF6B00", "#EA580C", "#F97316", "#F59E0B"))

    def test_settings_persistence_and_orange_livery_rejection(self) -> None:
        mgr = SteamProfileManager(save_path=self.save_file)

        mgr.update_settings(
            radial_deadzone=0.08,
            continuous_expo=0.35,
            hud_theme="STEAM_DIEGETIC",
            hull_livery="stealth_titanium",
            controller_bindings={"UT_Sample": "gamepad_rb", "HUD_Cycle": "button_select"},
        )
        self.assertTrue(self.save_file.exists())

        reloaded = SteamProfileManager(save_path=self.save_file)
        s = reloaded.data["settings"]
        self.assertAlmostEqual(s["radial_deadzone"], 0.08)
        self.assertAlmostEqual(s["continuous_expo"], 0.35)
        self.assertEqual(s["hud_theme"], "STEAM_DIEGETIC")
        self.assertEqual(s["hull_livery"], "stealth_titanium")
        self.assertEqual(s["hull_palette"]["buoyancy_foam"], "#1E293B")
        self.assertEqual(s["controller_bindings"]["UT_Sample"], "gamepad_rb")
        self.assertEqual(s["controller_bindings"]["HUD_Cycle"], "button_select")

        with self.assertRaisesRegex(ValueError, "prohibited hull livery"):
            reloaded.update_settings(hull_livery="orange")
        with self.assertRaisesRegex(ValueError, "prohibited hull livery"):
            reloaded.update_settings(hull_livery="#FF6B00")
        with self.assertRaisesRegex(ValueError, "Unsupported HUD theme"):
            reloaded.update_settings(hud_theme="ARCADE_ORANGE")
        with self.assertRaisesRegex(ValueError, "radial_deadzone"):
            reloaded.update_settings(radial_deadzone=0.55)

    def test_speedrun_pb_medals_and_achievements_m1_to_m4(self) -> None:
        mgr = SteamProfileManager(save_path=self.save_file)

        r1 = mgr.record_mission_run("M1", completion_time_sec=120.5, score=84.0)
        self.assertEqual(r1.medal, "SILVER")
        self.assertTrue(r1.is_new_pb)
        self.assertIn("M1_POOL_CLEAR", r1.newly_unlocked_achievements)

        r2 = mgr.record_mission_run("mission_1_pool", completion_time_sec=82.35, score=94.5)
        self.assertEqual(r2.medal, "GOLD")
        self.assertTrue(r2.is_new_pb)
        self.assertEqual(r2.newly_unlocked_achievements, [])

        r_m2 = mgr.record_mission_run("M2", completion_time_sec=128.0, score=92.0, ut_certified=True)
        self.assertEqual(r_m2.medal, "GOLD")
        self.assertIn("M2_UT_CERTIFIED", r_m2.newly_unlocked_achievements)

        r_m3 = mgr.record_mission_run("M3", completion_time_sec=165.0, score=81.0, t3_fault_recovered=True)
        self.assertEqual(r_m3.medal, "SILVER")
        self.assertIn("M3_T3_FAULT_SURVIVOR", r_m3.newly_unlocked_achievements)

        r_m4_snag = mgr.record_mission_run("M4", completion_time_sec=140.0, score=88.0, tether_entangled=True)
        self.assertEqual(r_m4_snag.medal, "GOLD")
        self.assertNotIn("M4_PIPE_GOLD", r_m4_snag.newly_unlocked_achievements)

        r_m4_clean = mgr.record_mission_run("mission_4_pipeline", completion_time_sec=131.2, score=91.0, tether_entangled=False)
        self.assertEqual(r_m4_clean.medal, "GOLD")
        self.assertTrue(r_m4_clean.is_new_pb)
        self.assertIn("M4_PIPE_GOLD", r_m4_clean.newly_unlocked_achievements)

        reloaded = SteamProfileManager(save_path=self.save_file)
        summary = reloaded.get_leaderboard_summary()
        self.assertAlmostEqual(summary["M1"]["pb_time_sec"], 82.35)
        self.assertEqual(summary["M1"]["best_medal"], "GOLD")
        self.assertEqual(summary["M1"]["top_runs"][0]["medal"], "GOLD")
        self.assertEqual(summary["M2"]["best_medal"], "GOLD")
        self.assertEqual(summary["M3"]["best_medal"], "SILVER")
        self.assertAlmostEqual(summary["M4"]["pb_time_sec"], 131.2)
        self.assertEqual(summary["M4"]["best_medal"], "GOLD")

        unsynced = reloaded.get_unsynced_achievements()
        self.assertEqual(set(unsynced), set(STEAM_ACHIEVEMENTS.keys()))

        reloaded.mark_achievements_synced(["M1_POOL_CLEAR", "M2_UT_CERTIFIED"])
        reloaded_again = SteamProfileManager(save_path=self.save_file)
        self.assertEqual(set(reloaded_again.get_unsynced_achievements()), {"M3_T3_FAULT_SURVIVOR", "M4_PIPE_GOLD"})

    def test_zero_hull_integrity_denies_medals_and_clears(self) -> None:
        mgr = SteamProfileManager(save_path=self.save_file)
        res = mgr.record_mission_run("M1", completion_time_sec=70.0, score=0.0, cleared=False, hull_integrity=0.0)
        self.assertEqual(res.medal, "NONE")
        self.assertFalse(res.is_new_pb)
        self.assertEqual(mgr.data["missions"]["M1"]["clears"], 0)
        self.assertEqual(evaluate_medal("M1", 70.0, 95.0, hull_integrity=0.0), "NONE")

    def test_rov01_mesh_and_livery_files_contain_zero_orange(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        mesh_js = (repo_root / "viewer" / "rov01_mesh.js").read_text(encoding="utf-8")
        livery_js = (repo_root / "viewer" / "vehicle_livery.js").read_text(encoding="utf-8")

        for forbidden_hex in ("#FF6B00", "0xFF6B00", "#EA580C", "0xEA580C"):
            self.assertNotIn(forbidden_hex.lower(), mesh_js.lower())
            self.assertNotIn(forbidden_hex.lower(), livery_js.lower())

        for required_token in (
            "cyber_cyan",
            "arctic_white",
            "stealth_titanium",
            "0x06B6D4",
            "0x22D3EE",
            "0x38BDF8",
            "0x1E293B",
            "0xF8FAFC",
        ):
            self.assertIn(required_token, mesh_js)


if __name__ == "__main__":
    unittest.main()
