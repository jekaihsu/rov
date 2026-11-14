"""Ocean current model checks: turbulence statistics, tide, structure flow, near-bed profile.

Targets come from research_notes/洋流與波浪對ROV作業/ (current_model_audit.md gap list and
currents_and_waves_physics.md). The numbers are provisional simulator assumptions, not X1 data.
"""
import math
import unittest

import numpy as np

from qysim.flow import M2_PERIOD_S, Tide, TurbulenceField
from qysim.physics import KNOT
from qysim.world import CurrentProfile


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


if __name__ == "__main__":
    unittest.main()
