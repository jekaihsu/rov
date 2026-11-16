"""Tether physics: reel and payout, contact and friction, axial stiffness, twist, failure, snags.

Each class covers one ranked gap in research_notes/臍帶纜物理與收放文獻/simulators_and_current_model.md.
"""
import math
import unittest

import numpy as np

from qysim import scenarios
from qysim.engine import Simulator
from qysim.physics import RHO, q_from_euler
from qysim.tether import Tether, TetherParams
from qysim.vehicles import X1_TETHER_PARAMETERS
from qysim.world import Box, Cylinder, SnagFeature, World

IDENTITY = np.array([1.0, 0.0, 0.0, 0.0])


def straight(world, start, end, length, params=None, mode="hold"):
    """Tether laid on the straight line start -> end with ``length`` of rest length."""
    tether = Tether(world, np.asarray(start, float), np.asarray(end, float), length, params or TetherParams(),
                    gland_body=np.zeros(3))
    tether.layout([np.asarray(start, float), np.asarray(end, float)])
    tether.length = length
    tether.reel_command(mode)
    return tether


def drive(tether, pos, vel, seconds, dt=0.01, t0=0.0):
    """Kinematic gland at constant velocity; returns the final gland position."""
    pos = np.asarray(pos, float)
    vel = np.asarray(vel, float)
    for i in range(int(round(seconds / dt))):
        tether.step(dt, t0 + i * dt, pos, IDENTITY, vel)
        pos = pos + vel * dt
    return pos


class PointBody:
    """A thrust-limited body standing in for the vehicle: force-coupled like engine.step."""

    def __init__(self, pos, mass=55.0, thrust=120.0, drag=40.0):
        self.pos = np.asarray(pos, float)
        self.vel = np.zeros(3)
        self.mass, self.thrust, self.drag = mass, thrust, drag

    def go(self, tether, target, speed, seconds, t0, dt=0.01):
        t = t0
        for _ in range(int(round(seconds / dt))):
            to = np.asarray(target, float) - self.pos
            dist = float(np.linalg.norm(to))
            want = to / dist * min(speed, dist) if dist > 1e-6 else np.zeros(3)
            push = np.clip(self.mass * (want - self.vel) / 0.05, -self.thrust, self.thrust)
            wrench = tether.step(dt, t, self.pos, IDENTITY, self.vel)
            self.vel = self.vel + (push + wrench[:3] - self.drag * self.vel) / self.mass * dt
            self.vel[2] = 0.0
            self.pos = self.pos + self.vel * dt
            t += dt
        return t


class TestReel(unittest.TestCase):
    """Gap 1: payout is a reel with inertia, brake and rates; length enters at the spool."""

    def test_legacy_payout_runs_at_feed_rate_and_adds_length_at_the_spool(self):
        world = World(60)
        tether = straight(world, (0, 0, 10), (9.8, 0, 10), 10.0)
        near_rov = tether.l0[-10:].copy()
        tether.payout(5.0)
        gland = np.array([9.8, 0, 10])
        drive(tether, gland, np.zeros(3), 1.0)
        self.assertLess(tether.length - 10.0, 0.6)          # not an instant +5 m
        self.assertGreater(tether.length - 10.0, 0.3)
        drive(tether, gland, np.zeros(3), 12.0, t0=1.0)
        self.assertAlmostEqual(tether.length, 15.0, places=2)
        np.testing.assert_allclose(tether.l0[-10:], near_rov)  # vehicle-end segments untouched
        self.assertEqual(tether.reel.mode, "hold")              # resumes the previous mode

    def test_powered_haul_in_rate(self):
        world = World(60)
        tether = straight(world, (0, 0, 10), (5, 0, 10), 20.0)
        tether.reel_command("haul_in")
        drive(tether, (5, 0, 10), np.zeros(3), 5.0)
        hauled = 20.0 - tether.length
        rate = X1_TETHER_PARAMETERS["reel_haul_rate"]["value"]
        self.assertLess(abs(hauled / (rate * 5.0) - 1.0), 0.15)

    def test_free_drum_pays_out_passively_against_bearing_drag(self):
        world = World(60)
        tether = straight(world, (0, 0, 10), (9.95, 0, 10), 10.0, mode="free")
        tensions = []
        for i in range(400):
            pos = np.array([9.95 + 0.3 * i * 0.01, 0, 10])
            tether.step(0.01, i * 0.01, pos, IDENTITY, np.array([0.3, 0, 0]))
            tensions.append(tether.tension_spool)
        self.assertGreater(tether.length, 10.8)
        drag = X1_TETHER_PARAMETERS["reel_free_drag_n"]["value"]
        self.assertLess(np.mean(tensions[200:]), drag * 1.3)
        self.assertGreater(np.mean(tensions[200:]), drag * 0.5)

    def test_brake_slips_above_its_holding_force(self):
        world = World(60)
        tether = straight(world, (0, 0, 10), (10.0, 0, 10), 10.0, TetherParams(reel_brake_hold_n=200.0))
        drive(tether, (10.0, 0, 10), np.array([0.2, 0, 0]), 3.0)
        self.assertGreater(tether.length, 10.3)
        self.assertLess(tether.tension_spool, 1.15 * 200.0)      # stick-slip round the holding force
        self.assertFalse(tether.broken)

    def test_auto_controller_pays_out_hauls_slack_and_detects_stall(self):
        world = World(60)
        params = TetherParams()
        tether = straight(world, (0, 0, 10), (9.95, 0, 10), 10.0, params, mode="auto")
        pos, vel = np.array([9.95, 0, 10]), np.array([0.4, 0, 0])
        tensions = []
        for i in range(600):
            tether.step(0.01, i * 0.01, pos, IDENTITY, vel)
            pos = pos + vel * 0.01
            tensions.append(tether.tension_spool)
        self.assertGreater(tether.length, 11.5)
        # slip clutch at setpoint + deadband plus viscous payout: T = clutch + speed / gain
        expected = params.auto_setpoint_n + params.auto_deadband_n + 0.4 / params.auto_gain
        self.assertLess(abs(np.mean(tensions[200:]) / expected - 1.0), 0.2)
        # slack: the controller takes it in slowly
        slack = straight(world, (0, 0, 10), (5, 0, 10), 15.0, params, mode="auto")
        drive(slack, (5, 0, 10), np.zeros(3), 4.0)
        self.assertLess(abs((15.0 - slack.length) / (params.auto_slack_rate * 4.0) - 1.0), 0.25)
        # a taut line to a fixed point stalls the haul at the pull cap
        taut = straight(world, (0, 0, 10), (10.0, 0, 10), 10.0, params, mode="haul_in")
        drive(taut, (10.0, 0, 10), np.zeros(3), 3.0)
        self.assertTrue(taut.reel.stalled)
        self.assertLess(taut.tension_spool, params.reel_pull_cap_n * 1.1)
        self.assertTrue(any(e["type"] == "reel_stall" for e in taut.events))

    def test_auto_payout_rate_uses_the_tick_length(self):
        lengths = []
        for dt in (0.01, 0.02):
            world = World(60)
            tether = straight(world, (0, 0, 10), (9.95, 0, 10), 10.0, mode="auto")
            drive(tether, (9.95, 0, 10), np.array([0.4, 0, 0]), 4.0, dt=dt)
            lengths.append(tether.length)
        self.assertLess(abs(lengths[0] - lengths[1]), 0.1)

    def test_legacy_auto_payout_toggle_maps_onto_reel_modes(self):
        tether = straight(World(60), (0, 0, 10), (5, 0, 10), 8.0)
        tether.auto_payout = True
        self.assertEqual(tether.reel.mode, "auto")
        tether.auto_payout = False
        self.assertEqual(tether.reel.mode, "hold")
        self.assertFalse(tether.state()["auto_payout"])

    def test_engine_default_is_a_free_drum_and_the_real_state_reports_it(self):
        sim = Simulator("open_water", seed=1)
        state = sim.tether.state()
        self.assertEqual(state["reel"]["mode"], "free")
        self.assertFalse(state["auto_payout"])


class TestStiffness(unittest.TestCase):
    """Gap 3: physical EA independent of deployed length; snap loads bounded and plausible."""

    def test_static_stiffness_does_not_depend_on_length(self):
        for length in (5.0, 40.0, 160.0):
            with self.subTest(length=length):
                strain = 0.002
                tether = straight(World(400), (0, 0, 10), (length * (1 + strain), 0, 10), length,
                                  TetherParams(density=RHO, cd_normal=0.0, cd_tangent=0.0))
                drive(tether, (length * (1 + strain), 0, 10), np.zeros(3), 1.0)
                expected = tether.p.ea * strain
                self.assertLess(abs(tether._seg_tension[-1] / expected - 1.0), 0.02)

    def test_snap_load_is_bounded_and_close_to_the_spring_mass_estimate(self):
        """A 55 kg body (X1 plus added mass, provisional) at 0.5 m/s takes up 5 cm of slack on 10 m.

        Lumped estimate T_peak = V sqrt((EA / L) M); the cable's damping makes the peak lower and
        the rebound slower than the impact."""
        mass, speed, length = 55.0, 0.5, 10.0
        tether = straight(World(100), (0, 0, 10), (length - 0.05, 0, 10), length,
                          TetherParams(density=RHO, cd_normal=0.0, cd_tangent=0.0))
        pos = np.array([length - 0.05, 0, 10])
        vel = np.array([speed, 0, 0])
        peak = 0.0
        for i in range(400):
            wrench = tether.step(0.01, i * 0.01, pos, IDENTITY, vel)
            vel = vel + wrench[:3] / mass * 0.01
            pos = pos + vel * 0.01
            peak = max(peak, tether.tension_rov)
            self.assertTrue(np.all(np.isfinite(tether.x)))
        estimate = speed * math.sqrt(tether.p.ea / length * mass)
        print(f"snap: peak {peak:.0f} N, spring-mass estimate {estimate:.0f} N, rebound {vel[0]:.2f} m/s")
        self.assertGreater(peak, 0.8 * estimate)
        self.assertLess(peak, 1.05 * estimate)
        self.assertLess(peak, tether.p.gland_breaking_n)
        self.assertLess(vel[0], 0.0)
        self.assertGreater(vel[0], -speed)
        self.assertFalse(tether.broken)

    def test_full_thrust_against_a_braked_reel_is_stable(self):
        sim = Simulator("tutorial_pool", seed=1)
        sim.tether.reel_command("hold")
        sim.rc_physical.rc_lock = 0
        sim.rc_physical.right_ud = 2000
        tensions = []
        for _ in range(1500):
            sim.step(0.01)
            tensions.append(sim.tether.tension_rov)
        self.assertTrue(np.all(np.isfinite(sim.vehicle.s.pos)))
        self.assertFalse(sim.tether.broken)
        self.assertLess(np.std(tensions[-300:]), 40.0)


class TestContact(unittest.TestCase):
    """Gap 2: segment contact, normal-force friction, wraps on any member."""

    def test_long_segments_do_not_tunnel_through_a_thin_member(self):
        """A 0.25 m member sits mid-segment (4.5 m segments, nodes either side at x 17.9 and 22.3).

        Node-only contact let such a segment pass straight through; sampled segment contact stops it."""
        world = World(60)
        world.obstacles.append(Cylinder("thin", (20, 0, -1), (20, 0, 61), 0.25, "brace"))
        params = TetherParams(segments=9, density=RHO)
        tether = straight(world, (0, -0.4, 10), (40, -0.4, 10), 40.2, params, mode="free")
        self.assertGreater(tether.l0[0], 4.0)
        drive(tether, (40, -0.4, 10), np.array([0, 0.3, 0]), 15.0)
        at_pile = np.interp(20.0, tether.x[:, 0], tether.x[:, 1])
        self.assertLess(at_pile, 0.0)                             # held on the near side of the member
        self.assertIn("thin", tether.snag_names)
        self.assertFalse(tether.broken)

    def test_capstan_friction_round_a_horizontal_bar(self):
        """Cable slid over a bar through half a turn: T_out / T_in near exp(mu theta)."""
        world = World(100)
        world.obstacles.append(Cylinder("bar", (0, -5, 10), (0, 5, 10), 1.0, "brace"))
        params = TetherParams(density=RHO, cd_normal=0.3, cd_tangent=0.0, segments=60)
        r = 1.0 + params.node_radius
        spool = np.array([-r, 0, 14.0])
        points = [spool, np.array([-r, 0, 10.0])]
        for angle in np.linspace(math.pi, 0, 40)[1:-1]:
            points.append(np.array([r * math.cos(angle), 0, 10 - r * math.sin(angle)]))
        points += [np.array([r, 0, 10.0]), np.array([r, 0, 14.0])]
        tether = Tether(world, spool, points[-1], 12, params, gland_body=np.zeros(3))
        tether.layout(points)
        tether.length = float(np.sum(np.linalg.norm(np.diff(np.array(points), axis=0), axis=1)))
        tether.reel_command("free")
        pos, vel = points[-1].copy(), np.array([0, 0, 0.1])
        pairs = []
        for i in range(1500):
            tether.step(0.01, i * 0.01, pos, IDENTITY, vel)
            pos = pos + vel * 0.01
            if i > 500:
                pairs.append((tether._seg_tension[0], tether._seg_tension[-1]))
        t_in, t_out = np.mean(pairs, axis=0)
        mu = params.mu_kinetic + (params.mu_static - params.mu_kinetic) * math.exp(-0.1 / params.stribeck_v)
        expected = math.exp(mu * math.pi)
        print(f"capstan: T_out/T_in {t_out / t_in:.2f}, exp(mu*pi) {expected:.2f}")
        self.assertLess(abs(t_out / t_in / expected - 1.0), 0.15)
        self.assertGreater(abs(tether.wraps["bar"]), 0.4)

    def test_wraps_count_on_horizontal_braces(self):
        world = World(60)
        world.obstacles.append(Cylinder("brace", (0, -6, 10), (0, 6, 10), 0.4, "brace"))
        r = 0.45
        points = [np.array([-3.0, -3.0, 10.0])]                  # starts on the -x side (angle pi)
        for k in range(81):
            angle = math.pi + 2 * math.pi * 1.25 * k / 80
            points.append(np.array([r * math.cos(angle), -1.5 + 3.0 * k / 80, 10 + r * math.sin(angle)]))
        points.append(np.array([0.0, 3.0, 6.0]))                    # leaves straight up (angle -pi/2)
        tether = Tether(world, points[0], points[-1], 15, TetherParams(segments=80), gland_body=np.zeros(3))
        tether.layout(points)
        tether.reel_command("hold")
        tether.step(0.01, 0.0, points[-1], IDENTITY, np.zeros(3))
        self.assertAlmostEqual(abs(tether.wraps["brace"]), 1.25, delta=0.15)

    def test_wrap_over_a_box_edge_counts_contact_turning(self):
        world = World(60)
        world.obstacles.append(Box("block", (0, 0, 12), (2, 2, 2), 0, "hull"))
        r = 0.03
        points = [np.array([-6.0, 0, 10 - r]), np.array([2.0 + r, 0, 10 - r]), np.array([2.0 + r, 0, 16.0])]
        tether = Tether(world, points[0], points[-1], 15, TetherParams(segments=60, wet_weight_per_m=0.05),
                        gland_body=np.zeros(3))
        tether.layout(points)
        tether.length = 14.0
        tether.reel_command("hold")
        drive(tether, points[-1], np.zeros(3), 2.0)
        self.assertAlmostEqual(tether.wraps.get("block", 0.0), 0.25, delta=0.1)

    def test_seabed_friction_holds_a_light_load_and_slides_under_a_strong_one(self):
        for speed, moves in ((0.05, False), (0.6, True)):
            with self.subTest(current=speed):
                world = World(20)
                world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 0.0
                params = TetherParams(density=1300.0)
                tether = straight(world, (0, 0, 19.97), (10, 0, 19.97), 10.0, params)
                drive(tether, (10, 0, 19.97), np.zeros(3), 2.0)
                start = tether.x.copy()
                water = np.array([0.0, speed, 0.0])
                tether.world.current.sample_many = lambda X, seabed, t=0.0, **_: np.tile(water, (len(X), 1))
                drive(tether, (10, 0, 19.97), np.zeros(3), 3.0, t0=2.0)
                moved = float(np.abs(tether.x[:, 1] - start[:, 1]).max())
                if moves:
                    self.assertGreater(moved, 0.05)
                else:
                    self.assertLess(moved, 0.02)


class TestTwist(unittest.TestCase):
    """Gap 4: net heading turns, small restoring moment."""

    def test_turns_follow_vehicle_heading_and_torque_opposes(self):
        tether = straight(World(60), (0, 0, 10), (8, 0, 10), 9.0)
        pos = np.array([8.0, 0, 10])
        wrench = np.zeros(6)
        for i in range(800):
            q = q_from_euler(0.0, 0.0, 2 * 2 * math.pi * i / 799)
            wrench = tether.step(0.01, i * 0.01, pos, q, np.zeros(3))
        self.assertAlmostEqual(tether.state()["turns"], 2.0, delta=0.02)
        expected = tether.p.gj * 2 * math.pi * 2.0 / tether.length
        self.assertAlmostEqual(wrench[5], -expected, delta=0.1 * expected)


class TestFailure(unittest.TestCase):
    """Gap 6: termination weak link, working-load warning, chafe."""

    def test_termination_fails_before_the_cable(self):
        tether = straight(World(60), (0, 0, 10), (6.0, 0, 10), 6.0)
        drive(tether, (6.0, 0, 10), np.array([2.0, 0, 0]), 1.0)
        self.assertTrue(tether.broken)
        self.assertEqual(tether.break_reason, "gland")
        event = next(e for e in tether.events if e["type"] == "tether_break")
        self.assertEqual(event["where"], "gland")
        self.assertLess(event["tension_n"], tether.p.breaking_n)

    def test_warning_tracks_rated_working_load(self):
        params = TetherParams()
        tether = straight(World(60), (0, 0, 10), (6.0, 0, 10), 6.0, params)
        tether.tension_rov = tether.tension_max = 300.0          # above the old fixed 250 N
        self.assertFalse(tether.over_working_load)
        tether.tension_rov = tether.tension_max = params.gland_warn_n + 1.0
        self.assertTrue(tether.over_working_load)
        self.assertAlmostEqual(params.warn_n, 0.5 * params.breaking_n)
        state = tether.state()
        self.assertAlmostEqual(state["working_load_n"], params.warn_n, places=0)

    def test_scorer_penalises_one_episode_above_working_load(self):
        sim = Simulator("open_water", seed=1)
        sim.tether.tension_rov = sim.tether.tension_max = sim.tether.p.warn_n + 10.0
        sim.scorer.update(0.01, sim)
        sim.scorer.update(0.01, sim)
        reasons = [p for p in sim.scorer.penalties if p["points"] == 10]
        self.assertEqual(len(reasons), 1)

    def test_chafe_accumulates_on_hard_contact_only(self):
        world = World(60)
        world.obstacles.append(Cylinder("edge", (5, -5, 12), (5, 5, 12), 0.3, "brace"))
        params = TetherParams(density=1400.0)
        tether = straight(world, (0, 0, 11.6), (10, 0, 11.6), 10.6, params, mode="free")
        drive(tether, (10, 0, 11.6), np.array([0.3, 0, 0]), 6.0)
        self.assertGreater(tether.chafe_fraction, 0.0)
        seabed = straight(World(20), (0, 0, 19.97), (10, 0, 19.97), 10.0, params, mode="free")
        drive(seabed, (10, 0, 19.97), np.array([0.3, 0, 0]), 4.0)
        self.assertEqual(seabed.chafe_fraction, 0.0)


class TestSolverEquivalence(unittest.TestCase):
    """The compiled path must match the NumPy reference with contact samples, reel payout and a snag pin."""

    def run_case(self, accelerated):
        world = World(20)
        world.obstacles.append(Cylinder("pile", (6, 0.6, -1), (6, 0.6, 21), 0.3))
        world.obstacles.append(SnagFeature("rock", (12.0, 1.0, 20.0), 0.25, 0.4, hold_n=(150.0, 150.0)))
        params = TetherParams(density=1300.0, accelerated=accelerated, segments=12, snag_hook_tension_n=1.0)
        tether = straight(world, (0, 0, 19.9), (15, 0, 19.6), 15.6, params, mode="free")
        body = PointBody((15.0, 0.0, 19.6))
        body.go(tether, (15, 5, 19.6), 0.3, 12.0, 0.0)
        return tether

    def test_compiled_matches_reference(self):
        from qysim._cable_accel import advance_batch
        if advance_batch is None:
            self.skipTest("optional Numba is not installed")
        compiled = self.run_case(True)
        reference = self.run_case(False)
        self.assertEqual(len(compiled.l0), len(reference.l0))
        np.testing.assert_allclose(compiled.x, reference.x, atol=1e-8, rtol=1e-8)
        np.testing.assert_allclose(compiled.v, reference.v, atol=1e-8, rtol=1e-8)
        np.testing.assert_allclose(compiled.l0, reference.l0, atol=1e-10)
        self.assertEqual(len(compiled.snags.hooks), 1)
        self.assertEqual(len(reference.snags.hooks), 1)
        self.assertGreater(len(compiled.l0), 12)                   # payout split the spool segment


class TestParameters(unittest.TestCase):
    """Gap 8: one density sets mass and wet weight; added mass is normal only; sources labelled."""

    def test_mass_and_wet_weight_follow_density_and_diameter(self):
        params = TetherParams()
        area = math.pi * (params.diameter / 2) ** 2
        self.assertAlmostEqual(params.mass, params.density * area)
        self.assertAlmostEqual(params.wet_weight, (params.density - RHO) * area)
        self.assertLess(params.wet_weight, 0.0)                   # fresh-water neutral floats in the sea

    def test_added_mass_acts_normal_to_the_cable_only(self):
        tether = straight(World(60), (0, 0, 10), (8, 0, 10), 8.0)
        ms, ma, lw = tether._node_masses()
        self.assertAlmostEqual(ma[3] / lw[3], RHO * tether.p.area * tether.p.added_mass_normal)
        self.assertAlmostEqual(ms[3] / lw[3], tether.p.mass)

    def test_every_tether_value_has_a_level_and_a_source(self):
        for key, item in X1_TETHER_PARAMETERS.items():
            with self.subTest(key=key):
                self.assertIn(item["level"], ("official", "reseller", "estimated"))
                self.assertTrue(item["source"])


class TestSnags(unittest.TestCase):
    """Seabed snags: hook when dragged across, tighten when pulled, release by backtracking."""

    def rig(self, density):
        world = World(20)
        world.obstacles.append(SnagFeature("rock", (12.0, 1.0, 20.0), 0.25, 0.4, hold_n=(150.0, 150.0)))
        params = TetherParams(density=density, snag_hook_tension_n=1.0)
        tether = straight(world, (0, 0, 19.9), (15, 0, 19.6), 15.6, params)
        body = PointBody((15.0, 0.0, 19.6))
        return tether, body

    def test_negative_tether_hooks_tightens_and_backtracking_releases(self):
        tether, body = self.rig(1300.0)
        t = body.go(tether, (15, 0, 19.6), 0.0, 3.0, 0.0)
        t = body.go(tether, (15, 4, 19.6), 0.3, 14.0, t)
        self.assertEqual([s["name"] for s in tether.state()["snags"]], ["rock"])
        hooked = tether.snags.hooks[0]
        t = body.go(tether, (15, 7, 19.6), 0.3, 10.0, t)
        self.assertGreater(hooked.hold_n, hooked.base_hold_n * 1.2)         # pulling tightened it
        self.assertLess(body.pos[1], 5.0)                                   # and it held the vehicle
        t = body.go(tether, (12.5, 3, 19.6), 0.3, 15.0, t)                  # back along the tether
        self.assertTrue(tether.snags.hooks)                                 # slack alone does not free it
        body.go(tether, (12.5, -1.5, 19.6), 0.3, 15.0, t)                   # round to the other side
        self.assertFalse(tether.snags.hooks)
        kinds = [e["type"] for e in tether.events]
        self.assertIn("tether_snag", kinds)
        self.assertIn("tether_snag_released", kinds)

    def test_neutral_tether_held_off_the_bottom_does_not_hook(self):
        tether, body = self.rig(1000.0)
        t = body.go(tether, (15, 0, 19.6), 0.0, 3.0, 0.0)
        body.go(tether, (15, 4, 19.6), 0.3, 14.0, t)
        self.assertEqual(tether.state()["snags"], [])
        self.assertNotIn("rock", tether.snag_names)

    def test_snaggable_structures_and_scenario_features(self):
        castle = scenarios.build("korean_castle").obstacles[0]
        self.assertIsNotNone(castle.snag_hold)
        for key in ("harbor_inspection", "wreck_survey", "incident_wreck", "tether_untangle"):
            with self.subTest(key=key):
                features = [o for o in scenarios.build(key).obstacles if isinstance(o, SnagFeature)]
                self.assertTrue(features)
                self.assertEqual(features[0].as_dict()["type"], "snag")


class SettleTests(unittest.TestCase):
    def test_initial_settle_never_breaks_the_cable(self):
        # Campaign chapters always load seed 42; harbor_inspection's initial bight used to spike past the
        # breaking load on the first settle step, so harbor / harbor_signoff / finale started already failed.
        sim = Simulator("harbor_inspection", 42)
        self.assertFalse(sim.tether.broken)
        self.assertLess(sim.tether.tension_max, sim.tether.p.breaking_n)
        self.assertFalse(sim.tether._settling)          # breaking during flight is covered by the failure tests


if __name__ == "__main__":
    unittest.main()
