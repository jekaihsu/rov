"""Ocean current model checks: turbulence statistics, tide, structure flow, near-bed profile.

Targets come from research_notes/洋流與波浪對ROV作業/ (current_model_audit.md gap list and
currents_and_waves_physics.md). The numbers are provisional simulator assumptions, not X1 data.
"""
import math
import unittest

import numpy as np

from qysim.flow import FlowAccelerometer, M2_PERIOD_S, Tide, TurbulenceField
from qysim.physics import KNOT
from qysim.world import Box, CurrentProfile, Cylinder, Wall, World


def uniform_profile(knots=1.6, direction=180.0, turbulence=0.1, seed=3):
    profile = CurrentProfile(knots, direction, knots, direction, knots, direction, turbulence)
    profile.reseed(seed)
    return profile


def series(profile, point, seconds, dt, seabed=28.0, every=1):
    """Ambient velocity samples at one point, one per ``every`` steps of ``dt``."""
    p = np.asarray(point, float)[None, :]
    profile.sample_many(p, seabed)
    out = []
    for i in range(int(round(seconds / dt))):
        profile.step_gust(dt)
        if (i + 1) % every == 0:
            out.append(profile.sample_many(p, seabed)[0])
    return np.array(out)


def streamwise_frame(v):
    mean = v.mean(axis=0)
    e_s = mean[:2] / np.linalg.norm(mean[:2])
    e_n = np.array([-e_s[1], e_s[0]])
    return v[:, :2] @ e_s, v[:, :2] @ e_n, v[:, 2], float(np.linalg.norm(mean[:2]))


class TurbulenceTests(unittest.TestCase):
    """Gap 1: smooth, anisotropic, spatially decorrelating turbulence."""

    @classmethod
    def setUpClass(cls):
        cls.profile = uniform_profile()
        records = [series(uniform_profile(seed=s), (0.0, 0.0, 12.0), 3600.0, 0.25) for s in (3, 4)]
        cls.records = records

    def test_intensity_and_component_ratios(self):
        ti, rv, rw = [], [], []
        for v in self.records:
            u, c, w, mean = streamwise_frame(v)
            ti.append(u.std() / mean)
            rv.append(c.std() / u.std())
            rw.append(w.std() / u.std())
        self.assertAlmostEqual(float(np.mean(ti)), 0.10, delta=0.02)
        self.assertAlmostEqual(float(np.mean(rv)), 0.7, delta=0.14)
        self.assertAlmostEqual(float(np.mean(rw)), 0.5, delta=0.10)

    def test_no_reverse_flow_or_doubling(self):
        for v in self.records:
            u, _, _, mean = streamwise_frame(v)
            self.assertGreater(u.min(), 0.5 * mean)
            self.assertLess(u.max(), 1.5 * mean)

    def test_integral_timescale_follows_length_over_speed(self):
        L, _ = self.profile.turbulence_scales(28.0)
        U = 1.6 * KNOT
        expected = 0.92 * L / U
        scales = []
        for v in self.records:
            u = streamwise_frame(v)[0]
            u = u - u.mean()
            spectrum = np.fft.rfft(u, 2 * len(u))
            acf = np.fft.irfft(spectrum * np.conj(spectrum))[:len(u)] / (u.var() * len(u))
            first_zero = int(np.argmax(acf < 0))
            scales.append(float(acf[:first_zero].sum() * 0.25))
        self.assertAlmostEqual(float(np.mean(scales)), expected, delta=0.3 * expected)

    def test_two_point_correlation_decays_with_separation(self):
        field = TurbulenceField(seed=11)
        rng = np.random.default_rng(5)
        ell = 10.0
        L = ell / TurbulenceField.SCALE
        base = rng.uniform(-2000, 2000, (4000, 3))
        base[:, 2] = 0.0

        def rho(separation):
            ang = rng.uniform(0, 2 * math.pi, len(base))
            other = base + separation * np.stack([np.cos(ang), np.sin(ang), np.zeros_like(ang)], axis=1)
            a, b = field.unit(base, ell)[:, 0], field.unit(other, ell)[:, 0]
            return float(np.corrcoef(a, b)[0, 1])

        self.assertGreater(rho(0.1 * L), 0.9)
        self.assertLess(rho(L), 0.45)
        self.assertLess(abs(rho(3 * L)), 0.15)

    def test_tether_nodes_ten_metres_apart_see_different_gusts(self):
        profile = uniform_profile(seed=8)
        points = np.array([[0.0, 0.0, 12.0], [0.0, 10.0, 12.0], [0.0, 30.0, 12.0]])
        records = []
        for _ in range(2400):
            profile.step_gust(0.5)
            records.append(profile.sample_many(points, 28.0))
        u = np.array(records)[:, :, 0]
        near = np.corrcoef(u[:, 0], u[:, 1])[0, 1]
        far = np.corrcoef(u[:, 0], u[:, 2])[0, 1]
        self.assertLess(near, 0.8)
        self.assertLess(far, near)

    def test_time_derivative_bounded_and_step_size_independent(self):
        fine, coarse = uniform_profile(seed=21), uniform_profile(seed=21)
        point = (0.0, 0.0, 12.0)
        a = series(fine, point, 20.0, 0.001, every=100)
        b = series(coarse, point, 20.0, 0.01, every=10)
        np.testing.assert_allclose(a, b, atol=1e-6)
        rate = np.diff(b, axis=0) / 0.1
        self.assertLess(float(np.abs(rate).max()), 0.1)
        L, ell = coarse.turbulence_scales(28.0)
        analytic = coarse._field().unit_rate(np.array([point]), ell, coarse.depth_average(), 0.08)
        self.assertLess(float(np.abs(analytic).max()), 1.0)

    def test_still_water_has_no_gusts(self):
        profile = uniform_profile(knots=0.0, turbulence=0.1)
        v = series(profile, (5.0, 5.0, 5.0), 20.0, 0.1, seabed=20.0)
        self.assertLess(float(np.abs(v).max()), 1e-9)
        calm = uniform_profile(knots=1.0, turbulence=0.0)
        v = series(calm, (5.0, 5.0, 5.0), 20.0, 0.1, seabed=20.0)
        self.assertLess(float(np.ptp(v, axis=0).max()), 1e-12)


def tidal_profile(knots=1.0, **tide):
    profile = CurrentProfile(knots, 90, knots, 90, knots, 90, 0.0, tide=Tide(**tide))
    return profile


def speeds_over_cycle(profile, step=10.0, seabed=20.0):
    out = []
    for _ in range(int(M2_PERIOD_S / step)):
        out.append(profile.mean_at(5.0, seabed).copy())
        profile.step_gust(step)
    return np.array(out)


class TideTests(unittest.TestCase):
    """Gap 3: optional M2/S2 tide reproducing NOAA slack-water durations."""

    def test_absent_tide_keeps_steady_profile(self):
        profile = CurrentProfile(1.0, 90, 0.8, 100, 0.3, 110, 0.0)
        before = profile.mean_many([0.0, 10.0, 18.0], 20.0)
        profile.step_gust(3 * 3600.0)
        np.testing.assert_array_equal(profile.mean_many([0.0, 10.0, 18.0], 20.0), before)
        self.assertNotIn("tide", profile.as_dict())
        self.assertIsNone(profile.tide_info())

    def test_slack_windows_match_noaa_table_4a(self):
        # NOAA Tidal Current Tables Table 4A: minutes at or below 0.1 kn around slack.
        for knots, minutes in ((1.0, 23), (2.0, 11), (4.0, 6)):
            with self.subTest(knots=knots):
                v = speeds_over_cycle(tidal_profile(knots), step=10.0)
                slow = np.linalg.norm(v, axis=1) / KNOT <= 0.1
                window = slow.sum() * 10.0 / 60.0 / 2          # two slacks per M2 cycle
                self.assertAlmostEqual(window, minutes, delta=max(1.5, 0.1 * minutes))

    def test_period_reversal_and_ebb_direction(self):
        profile = tidal_profile(1.0, ebb_dir=250.0, ebb_ratio=0.8)
        v = speeds_over_cycle(profile, step=60.0)
        flood, ebb = v[np.argmax(v[:, 1])], v[np.argmax(-v[:, 1] - v[:, 0])]
        heading = math.degrees(math.atan2(ebb[1], ebb[0])) % 360
        self.assertAlmostEqual(np.linalg.norm(flood) / KNOT, 1.0, delta=0.01)
        self.assertAlmostEqual(heading, 250.0, delta=0.5)
        self.assertAlmostEqual(np.linalg.norm(ebb) / KNOT, 0.8, delta=0.01)
        np.testing.assert_allclose(profile.mean_at(5.0, 20.0), v[0], atol=1e-3)

    def test_rotary_tide_turns_clockwise_without_slack(self):
        v = speeds_over_cycle(tidal_profile(1.0, kind="rotary", minor_ratio=0.3), step=60.0)
        speed = np.linalg.norm(v, axis=1) / KNOT
        self.assertAlmostEqual(speed.min(), 0.3, delta=0.01)
        heading = np.unwrap(np.arctan2(v[:, 1], v[:, 0]))
        self.assertGreater(heading[-1] - heading[0], 1.9 * math.pi)        # one clockwise turn

    def test_time_of_tide_selector(self):
        for start, factor in (("peak_flood", 1.0), ("peak_ebb", -1.0), ("slack_before_flood", 0.0),
                              ("slack_before_ebb", 0.0), (3.105, 0.0)):
            with self.subTest(start=start):
                profile = tidal_profile(2.0, start=start, m2_phase_deg=40.0)
                self.assertAlmostEqual(profile.tide_info()["factor"], factor, delta=0.01)
        rising = tidal_profile(2.0, start="slack_before_flood")
        rising.step_gust(600.0)
        self.assertEqual(rising.tide_info()["stage"], "flood")
        rising.set_tide_start("peak_ebb")
        self.assertAlmostEqual(rising.tide_info()["factor"], -1.0, delta=0.01)
        with self.assertRaises(ValueError):
            rising.set_tide_start("noon")
        self.assertEqual(rising.tide.start, "peak_ebb")

    def test_spring_tide_adds_s2(self):
        v = speeds_over_cycle(tidal_profile(1.0, s2=0.3), step=60.0)
        self.assertAlmostEqual(np.linalg.norm(v, axis=1).max() / KNOT, 1.3, delta=0.02)

    def test_validation(self):
        for bad in ({"kind": "spiral"}, {"m2": -1}, {"time_scale": 0}, {"start": "noon"},
                    {"m2": float("nan")}, {"unknown": 1}):
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                Tide.from_dict(bad)

    def test_host_messages_set_tide_and_time_of_tide(self):
        from qysim.engine import Simulator
        from qysim.server import SimHost
        host = SimHost(Simulator("open_water"))
        sim = host.room.primary
        host.handle_viewer({"type": "current", "tide": {"kind": "rectilinear", "start": "peak_flood"}})
        self.assertEqual(sim.world.current.as_dict()["tide"]["kind"], "rectilinear")
        host.handle_viewer({"type": "current", "tide_start": "slack_before_flood"})
        self.assertAlmostEqual(sim.world.current.tide_info()["factor"], 0.0, delta=0.01)
        for bad in ({"tide": {"kind": "spiral"}}, {"tide_start": "noon"}, {"tide": 3}):
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                host.handle_viewer({"type": "current", **bad})
        host.handle_viewer({"type": "current", "tide": None})
        self.assertNotIn("tide", sim.world.current.as_dict())
        with self.assertRaises(ValueError):
            host.handle_viewer({"type": "current", "tide_start": "peak_flood"})


def pile_world(radius=3.0, speed=1.0, obstacles=None):
    """28 m deep world with a uniform turbulence-free 1 m/s current toward north (+x)."""
    world = World(28.0)
    knots = speed / KNOT
    world.current = CurrentProfile(knots, 0, knots, 0, knots, 0, 0.0)
    world.obstacles = obstacles if obstacles is not None else [
        Cylinder("pile", (0.0, 0.0, -3.0), (0.0, 0.0, 29.0), radius, "monopile")]
    return world


def time_series(world, point, seconds, dt=0.5):
    out = []
    for _ in range(int(seconds / dt)):
        world.current.step_gust(dt)
        out.append(world.current_at(np.asarray(point, float)))
    return np.array(out)


class StructureFlowTests(unittest.TestCase):
    """Gap 2: stagnation, shoulder speed-up, wake deficit, shedding, lee shelter."""

    def test_cylinder_speed_ratios(self):
        world = pile_world()
        R, z = 3.0, 12.0
        at = lambda x, y: np.linalg.norm(time_series(world, (x, y, z), 120.0).mean(axis=0))
        self.assertLess(at(-1.05 * R, 0), 0.15)                     # stagnation upstream
        self.assertGreater(at(0, 1.05 * R), 1.8)                    # up to 2U at the shoulder
        self.assertLess(at(0, 1.05 * R), 2.0 + 1e-9)
        self.assertLess(at(4 * R, 0), 0.5)                           # near wake (2D behind the axis)
        wake5d = at(10 * R, 0)
        self.assertGreater(wake5d, 0.5)
        self.assertLess(wake5d, 0.7)                                 # 30-50 % deficit at 5 D
        self.assertGreater(at(40 * R, 0), 0.8)                       # recovering by 20 D

    def test_far_field_matches_free_stream(self):
        world = pile_world()
        for point in ((-200.0, 0.0, 12.0), (0.0, 60.0, 12.0), (0.0, -90.0, 20.0)):
            v = world.current_at(np.array(point))
            np.testing.assert_allclose(v, [1.0, 0.0, 0.0], atol=0.01)

    def test_field_is_continuous_around_the_pile(self):
        world = pile_world()
        world.current.step_gust(3.0)
        for y in (0.0, 4.0, 8.0):
            xs = np.linspace(-30.0, 60.0, 1801)
            pts = np.stack([xs, np.full_like(xs, y), np.full_like(xs, 12.0)], axis=1)
            v = world.current_at_many(pts)
            outside = np.hypot(xs, y) > 3.05
            jumps = np.linalg.norm(np.diff(v, axis=0), axis=1)[outside[1:] & outside[:-1]]
            self.assertLess(float(jumps.max()), 0.1)

    def test_zero_flow_inside_solids(self):
        hull = Box("hull", (40.0, 0.0, 4.0), (20.0, 5.0, 4.0), 0.0, "hull")
        wall = Wall("quay", (-30.0, 0.0, 0.0), 0.0, 60.0, -2.0, "wall")
        world = pile_world(obstacles=[Cylinder("pile", (0.0, 0.0, -3.0), (0.0, 0.0, 29.0), 3.0), hull, wall])
        for point in ((1.0, 1.0, 10.0), (40.0, 0.0, 4.0), (-35.0, 0.0, 10.0)):
            np.testing.assert_array_equal(world.current_at(np.array(point)), np.zeros(3))

    def test_shedding_period_follows_strouhal(self):
        world = pile_world(radius=3.0, speed=1.0)
        v = time_series(world, (12.0, 1.0, 12.0), 600.0, dt=0.5)
        lateral = v[:, 1] - v[:, 1].mean()
        spectrum = np.abs(np.fft.rfft(lateral))
        freqs = np.fft.rfftfreq(len(lateral), 0.5)
        peak = freqs[int(np.argmax(spectrum[1:])) + 1]
        self.assertAlmostEqual(1.0 / peak, 6.0 / (0.2 * 1.0), delta=3.0)   # D / (St U) = 30 s
        self.assertGreater(lateral.std(), 0.05)

    def test_jacket_leg_sheds_faster_and_brace_respects_its_axis(self):
        leg = Cylinder("leg", (0.0, 0.0, -3.0), (0.0, 0.0, 29.0), 0.6, "jacket_leg")
        world = pile_world(obstacles=[leg])
        v = time_series(world, (2.4, 0.2, 12.0), 120.0, dt=0.1)
        lateral = v[:, 1] - v[:, 1].mean()
        freqs = np.fft.rfftfreq(len(lateral), 0.1)
        peak = freqs[int(np.argmax(np.abs(np.fft.rfft(lateral))[1:])) + 1]
        self.assertAlmostEqual(1.0 / peak, 1.2 / 0.2, delta=1.0)
        brace = Cylinder("brace", (-10.0, 0.0, 10.0), (10.0, 0.0, 10.0), 0.25, "brace")   # along the flow
        aligned = pile_world(obstacles=[brace])
        np.testing.assert_allclose(aligned.current_at(np.array([0.0, 0.6, 10.0])), [1.0, 0.0, 0.0], atol=1e-9)

    def test_lee_shelter_behind_hull_and_wall_layer(self):
        hull = Box("hull", (0.0, 0.0, 4.0), (10.0, 5.0, 4.0), 90.0, "hull")       # beam-on to the flow
        world = pile_world(obstacles=[hull])
        behind = np.linalg.norm(world.current_at(np.array([7.0, 0.0, 4.0])))
        far = np.linalg.norm(world.current_at(np.array([7.0, 0.0, 14.0])))
        ahead = np.linalg.norm(world.current_at(np.array([-7.0, 0.0, 4.0])))
        self.assertLess(behind, 0.5)
        self.assertLess(ahead, 0.9)
        self.assertAlmostEqual(far, 1.0, delta=0.02)
        quay = Wall("quay", (0.0, 20.0, 0.0), 270.0, 100.0, -2.0, "wall")           # flow runs along it
        side = pile_world(obstacles=[quay])
        near = np.linalg.norm(side.current_at(np.array([0.0, 19.9, 10.0])))
        self.assertLess(near, 0.7)                                   # (0.1 m / 2 m)^(1/7) = 0.65
        self.assertAlmostEqual(np.linalg.norm(side.current_at(np.array([0.0, 15.0, 10.0]))), 1.0, delta=1e-9)

    def test_performance_budget(self):
        from qysim.engine import Simulator
        import time
        sim = Simulator("jacket_inspection")
        nodes = sim.tether.x.copy()
        sim.world.current_at_many(nodes)
        start = time.process_time()
        for _ in range(100):
            sim.world.current_at_many(nodes)
        per_call = (time.process_time() - start) / 100
        self.assertLess(per_call, 0.004)            # 41 tether nodes among 24 jacket members
        open_water = Simulator("open_water")
        self.assertTrue(open_water.world.structure_flow().empty)


class FluidAccelerationTests(unittest.TestCase):
    """Gap 4: (displaced + added mass) x flow acceleration on the vehicle and tether nodes."""

    @staticmethod
    def oscillate(use_accel, period=6.0, amplitude=0.3, seconds=30.0, dt=0.01):
        from qysim.physics import Vehicle
        vehicle = Vehicle()
        vehicle.p.net_buoyancy = 0.0                      # neutral body
        vehicle.seabed_depth = 30.0
        vehicle.s.pos = np.array([0.0, 0.0, 10.0])
        omega = 2 * math.pi / period
        velocity = []
        for i in range(int(seconds / dt)):
            t = i * dt
            vehicle.current_ned = np.array([amplitude * math.sin(omega * t), 0.0, 0.0])
            if use_accel:
                vehicle.current_accel_ned = np.array([amplitude * omega * math.cos(omega * t), 0.0, 0.0])
            vehicle.step(dt, np.zeros(len(vehicle.thrusters)))
            velocity.append(vehicle.world_velocity()[0])
        tail = np.array(velocity[len(velocity) // 2:])
        return (tail.max() - tail.min()) / (2 * amplitude)

    def test_neutral_body_follows_oscillating_flow(self):
        with_inertia = self.oscillate(True)
        drag_only = self.oscillate(False)
        self.assertAlmostEqual(with_inertia, 1.0, delta=0.03)
        self.assertLess(drag_only, with_inertia - 0.05)

    def test_steady_flow_has_no_fluid_acceleration(self):
        from qysim.engine import Simulator
        sim = Simulator("open_water")
        sim.world.current.turbulence = 0.0
        for _ in range(200):
            sim.step(0.01)
        self.assertEqual(float(np.abs(sim.vehicle.current_accel_ned).max()), 0.0)
        # settling nodes drift through the (sheared) profile: only round-off level accelerations
        self.assertLess(float(np.abs(sim.tether._flow_accel.value).max()), 1e-6)

    def test_accelerometer_is_step_size_independent_and_bounded(self):
        estimates = []
        for dt in (0.01, 0.001):
            meter = FlowAccelerometer()
            for i in range(int(round(2.0 / dt)) + 1):
                value = meter.update(np.array([[0.5 * math.sin(2 * math.pi * i * dt / 4.0), 0.0, 0.0]]), dt)
            estimates.append(float(value[0, 0]))
        self.assertAlmostEqual(estimates[0], estimates[1], delta=0.02 * abs(estimates[1]) + 1e-3)
        meter = FlowAccelerometer()
        meter.update(np.zeros((1, 3)), 0.01)
        for _ in range(20):
            jump = meter.update(np.array([[5.0, 0.0, 0.0]]), 0.01)
        self.assertLessEqual(float(np.linalg.norm(jump)), 3.0 + 1e-9)

    def test_tether_nodes_follow_oscillating_water(self):
        from qysim.tether import Tether, TetherParams
        amplitudes = []
        for inertia in (True, False):
            world = World(30.0)
            clock = {"t": 0.0}

            def flow(points, t=None, clock=clock):
                u = 0.3 * math.sin(2 * math.pi * clock["t"] / 4.0)
                return np.tile([0.0, u, 0.0], (len(points), 1))

            world.current_at_many = flow
            tether = Tether(world, np.zeros(3), np.array([0.0, 0.0, 20.0]), 30.0,
                            TetherParams(accelerated=False))
            tether.auto_payout = False
            if not inertia:
                tether._flow_accel = type("Off", (), {"update": lambda self, v, dt: np.zeros_like(v)})()
            mid = []
            for i in range(800):
                clock["t"] = i * 0.01
                tether.step(0.01, clock["t"], np.array([0.0, 0.0, 20.0]), np.array([1.0, 0, 0, 0]), np.zeros(3))
                mid.append(tether.v[len(tether.v) // 2, 1])
            tail = np.array(mid[400:])
            amplitudes.append((tail.max() - tail.min()) / 0.6)
        # The provisional cable is heavier than the water it displaces and its ends are held, so
        # it follows less than a neutral body; the inertia term must still bring it clearly closer.
        self.assertGreater(amplitudes[0], amplitudes[1] + 0.05)
        self.assertGreater(amplitudes[0], 0.6)


class NearBedProfileTests(unittest.TestCase):
    """Gap 7: log-law bed layer on the local (terrain) seabed with biome roughness."""

    def test_log_law_ratios(self):
        profile = CurrentProfile(1.0, 90, 1.0, 90, 1.0, 90, 0.0, z0=0.003)          # gravel
        seabed = 20.0
        h_ref = 2.0                                                                  # 0.1 x depth
        for height in (0.2, 1.0):
            speed = np.linalg.norm(profile.mean_at(seabed - height, seabed)) / KNOT
            self.assertAlmostEqual(speed, math.log(height / 0.003) / math.log(h_ref / 0.003), places=6)
        self.assertAlmostEqual(np.linalg.norm(profile.mean_at(seabed - 5.0, seabed)) / KNOT, 1.0, places=6)
        u02, u1 = (np.linalg.norm(profile.mean_at(seabed - h, seabed)) for h in (0.2, 1.0))
        self.assertLess(u02, u1)

    def test_rougher_beds_slow_the_flow_more(self):
        speeds = []
        for z0 in (0.0002, 0.006, 0.03):                         # mud, rippled sand, rock
            profile = CurrentProfile(1.0, 90, 1.0, 90, 1.0, 90, 0.0, z0=z0)
            speeds.append(np.linalg.norm(profile.mean_at(19.7, 20.0)))
        self.assertGreater(speeds[0], speeds[1])
        self.assertGreater(speeds[1], speeds[2])

    def test_terrain_high_point_uses_local_seabed(self):
        from qysim.engine import Simulator
        sim = Simulator("coral_reef")
        world = sim.world
        world.current.turbulence = 0.0
        self.assertEqual(world.bed_roughness(), 0.03)
        rng = np.random.default_rng(0)
        xy = rng.uniform(-40, 60, (4000, 3))
        xy[:, 2] = 0.0
        beds = world.terrain.sample_many(xy)[0]
        top = xy[int(np.argmin(beds))].copy()
        bed = float(beds.min())
        self.assertLess(bed, world.seabed_depth - 0.8)
        top[2] = bed - 0.3
        above_reef = np.linalg.norm(world.current_at(top))
        mid_water = np.linalg.norm(world.current_at(np.array([top[0], top[1], 7.0])))
        same_depth_profile = np.linalg.norm(world.current.mean_at(top[2], world.seabed_depth))
        self.assertLess(above_reef, mid_water)
        self.assertLess(above_reef, 0.8 * same_depth_profile)
        self.assertEqual(np.linalg.norm(world.current_at(np.array([top[0], top[1], bed + 0.2]))), 0.0)


class HullSamplingTests(unittest.TestCase):
    """Gap 10: flow sampled at several hull points gives torque in uneven flow."""

    @staticmethod
    def run_vehicle(points_flow, seconds=3.0):
        from qysim.physics import Vehicle
        vehicle = Vehicle()
        vehicle.s.pos = np.array([0.0, 0.0, 10.0])
        vehicle.current_ned = np.array([0.0, 0.3, 0.0])
        for _ in range(int(seconds / 0.01)):
            if points_flow is not None:
                vehicle.current_points = points_flow(vehicle)
            vehicle.step(0.01, np.zeros(len(vehicle.thrusters)))
        return vehicle

    def test_uniform_flow_is_unchanged(self):
        from qysim.engine import hull_flow_points
        body = hull_flow_points(self.run_vehicle(None).definition)
        uniform = self.run_vehicle(lambda v: (body, np.tile(v.current_ned, (len(body), 1))))
        plain = self.run_vehicle(None)
        np.testing.assert_allclose(uniform.s.pos, plain.s.pos, atol=1e-12)
        np.testing.assert_allclose(uniform.s.omega, plain.s.omega, atol=1e-12)

    def test_cross_flow_on_the_bow_only_yaws_the_vehicle(self):
        from qysim.engine import hull_flow_points
        body = hull_flow_points(self.run_vehicle(None).definition)

        def bow_in_jet(vehicle):
            flows = np.tile(vehicle.current_ned, (len(body), 1))
            flows[0] = vehicle.current_ned + np.array([0.0, 0.4, 0.0])     # bow sees extra east flow
            return body, flows

        yawed = self.run_vehicle(bow_in_jet, seconds=1.0)
        self.assertGreater(yawed.s.omega[2], 0.01)                   # bow pushed to starboard

    def test_engine_samples_hull_points_beside_a_pile(self):
        from qysim.engine import Simulator
        sim = Simulator("monopile_current")
        sim.world.current.turbulence = 0.0
        pile = sim.world.obstacles[0]
        centre = np.asarray(pile.p0, float)
        # 1 m upstream of the stagnation point: the flow slows sharply toward the pile
        sim.vehicle.s.pos = np.array([centre[0] + pile.radius + 1.0, centre[1] + 0.5, 12.0])
        sim.step(0.01)
        points, flows = sim.vehicle.current_points
        self.assertEqual(len(points), 6)
        spread = float(np.ptp(np.linalg.norm(flows, axis=1)))
        self.assertGreater(spread, 0.1)


class ViewerFlowFieldTests(unittest.TestCase):
    """Gap 8: the viewer's particles and kelp sample the same field as the physics."""

    def test_state_carries_a_compact_grid_of_the_physics_flow(self):
        import json
        from qysim.engine import FLOW_GRID_SIZE, Simulator
        from qysim.room import Room
        room = Room(Simulator("monopile_current"))
        sim = room.primary
        sim.vehicle.s.pos = np.array([5.0, 1.0, 12.0])
        for _ in range(60):
            room.step(0.01)
        grid = room.state()["flow_field"]
        nx, ny, nz = FLOW_GRID_SIZE
        values = np.array(grid["cm_s"]).reshape(nx, ny, nz, 3) / 100
        axes = [grid["origin"][k] + grid["step"][k] * np.arange(grid["size"][k]) for k in range(3)]
        points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
        np.testing.assert_allclose(values.reshape(-1, 3), sim.world.current_at_many(points), atol=0.0051)
        self.assertLess(len(json.dumps(grid, separators=(",", ":"))), 900)
        # The vehicle sits between the two levels at the grid centre: trilinear = midpoint average.
        centre = values[nx // 2, ny // 2].mean(axis=0)
        here = sim.world.current_at(sim.vehicle.s.pos)
        self.assertAlmostEqual(axes[2].mean(), sim.vehicle.s.pos[2], delta=0.05)
        self.assertLess(np.linalg.norm(centre - here), 0.25 * np.linalg.norm(here))

    def test_grid_refreshes_every_half_second_only(self):
        from qysim.engine import Simulator
        from qysim.room import Room
        room = Room(Simulator("open_water"))
        first = room.state()["flow_field"]
        for _ in range(20):
            room.step(0.01)
        self.assertIs(room.state()["flow_field"], first)
        for _ in range(31):
            room.step(0.01)
        self.assertEqual(room.state()["flow_field"]["seq"], first["seq"] + 1)


class ScenarioCurrentTests(unittest.TestCase):
    """Gap 9: scenario currents are realistic assumptions."""

    def test_turbulence_intensities_are_in_the_measured_range(self):
        from qysim import scenarios
        for key in scenarios.LIBRARY:
            with self.subTest(key=key):
                current = scenarios.build(key).current
                if key == "tutorial_pool":
                    self.assertEqual(current.turbulence, 0)
                else:
                    self.assertGreaterEqual(current.turbulence, 0.05)
                    self.assertLessEqual(current.turbulence, 0.15)

    def test_deep_wreck_has_a_weak_current(self):
        from qysim import scenarios
        current = scenarios.build("incident_wreck").current
        speeds = [current.surface_kn, current.mid_kn, current.bottom_kn]
        self.assertGreater(min(speeds), 0.1)
        self.assertLess(max(speeds), 1.0)

    def test_tidal_scenarios_start_at_peak_and_support_slack_start(self):
        from qysim.engine import Simulator
        sim = Simulator("monopile_current")
        self.assertAlmostEqual(sim.world.current.tide_info()["factor"], 1.0, delta=0.01)
        sim.world.current.set_tide_start("slack_before_flood")
        self.assertLess(np.linalg.norm(sim.world.current.mean_at(12.0, sim.world.seabed_depth)), 0.01)

    def test_random_currents_follow_a_sea_type(self):
        from qysim import scenarios
        for seed in range(20):
            current = scenarios.build("random", seed).current
            self.assertLessEqual(current.surface_kn, 3.0)
            self.assertLessEqual(abs(current.bottom_dir - current.surface_dir), 30.0 + 1e-9)
            self.assertGreaterEqual(current.turbulence, 0.05)
            self.assertLessEqual(current.turbulence, 0.15)
            self.assertIsNotNone(current.tide)
        a, b = scenarios.build("random", 5).current, scenarios.build("random", 5).current
        self.assertEqual(a.as_dict(), b.as_dict())


if __name__ == "__main__":
    unittest.main()
