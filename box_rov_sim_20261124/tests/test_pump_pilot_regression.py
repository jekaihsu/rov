"""Pump fault snapshots and complete deterministic pilot qualification regression."""
import unittest
from rov01sim.engine import Simulator
from rov01sim.b2b_roster import TraineeSessionRecord, verify_certificate_signature


class TestPumpAndPilotRegression(unittest.TestCase):
    def test_thermal_trip_publishes_stopped_pump_in_same_step_and_recovers(self):
        sim = Simulator('open_water', seed=80, model_id='rov01_pro')
        tools = sim.tools
        tools.command({'tool': 'hpu', 'verb': 'toggle'})
        tools.step(.1)
        self.assertTrue(tools.state()['systems']['hydraulic']['pump'])
        tools.oil_temp = 61.
        tools.step(.01)
        snap = tools.state()['systems']
        self.assertFalse(tools.pump)
        self.assertFalse(snap['hydraulic']['pump'])
        self.assertEqual(snap['hydraulic']['flow_lpm'], 0.)
        self.assertIn('液壓油溫過高', snap['alarms'])
        tools.oil_temp = 24.
        tools.command({'tool': 'hpu', 'verb': 'toggle'})
        tools.step(.1)
        self.assertTrue(tools.state()['systems']['hydraulic']['pump'])
        # Disconnected snapshots stay stopped until the operator restarts.
        sim.tether.broken = True
        tools.step(.01)
        self.assertFalse(tools.state()['systems']['hydraulic']['pump'])
        sim.tether.broken = False
        tools.step(.1)
        self.assertFalse(tools.pump)
        tools.command({'tool': 'hpu', 'verb': 'toggle'})
        tools.step(.1)
        self.assertTrue(tools.state()['systems']['hydraulic']['pump'])

    def test_ut_dwell_cannot_be_reused_for_another_target_or_direct_samples(self):
        sim = Simulator('mission_2_hull_ut', seed=80)
        w = sim.wave1
        w.sample_ut_checkpoint('UT-01')
        self.assertFalse(any(c.completed for c in w.ut_checkpoints))
        w.start_ut_coupling('UT-01')
        for _ in range(3):
            sim.t += 1.
            w.step(1.)
        self.assertTrue(w.ut_checkpoints[0].completed)
        w.sample_ut_checkpoint('UT-02')
        self.assertFalse(w.ut_checkpoints[1].completed)
        self.assertEqual(w.ut_hold_elapsed_s, 0.)
        w.start_ut_coupling('UT-02', tilt_deg=3.)
        for _ in range(4):
            sim.t += 1.
            w.step(1.)
        self.assertFalse(w.ut_checkpoints[1].completed)

    def test_full_headless_pilot_assessment_and_fault_recovery(self):
        outcomes = []
        for seed in (80, 80, 80):
            sim = Simulator('mission_3_sar_fault', seed=seed)
            w = sim.wave1
            for c in w.ut_checkpoints:
                w.start_ut_coupling(c.id, tilt_deg=1.4, distance_m=.42)
                for _ in range(300):
                    sim.t = round(sim.t + .01, 2)
                    w.step(.01)
                self.assertTrue(c.completed)
                self.assertEqual(c.sampled_at_s, sim.t)
            w.inject_thruster_fault(2, True)
            self.assertNotEqual(w.compute_sop_evaluation()['sop_cert_status'], 'Certified_Pass')
            pending = TraineeSessionRecord.from_wave1_evaluation(w, trainee_id='QA-80', trainee_name='羅薇')
            self.assertNotEqual(pending.cert_status, 'Certified_Pass')
            self.assertFalse(pending.t3_fault_survived)
            # A started RTH timer must not count as completed RTH.
            w.trigger_emergency_return(True)
            sim.vehicle.s.pos[:] = sim.scenario.start_pos
            for _ in range(2):
                sim.t += 1.
                w.step(1.)
            self.assertFalse(w.emergency_return_completed)
            self.assertNotEqual(w.compute_sop_evaluation()['sop_cert_status'], 'Certified_Pass')
            sim.t += 1.
            w.step(1.)
            self.assertTrue(w.emergency_return_completed)
            result = w.compute_sop_evaluation()
            self.assertEqual(result['sop_cert_status'], 'Certified_Pass')
            record = TraineeSessionRecord.from_wave1_evaluation(w, trainee_id='QA-80', trainee_name='羅薇')
            self.assertEqual(record.cert_status, 'Certified_Pass')
            self.assertTrue(record.t3_fault_survived)
            self.assertTrue(verify_certificate_signature(record))
            outcomes.append((result['total_score'], [c.sampled_at_s for c in w.ut_checkpoints]))
        self.assertEqual(outcomes, [outcomes[0]] * 3)

    def test_roster_preserves_pending_guard_and_85_point_threshold(self):
        sim = Simulator('mission_2_hull_ut', seed=80)
        w = sim.wave1
        for c in w.ut_checkpoints:
            c.completed = True
        w.tether_snag_simulated = True
        rec = TraineeSessionRecord.from_wave1_evaluation(w, trainee_id='QA-80', trainee_name='羅薇')
        self.assertNotEqual(rec.cert_status, 'Certified_Pass')
        for score in (80., 84., 85.):
            rec = TraineeSessionRecord(trainee_id='QA-80', trainee_name='羅薇', total_score=score,
                                      hull_integrity_pct=100., ut_checkpoints_completed=4,
                                      cert_status='Certified_Pass')
            self.assertEqual(rec.cert_status == 'Certified_Pass', score >= 85.)


if __name__ == '__main__':
    unittest.main()
