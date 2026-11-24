"""Chapter-1 physics turns: turbid standoff, prop suction, sonar echoes, and sign-off wrap."""
import math
import unittest

import numpy as np

from qysim import chapter1
from qysim.engine import Simulator
from qysim.scenarios import LIBRARY, build
from qysim.tether import Tether
from qysim.tether_snag import snag_hold


def fly_to(sim, target, seconds, yaw=None, speed=0.35, until=None):
    """Crude pilot on physical RC sticks (same helper style as test_cold_open)."""
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
    """Hold the surge stick with depth hold on; True once ``until()`` holds."""
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


def rebuild_tether_at(sim, pos):
    """Move the vehicle and rebuild the tether from the spool to ``pos`` (start_point pattern)."""
    pos = np.asarray(pos, float)
    sim.vehicle.s.pos[:] = pos
    sim.vehicle.s.vel[:] = 0.0
    old = sim.tether
    sim.tether = Tether(sim.world, old.spool, pos, old.length, old.p, gland_body=old.gland_body)
    sim.tether.settle(2.0, sim.vehicle.s.pos, sim.vehicle.s.q)


class Chapter1CatalogueTests(unittest.TestCase):
    def test_variant_keys_build(self):
        keys = (
            "harbor_inspection_turbid",
            "hull_inspection_berth",
            "sonar_search_echoes",
            "harbor_inspection_signoff",
        )
        for key in keys:
            self.assertIn(key, LIBRARY)
            sc = build(key, 42)
            self.assertEqual(sc.key, key)
            self.assertGreater(len(sc.obstacles), 0)


class TurbidStandoffTests(unittest.TestCase):
    """C1-1: 0.7×visibility standoff at pile A without contact; ramming contacts."""

    def test_low_vis_standoff_no_contact(self):
        sim = Simulator("harbor_inspection_turbid", seed=42)
        self.assertEqual(sim.scenario.visibility_m, chapter1.TURBID_VIS_M)
        self.assertEqual(tuple(sim.scenario.start_pos), chapter1.TURBID_START)
        before = len(sim.world.events)
        fly_to(sim, chapter1.TURBID_APPROACH[:2], 20.0, speed=0.35)
        clearance = chapter1.pile_a_surface_distance(sim.vehicle.s.pos)
        self.assertGreater(clearance, chapter1.TURBID_STANDOFF_M * 0.75)
        self.assertLess(clearance, chapter1.TURBID_STANDOFF_M * 1.4)
        sticks(sim, 3.0)
        contacts = [e for e in sim.world.events[before:] if e.obstacle.startswith(chapter1.PILE_A_NAME)]
        self.assertEqual(contacts, [])

    def test_ramming_pile_contacts(self):
        sim = Simulator("harbor_inspection_turbid", seed=42)
        before = len(sim.world.events)

        def hit():
            return any(e.obstacle.startswith(chapter1.PILE_A_NAME) for e in sim.world.events[before:])

        self.assertTrue(fly_to(sim, chapter1.PILE_A_CENTER, 20.0, speed=0.6, until=hit))
        self.assertTrue(hit())


class BerthSuctionTests(unittest.TestCase):
    """C1-2: provisional prop suction current; LOTO hazard zone is the propeller obstacles."""

    def test_prop_approach_drifts_toward_hub(self):
        sim = Simulator("hull_inspection_berth", seed=42)
        self.assertEqual(sim.scenario.visibility_m, chapter1.BERTH_VIS_M)
        self.assertAlmostEqual(sim.scenario.current.mid_kn, chapter1.SUCTION_CURRENT_KN[1])
        self.assertEqual(sim.scenario.current.mid_dir, chapter1.SUCTION_CURRENT_DIR[1])
        rebuild_tether_at(sim, chapter1.PROP_APPROACH_SAMPLE)
        start = sim.vehicle.s.pos.copy()
        sticks(sim, 18.0)
        self.assertGreater(sim.vehicle.s.pos[0] - start[0], 0.4,
                           "northward mid/bottom current pushes the vehicle toward the prop")

    def test_propeller_obstacles_mark_the_loto_zone(self):
        sc = build("hull_inspection_berth", 42)
        props = [o for o in sc.obstacles if getattr(o, "kind", None) == "propeller"]
        self.assertGreaterEqual(len(props), 1)
        hubs = [o for o in props if "hub" in o.name]
        self.assertEqual(len(hubs), 1)
        self.assertEqual(hubs[0].name, chapter1.PROP_HUB_NAME)
        mid = 0.5 * (np.asarray(hubs[0].p0, float) + np.asarray(hubs[0].p1, float))
        self.assertLess(float(np.linalg.norm(mid - np.asarray(chapter1.PROP_HUB))), 0.2)


class SonarEchoesTests(unittest.TestCase):
    """C1-3: three solid returns; only the instrument is the objective checkpoint."""

    def test_three_echoes_one_objective(self):
        sc = build("sonar_search_echoes", 42)
        names = [o.name for o in sc.obstacles]
        self.assertEqual(len(sc.obstacles), 3)
        self.assertIn(chapter1.INSTRUMENT_NAME, names)
        self.assertIn(chapter1.STRINGS["rock_west"], names)
        self.assertIn(chapter1.STRINGS["rock_east"], names)
        self.assertEqual(len(sc.objectives), 1)
        goal = sc.objectives[0]
        self.assertEqual(goal.target, chapter1.INSTRUMENT_NAME)
        self.assertEqual(tuple(goal.point), chapter1.INSTRUMENT_CHECKPOINT)
        rock_centres = [o.center for o in sc.obstacles if o.name != chapter1.INSTRUMENT_NAME]
        for centre in rock_centres:
            self.assertGreater(math.dist(centre, goal.point), goal.radius)

    def test_flying_to_instrument_reaches_checkpoint(self):
        sim = Simulator("sonar_search_echoes", seed=42)
        goal = sim.scenario.objectives[0]
        self.assertFalse(goal.done)
        rebuild_tether_at(sim, goal.point)
        sticks(sim, 2.0)
        self.assertTrue(goal.done)
        rock = next(o for o in sim.scenario.obstacles if o.name == chapter1.STRINGS["rock_west"])
        self.assertGreater(math.dist(rock.center, goal.point), goal.radius)


class SignoffWrapTests(unittest.TestCase):
    """C1-4: rushed B3→quay path wraps or snags; A3 is marked snaggable."""

    def test_a3_is_snaggable(self):
        sc = build("harbor_inspection_signoff", 42)
        self.assertEqual(sc.visibility_m, chapter1.SIGNOFF_VIS_M)
        names = {o.name: o for o in sc.obstacles}
        self.assertEqual(snag_hold(names[chapter1.SNAG_PILE]), chapter1.SNAG_HOLD)
        self.assertEqual(tuple(sc.spool_pos), chapter1.SIGNOFF_SPOOL)
        self.assertEqual(sc.tether_length, chapter1.SIGNOFF_TETHER_LENGTH)

    def test_rushed_b3_to_quay_wraps_or_snags(self):
        sim = Simulator("harbor_inspection_signoff", seed=42)
        rebuild_tether_at(sim, chapter1.SIGNOFF_B3)
        self.assertFalse(sim.tether.snags.hooks)
        self.assertFalse(any(abs(v) >= 0.35 for v in (sim.tether.wraps or {}).values()))

        def caught():
            if sim.tether.snags.hooks:
                return True
            return any(abs(v) >= 0.35 for v in (sim.tether.wraps or {}).values())

        self.assertTrue(
            fly_to(sim, chapter1.SIGNOFF_QUAY[:2], 25.0, speed=0.55, until=caught),
            "a rushed straight B3→quay path wraps or snags within a few seconds",
        )
        self.assertTrue(caught())


if __name__ == "__main__":
    unittest.main()
