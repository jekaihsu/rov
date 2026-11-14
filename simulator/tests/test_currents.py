"""Ocean current model checks: turbulence statistics, tide, structure flow, near-bed profile.

Targets come from research_notes/洋流與波浪對ROV作業/ (current_model_audit.md gap list and
currents_and_waves_physics.md). The numbers are provisional simulator assumptions, not X1 data.
"""
import math
import unittest

import numpy as np

from qysim.flow import TurbulenceField
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


if __name__ == "__main__":
    unittest.main()
