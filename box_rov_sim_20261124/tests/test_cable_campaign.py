import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rov01sim.cable_campaign import (
    SubseaCableCampaign,
    compute_catenary_curve_ned,
    STAGE_1_LOCATE,
    STAGE_2_RETRIEVE,
    STAGE_3_REPAIR,
    STAGE_4_EXTRACT,
)
from rov01sim.engine import Simulator
from rov01sim.server import SimHost, handle_simready_api_request


class TestSubseaCableCampaign(unittest.TestCase):
    def test_01_catenary_cable_curve_physics(self):
        anchor = [6.8, 1.2, 6.2]
        rov_pos = [8.2, -0.5, 6.0]
        pts = compute_catenary_curve_ned(anchor, rov_pos, num_points=14, sag_m=0.55)
        self.assertEqual(len(pts), 14)
        self.assertAlmostEqual(pts[0][0], anchor[0], places=3)
        self.assertAlmostEqual(pts[-1][0], rov_pos[0], places=3)
        # Midpoint should sag deeper (larger Down Z) than linear midpoint
        mid_z = pts[7][2]
        linear_mid_z = 0.5 * (anchor[2] + rov_pos[2])
        self.assertGreater(mid_z, linear_mid_z + 0.25)

    def test_02_seamless_four_stage_progression(self):
        camp = SubseaCableCampaign()
        st0 = camp.to_dict([0.0, 0.0, 1.5])
        self.assertEqual(st0["stage_code"], STAGE_1_LOCATE)
        self.assertEqual(st0["stage_num"], 1)

        # Stage 1 -> clear 3 sonar waypoint rings -> auto-transitions to Stage 2
        camp.advance_sonar_ring([2.2, -0.6, 3.0])
        camp.advance_sonar_ring([3.4, -1.1, 4.2])
        st2 = camp.advance_sonar_ring([4.5, -1.5, 5.2])
        self.assertEqual(st2["stage_code"], STAGE_2_RETRIEVE)
        self.assertEqual(st2["stage_num"], 2)
        self.assertEqual(st2["waypoint_rings_cleared"], 3)

        # Stage 2 -> grab cable with manipulator -> tow and seat into splice saddle -> Stage 3
        st2_grab = camp.grab_or_tow_cable([7.0, 0.4, 6.0], place_in_saddle=False)
        self.assertTrue(st2_grab["cable_grabbed"])
        self.assertEqual(st2_grab["stage_code"], STAGE_2_RETRIEVE)

        st3 = camp.grab_or_tow_cable([9.1, -1.7, 6.7], place_in_saddle=True)
        self.assertEqual(st3["stage_code"], STAGE_3_REPAIR)
        self.assertEqual(st3["stage_num"], 3)
        self.assertTrue(st3["cable_seated_in_saddle"])

        # Stage 3 -> 3-step repair & clamp lock -> auto-energizes cable & advances to Stage 4
        camp.perform_repair_step(34.0, [9.2, -1.8, 6.8])
        camp.perform_repair_step(34.0, [9.2, -1.8, 6.8])
        st4 = camp.perform_repair_step(35.0, [9.2, -1.8, 6.8])
        self.assertEqual(st4["stage_code"], STAGE_4_EXTRACT)
        self.assertEqual(st4["stage_num"], 4)
        self.assertTrue(st4["cable_energized"])
        self.assertEqual(st4["power_restore_pct"], 100.0)

        # Stage 4 -> dock into TMS recovery cage -> S-Rank victory
        done = camp.complete_extraction(hull_integrity_pct=99.0, elapsed_s=125.0, rov_pos_ned=[0.0, 0.0, 2.2])
        self.assertTrue(done["campaign_completed"])
        self.assertTrue(done["campaign_rank"].startswith("S"))
        self.assertGreaterEqual(done["campaign_score"], 90.0)

    def test_03_rest_and_wave1_campaign_endpoints(self):
        room = SimHost(Simulator('mission_1_pool', seed=42))
        code, state_res = handle_simready_api_request("GET", "/api/campaign/state", None, room)
        self.assertEqual(code, 200)
        self.assertTrue(state_res["ok"])
        self.assertEqual(state_res["campaign"]["stage_num"], 1)

        code2, act_res = handle_simready_api_request(
            "POST", "/api/campaign/action", {"sub_action": "set_stage", "stage_num": 2}, room
        )
        self.assertEqual(code2, 200)
        self.assertEqual(act_res["campaign"]["stage_num"], 2)
        self.assertTrue(act_res["campaign"]["cable_grabbed"])

        code3, grab_res = handle_simready_api_request(
            "POST", "/api/campaign/action", {"sub_action": "grab_cable", "place_in_saddle": True}, room
        )
        self.assertEqual(code3, 200)
        self.assertTrue(grab_res["campaign"]["cable_seated_in_saddle"])
        self.assertEqual(grab_res["campaign"]["stage_num"], 3)


if __name__ == "__main__":
    unittest.main()


class TestDeepLinkGateM09(unittest.TestCase):
    """Regression for M_09 TLC counterexample: Init -> Extract gave an S rank from Stage 1."""

    def _full_run(self, camp):
        for p in ([2.2, -0.6, 3.0], [3.4, -1.1, 4.2], [4.5, -1.5, 5.2]):
            camp.advance_sonar_ring(p)
        camp.grab_or_tow_cable([7.0, 0.4, 6.0])
        camp.grab_or_tow_cable([9.1, -1.7, 6.7], place_in_saddle=True)
        for d in (34.0, 34.0, 35.0):
            camp.perform_repair_step(d, [9.2, -1.8, 6.8])

    def test_tlc_trace_stage1_extract_is_rejected(self):
        from rov01sim.cable_campaign import SubseaCableCampaign
        camp = SubseaCableCampaign()
        st = camp.complete_extraction(hull_integrity_pct=100.0, rov_pos_ned=[0.0, 0.0, 2.2])
        self.assertFalse(st["campaign_completed"])
        self.assertEqual(st["stage_num"], 1)
        self.assertEqual(st["campaign_rank"], "IN_PROGRESS")
        self.assertTrue(st["last_rejection"].startswith("WRONG_STAGE_1"))

    def test_stage_skips_rejected(self):
        from rov01sim.cable_campaign import SubseaCableCampaign
        camp = SubseaCableCampaign()
        self.assertTrue(camp.perform_repair_step(100.0, [9.2, -1.8, 6.8])["last_rejection"].startswith("WRONG_STAGE"))
        self.assertTrue(camp.grab_or_tow_cable([6.8, 1.2, 6.4])["last_rejection"].startswith("WRONG_STAGE"))
        self.assertEqual(camp.stage_num, 1)
        self.assertEqual(camp.waypoint_rings_cleared, 0)

    def test_out_of_range_actions_rejected(self):
        from rov01sim.cable_campaign import SubseaCableCampaign
        camp = SubseaCableCampaign()
        st = camp.advance_sonar_ring([40.0, 40.0, 40.0])
        self.assertTrue(st["last_rejection"].startswith("OUT_OF_RANGE"))
        self.assertEqual(st["waypoint_rings_cleared"] if "waypoint_rings_cleared" in st else camp.waypoint_rings_cleared, 0)
        self._full_run(camp)
        self.assertEqual(camp.stage_num, 4)
        far = camp.complete_extraction(rov_pos_ned=[9.2, -1.8, 6.8])
        self.assertFalse(far["campaign_completed"])
        self.assertTrue(far["last_rejection"].startswith("OUT_OF_RANGE"))
        nopos = camp.complete_extraction()
        self.assertEqual(nopos["last_rejection"], "ROV_POSITION_REQUIRED")

    def test_full_run_still_ranks_and_cannot_rerank(self):
        from rov01sim.cable_campaign import SubseaCableCampaign
        camp = SubseaCableCampaign()
        self._full_run(camp)
        done = camp.complete_extraction(hull_integrity_pct=99.0, rov_pos_ned=[0.0, 0.0, 2.2])
        self.assertTrue(done["campaign_completed"])
        self.assertTrue(done["campaign_rank"].startswith("S"))
        again = camp.complete_extraction(hull_integrity_pct=10.0, rov_pos_ned=[0.0, 0.0, 2.2])
        self.assertEqual(again["last_rejection"], "CAMPAIGN_ALREADY_COMPLETED")
        self.assertTrue(again["campaign_rank"].startswith("S"))

    def test_stage_jump_is_unranked_drill(self):
        from rov01sim.cable_campaign import DRILL_RANK, SubseaCableCampaign
        camp = SubseaCableCampaign()
        st = camp.set_stage(4, [0.8, 0.0, 2.3])
        self.assertTrue(st["drill_mode"])
        self.assertFalse(st["campaign_completed"])
        done = camp.complete_extraction(hull_integrity_pct=100.0, rov_pos_ned=[0.8, 0.0, 2.3])
        self.assertTrue(done["campaign_completed"])
        self.assertEqual(done["campaign_rank"], DRILL_RANK)
        self.assertFalse(camp.reset_campaign()["drill_mode"])
