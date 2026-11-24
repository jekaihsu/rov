"""Harbour shallows: prologue site data and a reliable slack-water drift toward pile 2."""
import math
import unittest

import numpy as np

from qysim import harbor_shallows as site
from qysim.engine import Simulator
from qysim.scenarios import LIBRARY, build


class HarborShallowsSiteTests(unittest.TestCase):
    def test_site_is_registered_and_shallow(self):
        self.assertIn('harbor_shallows', LIBRARY)
        sc = build('harbor_shallows', 42)
        self.assertEqual(sc.key, 'harbor_shallows')
        self.assertEqual(sc.seabed_depth, site.SEABED)
        self.assertGreaterEqual(sc.seabed_depth, 4.0)
        self.assertLessEqual(sc.seabed_depth, 8.0)
        self.assertEqual(sc.visibility_m, site.VISIBILITY_M)
        self.assertEqual(sc.start_pos, site.START)
        self.assertEqual(sc.spool_pos, site.SPOOL)
        self.assertEqual(sc.summary()['water_type'], 'harbour')
        piles = [o for o in sc.obstacles if getattr(o, 'kind', None) == 'pile']
        self.assertEqual(len(piles), 3)
        self.assertTrue(any(o.name == 'Harbor pile 2' for o in piles))
        self.assertTrue(any('shackle' in o.name.lower() for o in sc.obstacles))
        self.assertTrue(any('crab' in o.name.lower() for o in sc.obstacles))
        self.assertEqual(len(sc.fish_schools), len(site.FISH))

    def test_tutorial_pool_remains_available(self):
        pool = build('tutorial_pool', 1)
        self.assertEqual(pool.key, 'tutorial_pool')
        self.assertTrue(pool.enclosed)
        self.assertEqual(pool.seabed_depth, 8.0)

    def test_spool_sits_aft_so_tether_rises_behind_the_camera(self):
        # Bow faces north toward the piles; spool is south of the start so the umbilical does not cross the lens.
        self.assertLess(site.SPOOL[0], site.START[0])
        self.assertAlmostEqual(site.SPOOL[1], site.START[1])
        run = math.dist(site.SPOOL[:2], site.START[:2])
        self.assertGreater(site.TETHER_LENGTH, run + 5.0)


class HarborShallowsDriftTests(unittest.TestCase):
    def test_slack_current_drifts_unlocked_vehicle_toward_pile_2(self):
        """Hands-off with thrusters unlocked: the northward set carries the vehicle toward pile 2 within 12 s.

        This is the prologue's reliable small incident (coast / hold): learn depth hold and trim against a real
        force built only from scenario current data — no vehicle or tether model changes.
        """
        sim = Simulator('harbor_shallows', seed=42)
        rc = sim.rc_physical
        rc.rc_lock = 0
        rc.keep_depth = 0
        rc.right_ud = rc.right_wave = rc.left_ud = rc.left_lr = 1500
        start = np.array(sim.vehicle.s.pos[:2], float)
        pile = np.array(site.PILE_2[:2], float)
        start_range = float(np.linalg.norm(pile - start))
        drifted = False
        for _ in range(int(12.0 / sim.dt)):
            sim.step()
            pos = np.array(sim.vehicle.s.pos[:2], float)
            if float(np.linalg.norm(pile - pos)) < start_range - 1.0:
                drifted = True
                break
        self.assertTrue(drifted, 'vehicle should close on pile 2 under the slack-water set with sticks released')
        # Depth also changes without the hold (buoyancy / residual heave), matching the coast beat's drift cue.
        self.assertNotAlmostEqual(sim.depth, site.START[2], places=2)

    def test_depth_hold_limits_vertical_wander_while_current_still_sets(self):
        sim = Simulator('harbor_shallows', seed=42)
        rc = sim.rc_physical
        rc.rc_lock = 0
        rc.keep_depth = 1
        rc.right_ud = rc.right_wave = rc.left_ud = rc.left_lr = 1500
        depth0 = sim.depth
        for _ in range(int(8.0 / sim.dt)):
            sim.step()
        self.assertLess(abs(sim.depth - depth0), 0.25)
        # Horizontal set still moves the vehicle — hold alone is not station-keeping.
        moved = math.hypot(sim.vehicle.s.pos[0] - site.START[0], sim.vehicle.s.pos[1] - site.START[1])
        self.assertGreater(moved, 0.4)


if __name__ == '__main__':
    unittest.main()
