"""Play D1 via operation inputs and real admission checks, with travel pose fixtures.

Like test_expedition/test_mission_modes, this isolates script gates from flight:
no result, completion flag, campaign index or observation admission is injected.
It does not measure RC flight performance or human completion time.
"""
import json
import math
import unittest

import numpy as np

from qysim.campaign import DATA, validate
from qysim.engine import Simulator
from qysim.expedition import ensure_expedition
from qysim.physics import q_from_euler, q_rot
from qysim.room import Room

CHAPTERS = ('hull', 'harbor_signoff', 'offshore', 'reef', 'wreck', 'finale')


class CampaignChapterTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(Simulator('open_water', 42, model_id='falcon'))
        self.host = self.room.join(now=0, model_id='falcon')
        self.sim = self.room.primary
        self.campaign = self.room.campaign
        self.serial = 0

    def command(self, action, **values):
        reply = self.campaign.command(dict(action=action, **values), self.host)
        self.assertTrue(reply['ok'], reply)

    def operation(self, action, **values):
        reply = self.sim.operations.command(dict(action=action, **values))
        self.assertTrue(reply['ok'], reply)
        self.campaign.update(0)
        return reply

    def start(self, chapter):
        prerequisite = self.campaign.scripts[chapter]['requires']
        self.command('campaign_restore', save=dict(completed=[prerequisite]))
        self.command('campaign_start', chapter=chapter)

    def radio(self):
        for _ in range(40):
            if self.campaign.node is None or self.campaign.node['type'] != 'dialogue':
                return
            self.command('campaign_advance')
        self.fail('Radio loop')

    def pose(self, point, heading=0):
        self.sim.vehicle.s.pos[:] = point
        self.sim.vehicle.s.q[:] = q_from_euler(0, 0, heading)
        self.sim.vehicle.s.vel[:] = 0

    def dwell(self, update, seconds):
        for _ in range(round(seconds / .01)):
            self.sim.t += .01
            update(self.sim, .01)
        self.campaign.update(seconds)

    def inspection(self, chapter):
        self.start(chapter)
        run = self.sim.world.mission_run
        for index, target in enumerate(run.targets):
            self.radio()
            self.assertIn(self.campaign.node['id'], (f'task_{index + 1}_poll', f'task_{index + 1}_repeat'))
            heading = 0
            if target['face_point'] is not None:
                delta = np.asarray(target['face_point']) - target['point']
                heading = math.atan2(delta[1], delta[0])
            self.pose(target['point'], heading)
            self.operation('mission_photo')
            self.assertFalse(target['completed'])
            self.dwell(run.update, 3.01)
            self.operation('mission_photo')
            self.assertTrue(target['completed'])
        self.radio()
        self.assertEqual(self.campaign.status, 'completed')
        self.assertIn(chapter + '_badge', self.campaign.rewards)
        print(f'{chapter.upper()} AUTOMATIC OPERATIONS COMPLETED: 3 validated stations')

    def test_hull_to_end(self):
        self.inspection('hull')
        self.assertEqual(self.sim.scenario.visibility_m, 3)

    def test_harbor_signoff_to_end(self):
        self.inspection('harbor_signoff')
        self.assertIn('falcon', self.campaign.state()['unlocks']['vehicles'])

    def test_offshore_to_end(self):
        self.inspection('offshore')
        self.assertEqual(self.sim.scenario.key, 'jacket_inspection')

    def test_wreck_to_end(self):
        self.inspection('wreck')
        self.assertEqual(self.sim.scenario.key, 'wreck_survey')

    def observe(self, entity, position=True):
        run = ensure_expedition(self.sim)
        if position:
            _, target, _ = run._entity(self.sim, entity)
            self.pose(target - [2.2, 0, .75])
        self.serial += 1
        camera = self.sim.vehicle.s.pos + q_rot(
            self.sim.vehicle.s.q, np.asarray(self.sim.vehicle.definition.camera_body))
        reply = self.operation(
            'observation_photo', photo_id=f'photo-{self.serial}', entity_id=entity,
            view='onboard', visible=True, coverage=.03,
            camera=dict(pos=camera.tolist(), q=self.sim.vehicle.s.q.tolist(), fov=70, aspect=1.6))
        self.assertTrue(reply['observation']['accepted'], reply)

    def contract(self, kind):
        self.serial += 1
        self.operation('expedition_start', contract=kind, request_id=f'contract-{self.serial}')
        return ensure_expedition(self.sim).active

    def engineering(self, kind):
        run = ensure_expedition(self.sim)
        task = self.contract(kind)
        object_id = task['target_object_id']
        if kind == 'recover':
            self.observe(object_id)
        self.pose(task['pickup_approach'])
        self.operation('arm', joints=task['suggested_joints'], grip=1)
        for _ in range(300):
            self.sim.operations.step(.01)
        self.operation('arm', grip=0)
        for _ in range(110):
            self.sim.operations.step(.01)
        self.assertEqual(self.sim.operations.held, object_id)
        self.pose(task['delivery_approach'])
        self.sim.operations.step(.01)
        self.operation('arm', grip=1)
        for _ in range(110):
            self.sim.operations.step(.01)
        self.assertIsNone(self.sim.operations.held)
        self.dwell(run.update, 2.01)
        if kind == 'deploy':
            self.assertIsNotNone(run.active, 'Deployment requires an after-placement photograph')
            self.observe(object_id)
        self.assertIsNone(run.active)
        self.assertEqual(run.results[-1]['kind'], kind)

    def test_reef_to_end(self):
        self.start('reef')
        self.radio()
        self.operation('mission_photo')
        self.assertEqual(self.campaign.node['id'], 'biology_wait')
        run = ensure_expedition(self.sim)
        for entity in self.sim.world.habitat_entities:
            try:
                _, target, radius = run._entity(self.sim, entity['id'])
            except ValueError:
                continue
            origin = target - [2.2, 0, .75]
            if self.sim.world.sdf(origin)[0] < .8:
                continue
            camera = origin + np.asarray(self.sim.vehicle.definition.camera_body)
            delta = target - camera
            distance = np.linalg.norm(delta)
            if self.sim.world.raycast(camera, delta, max_range=distance) < distance - radius - .15:
                continue
            self.observe(entity['id'])
            break
        else:
            self.fail('No real reachable biology target')
        self.radio()
        self.engineering('recover')
        self.radio()
        self.engineering('deploy')
        self.radio()
        self.assertEqual(self.campaign.status, 'completed')
        print('REEF AUTOMATIC OPERATIONS COMPLETED: biology, recovery, deployment')

    def finale_verification(self):
        self.start('finale')
        self.radio()
        self.engineering('recover')
        self.radio()
        self.engineering('deploy')
        self.radio()
        self.assertEqual(self.campaign.node['id'], 'verify_start')
        return self.contract('inspect')

    def ending(self, complete):
        self.radio()
        self.assertEqual(self.campaign.status, 'completed')
        expected = 'ending_evidence_complete' if complete else 'ending_open_question'
        other = 'ending_open_question' if complete else 'ending_evidence_complete'
        self.assertIn(expected, self.campaign.rewards)
        self.assertNotIn(other, self.campaign.rewards)

    def test_finale_complete_evidence_to_end(self):
        task = self.finale_verification()
        run = ensure_expedition(self.sim)
        for step in task['steps']:
            self.pose(step['point'])
            self.dwell(run.update, 3.01)
            self.observe(step['entity_id'], position=False)
        self.ending(True)
        print('FINALE AUTOMATIC OPERATIONS COMPLETED: complete evidence ending')

    def test_finale_late_last_photo_cannot_bypass_deadline(self):
        task = self.finale_verification()
        run = ensure_expedition(self.sim)
        for index, step in enumerate(task['steps']):
            self.pose(step['point'])
            self.dwell(run.update, 3.01)
            if index == 2:
                self.sim.t += 721
                run.update(self.sim, .01)
            self.observe(step['entity_id'], position=False)
        self.ending(False)

    def test_finale_incomplete_evidence_to_end(self):
        self.finale_verification()
        self.pose([0, 0, 1])
        self.campaign.update(.1)
        self.ending(False)

    def test_finale_deadline(self):
        self.finale_verification()
        run = ensure_expedition(self.sim)
        self.sim.t += 721
        run.update(self.sim, .01)
        self.campaign.update(.1)
        self.ending(False)

    def test_abort_never_unlocks_inspection_chapters(self):
        for chapter in ('hull', 'harbor_signoff', 'offshore', 'wreck'):
            for reason in ('expired', 'broken'):
                with self.subTest(chapter=chapter, reason=reason):
                    self.setUp()
                    self.start(chapter)
                    self.radio()
                    if reason == 'expired':
                        self.sim.t = 721
                        self.sim.world.mission_run.update(self.sim, .01)
                    else:
                        self.sim.tether.broken = True
                    self.campaign.update(.1)
                    self.radio()
                    self.assertEqual(self.campaign.node['id'], 'abort_hold')
                    self.assertNotIn(chapter, self.campaign.completed)
                    self.assertNotIn(chapter + '_badge', self.campaign.rewards)
                    self.command('campaign_start', chapter=chapter)
                    self.assertEqual(self.campaign.status, 'active')

    def test_schema_locales_and_task_counts(self):
        for chapter in CHAPTERS:
            with self.subTest(chapter=chapter):
                script = json.loads((DATA / f'{chapter}.json').read_text(encoding='utf-8'))
                validate(script)
                self.assertEqual(script['category'], 'story')
                self.assertFalse(script.get('placeholder'))
                tasks = [n for n in script['nodes'] if n['type'] == 'objective' and n['id'].startswith('task_')]
                self.assertGreaterEqual(len(tasks), 3)
                self.assertLessEqual(len(tasks), 5)
                self.assertEqual(script['nodes'][0]['type'], 'checkpoint')
                for node in script['nodes']:
                    if node['type'] in ('dialogue', 'objective', 'hint'):
                        self.assertIn(node['text_key'], script['strings']['zh-TW'])
                checkpoints = [i for i, n in enumerate(script['nodes']) if n['type'] == 'checkpoint']
                first = script['nodes'].index(tasks[0])
                last = script['nodes'].index(tasks[-1])
                self.assertFalse(any(first < i < last for i in checkpoints))


if __name__ == '__main__':
    unittest.main()
