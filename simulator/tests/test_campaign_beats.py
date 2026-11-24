"""Directed campaign timing, shutter evidence and compatibility with legacy clients."""
import unittest

from qysim.engine import Simulator
from qysim.room import Room
from qysim.campaign.beats import photo_matches


class DirectedCampaignTest(unittest.TestCase):
    def test_shutter_range_depth_and_bearing(self):
        shot = dict(name='picture.JPG', pose=dict(n=5, e=0, depth=4, yaw=358))
        self.assertTrue(photo_matches((11, 0, 4), shot))
        for plate in ((14, 0, 4), (11, 0, 7), (0, 5, 4)):
            self.assertFalse(photo_matches(plate, shot))

    def test_photo_matches_accepts_stills_without_jpg_extension(self):
        pose = dict(n=5, e=0, depth=4, yaw=358)
        self.assertTrue(photo_matches((11, 0, 4), dict(name='SING0001', pose=pose)))
        self.assertTrue(photo_matches((11, 0, 4), dict(name='still.png', pose=pose)))
        self.assertFalse(photo_matches((11, 0, 4), dict(name='clip.MP4', pose=pose, time=12)))
        self.assertFalse(photo_matches((11, 0, 4), dict(name='clip.mov', pose=pose, time=3)))

    def test_timed_advance_is_authoritative_and_idempotent(self):
        room = Room(Simulator('harbor_shallows', 42))
        host = room.join(now=0)
        campaign = room.campaign
        start = dict(action='campaign_start', chapter='prologue', beats=True)
        campaign.command(start, host)
        advance = dict(action='campaign_advance', beat='black', next='establish')
        self.assertFalse(campaign.command(advance, host)['ok'])
        room.primary.t += campaign.node['limit']
        self.assertTrue(campaign.command(advance, host)['ok'])
        self.assertFalse(campaign.command(advance, host)['ok'])
        self.assertEqual(campaign.node['id'], 'establish')
        self.assertEqual(len(campaign.state()['plates']), 3)
        campaign.command(dict(action='campaign_start'), host)
        self.assertNotIn('directed', campaign.state())
