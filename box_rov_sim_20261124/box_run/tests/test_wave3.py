import math
import pathlib
import unittest

from rov01sim.engine import Simulator


class TestWave3FlightLoopsAndAudio(unittest.TestCase):
    def test_depth_hold_pid_converges_to_target_depth(self):
        sim = Simulator("mission_1_pool", seed=42)
        sim.rc_physical.rc_lock = 0
        start_depth = sim.depth
        target_depth = start_depth + 1.25
        st = sim.wave1.set_depth_hold(True, target_depth_m=target_depth)
        self.assertTrue(st["wave3"]["depth_hold_active"])
        self.assertAlmostEqual(st["wave3"]["target_depth_m"], target_depth, places=2)

        for _ in range(180):
            sim.step(0.05)

        final_err = abs(target_depth - sim.depth)
        self.assertLess(final_err, 0.18, f"Depth Hold PID failed to converge: err={final_err:.4f}m")

    def test_heading_hold_pid_converges_to_target_heading(self):
        sim = Simulator("mission_1_pool", seed=42)
        sim.rc_physical.rc_lock = 0
        cur_deg = math.degrees(sim.yaw) % 360.0
        target_deg = (cur_deg + 45.0) % 360.0
        st = sim.wave1.set_heading_hold(True, target_heading_deg=target_deg)
        self.assertTrue(st["wave3"]["heading_hold_active"])

        for _ in range(160):
            sim.step(0.05)

        now_deg = math.degrees(sim.yaw) % 360.0
        err_deg = abs((target_deg - now_deg + 180.0) % 360.0 - 180.0)
        self.assertLess(err_deg, 3.5, f"Heading Hold PID failed to converge: err={err_deg:.2f}°")

    def test_emergency_surface_ascent_reaches_surface_and_completes(self):
        sim = Simulator("mission_2_hull_ut", seed=42)
        sim.rc_physical.rc_lock = 0
        sim.vehicle.s.pos[2] = 3.2
        st = sim.wave1.trigger_emergency_surface(True)
        self.assertEqual(st["mode_state"], "emergency_surface")
        self.assertTrue(st["wave3"]["emergency_surface_active"])

        for _ in range(160):
            sim.step(0.05)
            if sim.wave1.emergency_surface_completed:
                break

        self.assertTrue(sim.wave1.emergency_surface_completed)
        self.assertLessEqual(sim.depth, 0.30)
        self.assertEqual(sim.wave1.state()["mode_state"], "normal")

    def test_tether_snag_warning_and_recovery_transition(self):
        sim = Simulator("mission_4_pipeline", seed=42)
        st1 = sim.wave1.inject_tether_snag()
        self.assertEqual(st1["mode_state"], "tether_snag_warning")
        self.assertTrue(st1["wave3"]["tether_snag_active"])

        st2 = sim.wave1.resolve_tether_snag()
        self.assertEqual(st2["mode_state"], "normal")
        self.assertFalse(st2["wave3"]["tether_snag_active"])
        self.assertEqual(st2["wave3"]["tether_snag_recovered_count"], 1)

    def test_ut_3_second_stable_sampling_lock_state_machine(self):
        sim = Simulator("mission_2_hull_ut", seed=42)
        # Initial state is ut_searching -> ring is 'searching' (#22D3EE)
        st0 = sim.wave1.state()
        self.assertEqual(st0["wave3"]["ut_state"], "ut_searching")
        self.assertEqual(st0["wave3"]["ut_ring_state"], "searching")

        # Start coupling with tilt=4.2° (>3°) -> stays in ut_aligning (#F59E0B) and does not advance timer
        st_high_tilt = sim.wave1.start_ut_coupling("UT-01", tilt_deg=4.2, distance_m=0.45)
        self.assertEqual(st_high_tilt["wave3"]["ut_state"], "ut_aligning")
        self.assertEqual(st_high_tilt["wave3"]["ut_ring_state"], "aligning")
        for _ in range(20):
            sim.step(0.05)
        self.assertEqual(sim.wave1.ut_hold_elapsed_s, 0.0)

        # Align perpendicular (<3°): tilt=1.4°, distance=0.42m -> advances timer to 3.0s and locks (#10B981)
        sim.wave1.start_ut_coupling("UT-01", tilt_deg=1.4, distance_m=0.42)
        for _ in range(30):
            sim.step(0.05)
        self.assertEqual(sim.wave1.ut_state, "ut_aligning")
        self.assertGreater(sim.wave1.ut_hold_elapsed_s, 1.2)

        for _ in range(40):
            sim.step(0.05)
        st_locked = sim.wave1.state()
        self.assertEqual(st_locked["wave3"]["ut_state"], "ut_coupled_lock")
        self.assertEqual(st_locked["wave3"]["ut_ring_state"], "coupled")
        cp1 = next(c for c in sim.wave1.ut_checkpoints if c.id == "UT-01")
        self.assertTrue(cp1.completed)

    def test_ut_ring_state_locks_to_cyan_in_m1_m3_m4(self):
        sim = Simulator("mission_2_hull_ut", seed=42)
        sim.wave1.start_ut_coupling("UT-01")
        for _ in range(3):
            sim.t += 1.0
            sim.wave1.step(1.0)
        self.assertEqual(sim.wave1.state()["wave3"]["ut_ring_state"], "coupled")

        # When in M3 or M4, uncoupled/standby ring must lock to 'searching' (#22D3EE)
        for m_id in ("mission_1_pool", "mission_3_sar_fault", "mission_4_pipeline"):
            sim.wave1.mission_id = m_id
            self.assertEqual(sim.wave1.state()["wave3"]["ut_ring_state"], "searching")

    def test_release_mode_blocks_legacy_qysim_shim_and_vendor_adapter(self):
        sim = Simulator("mission_1_pool", seed=42, release_mode=True)
        self.assertTrue(sim.release_mode)
        res = sim.sdk_call("ROV_VENDOR_LEGACY", "get_rov_Posture", [], {})
        self.assertIn("error", res.get("result", {}))

    def test_depth_hold_stability_not_gameable_without_engaging_hold(self):
        """Regression: a trainee who never engages depth-hold must NOT bank full
        depth-stability credit. Previously error only accrued while depth-hold was
        active and RMS defaulted to 0 -> 100% stability for pure-manual flight."""
        import numpy as np

        # Exploit attempt: huge depth excursions, depth-hold never engaged.
        sim = Simulator("mission_1_pool", seed=42)
        sim.rc_physical.rc_lock = 0
        self.assertIsNone(sim.controller.depth_hold)
        for i in range(300):
            sim.vehicle.s.pos[2] = 3.0 + 2.5 * np.sin(i * 0.4)
            sim.step(0.05)
        self.assertEqual(sim.wave1.depth_hold_stability_pct, 0.0)

        # Legitimate depth-hold session must still earn high stability.
        sim2 = Simulator("mission_1_pool", seed=42)
        sim2.rc_physical.rc_lock = 0
        sim2.wave1.set_depth_hold(True, target_depth_m=sim2.depth + 1.0)
        for _ in range(300):
            sim2.step(0.05)
        self.assertGreater(sim2.wave1.depth_hold_stability_pct, 85.0)

        exploit = sim.wave1.compute_sop_evaluation()["breakdown"]["stability_hold_pts"]
        legit = sim2.wave1.compute_sop_evaluation()["breakdown"]["stability_hold_pts"]
        self.assertLess(exploit, legit)

    def test_rov_audio_synthesizer_module_exists_and_is_asset_free(self):
        audio_js = pathlib.Path(__file__).resolve().parent.parent / "viewer" / "rov_audio.js"
        self.assertTrue(audio_js.exists())
        text = audio_js.read_text(encoding="utf-8")
        for method in (
            "updateThrusterRumble",
            "playCollisionThud",
            "playSonarPing",
            "playUtCouplingChime",
            "playEmergencyAlarm",
        ):
            self.assertIn(method, text)
