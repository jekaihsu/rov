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


def fly_to(sim, target, seconds, yaw=None, speed=0.35, until=None):
    """Crude pilot: point at (or hold `yaw` while sliding to) a horizontal target with the depth hold on.

    It drives the physical RC sticks (ROV_USA: right stick surge, wheels heave and sway, left stick yaw), the same
    channels a player uses, so the vehicle, tether and snag models run exactly as in a dive. `speed` is the stick
    deflection (0.6 is the keyboard's default, 1 a pad pushed to its stop). Stops early, returning True, once
    `until()` holds."""
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
        if until is not None and until():
            return True
    return False


def sticks(sim, seconds, surge=0.0, until=None):
    """Hold the surge stick (0 = hands off) with the depth hold on; True once `until()` holds."""
    rc = sim.rc_physical
    rc.rc_lock = 0
    rc.keep_depth = 1
    rc.right_ud = int(1500 + 500 * surge)
    rc.right_wave = 1500
    rc.left_lr = 1500
    for _ in range(int(seconds / sim.dt)):
        sim.step()
        if until is not None and until():
            return True
    return False


class ColdOpenSiteTests(unittest.TestCase):
    def test_site_is_an_ordinary_scenario(self):
        self.assertIn('cold_open_jacket', LIBRARY)
        sc = build('cold_open_jacket', 42)
        names = {o.name: o for o in sc.obstacles}
        for name in cold_open.SNAG_NAMES:
            self.assertEqual(snag_hold(names[name]), cold_open.SNAG_HOLD, name)
        self.assertEqual(cold_open.SNAG_NAMES[0], cold_open.SNAG_ANODE)
        self.assertIsNotNone(snag_hold(names[cold_open.SNAG_ANODE + ' strap 1']))
        # Only leg C's anode and its straps are snaggable; the rest of the jacket keeps the usual behaviour.
        other = [o.name for o in sc.obstacles if snag_hold(o) and o.kind not in ('mudmat',)]
        self.assertEqual(sorted(other), sorted(cold_open.SNAG_NAMES))
        # The tether hand keeps the slack short: a few metres more than the straight run to the vehicle.
        run = math.dist(cold_open.SPOOL, cold_open.START)
        self.assertLess(cold_open.TETHER_LENGTH - run, 12.0)
        self.assertGreater(cold_open.TETHER_LENGTH - run, 8.0)
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
    """The incident is the real snag model, set up by where the tether runs (qysim/cold_open.py)."""

    def arrive(self, seed):
        """The opening as flown: the cinematic's hover, then up to leg C's anode for the photo."""
        sim = Simulator('cold_open_jacket', seed=seed)
        sticks(sim, 13.0)
        fly_to(sim, sim.scenario.objectives[0].point[:2], 16.0, yaw=math.radians(45))
        self.assertFalse(sim.tether.snags.hooks, 'nothing catches on the way to the photo')
        self.assertEqual(self.kinds(sim), [])
        return sim

    def kinds(self, sim):
        return [e['type'] for e in sim.tether.state()['events'] if e['type'].startswith('tether_snag')]

    def head_north(self, sim, speed):
        """Straight for leg B, as a new pilot would, until the tether has been hooked for a moment."""
        held = {'since': None}

        def caught():
            if not sim.tether.snags.hooks:
                held['since'] = None
                return False
            if held['since'] is None:
                held['since'] = sim.t
            return sim.t - held['since'] >= 0.6

        self.assertTrue(fly_to(sim, sim.scenario.objectives[1].point[:2], 25.0, speed=speed, until=caught),
                        'the tether hooks before the vehicle reaches leg B')
        self.assertEqual([h.name for h in sim.tether.snags.hooks], [cold_open.SNAG_ANODE])

    def back_out(self, sim, speed):
        """Without turning, back to the anode and on towards where the dive started; True once it is free."""
        free = lambda: not sim.tether.snags.hooks  # noqa: E731
        heading = sim.yaw
        return (fly_to(sim, sim.scenario.objectives[0].point[:2], 30.0, yaw=heading, speed=speed, until=free)
                or fly_to(sim, cold_open.START[:2], 30.0, yaw=heading, speed=speed, until=free))

    def test_leaving_north_snags_on_the_anode_holds_and_backing_out_releases(self):
        sim = self.arrive(42)
        anode_north = sim.scenario.objectives[0].face_point[0]
        self.head_north(sim, 0.35)
        hook = sim.tether.snags.hooks[0]
        caught_at = sim.vehicle.s.pos.copy()
        self.assertGreater(caught_at[0], anode_north + 1.5, 'it catches once the vehicle is past the anode')
        self.assertLess(caught_at[0], 3.0, 'and stops it well short of leg B')
        self.assertLess(abs(hook.target[2] - cold_open.ANODE_DEPTH), 1.0, 'on the anode bar itself')
        # Hands off: the snag holds. The slack-water current does not carry the vehicle round to the free side.
        self.assertFalse(sticks(sim, 25.0, until=lambda: not sim.tether.snags.hooks), 'it never frees by itself')
        self.assertIs(sim.tether.snags.hooks[0], hook)
        self.assertLess(sim.tether.tension_rov, 20.0)
        self.assertLess(float(np.linalg.norm(sim.vehicle.s.pos[:2] - caught_at[:2])), 2.5, 'held on a short leash')
        # Pulling does not free it either; it loads the tether, and a steady pull does not part it.
        self.assertFalse(sticks(sim, 8.0, surge=1.0, until=lambda: not sim.tether.snags.hooks))
        self.assertGreater(sim.tether.tension_rov, 25.0)
        self.assertFalse(sim.tether.broken)
        self.assertNotIn('tether_snag_released', self.kinds(sim))
        # Back out the way it came: the hook opens once the vehicle is back abeam of the anode, not before.
        sticks(sim, 2.0)
        self.assertTrue(self.back_out(sim, 0.35), 'backing out along the approach frees the tether')
        self.assertLess(sim.vehicle.s.pos[0], anode_north + 2.0, 'only once it is back by the anode')
        self.assertEqual(self.kinds(sim)[-1], 'tether_snag_released')
        self.assertFalse(sim.tether.broken)
        # Free for good: it does not catch again while the vehicle waits there.
        self.assertFalse(sticks(sim, 5.0, until=lambda: bool(sim.tether.snags.hooks)))

    def test_incident_is_the_same_for_other_seeds_and_a_faster_pilot(self):
        for seed, speed in ((7, 0.6), (3, 0.6)):
            with self.subTest(seed=seed, speed=speed):
                sim = self.arrive(seed)
                self.head_north(sim, speed)
                self.assertFalse(sticks(sim, 20.0, until=lambda: not sim.tether.snags.hooks),
                                 'it never frees by itself')
                self.assertTrue(self.back_out(sim, speed), 'backing out along the approach frees the tether')
                self.assertEqual(self.kinds(sim).count('tether_snag'), 1, 'one snag, caught once')
                self.assertFalse(sim.tether.broken)


if __name__ == '__main__':
    unittest.main()
