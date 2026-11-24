"""Wave 4 Worker A unit tests for B2B Enterprise Instructor & Multi-Trainee Roster Module (rov01sim/b2b_roster.py).

Covers:
1. Deterministic HMAC/SHA-256 tamper-evident signature generation & verification across M1..M4.
2. Tampered score / grade / cert_status / hull_integrity_pct / trainee_id rejection.
3. hull_integrity_pct == 0% automatic Failed_Retry, Grade F, and 0.0 score enforcement (both direct and via Wave1Manager).
4. CohortRosterManager analytics (pass rate, average UT thickness error, most frequent hazard deduction) and UTF-8-BOM CSV, JSON, and ISO-13628-6 HTML exports.
5. REST endpoints GET /api/b2b/roster and POST /api/b2b/record_run in rov01sim.server.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import socket
import tempfile
import unittest
import urllib.request

from rov01sim.b2b_roster import (
    CohortRosterManager,
    STANDARD_SOP_MODULES,
    TraineeSessionRecord,
    verify_certificate_signature,
)
from rov01sim.engine import Simulator
from rov01sim.server import SimHost, handle_b2b_api_request, start_static


class TestB2BRosterAndTamperEvidentCerts(unittest.TestCase):
    def test_valid_signature_and_standard_sop_modules(self):
        self.assertEqual(
            STANDARD_SOP_MODULES,
            ("M1_POOL_6DOF", "M2_HULL_UT", "M3_T3_FAULT_RETURN", "M4_PIPELINE_TRIAL"),
        )
        rec = TraineeSessionRecord(
            trainee_id="YX-PILOT-101",
            trainee_name="張爲斌 (Robin Chang)",
            department="永祥水下工程部",
            mission_id="M2_HULL_UT",
            timestamp="2026-10-25 12:00:00 UTC+8",
            hull_integrity_pct=100.0,
            ut_checkpoints_completed=4,
            ut_max_tilt_deg=1.2,
            t3_fault_survived=True,
            tether_snag_count=0,
            elapsed_sec=92.4,
            total_score=96.5,
            grade="A+",
            cert_status="Certified_Pass",
        )
        self.assertEqual(len(rec.verification_hash), 64)
        self.assertTrue(verify_certificate_signature(rec))
        self.assertTrue(verify_certificate_signature(rec.to_dict()))

        # Verify determinism across identical telemetry payloads
        rec_identical = TraineeSessionRecord(
            trainee_id="YX-PILOT-101",
            trainee_name="張爲斌 (Robin Chang)",
            department="永祥水下工程部",
            mission_id="M2_HULL_UT",
            timestamp="2026-10-25 12:00:00 UTC+8",
            hull_integrity_pct=100.0,
            ut_checkpoints_completed=4,
            ut_max_tilt_deg=1.2,
            t3_fault_survived=True,
            tether_snag_count=0,
            elapsed_sec=92.4,
            total_score=96.5,
            grade="A+",
            cert_status="Certified_Pass",
        )
        self.assertEqual(rec.verification_hash, rec_identical.verification_hash)

    def test_tampered_score_and_fields_rejected(self):
        rec = TraineeSessionRecord(
            trainee_id="YX-PILOT-102",
            trainee_name="林承翰 (Hank Lin)",
            department="離岸海事工程組",
            mission_id="M3_T3_FAULT_RETURN",
            timestamp="2026-10-25 12:05:00 UTC+8",
            hull_integrity_pct=84.0,
            ut_checkpoints_completed=3,
            ut_max_tilt_deg=2.4,
            t3_fault_survived=True,
            tether_snag_count=1,
            elapsed_sec=140.0,
            total_score=75.0,
            grade="B",
            cert_status="Conditional_Retest",
        )
        base_dict = rec.to_dict()
        self.assertTrue(verify_certificate_signature(base_dict))

        # Tamper with total_score
        tampered_score = dict(base_dict)
        tampered_score["total_score"] = 95.0
        self.assertFalse(verify_certificate_signature(tampered_score))

        # Tamper with cert_status
        tampered_status = dict(base_dict)
        tampered_status["cert_status"] = "Certified_Pass"
        self.assertFalse(verify_certificate_signature(tampered_status))

        # Tamper with grade
        tampered_grade = dict(base_dict)
        tampered_grade["grade"] = "A+"
        self.assertFalse(verify_certificate_signature(tampered_grade))

        # Tamper with hull_integrity_pct
        tampered_hull = dict(base_dict)
        tampered_hull["hull_integrity_pct"] = 100.0
        self.assertFalse(verify_certificate_signature(tampered_hull))

        # Tamper with trainee_name
        tampered_name = dict(base_dict)
        tampered_name["trainee_name"] = "Hacker Pilot"
        self.assertFalse(verify_certificate_signature(tampered_name))

        # Corrupt verification_hash
        tampered_hash = dict(base_dict)
        tampered_hash["verification_hash"] = "0" * 64
        self.assertFalse(verify_certificate_signature(tampered_hash))

    def test_zero_hull_integrity_forces_failed_retry_and_zero_score(self):
        # Direct instantiation with hull_integrity_pct=0.0 even when caller passes high score/pass
        rec = TraineeSessionRecord(
            trainee_id="YX-PILOT-103",
            trainee_name="蔡明哲 (Alex Tsai)",
            department="外包測試組",
            mission_id="M4_PIPELINE_TRIAL",
            hull_integrity_pct=0.0,
            total_score=92.0,
            grade="A+",
            cert_status="Certified_Pass",
        )
        self.assertEqual(rec.hull_integrity_pct, 0.0)
        self.assertEqual(rec.total_score, 0.0)
        self.assertEqual(rec.grade, "F")
        self.assertEqual(rec.cert_status, "Failed_Retry")
        self.assertTrue(verify_certificate_signature(rec))

        # End-to-end from Wave1Manager with fatal collision (hull_integrity == 0%)
        sim = Simulator("mission_2_hull_ut", seed=42)
        sim.wave1.inject_collision_impulse(100.0, zone="front-hull")
        self.assertEqual(sim.wave1.hull_integrity, 0.0)
        self.assertTrue(sim.wave1.mission_aborted)

        w1_rec = TraineeSessionRecord.from_wave1_evaluation(
            sim.wave1,
            trainee_id="YX-PILOT-104",
            trainee_name="Fatal Collision Trainee",
            department="外包測試組",
        )
        self.assertEqual(w1_rec.hull_integrity_pct, 0.0)
        self.assertEqual(w1_rec.total_score, 0.0)
        self.assertEqual(w1_rec.grade, "F")
        self.assertEqual(w1_rec.cert_status, "Failed_Retry")
        self.assertTrue(verify_certificate_signature(w1_rec))

    def test_cohort_exports_csv_bom_json_and_printable_html(self):
        mgr = CohortRosterManager.create_tuesday_demo_cohort()
        summary = mgr.compute_cohort_summary()
        self.assertEqual(summary["total_runs"], 6)
        self.assertEqual(summary["certified_pass_count"], 3)
        self.assertEqual(summary["conditional_retest_count"], 2)
        self.assertEqual(summary["failed_retry_count"], 1)
        self.assertAlmostEqual(summary["cohort_pass_rate"], 50.0, places=1)
        self.assertGreater(summary["average_ut_thickness_error_mm"], 0.0)
        self.assertEqual(summary["most_frequent_hazard_deduction"], "HULL_COLLISION_IMPULSE")
        self.assertTrue(summary["all_signatures_valid"])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = mgr.export_cohort_csv(tmp / "cohort.csv")
            json_path = mgr.export_cohort_json(tmp / "cohort.json")
            html_path = mgr.export_printable_certificate_html(tmp / "cert.html")

            # Verify UTF-8 BOM on CSV for Excel compatibility
            raw_csv = csv_path.read_bytes()
            self.assertTrue(raw_csv.startswith(b"\xef\xbb\xbf"), "CSV must start with UTF-8 BOM")
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 6)
            for row in rows:
                self.assertEqual(len(row["verification_hash"]), 64)

            # Verify JSON export and signature round-trip
            loaded_json = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_json["summary"]["total_runs"], 6)
            for r_dict in loaded_json["records"]:
                self.assertTrue(verify_certificate_signature(r_dict))

            # Verify printable HTML certificate contains ISO-13628-6, Robin sign-off, and SHA-256 seal
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn("ISO 13628-6", html_text)
            self.assertIn("張爲斌 (Robin Chang)", html_text)
            self.assertIn("ROV-01", html_text)
            self.assertIn(mgr.records[0].verification_hash, html_text)

    def test_rest_endpoints_get_roster_and_post_record_run(self):
        sim = Simulator("mission_2_hull_ut", seed=42)
        sim.wave1.set_depth_hold(True, target_depth_m=5.0)
        for cp in sim.wave1.ut_checkpoints:
            cp.completed = True
        host = SimHost(sim)

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        httpd = start_static(port, "127.0.0.1", sim_host=host)
        try:
            base_url = f"http://127.0.0.1:{port}"
            # 1. GET /api/b2b/roster
            with urllib.request.urlopen(f"{base_url}/api/b2b/roster", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                roster_data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(roster_data["ok"])
            initial_count = roster_data["summary"]["total_runs"]
            self.assertGreaterEqual(initial_count, 6)

            # 2. POST /api/b2b/record_run
            req_body = json.dumps({
                "trainee_id": "YX-PILOT-777",
                "trainee_name": "周俊傑 (Jason Chou)",
                "department": "永祥水下工程部 · 特遣隊",
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/b2b/record_run",
                data=req_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                cert_resp = json.loads(resp.read().decode("utf-8"))

            self.assertTrue(cert_resp["ok"])
            self.assertTrue(cert_resp["verified"])
            self.assertEqual(cert_resp["trainee_id"], "YX-PILOT-777")
            self.assertEqual(cert_resp["mission_id"], "M2_HULL_UT")
            self.assertTrue(verify_certificate_signature(cert_resp))
            self.assertTrue(verify_certificate_signature(cert_resp["record"]))
            self.assertEqual(cert_resp["cohort_summary"]["total_runs"], initial_count + 1)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
