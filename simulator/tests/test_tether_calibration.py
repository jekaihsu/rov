"""Three payout cases against a catenary and a steady uniform-current cable.

Numbers are locked here and tabulated in docs/reference/tether-parameters.md.
The vehicle is held, so the reported force is the cable load at the gland.
X1 length, diameter and strength stay provisional; these checks use that model.
"""

import math
import unittest

import numpy as np

from qysim.physics import G
from qysim.tether import TetherParams
from qysim.tether_reference import (
    case_by_name,
    run_from_bight,
    settle_on_curve,
    specific_weight_n_per_m,
    steady_current_cable,
    upward_catenary,
)
from qysim.vehicles import X1_TETHER_PARAMETERS


def _sag(points: np.ndarray, depth: float) -> float:
    return depth - float(points[:, 2].min())


class TetherCalibration(unittest.TestCase):
    def test_public_coefficients_are_labelled_and_x1_cable_stays_provisional(self):
        """Cylinder added mass and the adopted drag coefficients are published literature.

        Diameter, length and breaking strength stay a single reseller listing.
        Nothing in the table is an X1 measurement.
        """
        published = ("added_mass_normal", "cd_normal", "cd_tangent")
        for key in published:
            self.assertEqual(X1_TETHER_PARAMETERS[key]["level"], "published")
        self.assertEqual(X1_TETHER_PARAMETERS["cd_normal"]["value"], 1.25)
        self.assertEqual(X1_TETHER_PARAMETERS["cd_tangent"]["value"], 0.02)
        self.assertEqual(X1_TETHER_PARAMETERS["added_mass_normal"]["value"], 1.0)
        for key in ("diameter", "max_length", "breaking_n"):
            self.assertEqual(X1_TETHER_PARAMETERS[key]["level"], "reseller")
        self.assertEqual(X1_TETHER_PARAMETERS["density"]["level"], "estimated")
        levels = {item["level"] for item in X1_TETHER_PARAMETERS.values()}
        self.assertNotIn("measured", levels)

    def test_fresh_neutral_mass_and_seawater_wet_weight(self):
        """Air weight follows the fresh-water-neutral density; seawater wet weight is the remainder."""
        params = TetherParams()
        area = math.pi * (0.0095 / 2.0) ** 2
        self.assertAlmostEqual(params.mass, 1000.0 * area, places=6)
        self.assertAlmostEqual(params.mass, 0.070882, places=5)
        self.assertAlmostEqual(params.wet_weight, (1000.0 - 1025.0) * area, places=8)
        self.assertAlmostEqual(specific_weight_n_per_m(params), params.wet_weight * G, places=9)
        self.assertAlmostEqual(specific_weight_n_per_m(params), -0.017384, places=5)

    def test_still_50m_matches_the_upward_catenary(self):
        """50 m paid out, no current, ends 40 m apart at 20 m depth.

        Closed-form sag is 13.272 m and the gland force is [-0.294, 0, -0.435] N.
        The solver, started on that curve, keeps the sag and the horizontal force.
        """
        case = case_by_name("still-50m")
        params = TetherParams()
        reference, force = upward_catenary(case, params)
        shot, shot_force = steady_current_cable(case, params)
        self.assertAlmostEqual(_sag(reference, case.depth_m), 13.272, delta=0.01)
        self.assertAlmostEqual(float(force[0]), -0.294, delta=0.002)
        self.assertAlmostEqual(float(force[2]), -0.435, delta=0.002)
        self.assertAlmostEqual(_sag(shot, case.depth_m), _sag(reference, case.depth_m), delta=0.02)
        self.assertLess(float(np.linalg.norm(shot_force - force)), 0.02)
        tether = settle_on_curve(case, reference, 20.0)
        sag = _sag(tether.x, case.depth_m)
        gland = tether.force_on_rov
        self.assertFalse(tether.broken)
        self.assertAlmostEqual(tether.length, 50.0, places=6)
        self.assertAlmostEqual(sag, 13.272, delta=0.05)
        self.assertAlmostEqual(float(gland[0]), -0.294, delta=0.01)
        self.assertAlmostEqual(float(gland[1]), 0.0, delta=0.01)
        self.assertAlmostEqual(float(gland[2]), -0.424, delta=0.02)
        self.assertLess(abs(float(gland[2]) / force[2] - 1.0), 0.04)

    def test_cross_50m_matches_the_steady_cable(self):
        """50 m paid out in a 0.5 kn eastward current. Same ends as the still-water case.

        Steady bow is 13.26 m east and the gland load magnitude is 6.89 N.
        """
        case = case_by_name("cross-50m")
        params = TetherParams()
        reference, force = steady_current_cable(case, params)
        bow = float(reference[:, 1].max())
        self.assertAlmostEqual(bow, 13.259, delta=0.02)
        self.assertAlmostEqual(float(np.linalg.norm(force)), 6.890, delta=0.02)
        tether = settle_on_curve(case, reference, 20.0)
        gland = tether.force_on_rov
        self.assertFalse(tether.broken)
        self.assertAlmostEqual(float(tether.x[:, 1].max()), 13.264, delta=0.03)
        self.assertAlmostEqual(float(np.linalg.norm(gland)), 6.876, delta=0.05)
        self.assertLess(abs(float(tether.x[:, 1].max()) / bow - 1.0), 0.01)
        self.assertLess(abs(float(np.linalg.norm(gland)) / np.linalg.norm(force) - 1.0), 0.02)
        self.assertLess(float(gland[0]), 0.0)
        self.assertGreater(float(gland[1]), 0.0)

    def test_cross_100m_matches_the_steady_cable(self):
        """100 m paid out in the same 0.5 kn current, ends 70 m apart at 25 m depth.

        Steady bow is 31.93 m east and the gland load magnitude is 9.52 N.
        Twice the cable at the same speed does not double the gland load: the
        extra length lies more nearly across the current but the end slope stays moderate.
        """
        case = case_by_name("cross-100m")
        params = TetherParams()
        reference, force = steady_current_cable(case, params)
        bow = float(reference[:, 1].max())
        self.assertAlmostEqual(bow, 31.935, delta=0.03)
        self.assertAlmostEqual(float(np.linalg.norm(force)), 9.518, delta=0.03)
        tether = settle_on_curve(case, reference, 25.0)
        gland = tether.force_on_rov
        self.assertFalse(tether.broken)
        self.assertAlmostEqual(tether.length, 100.0, places=6)
        self.assertAlmostEqual(float(tether.x[:, 1].max()), 31.947, delta=0.05)
        self.assertAlmostEqual(float(np.linalg.norm(gland)), 9.486, delta=0.06)
        self.assertLess(abs(float(tether.x[:, 1].max()) / bow - 1.0), 0.01)
        self.assertLess(abs(float(np.linalg.norm(gland)) / np.linalg.norm(force) - 1.0), 0.02)

    def test_cross_50m_bight_reaches_the_steady_bow(self):
        """The solver's own slack curve, not the reference shape, settles onto the same bow.

        One hundred seconds is enough at 0.5 kn. The still-water arch is not repeated
        here: its driving force is only 0.017 N/m, so the transient is much longer
        than the steady-shape check above.
        """
        case = case_by_name("cross-50m")
        tether = run_from_bight(case, 100.0)
        gland = tether.force_on_rov
        self.assertFalse(tether.broken)
        self.assertAlmostEqual(tether.length, 50.0, places=6)
        self.assertAlmostEqual(float(tether.x[:, 1].max()), 13.28, delta=0.15)
        self.assertAlmostEqual(float(np.linalg.norm(gland)), 6.86, delta=0.15)
        self.assertLess(float(gland[2]), 0.25)


if __name__ == "__main__":
    unittest.main()
