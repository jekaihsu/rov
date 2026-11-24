"""Unit & integration tests for Steamworks SDK scaffold, Steam Input VDF,
steam_bridge.js (Achievements + Rich Presence + standalone B2B fallback),
win64 Steam depot staging, /arena HUD themes, and Valve-compliant Steam graphical assets."""
import json
import hashlib
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

BOX = Path(__file__).resolve().parents[1]
ROOT = BOX.parent
DESKTOP = BOX / "desktop" if (BOX / "desktop").exists() else ROOT / "desktop"


def read_png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a valid PNG: {path}")
    w, h = struct.unpack(">II", data[16:24])
    return w, h


class TestSteamPackagingAndBridge(unittest.TestCase):
    def test_steam_app_id_files(self):
        for fname in ("steam_app_id.txt", "steam_appid.txt"):
            p = DESKTOP / fname
            self.assertTrue(p.exists(), f"Missing {p}")
            self.assertEqual(p.read_text(encoding="utf-8").strip(), "480")

    def test_steamworks_vdf_configs(self):
        cfg = DESKTOP / "steamworks_config"
        app_vdf = (cfg / "app_build_template.vdf").read_text(encoding="utf-8")
        depot_vdf = (cfg / "depot_build_win64.vdf").read_text(encoding="utf-8")
        input_vdf = (cfg / "steam_input_manifest.vdf").read_text(encoding="utf-8")

        self.assertIn('"AppBuild"', app_vdf)
        self.assertIn('"AppID" "480"', app_vdf)
        self.assertIn('"depot_build_win64.vdf"', app_vdf)

        self.assertIn('"DepotBuild"', depot_vdf)
        self.assertIn('"FileExclusion" "steam_appid.txt"', depot_vdf)

        for action in (
            "LeftStick_SurgeSway",
            "RightStick_HeaveYaw",
            "Surge",
            "Sway",
            "Heave",
            "Yaw",
            "Depth_Hold",
            "Heading_Hold",
            "Emergency_Surface",
            "UT_Sample",
        ):
            self.assertIn(action, input_vdf, f"Missing Steam Input action {action}")
        self.assertIn('"english"', input_vdf)
        self.assertIn('"tchinese"', input_vdf)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_steam_bridge_achievements_and_fallback(self):
        bridge_uri = (DESKTOP / "steam_bridge.js").resolve().as_posix()
        script = f"""
        const {{ createSteamBridge, ACHIEVEMENTS, readConfiguredAppId }} = require({json.dumps(bridge_uri)});
        const b2b = createSteamBridge({{ baseDir: {json.dumps(str(DESKTOP.resolve()))} }});
        const r1 = b2b.unlockAchievement('M1_POOL_CLEAR');
        const r2 = b2b.unlockAchievement('M2_UT_CERTIFIED');
        const r3 = b2b.unlockAchievement('M3_T3_FAULT_SURVIVOR');
        const r4 = b2b.unlockAchievement('M4_PIPE_GOLD');
        const bad = b2b.unlockAchievement('UNKNOWN_ACH');
        b2b.setRichPresence({{ status: 'UT Hull Inspection', mission: 'mission_2_hull', depth_m: '12.4' }});

        const activated = [];
        const presence = {{}};
        const mocked = createSteamBridge({{
          appId: 480,
          mockClient: {{
            achievement: {{ activate: (id) => {{ activated.push(id); return true; }} }},
            localplayer: {{ setRichPresence: (k, v) => {{ presence[k] = v; }} }}
          }}
        }});
        const mr = mocked.unlockAchievement('M2_UT_CERTIFIED');
        mocked.setRichPresence('mission', 'mission_2_hull');

        console.log(JSON.stringify({{
          appId: readConfiguredAppId({json.dumps(str(DESKTOP.resolve()))}),
          catalogue: Object.keys(ACHIEVEMENTS),
          b2bStatus: b2b.getStatus(),
          r1, r2, r3, r4, bad,
          mockedResult: mr,
          activated,
          presence
        }}));
        """
        proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertEqual(data["appId"], 480)
        self.assertEqual(
            data["catalogue"],
            ["M1_POOL_CLEAR", "M2_UT_CERTIFIED", "M3_T3_FAULT_SURVIVOR", "M4_PIPE_GOLD"],
        )
        self.assertEqual(data["b2bStatus"]["mode"], "standalone-b2b")
        self.assertEqual(
            data["b2bStatus"]["unlockedAchievements"],
            ["M1_POOL_CLEAR", "M2_UT_CERTIFIED", "M3_T3_FAULT_SURVIVOR", "M4_PIPE_GOLD"],
        )
        self.assertEqual(data["b2bStatus"]["richPresence"]["depth_m"], "12.4")
        self.assertFalse(data["bad"]["ok"])
        self.assertTrue(data["mockedResult"]["steamActivated"])
        self.assertEqual(data["activated"], ["M2_UT_CERTIFIED"])
        self.assertEqual(data["presence"]["mission"], "mission_2_hull")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_build_win64_steam_depot_script(self):
        # A rebuild must also remove files that no longer exist in source.
        old_payload = DESKTOP / 'dist/steam_depot_win64/rov01sim/obsolete_release_module.py'
        old_payload.parent.mkdir(parents=True, exist_ok=True)
        old_payload.write_text('# stale build payload\n')
        old_cache = old_payload.parent / '__pycache__/obsolete_release_module.pyc'
        old_cache.parent.mkdir(parents=True, exist_ok=True)
        old_cache.write_bytes(b'stale bytecode')
        proc = subprocess.run(
            ["npm", "run", "build:win64-steam", "--silent"],
            cwd=str(DESKTOP),
            capture_output=True,
            text=True,
            check=True,
        )
        manifest = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(manifest["productName"], "ROV-01 Simulator")
        self.assertEqual(manifest["appId"], 480)
        self.assertTrue(manifest["vendorAdapterRemoved"])
        depot_dir = Path(manifest["depotDir"])
        self.assertTrue((depot_dir / "viewer" / "index.html").exists())
        self.assertTrue((depot_dir / "viewer" / "arena_hud_themes.js").exists())
        self.assertTrue((depot_dir / "rov01sim" / "engine.py").exists())
        self.assertFalse((depot_dir / "rov01sim" / "sdk_vendor_adapter.py").exists())
        self.assertTrue((depot_dir / "steam_build_manifest.json").exists())
        self.assertFalse(old_payload.exists())
        self.assertFalse(old_cache.exists())
        payload = {entry['path']: entry for entry in manifest['payloadFiles']}
        self.assertEqual(set(payload), {
            p.relative_to(depot_dir).as_posix() for p in depot_dir.rglob('*')
            if p.is_file() and p.name != 'steam_build_manifest.json'
        })
        for relative, entry in payload.items():
            data = (depot_dir / relative).read_bytes()
            self.assertEqual(entry['bytes'], len(data))
            self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())
        for directory in ('rov01sim', 'viewer'):
            expected = {
                p.relative_to(BOX).as_posix(): p for p in (BOX / directory).rglob('*')
                if p.is_file() and '__pycache__' not in p.parts
                and p.suffix not in ('.pyc', '.pyo') and p.name != 'sdk_vendor_adapter.py'
            }
            self.assertEqual(set(expected), {
                name for name in payload if name.startswith(directory + '/')
            })
            for relative, source in expected.items():
                self.assertEqual((depot_dir / relative).read_bytes(), source.read_bytes(), relative)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_depot_stages_steam_appid_file_for_runtime(self):
        # Regression: a shipped/standalone build must be able to recover its own
        # Steam AppID from disk. steamworks.js + readConfiguredAppId read a
        # `steam_appid.txt` beside the executable; if the depot stages no appid
        # file, the build silently falls back to Spacewar (480) once a real
        # AppID is assigned.
        proc = subprocess.run(
            ["npm", "run", "build:win64-steam", "--silent"],
            cwd=str(DESKTOP), capture_output=True, text=True, check=True,
        )
        manifest = json.loads(proc.stdout.strip().splitlines()[-1])
        depot_dir = Path(manifest["depotDir"])
        expected_id = str(manifest["appId"])
        staged = False
        for fname in ("steam_appid.txt", "steam_app_id.txt"):
            p = depot_dir / fname
            self.assertTrue(p.exists(), f"Depot missing runtime appid file {fname}")
            self.assertEqual(p.read_text(encoding="utf-8").strip(), expected_id)
            staged = True
        self.assertTrue(staged)
        # The staged appid must match what the bridge resolves at runtime from
        # the depot content root.
        bridge_uri = (DESKTOP / "steam_bridge.js").resolve().as_posix()
        check = subprocess.run(
            ["node", "-e",
             f"const {{readConfiguredAppId}}=require({json.dumps(bridge_uri)});"
             f"process.stdout.write(String(readConfiguredAppId({json.dumps(str(depot_dir))})))"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(check.stdout.strip(), expected_id)

    def test_arena_hud_themes_and_steam_graphical_assets(self):
        arena_js = (BOX / "viewer" / "arena_hud_themes.js").read_text(encoding="utf-8")
        wave1_js = (BOX / "viewer" / "wave1_hud.js").read_text(encoding="utf-8")
        for preset in ("TACTICAL_SONAR", "INDUSTRIAL_P260", "STEAM_DIEGETIC", "STEAM_DIEGETIC_COCKPIT"):
            self.assertIn(preset, arena_js, f"Missing preset {preset} in arena_hud_themes.js")
        self.assertIn("installArenaHudThemes", wave1_js)
        self.assertIn("w1ArenaPresetPill", arena_js)

        report_path = ROOT / "ARENA_HUD_BAKEOFF_REPORT.md"
        self.assertTrue(report_path.exists(), "Missing ARENA_HUD_BAKEOFF_REPORT.md")

        assets_dir = ROOT / "steam_assets"
        expected_assets = {
            "steam_ss_01_m1_pool_6dof.png": (1920, 1080),
            "steam_ss_02_m2_hull_ut_gauging.png": (1920, 1080),
            "steam_ss_03_m3_deep_sar_t3_fault.png": (1920, 1080),
            "steam_ss_04_m4_pipeline_time_trial.png": (1920, 1080),
            "steam_ss_05_p260_dual_viewport.png": (1920, 1080),
            "main_capsule_1232x706.png": (1232, 706),
            "header_capsule_920x430.png": (920, 430),
            "small_capsule_462x174.png": (462, 174),
            "vertical_capsule_748x896.png": (748, 896),
            "library_capsule_600x900.png": (600, 900),
            "library_header_920x430.png": (920, 430),
            "library_hero_3840x1240.png": (3840, 1240),
            "library_logo_1280x720.png": (1280, 720),
        }
        for fname, expected_wh in expected_assets.items():
            p = assets_dir / fname
            self.assertTrue(p.exists(), f"Missing Steam asset {p}")
            self.assertEqual(read_png_dimensions(p), expected_wh, f"Dimension mismatch on {fname}")


if __name__ == "__main__":
    unittest.main()
