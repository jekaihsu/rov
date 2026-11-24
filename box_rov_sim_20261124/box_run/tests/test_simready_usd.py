"""Unit & integration tests for NVIDIA Omniverse SimReady OpenUSD (.usda) Subsea Assets & @huggingface/usd-web-viewer."""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import unittest

from rov01sim.engine import Simulator
from rov01sim.server import SimHost, handle_simready_api_request
from rov01sim.simready_usd import (
    compute_usd_collision_impulse,
    get_simready_usda_payload,
    load_simready_assets,
    load_simready_catalog_dict,
    parse_usda_file,
)


BOX = pathlib.Path(__file__).resolve().parents[1]
DESKTOP = BOX / "desktop" if (BOX / "desktop").exists() else BOX.parent / "desktop"


def staged_steam_depot() -> pathlib.Path:
    """The win64 depot is generated output (desktop/dist is not source). Resolve it relative to this checkout,
    not a hard-coded /workspace path, and stage it from the current viewer/ + rov01sim/ if it is absent."""
    depot = DESKTOP / "dist" / "steam_depot_win64"
    if not (depot / "viewer" / "simready_preview.html").is_file():
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node is required to stage the Steam depot")
        subprocess.run([node, str(DESKTOP / "package_steam_depot.js")], cwd=str(DESKTOP), check=True,
                       stdout=subprocess.DEVNULL, timeout=120)
    return depot


class TestSimReadyOpenUsdIntegration(unittest.TestCase):
    def test_catalog_loads_all_8_curated_industrial_assets(self):
        cat = load_simready_catalog_dict()
        self.assertEqual(cat["asset_count"], 8)
        assets = cat["assets"]
        self.assertEqual(len(assets), 8)
        ids = [a["asset_id"] for a in assets]
        self.assertEqual(
            ids,
            [
                "SR-IND-01",
                "SR-IND-02",
                "SR-IND-03",
                "SR-IND-04",
                "SR-IND-05",
                "SR-IND-06",
                "SR-IND-07",
                "SR-IND-08",
            ],
        )
        missions = {a["mission_id"] for a in assets}
        self.assertEqual(
            missions,
            {"mission_1_pool", "mission_2_hull_ut", "mission_3_sar_fault", "mission_4_pipeline"},
        )

    def test_usda_files_parse_usd_physics_schemas_and_buoyancy(self):
        assets = load_simready_assets()
        self.assertEqual(len(assets), 8)
        for a in assets:
            self.assertIn("PhysicsCollisionAPI", a.api_schemas)
            self.assertIn("PhysicsMassAPI", a.api_schemas)
            self.assertIn("PhysicsMaterialAPI", a.api_schemas)
            self.assertTrue(a.rigid_body_enabled)
            self.assertTrue(a.collision_enabled)
            self.assertGreater(a.mass_kg, 50.0)
            self.assertGreater(a.static_friction, 0.0)
            self.assertGreater(a.dynamic_friction, 0.0)
            self.assertGreater(a.restitution, 0.0)
            self.assertGreater(a.buoyancy_force_n, 0.0)
            self.assertGreater(a.submerged_weight_n, 0.0)
            self.assertLess(a.submerged_weight_n, a.dry_weight_n)
            self.assertEqual(len(a.hf_content_sha256), 64)
            self.assertEqual(a.license, "CC-BY-4.0")

    def test_usd_collision_impulse_and_wave1_rebound(self):
        sim = Simulator("mission_2_hull_ut", seed=42, model_id="rov01")
        w1 = sim.wave1
        initial_hull = w1.hull_integrity
        res = w1.collide_simready_asset("SR-IND-03", impact_speed_mps=0.95)
        self.assertTrue(res["ok"])
        col = res["collision"]
        self.assertEqual(col["asset_id"], "SR-IND-03")
        self.assertGreater(col["normal_impulse_ns"], 10.0)
        self.assertGreaterEqual(col["friction_impulse_ns"], 0.0)
        self.assertLess(w1.hull_integrity, initial_hull)
        self.assertIsNotNone(w1.last_simready_collision)

    def test_simready_teleport_and_ut_gauging_checkpoints(self):
        sim = Simulator("mission_2_hull_ut", seed=42, model_id="rov01")
        w1 = sim.wave1
        tp = w1.teleport_to_simready_asset("SR-IND-03")
        self.assertTrue(tp["ok"])
        self.assertTrue(w1.depth_hold_active)

        # Couple UT probe to UT-SR-01 (High-Pressure Gate Valve Manifold) and hold for 3.0s
        w1.start_ut_coupling("UT-SR-01", tilt_deg=1.1, distance_m=0.38)
        self.assertEqual(w1.ut_target_id, "UT-SR-01")
        self.assertEqual(w1.ut_sample_state, "Sampling_Hold_3s")
        for _ in range(3):
            sim.t += 1.0
            w1.step(1.0)
        sr_cp = next(c for c in w1.simready_ut_checkpoints if c.id == "UT-SR-01")
        self.assertTrue(sr_cp.completed)
        self.assertAlmostEqual(sr_cp.nominal_mm, 14.0)
        self.assertAlmostEqual(sr_cp.measured_mm, 12.6)
        self.assertEqual(sr_cp.status, "WARN_CORROSION")

    def test_simready_rest_api_endpoints(self):
        host = SimHost(Simulator("mission_2_hull_ut", seed=42))
        code, cat = handle_simready_api_request("GET", "/api/simready/catalog", sim_host=host)
        self.assertEqual(code, 200)
        self.assertTrue(cat["ok"])
        self.assertEqual(cat["asset_count"], 8)

        code2, usd_payload = handle_simready_api_request("GET", "/api/simready/usd/SR-IND-04", sim_host=host)
        self.assertEqual(code2, 200)
        self.assertIn("#usda 1.0", usd_payload["raw_usda"])
        self.assertEqual(usd_payload["asset"]["ut_checkpoint_id"], "UT-SR-02")

        code3, col_payload = handle_simready_api_request(
            "POST",
            "/api/simready/collide",
            {"asset_id": "SR-IND-05", "impact_speed_mps": 0.8},
            sim_host=host,
        )
        self.assertEqual(code3, 200)
        self.assertTrue(col_payload["ok"])
        self.assertEqual(col_payload["collision"]["asset_id"], "SR-IND-05")

    def test_ip_compliance_and_steam_depot_bundle(self):
        forbidden = re.compile(r"台電|海能|沃旭|qysea|fifish|\bx1\b|鰭源|bluerov|falcon", re.I)
        for a in load_simready_assets():
            payload = get_simready_usda_payload(a.asset_id)
            self.assertIsNotNone(payload)
            self.assertIsNone(forbidden.search(payload["raw_usda"]))

        depot_dir = staged_steam_depot()
        self.assertTrue((depot_dir / "viewer" / "simready_preview.html").is_file())
        self.assertTrue((depot_dir / "viewer" / "simready_usd_loader.js").is_file())
        self.assertTrue((depot_dir / "viewer" / "simready_usd" / "simready_catalog.json").is_file())
        self.assertTrue((depot_dir / "rov01sim" / "simready_usd.py").is_file())


if __name__ == "__main__":
    unittest.main()
