"""Wave 1 & CORR-ROV-01 unit tests:
1. 6DoF gamepad deadzone + exponential curve shaping across all 6 DoF.
2. 6-Thruster Moore-Penrose fault reallocation when T3 (index=2) fails.
3. Wave1Manager collision hull integrity deduction, Emergency RTH, and UT SOP evaluation (0..100 score).
4. CORR-ROV-01 Strict IP & Exterior Mesh Isolation guard (0 commercial brand / shell references).
"""
import re
from pathlib import Path
import unittest
import numpy as np

from rov01sim.engine import Simulator
from rov01sim.physics import Vehicle
from rov01sim.vehicles import vehicle_catalogue, get_vehicle_definition
from rov01sim.wave1 import (
    WAVE1_MISSION_CATALOG,
    allocate_6thruster_with_fault_compensation,
    apply_deadzone_and_expo,
    shape_6dof_gamepad,
)


class TestWave1AndCorrRov01(unittest.TestCase):
    def test_deadzone_and_expo_6dof_shaping(self):
        self.assertEqual(apply_deadzone_and_expo(0.05, deadzone=0.08, expo=0.35), 0.0)
        self.assertEqual(apply_deadzone_and_expo(-0.079, deadzone=0.08, expo=0.35), 0.0)
        self.assertAlmostEqual(apply_deadzone_and_expo(1.0, deadzone=0.08, expo=0.35), 1.0, places=6)
        self.assertAlmostEqual(apply_deadzone_and_expo(-1.0, deadzone=0.08, expo=0.35), -1.0, places=6)
        linear = apply_deadzone_and_expo(0.5, deadzone=0.08, expo=0.0)
        curved = apply_deadzone_and_expo(0.5, deadzone=0.08, expo=0.5)
        self.assertGreater(linear, curved)
        self.assertGreater(curved, 0.0)

        shaped = shape_6dof_gamepad(
            {"surge": 0.6, "sway": -0.4, "heave": 0.03, "roll": 0.5, "pitch": -0.7, "yaw": 1.0},
            deadzone=0.08,
            expo=0.35,
        )
        self.assertEqual(set(shaped.keys()), {"surge", "sway", "heave", "roll", "pitch", "yaw"})
        self.assertEqual(shaped["heave"], 0.0)
        self.assertAlmostEqual(shaped["yaw"], 1.0, places=6)
        self.assertGreater(shaped["surge"], 0.0)
        self.assertLess(shaped["sway"], 0.0)

    def test_6thruster_fault_reallocation_t3_jammed(self):
        v = Vehicle(model_id="rov01")
        wrench = np.array([0.65, 0.25, -0.35, 0.1, -0.15, 0.3], dtype=float)
        u_healthy = allocate_6thruster_with_fault_compensation(v.B, v.B_pinv, wrench, [1, 1, 1, 1, 1, 1])
        self.assertEqual(u_healthy.shape, (6,))
        self.assertLessEqual(np.max(np.abs(u_healthy)), 1.000001)

        u_fault = allocate_6thruster_with_fault_compensation(v.B, v.B_pinv, wrench, [1, 1, 0, 1, 1, 1])
        self.assertEqual(u_fault[2], 0.0)
        self.assertLessEqual(np.max(np.abs(u_fault)), 1.000001)
        achieved = v.B @ u_fault
        self.assertGreater(achieved[0], 0.3)

    def test_four_missions_and_ut_sop_evaluation(self):
        self.assertEqual(len(WAVE1_MISSION_CATALOG), 4)
        for m_key, m in WAVE1_MISSION_CATALOG.items():
            sim = Simulator(m_key, seed=42, model_id="rov01")
            st = sim.viewer_state()
            self.assertIsNotNone(st["wave1"])
            self.assertEqual(st["wave1"]["mission_id"], m["id"])

        sim = Simulator("mission_2_hull_ut", seed=42, model_id="rov01")
        w1 = sim.wave1
        w1.inject_thruster_fault(2, True)
        self.assertEqual(sim.health[2], 0.0)
        sim.apply_gamepad_6dof({"surge": 0.5, "yaw": 0.2, "deadzone": 0.08, "expo": 0.35})
        for _ in range(10):
            sim.step(0.02)
        self.assertEqual(sim.vehicle.s.thrust[2], 0.0)

        for cp in w1.ut_checkpoints:
            sim.vehicle.s.pos[:] = np.array(cp.point, dtype=float)
            w1.start_ut_coupling(cp.id)
            for _ in range(3):
                sim.t += 1.0
                w1.step(1.0)
            self.assertTrue(cp.completed)

        rth = w1.trigger_emergency_return(True)
        self.assertTrue(rth["hazards"]["emergency_return_active"])
        for _ in range(25):
            sim.step(0.04)

        report = w1.compute_sop_evaluation()
        self.assertIn("ROV-01", report["vehicle_model"])
        self.assertEqual(report["metrics"]["ut_completed"], 4)
        self.assertGreaterEqual(report["total_score"], 70.0)
        self.assertLessEqual(report["total_score"], 100.0)

    def test_corr_rov01_zero_commercial_brand_or_shell_references(self):
        cat = vehicle_catalogue()
        ids = [c["id"] for c in cat]
        self.assertIn("rov01", ids)
        self.assertNotIn("x1", ids)
        rov01_def = get_vehicle_definition("rov01").public()
        self.assertEqual(rov01_def["name"], "ROV-01")
        self.assertEqual(rov01_def["model"], "procedural://rov-01")

        viewer_dir = Path(__file__).resolve().parents[1] / "viewer"
        forbidden = re.compile(r"(qysea|fifish|q-irc|\bqic\b|rov\.glb|x1\.glb)", re.IGNORECASE)
        for path in viewer_dir.glob("*"):
            if path.suffix in (".html", ".js", ".css"):
                text = path.read_text(encoding="utf-8")
                match = forbidden.search(text)
                self.assertIsNone(match, f"CORR-ROV-01 violation in {path.name}: {match.group(0) if match else ''}")


if __name__ == "__main__":
    unittest.main()
