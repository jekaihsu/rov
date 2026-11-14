"""Campaign triggers, authority, persistence and real-input onboarding regression."""
import json
import unittest
from qysim.campaign import Campaign, DATA, condition_matches, validate
from qysim.engine import Simulator
from qysim.room import Room


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(Simulator('open_water', 42))
        self.host = self.room.join(now=0)
        self.campaign = self.room.campaign

    def command(self, action, **kwargs):
        return self.campaign.command(dict(action=action, **kwargs), self.host)

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
