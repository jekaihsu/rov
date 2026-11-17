"""Cold open: its jacket site, its prelude campaign entry, and a real snag-and-release with a scripted pilot."""
import math
import unittest

import numpy as np

from qysim import cold_open
from qysim.campaign import Campaign
from qysim.engine import Simulator
from qysim.room import Room
from qysim.scenarios import LIBRARY, build
from qysim.tether_snag import snag_hold


def fly_to(sim, target, seconds, yaw=None, speed=0.35):
    """Crude pilot: point at (or hold `yaw` while sliding to) a horizontal target with the depth hold on.

    It drives the physical RC sticks (ROV_USA: right stick surge, wheels heave and sway, left stick yaw), the same
    channels a player uses, so the vehicle, tether and snag models run exactly as in a dive."""
    rc = sim.rc_physical
    rc.rc_lock = 0
    rc.keep_depth = 1
    for _ in range(int(seconds / sim.dt)):
        pos = sim.vehicle.s.pos
        delta = np.asarray(target, float) - pos[:2]
        distance = float(np.linalg.norm(delta))
        heading = sim.yaw
        want = math.atan2(delta[1], delta[0]) if yaw is None else yaw
        turn = (want - heading + math.pi) % (2 * math.pi) - math.pi
        c, s = math.cos(heading), math.sin(heading)
        body = np.array([c * delta[0] + s * delta[1], -s * delta[0] + c * delta[1]])
        gain = min(1.0, distance / 2.0) * speed / max(distance, 1e-6) if distance > 0.3 else 0.0
        rc.right_ud = int(1500 + 500 * np.clip(body[0] * gain, -1, 1))
        rc.right_wave = int(1500 + 500 * np.clip(body[1] * gain, -1, 1))
        rc.left_lr = int(1500 + 500 * np.clip(turn * 0.8, -0.6, 0.6))
        sim.step()


class ColdOpenSiteTests(unittest.TestCase):
    def test_site_is_an_ordinary_scenario(self):
        self.assertIn('cold_open_jacket', LIBRARY)
        sc = build('cold_open_jacket', 42)
        names = {o.name: o for o in sc.obstacles}
        for name in cold_open.SNAG_NAMES:
            self.assertEqual(snag_hold(names[name]), cold_open.SNAG_HOLD, name)
        self.assertIsNotNone(snag_hold(names[cold_open.SNAG_ANODE + ' strap 1']))
        # Only the chosen fittings are snaggable; the rest of the jacket keeps the usual behaviour.
        other = [o.name for o in sc.obstacles if snag_hold(o) and o.kind not in ('mudmat',)]
        self.assertEqual(sorted(other), sorted(list(cold_open.SNAG_NAMES)
                                               + [cold_open.SNAG_ANODE + f' strap {k}' for k in (1, 2)]))
        self.assertEqual([o.kind for o in sc.objectives], ['inspect', 'inspect', 'surface'])
        self.assertEqual(sc.summary()['water_type'], 'oceanic')

    def test_fish_schools_are_placed_round_the_legs(self):
        sim = Simulator('cold_open_jacket', seed=42)
        schools = sim.world.fish_schools
        self.assertEqual(len(schools), len(cold_open.FISH))
        for school, spec in zip(schools, cold_open.FISH):
            self.assertEqual(school['home'].tolist(), list(spec['home']))
            self.assertEqual(school['count'], spec['count'])
            self.assertAlmostEqual(float(np.linalg.norm(school['pos'][:2] - school['home'][:2])), 5.0, places=6)

    def test_other_sites_keep_their_random_schools(self):
        a = Simulator('jacket_inspection', seed=7).world.fish_schools
        b = Simulator('jacket_inspection', seed=7).world.fish_schools
        self.assertEqual(len(a), 4)
        self.assertEqual([s['home'].tolist() for s in a], [s['home'].tolist() for s in b])


class ColdOpenCampaignTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(Simulator('open_water', 42))
        self.host = self.room.join(now=0)
        self.campaign = self.room.campaign

    def command(self, action, **kwargs):
        return self.campaign.command(dict(action=action, **kwargs), self.host)

    def test_prelude_is_listed_first_and_never_auto_started(self):
        state = self.campaign.state()
        self.assertEqual(state['chapters'][0]['id'], 'cold_open')
        self.assertEqual(state['chapters'][0]['category'], 'prelude')
        self.assertEqual(state['next_story'], 'prologue')
        self.assertEqual(self.campaign.next_story_chapter([]), 'prologue')

    def test_start_loads_the_site_and_waits_for_the_photo(self):
        self.assertTrue(self.command('campaign_start', chapter='cold_open')['ok'])
        self.assertEqual(self.room.primary.scenario.key, 'cold_open_jacket')
        self.assertEqual(self.campaign.node['id'], 'photo')
        self.assertEqual(self.campaign.objective, '拍下 C 腿 12 m 陽極')
        # Skipping it does not complete the story's prologue.
        self.command('campaign_skip')
        self.assertNotIn('prologue', self.campaign.completed)


class ColdOpenSnagTests(unittest.TestCase):
    def test_leaving_east_snags_on_leg_c_and_backing_out_releases(self):
        """The incident is the real snag model: the tether hooks on leg C's anode and lets go when backed out."""
        sim = Simulator('cold_open_jacket', seed=42)
        sc = sim.scenario
        anode_spot = sc.objectives[0].point[:2]
        leg_b_spot = sc.objectives[1].point[:2]
        fly_to(sim, anode_spot, 16.0, yaw=math.radians(45))
        self.assertFalse(sim.tether.snags.hooks)
        # Straight for leg B, as a new pilot would: the tether drags round leg C and hooks on its anode.
        fly_to(sim, leg_b_spot, 30.0)
        names = [h.name for h in sim.tether.snags.hooks]
        self.assertIn(cold_open.SNAG_ANODE, names)
        self.assertGreater(sim.tether.tension_rov, 25.0, 'pulling against the snag loads the tether')
        self.assertLess(sim.vehicle.s.pos[0], 0.0, 'the snag stops the vehicle well short of leg B')
        # Back out the way it came: past the anode, towards where it started.
        fly_to(sim, anode_spot, 30.0)
        fly_to(sim, cold_open.START[:2], 10.0)
        kinds = [e['type'] for e in sim.tether.state()['events']]
        self.assertIn('tether_snag_released', kinds)
        self.assertFalse(sim.tether.snags.hooks)
        self.assertFalse(sim.tether.broken)


if __name__ == '__main__':
    unittest.main()
