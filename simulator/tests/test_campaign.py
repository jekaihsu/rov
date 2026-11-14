"""Campaign triggers, authority, persistence and real-input onboarding regression."""
import json
import math
import unittest

import numpy as np

from qysim.campaign import Campaign, DATA, condition_matches, validate
from qysim.engine import Simulator
from qysim.operations import ensure_objects
from qysim.room import Room

STORY_CHAIN = [
    'prologue', 'harbor', 'hull', 'harbor_signoff', 'offshore', 'reef', 'wreck', 'finale',
]


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(Simulator('open_water', 42))
        self.host = self.room.join(now=0)
        self.campaign = self.room.campaign

    def command(self, action, **kwargs):
        return self.campaign.command(dict(action=action, **kwargs), self.host)

    def unlock_before(self, chapter):
        index = STORY_CHAIN.index(chapter)
        self.campaign.completed = list(STORY_CHAIN[:index])

    def start_chapter(self, chapter, model_id='x1'):
        if self.room.primary.model_id != model_id:
            self.room.select_model(self.host.vehicle_id, model_id)
        self.unlock_before(chapter)
        self.assertTrue(self.command('campaign_start', chapter=chapter)['ok'], chapter)

    def advance_dialogues(self):
        while self.campaign.node and self.campaign.node['type'] == 'dialogue':
            self.command('campaign_advance')

    def settle_passthrough(self):
        """Run until blocked on wait/dialogue or the chapter completes."""
        for _ in range(64):
            node = self.campaign.node
            if node is None or node['type'] in ('wait', 'dialogue', 'branch'):
                return
            self.campaign.update(0)

    def layout_at(self, point):
        sim = self.room.primary
        target = np.asarray(point, float)
        spool = np.asarray(sim.scenario.spool_pos, float)
        sim.tether.broken = False
        sim.tether.layout([spool, target])
        sim.vehicle.s.pos[:] = target
        sim.vehicle.s.vel[:] = 0.

    def face_point(self, point, face):
        delta = np.asarray(face, float) - np.asarray(point, float)
        yaw = math.atan2(delta[1], delta[0])
        self.room.primary.vehicle.s.q[:] = [math.cos(yaw / 2), 0., 0., math.sin(yaw / 2)]

    def complete_inspection_stations(self):
        sim = self.room.primary
        mission = sim.world.mission_run
        for target in mission.targets:
            self.layout_at(target['point'])
            if target.get('face_point') is not None:
                self.face_point(target['point'], target['face_point'])
            for _ in range(320):
                sim.t += .01
                mission.update(sim, .01)
                sim.vehicle.s.pos[:] = target['point']
                sim.vehicle.s.vel[:] = 0.
            sim._take_photo()
        self.assertEqual(mission.status, 'completed')

    def complete_scenario_objectives(self):
        sim = self.room.primary
        for objective in sim.scenario.objectives:
            self.layout_at(objective.point)
            if objective.face_point is not None:
                self.face_point(objective.point, objective.face_point)
            for _ in range(6):
                sim.scorer.update(1., sim)
                sim.vehicle.s.pos[:] = objective.point
                sim.vehicle.s.vel[:] = 0.
        sim.scorer.update(.01, sim)
        self.assertTrue(sim.scorer.finished)

    def force_hold(self, object_id):
        sim = self.room.primary
        objects = ensure_objects(sim)
        self.assertIn(object_id, objects, object_id)
        sim.operations.held = object_id
        objects[object_id]['held_by'] = sim.vehicle_id

    def force_release(self):
        self.room.primary.operations.release()

    def take_photos(self, count):
        sim = self.room.primary
        while sim.viewer_state()['photos'] < count:
            sim._take_photo()

    def run_until_complete(self, handlers, limit=80):
        visited = []
        for _ in range(limit):
            self.settle_passthrough()
            node = self.campaign.node
            if node is None:
                break
            visited.append(node['id'])
            if node['type'] == 'dialogue':
                self.command('campaign_advance')
                continue
            if node['type'] == 'branch':
                self.campaign.update(0)
                continue
            if node['type'] != 'wait':
                self.campaign.update(0)
                continue
            handler = handlers.get(node['id'])
            self.assertIsNotNone(handler, 'missing handler for ' + node['id'])
            handler()
            for _ in range(8):
                self.campaign.update(0)
                if self.campaign.node is not node:
                    break
            self.assertIsNot(self.campaign.node, node, node['id'])
        self.assertEqual(self.campaign.status, 'completed', visited)
        return visited

    def test_scripts_and_invalid_conditions(self):
        for path in DATA.glob('*.json'):
            if path.name != 'schema.json':
                validate(json.loads(path.read_text()))
        with self.assertRaises(ValueError):
            validate(dict(nodes=[dict(id='x', type='unknown')]))
        self.assertFalse(condition_matches(dict(path='missing.0', op='gt', value=0), {}))
        self.assertTrue(condition_matches(dict(path='pos.2', op='gt', value=2), dict(pos=[0, 0, 3])))

    def test_initial_scene_selection_keeps_onboarding_available(self):
        self.room.reset("harbor_inspection", 42)
        self.assertEqual(self.campaign.status, "idle")
        self.assertTrue(self.command("campaign_start")["ok"])
        self.assertEqual(self.campaign.chapter, "prologue")

    def viewer_auto_start(self, completed):
        # Mirrors the selection in viewer/story/campaign.js so both sides stay consistent.
        for entry in self.campaign.state()['chapters']:
            if entry['placeholder'] or entry.get('category', 'story') != 'story' or entry['id'] in completed:
                continue
            if not entry['requires'] or entry['requires'] in completed:
                return entry['id']
        return None

    def test_auto_start_only_picks_story_chapters_in_order(self):
        state = self.campaign.state()
        ids = [entry['id'] for entry in state['chapters']]
        story = [entry['id'] for entry in state['chapters'] if entry['category'] == 'story']
        incidents = [entry['id'] for entry in state['chapters'] if entry['category'] == 'incident']
        self.assertEqual(ids, story + incidents)
        self.assertEqual(story, STORY_CHAIN)
        self.assertTrue(all(not entry.get('placeholder') for entry in state['chapters']
                            if entry['category'] == 'story'))
        self.assertEqual(len(incidents), 5)
        self.assertTrue(all(key.startswith('incident_') for key in incidents))
        self.assertEqual(state['next_story'], 'prologue')
        self.assertEqual(self.viewer_auto_start([]), 'prologue')
        self.assertTrue(self.command('campaign_start', chapter=state['next_story'])['ok'])
        self.assertEqual(self.campaign.chapter, 'prologue')
        self.campaign.index = len(self.campaign.scripts['prologue']['nodes'])
        self.campaign.update(0)
        self.assertEqual(self.campaign.status, 'completed')
        self.assertEqual(self.campaign.state()['next_story'], 'harbor')
        self.assertEqual(self.viewer_auto_start(self.campaign.completed), 'harbor')
        self.campaign.completed = story + incidents
        self.assertIsNone(self.campaign.state()['next_story'])

    def test_incidents_stay_launchable_explicitly(self):
        self.assertTrue(self.command('campaign_start', chapter='incident_compass')['ok'])
        self.assertEqual(self.campaign.chapter, 'incident_compass')
        self.assertEqual(self.campaign.state()['next_story'], 'prologue')

    def test_chapter_metadata_is_required(self):
        script = json.loads((DATA / 'prologue.json').read_text(encoding='utf-8'))
        for key, value in (('category', None), ('category', 'drill'), ('order', None), ('order', 'first')):
            broken = dict(script)
            if value is None:
                del broken[key]
            else:
                broken[key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    validate(broken)

    def test_authority_and_reconnect(self):
        guest = self.room.join(now=0)
        result = self.campaign.command(dict(action='campaign_start'), guest)
        self.assertFalse(result['ok'])
        self.command('campaign_start')
        before = self.campaign.state()
        self.room.disconnect(self.host, self.host.generation, now=1)
        self.room.join(resume_token=self.host.token, now=2)
        self.assertEqual(before, self.campaign.state())
        self.assertEqual(self.room.state(guest)['campaign'], self.campaign.state())

    def test_save_and_lock(self):
        self.assertFalse(self.command('campaign_start', chapter='harbor')['ok'])
        self.command('campaign_start')
        self.command('campaign_skip')
        saved = self.campaign.state()
        other = Campaign(self.room)
        self.room.campaign = other
        self.assertTrue(other.command(dict(action='campaign_restore', save=saved), self.host)['ok'])
        self.assertEqual(other.completed, ['prologue'])
        self.assertTrue(other.command(dict(action='campaign_start', chapter='harbor'), self.host)['ok'])
        self.assertFalse(other.command(dict(action='campaign_start', chapter='reef'), self.host)['ok'])

    def test_checkpoint_restart(self):
        self.command('campaign_start')
        self.campaign.index = next(i for i, node in enumerate(self.campaign.scripts['prologue']['nodes'])
                                   if node['id'] == 'movement_checkpoint')
        self.campaign.update(0)
        saved = self.campaign.state()
        restored = Campaign(self.room)
        self.room.campaign = restored
        self.assertTrue(restored.command(dict(action='campaign_restore', save=saved), self.host)['ok'])
        self.assertTrue(restored.command(dict(action='campaign_start', resume=True), self.host)['ok'])
        self.assertEqual(restored.node['id'], 'depth_line')
        self.assertTrue(restored.resumed)

    def test_branch(self):
        self.command('campaign_start')
        self.campaign.scripts['prologue']['nodes'] = [
            dict(id='branch', type='branch', condition=dict(path='locked', op='eq', value=True), target='end'),
            dict(id='wrong', type='dialogue', text='wrong'), dict(id='end', type='checkpoint')]
        self.campaign.index = 0
        self.campaign.update(0)
        self.assertEqual(self.campaign.status, 'completed')

    def test_world_effects_refresh_the_shared_state(self):
        self.command('campaign_start')
        slot = len(self.room.primary.viewer_state()['operations']['objects'])
        spawned = dict(path=f'operations.objects.{slot}.id', op='eq', value='campaign-sample')
        self.campaign.scripts['prologue']['nodes'] = [
            dict(id='armed', type='wait', condition=dict(path='locked', op='eq', value=True)),
            dict(id='spawn', type='spawn', object_id='sample', label='樣品', point=[0, 0, 1]),
            dict(id='seen', type='branch', condition=spawned, target='end'),
            dict(id='stale', type='dialogue', speaker='督導', text='條件讀到舊狀態'),
            dict(id='end', type='checkpoint')]
        self.campaign.index = 0
        self.campaign.update(0)
        self.assertEqual(self.campaign.status, 'completed')

    def test_script_effects(self):
        self.command('campaign_start')
        self.campaign.scripts['prologue']['nodes'] = [
            dict(id='spawn', type='spawn', object_id='sample', label='樣品', point=[0, 0, 4]),
            dict(id='fog', type='environment', visibility_m=4),
            dict(id='remove', type='remove', object_id='sample'),
            dict(id='checkpoint', type='checkpoint'),
            dict(id='end', type='dialogue', speaker='督導', text='好了') ]
        self.campaign.index = 0
        self.campaign.update(0)
        self.assertNotIn('campaign-sample', self.room.primary.world.work_objects)
        self.assertEqual(self.room.primary.scenario.visibility_m, 4)
        self.assertEqual(self.campaign.checkpoint['index'], 4)

    def test_prologue_real_input(self):
        self.command('campaign_start')
        sim = self.room.primary
        sim.operation_mode = 'UAV_CHN'
        mapping = {'前': ('left_ud', 1800), '後': ('left_ud', 1200),
                   '右': ('left_lr', 1800), '左': ('left_lr', 1200),
                   '下': ('right_ud', 1200), '上': ('right_ud', 1800)}
        visited = []
        for _ in range(40):
            node = self.campaign.node
            if node is None:
                break
            visited.append(node['id'])
            if node['type'] == 'dialogue':
                self.command('campaign_advance')
                continue
            sim.rc_physical.centre_sticks()
            sim.rc_physical.rc_lock = 0
            if node['id'].startswith('move_'):
                channel, value = mapping[node['id'][5:]]
                setattr(sim.rc_physical, channel, value)
            elif node['id'] == 'depth':
                sim.rc_physical.keep_depth = 1
            elif node['id'] == 'light':
                sim.rc_physical.right_switch = 1
            elif node['id'] == 'photo':
                sim.rc_physical.photo = 1
            for tick in range(2000):
                self.room.step(.01)
                if self.campaign.node is not node:
                    break
            self.assertIsNot(self.campaign.node, node, node['id'])
        self.assertEqual(self.campaign.status, 'completed', visited)
        self.assertIn('first_dive', self.campaign.rewards)
        self.assertIn('prologue', self.campaign.completed)
        print('PROLOGUE REAL INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))

    def test_hull_auto_input(self):
        self.start_chapter('hull')
        sim = self.room.primary

        def depth():
            self.layout_at([18., 0., 9.5])

        def light():
            sim.rc_physical.right_switch = 1

        visited = self.run_until_complete({
            'depth': depth,
            'light': light,
            'survey': self.complete_inspection_stations,
        })
        self.assertIn('hull_badge', self.campaign.rewards)
        self.assertIn('hull', self.campaign.completed)
        print('HULL AUTO INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))

    def test_harbor_signoff_auto_input(self):
        self.start_chapter('harbor_signoff')
        sim = self.room.primary

        def extra_photo():
            self.take_photos(4)

        def surface():
            self.layout_at([0., 0., 1.])

        visited = self.run_until_complete({
            'survey': self.complete_inspection_stations,
            'extra_photo': extra_photo,
            'surface': surface,
        })
        self.assertIn('harbor_signoff_badge', self.campaign.rewards)
        self.assertIn('harbor_signoff', self.campaign.completed)
        print('HARBOR SIGNOFF AUTO INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))

    def test_offshore_auto_input(self):
        self.start_chapter('offshore')

        def dive():
            self.layout_at([10., 0., 6.])

        def survey():
            self.complete_scenario_objectives()

        def tension_check():
            self.room.primary.tether.broken = False

        visited = self.run_until_complete({
            'dive': dive,
            'survey': survey,
            'tension_check': tension_check,
        })
        self.assertIn('offshore_badge', self.campaign.rewards)
        self.assertIn('offshore', self.campaign.completed)
        print('OFFSHORE AUTO INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))

    def test_reef_auto_input(self):
        self.start_chapter('reef', model_id='falcon')
        sim = self.room.primary

        def eco_photos():
            self.take_photos(3)

        def work_depth():
            self.layout_at([16., -4., 8.])

        def grasp_sensor():
            self.force_hold('campaign-lost-sensor')

        def near_surface():
            self.layout_at([2., 0., 2.])

        def release_sensor():
            self.force_release()

        def grasp_logger():
            self.force_hold('campaign-new-logger')

        def place_depth():
            self.layout_at([18., 0., 9.])

        def release_logger():
            self.force_release()

        visited = self.run_until_complete({
            'eco_photos': eco_photos,
            'work_depth': work_depth,
            'grasp_sensor': grasp_sensor,
            'near_surface': near_surface,
            'release_sensor': release_sensor,
            'grasp_logger': grasp_logger,
            'place_depth': place_depth,
            'release_logger': release_logger,
        })
        self.assertIn('reef_badge', self.campaign.rewards)
        self.assertIn('reef', self.campaign.completed)
        self.assertTrue(sim.operations.has_arm)
        print('REEF AUTO INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))

    def test_wreck_auto_input(self):
        self.start_chapter('wreck')
        sim = self.room.primary

        def approach_depth():
            self.layout_at([10., 0., 14.])

        def light():
            sim.rc_physical.right_switch = 1

        def clue_photo():
            self.take_photos(4)

        def safe_tether():
            sim.tether.broken = False

        visited = self.run_until_complete({
            'approach_depth': approach_depth,
            'light': light,
            'survey': self.complete_inspection_stations,
            'clue_photo': clue_photo,
            'safe_tether': safe_tether,
        })
        self.assertIn('wreck_badge', self.campaign.rewards)
        self.assertIn('wreck', self.campaign.completed)
        print('WRECK AUTO INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))

    def test_finale_auto_input(self):
        self.start_chapter('finale', model_id='falcon')

        def dive():
            self.layout_at([20., 0., 18.])

        def light():
            self.room.primary.rc_physical.right_switch = 1

        def grasp_case():
            self.force_hold('campaign-evidence-case')

        def near_surface():
            self.layout_at([2., 0., 2.])

        def release_case():
            self.force_release()

        def clue_photos():
            self.take_photos(3)

        visited = self.run_until_complete({
            'dive': dive,
            'light': light,
            'grasp_case': grasp_case,
            'near_surface': near_surface,
            'release_case': release_case,
            'clue_photos': clue_photos,
        })
        self.assertIn('finale_badge', self.campaign.rewards)
        self.assertIn('finale', self.campaign.completed)
        self.assertIn('ending_full', visited)
        print('FINALE AUTO INPUT COMPLETED:', json.dumps(visited, ensure_ascii=False))
