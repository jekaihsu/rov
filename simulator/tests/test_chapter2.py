"""Chapter 2 turning points: lee-side net snag, stirred silt at the net floor, escape-hole schools.

Each crisis is ordinary scenario data (qysim/chapter2.py). Tests drive the physical RC sticks so the
vehicle, tether and silt models run exactly as in a dive — same pattern as test_cold_open.py.
"""
import math
import unittest

import numpy as np

from qysim import chapter2 as c2
from qysim.engine import Simulator
from qysim.scenarios import LIBRARY, build


def fly_to(sim, target, seconds, yaw=None, speed=0.35, until=None):
    """Point at (or hold yaw while sliding to) a horizontal target with depth hold on."""
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
        cos_h, sin_h = math.cos(heading), math.sin(heading)
        body = np.array([cos_h * delta[0] + sin_h * delta[1], -sin_h * delta[0] + cos_h * delta[1]])
        gain = min(1.0, distance / 2.0) * speed / max(distance, 1e-6) if distance > 0.3 else 0.0
        rc.right_ud = int(1500 + 500 * np.clip(body[0] * gain, -1, 1))
        rc.right_wave = int(1500 + 500 * np.clip(body[1] * gain, -1, 1))
        rc.left_lr = int(1500 + 500 * np.clip(turn * 0.8, -0.6, 0.6))
        sim.step()
        if until is not None and until():
            return True
    return False


def sticks(sim, seconds, surge=0.0, until=None):
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


class Chapter2SiteTests(unittest.TestCase):
    def test_variants_are_registered(self):
        for key in ("aquaculture_pen_slack", "aquaculture_pen_inside", "aquaculture_pen_escape"):
            self.assertIn(key, LIBRARY)
            sc = build(key, 1)
            aqua = sc.summary()["aquaculture"]
            self.assertIn("chapter2", aqua)
            self.assertEqual(aqua["chapter2"]["mission"], {
                "aquaculture_pen_slack": "net_inspection",
                "aquaculture_pen_inside": "mort_recovery",
                "aquaculture_pen_escape": "escape",
            }[key])

    def test_billow_zone_is_the_lee_east_arc(self):
        # Current toward east (90°): lee face is +E. Clock 3 is due east of the pen centre.
        self.assertTrue(c2.in_billow_zone([24.0, 20.0, 7.0]))
        self.assertAlmostEqual(c2.clock_on_pen([24.0, 18.0, 7.0]), 3.0, delta=0.2)
        self.assertFalse(c2.in_billow_zone([6.0, 0.0, 7.0]))  # west / hole side
        self.assertFalse(c2.in_billow_zone([42.0, 0.0, 7.0]))  # north


class Chapter2NetSnagTests(unittest.TestCase):
    """C2-1: flying the outer inspection arc with the lee current hooks the tether on the net."""

    def test_outer_lap_hooks_a_pen_net(self):
        sim = Simulator("aquaculture_pen_slack", seed=3)
        sticks(sim, 1.0)
        held = {"since": None}

        def caught():
            if not sim.tether.snags.hooks:
                held["since"] = None
                return False
            if held["since"] is None:
                held["since"] = sim.t
            return sim.t - held["since"] >= 0.6

        # South outer, then along the lee (east) face — the billow band.
        fly_to(sim, (24.0, -21.0), 30.0, speed=0.45)
        self.assertTrue(
            fly_to(sim, c2.LEE_SNAG_TARGET[:2], 55.0, yaw=math.radians(c2.LEE_SNAG_YAW_DEG),
                   speed=0.45, until=caught),
            "the tether hooks on a pen net before the east-face transit finishes",
        )
        names = [hook.name for hook in sim.tether.snags.hooks]
        self.assertTrue(any(name.startswith("pen-net-") or name.startswith("pen-sinker")
                            or name.startswith("pen-mooring") for name in names), names)
        # Hands off: the hook holds (same expectation as the cold open).
        hook = sim.tether.snags.hooks[0]
        self.assertFalse(sticks(sim, 8.0, until=lambda: not sim.tether.snags.hooks))
        self.assertIs(sim.tether.snags.hooks[0], hook)


class Chapter2SiltTests(unittest.TestCase):
    """C2-2: take-off thrust near the morts silts out the onboard camera (incident_silt pattern)."""

    def fly(self, channel, value, seconds):
        sim = Simulator("aquaculture_pen_inside", seed=1)
        sim.rc_physical.rc_lock = 0
        bed = sim.world.seabed_depth
        sim.vehicle.s.pos[:] = [13.0, -3.0, bed - 0.45]
        sim.vehicle.s.vel[:] = 0
        setattr(sim.rc_physical, channel, value)
        worst = sim.camera_turbidity()["visibility_m"]
        for _ in range(int(seconds / 0.01)):
            sim.step(0.01)
            worst = min(worst, sim.camera_turbidity()["visibility_m"])
        return sim, worst

    def test_inside_variant_is_a_fluff_net_floor(self):
        sim = Simulator("aquaculture_pen_inside", seed=1)
        self.assertEqual(sim.world.seabed_depth, c2.INSIDE_SEABED)
        self.assertEqual(sim.world.silt_field.seabed_type, "fluff")
        self.assertFalse(any(str(o.name).startswith("pen-floor-") for o in sim.scenario.obstacles))

    def test_take_off_thrust_near_morts_silts_out(self):
        sim, idle = self.fly("left_wave", 1500, 1.0)
        self.assertGreater(idle, 1.5)
        sim, worst = self.fly("left_wave", 1900, 1.0)
        self.assertLess(worst, 1.5)
        self.assertGreater(sim.world.silt_field.emitted, 0.01)


class Chapter2EscapeTests(unittest.TestCase):
    """C2-3: escape hole metadata and school soft bounds toward the priority tear."""

    def test_escape_hole_and_window(self):
        sim = Simulator("aquaculture_pen_escape", seed=1)
        aqua = sim.scenario.summary()["aquaculture"]
        self.assertTrue(aqua["escape"]["priority"])
        self.assertEqual(aqua["escape"]["window_s"], c2.ESCAPE_WINDOW_S)
        self.assertIsNotNone(sim.world.escape_hole)
        self.assertAlmostEqual(sim.world.escape_hole[0], aqua["escape"]["truth"]["pos"][0], places=4)

    def test_schools_are_drawn_toward_the_hole(self):
        sim = Simulator("aquaculture_pen_escape", seed=1)
        hole = np.asarray(sim.world.escape_hole, float)
        pens = [school for school in sim.world.fish_schools if school.get("pen")]
        self.assertGreaterEqual(len(pens), 4)
        before = [float(np.linalg.norm(school["pos"][:2] - hole[:2])) for school in pens]
        for _ in range(800):
            sim.step(0.01)
        after = [float(np.linalg.norm(school["pos"][:2] - hole[:2])) for school in pens]
        # Soft attractor: at least half the pen schools end closer to the tear than they started.
        closer = sum(1 for a, b in zip(after, before) if a < b - 0.2)
        self.assertGreaterEqual(closer, max(1, len(pens) // 2), (before, after))


if __name__ == "__main__":
    unittest.main()
