"""Cable site checks through deployed world, shutter and viewer telemetry."""
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_from_euler


class RepairSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = Simulator("cable_repair", 4)

    def test_survey_conditions(self):
        world = self.sim.world
        bed = world.seabed_at(np.zeros(3))
        self.assertGreater(bed, world.seabed_at(np.array([0, .9, 0])) + .2)
        self.assertLess(world.visibility_at([0, 0, bed - .4]), world.visibility_at([0, 0, bed - 4]))
        self.assertGreater(world.current_at(np.array([0, 0, bed - .4]))[1], .05)

    def test_report_requires_two_visible_end_photos(self):
        sim = self.sim
        names = {ob.name: ob for ob in sim.scenario.obstacles}
        for side, subject in [(-1, "shore_end"), (1, "sea_end")]:
            end = names[f"armoured run {side} 1"]
            self.assertTrue(end.snag_hold)
            sim.vehicle.s.pos[:] = np.array(end.p0) - [1.8, -.2, .50]
            sim.vehicle.s.q[:] = q_from_euler(0, 0, np.pi)
            sim._take_photo()
            self.assertNotIn(subject, sim.viewer_state()["repair_report"]["observations"])
            sim.vehicle.s.q[:] = q_from_euler(0, 0, 0)
            photo = sim._take_photo()
            report = sim.viewer_state()["repair_report"]
            self.assertEqual(report["observations"][subject]["photo"], photo["name"])
            if side == -1:
                self.assertNotIn("end_separation_m", report)
        self.assertAlmostEqual(report["end_separation_m"], 1.44, places=2)

    def test_next_beat_requires_a_new_exposure_of_the_requested_end(self):
        from qysim.campaign.beats import BeatRun
        sim = Simulator("cable_repair", 4)
        end = next(ob for ob in sim.scenario.obstacles if ob.name == "armoured run 1 1")
        sim.vehicle.s.pos[:] = np.array(end.p0) - [1.8, -.2, .5]
        sim.vehicle.s.q[:] = q_from_euler(0, 0, 0)
        sim._take_photo()
        beat = {"id": "close", "condition": {"path": "surveyPhotos.sea_end.t"}}
        run = BeatRun([beat], sim)
        self.assertEqual(run.evidence(sim, beat)["surveyPhotos"], {})
        self.assertIn("sea_end", sim.repair_evidence)
        sim._take_photo()
        self.assertIn("sea_end", run.evidence(sim, beat)["surveyPhotos"])

    def test_perimeter_records_a_relative_fix_and_requires_visible_rock(self):
        sim = Simulator("cable_perimeter", 42)
        sim.vehicle.s.pos[:] = [-.45, 2.35, 12.64]
        sim.vehicle.s.q[:] = q_from_euler(0, 0, 0)
        sim._take_photo()
        record = sim.viewer_state()["repair_report"]["observations"]["housing"]
        self.assertIn("from_rock_ned_m", record)
        self.assertNotIn("pos_ned_m", record)
        sim.vehicle.s.pos[:] = [1.3, 2.1, 10.]
        sim.vehicle.s.q[:] = q_from_euler(0, 0, np.pi)
        sim._take_photo()
        self.assertEqual(record, sim.repair_evidence["housing"])

    def test_neutral_vehicle_drifts_across_perimeter_station(self):
        sim = Simulator("cable_perimeter", 42)
        start = sim.vehicle.s.pos.copy()
        for _ in range(500):
            sim.step()
        self.assertGreater(sim.vehicle.s.pos[1] - start[1], .1)

    def test_taut_tether_crossing_the_shore_end_catches_on_armour(self):
        from qysim.cable_repair import RepairBed, repair_site
        from qysim.tether import TetherParams
        from qysim.world import World
        from tests.test_tether_physics import drive, straight
        site = repair_site()
        world = World(site.seabed_depth)
        world.terrain = RepairBed()
        world.obstacles = site.obstacles
        # A nearly taut six-metre reach, swept sideways at the lip of the shore-side break.
        end = (3.2, -1.1, 12.73)
        tether = straight(world, (-2.8, -1.1, 12.73), end, 5.97, TetherParams(segments=12))
        drive(tether, end, (0, -.6, 0), 1.5)
        names = [entry['obstacle'] for entry in tether.events if entry['type'] == 'tether_snag']
        self.assertIn('armoured run -1 1', names)
