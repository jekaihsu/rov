"""Core simulator tests: physics, control, collisions, tether, navigation, scenarios, SDK formats."""

import math
import unittest

import numpy as np

from qysim import scenarios
from qysim.controller import FlightController
from qysim.engine import Simulator
from qysim.physics import KNOT, Vehicle, q_from_euler, q_rot
from qysim.rc import RCState, Shaping, pilot_command
from qysim.tether import GLAND_BODY, Tether
from qysim.world import Cylinder, World

DT = 0.01


def run(sim: Simulator, seconds: float) -> None:
    for _ in range(int(seconds / DT)):
        sim.step(DT)


class TestPhysics(unittest.TestCase):
    def test_top_speeds_match_datasheet(self):
        for axis, kn in ((0, 4.5), (1, 2.5)):
            v = Vehicle()
            v.s.pos[2] = 10
            e = np.zeros(6)
            e[axis] = 1
            for _ in range(3000):
                v.step(DT, v.allocate(e))
            self.assertAlmostEqual(abs(v.s.vel[axis]) / KNOT, kn, delta=0.1)

    def test_forward_thrust_is_30_kgf(self):
        self.assertAlmostEqual(Vehicle().authority[0] / 9.81, 30, delta=1.0)

    def test_self_righting(self):
        from qysim.physics import q_from_euler
        v = Vehicle()
        v.s.pos[2] = 10
        v.s.q = q_from_euler(math.radians(40), math.radians(-25), 0)
        for _ in range(1500):
            v.step(DT, np.zeros(6))
        roll, pitch, _ = v.euler
        self.assertLess(abs(math.degrees(roll)), 2)
        self.assertLess(abs(math.degrees(pitch)), 2)


    def test_floating_on_surface_drifts_with_current(self):
        # regression: the surface clamp used to add the current to the water-relative velocity
        # every step, so a surfaced ROV accelerated to ~20 kn
        v = Vehicle()
        v.current_ned = np.array([0.0, 1.5 * KNOT, 0.0])
        v.s.pos = np.array([0.0, 0.0, 0.5])
        for _ in range(6000):
            v.step(0.01, np.zeros(6))
        self.assertAlmostEqual(v.s.pos[2], 0.0, places=3)
        speed = np.linalg.norm(v.world_velocity()[:2])
        self.assertAlmostEqual(speed, 1.5 * KNOT, delta=0.05)


class TestControl(unittest.TestCase):
    def fly(self, mode, rc_kw, secs, v=None, fc=None, keep_depth=False, op="ROV_USA"):
        v = v or Vehicle()
        if v.s.pos[2] == 0:
            v.s.pos[2] = 10
        fc = fc or FlightController(v)
        rc = RCState(rc_lock=0, **rc_kw)
        for _ in range(int(secs / DT)):
            v.step(DT, fc.update(DT, pilot_command(rc, op, Shaping()), mode, False, keep_depth))
        return v, fc

    def test_a_mode_ignores_roll_and_holds_heading(self):
        v, fc = self.fly("A", {"right_lr": 2000}, 2)
        self.assertLess(abs(math.degrees(v.euler[0])), 1)
        v, fc = self.fly("A", {"left_lr": 2000}, 2)
        yaw = v.euler[2]
        v, fc = self.fly("A", {}, 3, v, fc)
        self.assertLess(abs(math.degrees(v.euler[2] - yaw)), 3)

    def test_s_mode_rolls(self):
        v, _ = self.fly("S", {"right_lr": 2000}, 1.0)
        self.assertGreater(abs(math.degrees(v.euler[0])), 30)

    def test_depth_hold(self):
        v, fc = self.fly("A", {"right_ud": 2000}, 6, keep_depth=True)
        self.assertAlmostEqual(v.s.pos[2], 10, delta=0.3)

    def test_operation_modes_map_forward_differently(self):
        usa = pilot_command(RCState(right_ud=2000), "ROV_USA", Shaping())
        jpn = pilot_command(RCState(right_ud=2000), "ROV_JPN", Shaping())
        self.assertGreater(usa["surge"], 0.9)
        self.assertEqual(jpn["surge"], 0.0)
        self.assertLess(jpn["pitch"], 0)

    def test_locked_motors_produce_no_thrust(self):
        v = Vehicle()
        fc = FlightController(v)
        cmd = pilot_command(RCState(right_ud=2000), "ROV_USA", Shaping())
        self.assertTrue(np.all(fc.update(DT, cmd, "A", True, False) == 0))


class TestCollisionAndCurrent(unittest.TestCase):
    def test_pile_impact_no_tunnelling(self):
        w = World(30)
        w.obstacles.append(Cylinder("pile", (8, 0, -2), (8, 0, 31), 0.75))
        v = Vehicle()
        v.s.pos = np.array([0.0, 0.0, 10.0])
        e = np.zeros(6)
        e[0] = 1
        t = 0.0
        for _ in range(1000):
            t += DT
            v.step(DT, v.allocate(e), w.vehicle_contact(t, v.s.pos, v.s.q, v.s.vel, v.s.omega))
            self.assertGreater(w.sdf(v.s.pos)[0], 0.1)
        self.assertEqual(w.events[0].severity, "severe")
        self.assertEqual(w.events[0].obstacle, "pile")

    def test_current_profile(self):
        w = World(30)
        w.current.surface_kn, w.current.mid_kn, w.current.bottom_kn = 2.0, 1.0, 0.5
        self.assertAlmostEqual(np.linalg.norm(w.current.mean_at(0, 30)) / KNOT, 2.0, places=3)
        self.assertAlmostEqual(np.linalg.norm(w.current.mean_at(15, 30)) / KNOT, 1.0, places=3)
        self.assertLess(np.linalg.norm(w.current.mean_at(29.9, 30)) / KNOT, 0.1)


class TestTether(unittest.TestCase):
    def test_wrap_detection(self):
        w = World(30)
        w.obstacles.append(Cylinder("P1", (6, 0, -1), (6, 0, 31), 0.8))
        R = 2.2
        pos = np.array([6 - R, 0.0, 8.0])
        q = np.array([1.0, 0, 0, 0])
        tt = Tether(w, np.zeros(3), pos + q_rot(q, GLAND_BODY), length=15)
        t = 0.0
        for _ in range(3500):
            t += DT
            a = math.pi + min(1, t / 30) * 1.5 * 2 * math.pi
            new = np.array([6 + R * math.cos(a), R * math.sin(a), 8.0])
            vel = (new - pos) / DT
            pos = new
            tt.step(DT, t, pos, q, vel)
        self.assertAlmostEqual(abs(tt.wraps.get("P1", 0)), 1.5, delta=0.2)
        self.assertIn("P1", tt.snag_names)
        self.assertFalse(tt.broken)

    def test_break_on_overload(self):
        w = World(30)
        q = np.array([1.0, 0, 0, 0])
        pos = np.array([2.0, 0.0, 5.0])
        tt = Tether(w, np.zeros(3), pos, length=6)
        tt.auto_payout = False
        for i in range(200):
            pos = pos + np.array([0.2, 0, 0])      # yank at 20 m/s
            tt.step(DT, i * DT, pos, q, np.array([20.0, 0, 0]))
        self.assertTrue(tt.broken)


class TestNavigation(unittest.TestCase):
    def unlocked(self, key="open_water"):
        sim = Simulator(key, seed=1)
        sim.world.current.surface_kn = sim.world.current.mid_kn = sim.world.current.bottom_kn = 0
        sim.world.current.turbulence = 0
        sim.sdk_call("QYRovControllerManage", "set_remote_control_status", ["ON"], {})
        sim.sdk_call("QYRovControllerManage", "set_rc_lock_button", [0], {})
        return sim

    def test_h_navi_reaches_target(self):
        sim = self.unlocked()
        nav = "QYRovNavigationManage"
        self.assertEqual(sim.sdk_call(nav, "get_navigation_status", [], {})["status_code"], "201")
        sim.sdk_call(nav, "init_dr", [24.35, 120.45], {})
        lat, lng = sim.geo.to_geo(sim.vehicle.s.pos[0] + 12, sim.vehicle.s.pos[1] + 6)
        sim.sdk_call(nav, "set_h_navi_settings", [], {"speed": 0.8})
        r = sim.sdk_call(nav, "start_h_navi", ["DVL", lat, lng, 8.0], {})
        self.assertEqual(r["status"], "ok")
        run(sim, 60)
        self.assertEqual(sim.nav.nav_status, 2)
        la, ln = sim.latlng()
        n, e = sim.geo.to_ned(la, ln)
        tn, te = sim.geo.to_ned(lat, lng)
        self.assertLess(math.hypot(n - tn, e - te), 0.5)
        self.assertAlmostEqual(sim.depth, 8.0, delta=0.35)

    def test_v_navi_completes(self):
        sim = self.unlocked()
        sim.vehicle.s.pos = np.array([0.0, 0.0, 4.0])
        r = sim.sdk_call("QYRovNavigationManage", "start_v_navi",
                         ["GENERAL", "LATERAL", "RIGHT", 4.0, 4.0, 6.0, 1.0, 1.5], {})
        self.assertEqual(r["status"], "ok")
        run(sim, 120)
        self.assertEqual(sim.nav.nav_status, 2)

    def test_vccm_prechecks(self):
        sim = Simulator("open_water", seed=1)
        v = "QYRovVCCMManage"
        self.assertEqual(sim.sdk_call(v, "connect_vccm", [], {})["text"], "ROV locked")
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.left_switch = 1
        self.assertEqual(sim.sdk_call(v, "connect_vccm", [], {})["text"], "Mode not A")
        sim.rc_physical.left_switch = 0
        self.assertEqual(sim.sdk_call(v, "connect_vccm", [], {})["status"], "ok")
        self.assertEqual(sim.sdk_call(v, "start_vccm", [], {})["status"], "ok")
        self.assertEqual(sim.sdk_call(v, "get_vccm_status", [], {})["vccm_status"], "running")


class TestScenarios(unittest.TestCase):
    def test_all_scenarios_valid_and_stable(self):
        for key in list(scenarios.LIBRARY) + ["random"]:
            for seed in (1, 2, 3):
                sim = Simulator(key, seed=seed)
                w = sim.world
                self.assertGreater(w.sdf(sim.vehicle.s.pos)[0], 0.4, f"{key}: start inside obstacle")
                for ob in sim.scenario.objectives:
                    if ob.kind in ("checkpoint", "inspect", "station_keep", "surface"):
                        self.assertGreater(w.sdf(np.asarray(ob.point, float))[0], 0.3, f"{key}: {ob.label} inside obstacle")
                sim.rc_physical.rc_lock = 0
                run(sim, 3)
                self.assertTrue(np.all(np.isfinite(sim.vehicle.s.pos)), key)
                if key != "random":
                    break

    def test_random_is_reproducible(self):
        a, b = scenarios.build("random", 42), scenarios.build("random", 42)
        self.assertEqual(a.summary(), b.summary())
        self.assertEqual([o.as_dict() for o in a.obstacles], [o.as_dict() for o in b.obstacles])

    def test_checkpoint_scoring_and_penalty(self):
        sim = Simulator("open_water", seed=1)
        ob = sim.scenario.objectives[0]
        ob.point = tuple(sim.vehicle.s.pos)          # move the checkpoint, not the vehicle
        run(sim, 0.1)
        self.assertTrue(ob.done)
        self.assertGreater(sim.scorer.score, 0)
        from qysim.world import ContactEvent
        before = sim.scorer.score
        sim.world.events.append(ContactEvent(sim.t, "x", 1.0, "severe", "front"))
        run(sim, 0.05)
        self.assertEqual(sum(p["points"] for p in sim.scorer.penalties), 30, sim.scorer.penalties)
        self.assertEqual(sim.scorer.score, max(0, before - 30))

    def test_untangle_scenario_starts_wrapped(self):
        sim = Simulator("tether_untangle")
        run(sim, 1)
        self.assertGreater(abs(sim.tether.wraps.get("Pile P1", 0)), 0.75)


class TestSdkFormats(unittest.TestCase):
    def test_status_shape(self):
        st = Simulator("open_water").sdk_status()
        for k in ("Battery", "Temp", "Depth", "Compass", "Rov_Attitude_Angle", "RC_Switch_Status",
                  "Sonar_Application_Status", "Distance", "Altitude", "Accessories_Status", "A50DVL",
                  "QDVL", "MicroDVL", "QCamDVL", "rov_type"):
            self.assertIn(k, st)
        self.assertEqual(set(st["RC_Switch_Status"]), {"RC_Lock", "Depth_Keeping", "Record", "Photo",
                                                       "Rov_Ctrl_Limit", "Rov_Operation_Mode", "Rov_Ctrl_Mode", "LED"})
        self.assertRegex(st["Battery"], r"Left: \d+, Right: \d+")

    def test_remote_control_overrides_physical_rc(self):
        sim = Simulator("open_water")
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000
        sim.sdk_call("QYRovControllerManage", "set_remote_control_status", ["ON"], {})
        run(sim, 2)
        # SDK took over with sticks centred: no forward drive (only drift in the 0.3 kn current)
        self.assertLess(abs(sim.vehicle.s.vel[0]), 0.3)
        sim.sdk_call("QYRovControllerManage", "set_remote_control_status", ["OFF"], {})
        run(sim, 3)
        self.assertGreater(sim.vehicle.s.vel[0], 1.0)

    def test_severe_impact_fails_self_test_motor(self):
        sim = Simulator("monopile_current")
        from qysim.world import ContactEvent
        sim.world.events.append(ContactEvent(0.0, "Monopile M1", 1.5, "severe", "front-stbd"))
        sim._damage(0)
        data = sim.sdk_call("QYRovCheckManage", "ego_self_test", [], {})["text"]
        self.assertEqual(data["motor_right_front"], 0)


class TestWreck(unittest.TestCase):
    """Korean Castle: the distance-field wreck collides with the hull and the tether."""

    def test_field_matches_model_frame(self):
        sc = scenarios.build("korean_castle")
        wreck = sc.obstacles[0]
        self.assertAlmostEqual(float(np.linalg.det(wreck.R)), 1.0, places=6)     # no mirroring
        # just outside the port side of the mid hull the surface is close, far off it is not
        # (the mid-body plating is at local Y = -9.3 here)
        d_near, n_near = wreck.sdf(wreck.world_point((75.0, -9.6, 6.0)))
        d_far, _ = wreck.sdf(wreck.world_point((75.0, -40.0, 6.0)))
        self.assertLess(d_near, 0.5)
        self.assertGreater(d_far, 20.0)
        # the normal points away from the hull (towards local -Y)
        away = wreck.world_point((75.0, -10.6, 6.0)) - wreck.world_point((75.0, -9.6, 6.0))
        self.assertGreater(float(np.dot(n_near, away)), 0.5)

    def test_rov_hits_the_hull(self):
        sim = Simulator("korean_castle", seed=1)
        wreck = sim.world.obstacles[0]
        cur = sim.world.current
        cur.surface_kn = cur.mid_kn = cur.bottom_kn = cur.turbulence = 0.0
        start = wreck.world_point((75.0, -18.0, 6.0))
        sim.vehicle.s.pos = start.copy()
        into = wreck.world_point((75.0, 0.0, 6.0)) - start
        sim.vehicle.s.q = q_from_euler(0.0, 0.0, math.atan2(into[1], into[0]))
        sim.controller.reset_holds()                         # hold the new heading, not the scenario's
        sim.tether.layout([sim.scenario.spool_pos, start])
        sim.tether.length = 80.0                             # plenty of slack: only the hull stops it
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000                      # full ahead into the hull
        for _ in range(1500):
            sim.step(0.01)
        names = {e.obstacle for e in sim.world.events}
        self.assertIn("Korean Castle", names)
        d, _ = wreck.sdf(sim.vehicle.s.pos)
        self.assertGreater(d, -0.05)                         # stopped at the plating, not inside it

    def test_route_is_clear_of_the_wreck(self):
        sim = Simulator("korean_castle", seed=1)
        wreck = sim.world.obstacles[0]
        for p in scenarios.korean_castle_route():
            self.assertGreater(wreck.sdf(np.asarray(p))[0], 5.0)


if __name__ == "__main__":
    unittest.main()
