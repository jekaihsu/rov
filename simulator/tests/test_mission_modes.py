import unittest
from qysim.engine import Simulator
from qysim.mission_modes import MissionRun, ensure_mission


class TestMissionModes(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator('open_water', seed=42)
        self.run = MissionRun(self.sim, 'inspection_coop')
        self.sim.world.mission_run = self.run

    def hold(self, sim, target, seconds=3.01):
        sim.vehicle.s.pos[:] = target['point']
        sim.vehicle.s.vel[:] = 0.
        for _ in range(round(seconds/.01)):
            sim.t += .01
            self.run.update(sim, .01)

    def test_photo_requires_own_continuous_stable_hold(self):
        target = self.run.targets[0]
        self.sim.vehicle.s.pos[:] = target['point']
        self.sim._take_photo()
        self.assertFalse(target['completed'])
        self.hold(self.sim, target, 2.)
        self.sim.vehicle.s.vel[0] = .5
        self.run.update(self.sim, .01)
        self.sim.vehicle.s.vel[:] = 0.
        self.hold(self.sim, target, 1.1)
        self.sim._take_photo()
        self.assertFalse(target['completed'])
        self.hold(self.sim, target)
        self.sim._take_photo()
        self.assertTrue(target['completed'])
        self.assertEqual(target['completed_by'], self.sim.vehicle_id)

    def test_shared_progress_and_no_double_timer_or_duplicate_completion(self):
        peer = Simulator('open_water', seed=42, vehicle_id='v2', shared_world=self.sim.world)
        self.assertIs(ensure_mission(peer), self.run)
        target = self.run.targets[0]
        self.hold(self.sim, target)
        peer.t = self.sim.t
        peer.vehicle.s.pos[:] = target['point']
        before = self.run.elapsed
        self.run.update(peer, .01)
        self.assertEqual(self.run.elapsed, before)
        peer._take_photo()
        self.assertFalse(target['completed'])
        self.sim._take_photo()
        completed_at = target['completed_at']
        self.hold(peer, target)
        peer._take_photo()
        self.assertEqual(target['completed_by'], self.sim.vehicle_id)
        self.assertEqual(target['completed_at'], completed_at)
        self.assertEqual(self.run.state(peer)['completed'], 1)

    def test_expiry_is_terminal_and_free_has_no_timer_or_penalty(self):
        self.sim.t = 721
        self.run.update(self.sim, .01)
        self.assertEqual(self.run.status, 'expired')
        self.hold(self.sim, self.run.targets[0])
        self.sim._take_photo()
        self.assertFalse(self.run.targets[0]['completed'])
        free = MissionRun(self.sim, 'free_explore')
        self.sim.t += 2000
        free.update(self.sim, 2000)
        state = free.state(self.sim)
        self.assertIsNone(state['remaining'])
        self.assertIsNone(state['score'])
        self.assertEqual(free.score_state(self.sim)['penalties'], [])

    def test_selected_mode_survives_scenario_reload_and_invalid_command_is_atomic(self):
        response = self.sim.operations.command({'action':'mission_mode', 'mode':'unknown'})
        self.assertFalse(response['ok'])
        self.assertIs(ensure_mission(self.sim), self.run)
        self.sim.load_scenario('coral_reef', 7)
        self.assertEqual(ensure_mission(self.sim).mode, 'inspection_coop')
        self.assertIsNot(ensure_mission(self.sim), self.run)
        self.assertEqual(len(ensure_mission(self.sim).targets), 3)

    def test_legacy_training_keeps_original_score(self):
        run = MissionRun(self.sim, 'scenario_training')
        self.assertEqual(run.score_state(self.sim), self.sim.scorer.as_dict())

    def test_facing_requirement_and_all_targets_complete(self):
        target = self.run.targets[0]
        target['face_point'] = [target['point'][0]-3, target['point'][1], target['point'][2]]
        self.hold(self.sim, target)
        self.assertIsNone(self.run.state(self.sim)['ready_target'])
        target['face_point'] = None
        for target in self.run.targets:
            self.hold(self.sim, target)
            self.sim._take_photo()
        state = self.run.state(self.sim)
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['score'], 100)
        elapsed = self.run.elapsed
        self.sim.t += 1000
        self.run.update(self.sim, 1000)
        self.assertEqual(self.run.elapsed, elapsed)


if __name__ == '__main__':
    unittest.main()
