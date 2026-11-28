"""Mechanical energy, distributed flotation and relief contact of the lumped cable."""
import unittest

import numpy as np

from qysim import tether_contact, tether_solver
from qysim.ecology import SeabedTerrain
from qysim.physics import RHO
from qysim.tether import Tether, TetherParams
from qysim.world import World


class CableMechanics(unittest.TestCase):
    def test_float_sleeve_adds_mass_and_displaces_water(self):
        for density in (300.0, RHO, 1300.0):
            with self.subTest(density=density):
                p = TetherParams(density=RHO, float_area=0.0001, float_density=density)
                bare = TetherParams(density=RHO)
                self.assertAlmostEqual(p.mass - bare.mass, p.float_area * density)
                self.assertAlmostEqual(p.wet_weight, p.float_area * (density - RHO))

    def test_bend_relaxes_without_an_external_energy_source(self):
        p = TetherParams(segments=2, density=RHO, added_mass_normal=0, reel_mode="hold")
        points = np.array([[0., 0., 8.], [1., 0.6, 8.], [2., 0., 8.]])
        cable = Tether(World(40), points[0], points[-1], 3, p, gland_body=np.zeros(3))
        cable.layout(points)
        mass = cable._node_masses()[0]
        energies = []
        for i in range(301):
            segments = np.diff(cable.x, axis=0)
            length = np.linalg.norm(segments, axis=1)
            cosine = np.dot(*segments) / np.prod(length)
            axial = 0.5 * p.ea * np.sum(np.maximum(length - cable.l0, 0)**2 / cable.l0)
            kinetic = 0.5 * np.sum(mass[:, None] * cable.v**2)
            energies.append(kinetic + axial + p.ei * (1.0 - cosine) / cable.l0.mean())
            cable.step(0.01, i * 0.01, points[-1], np.array([1., 0., 0., 0.]), np.zeros(3))
        self.assertLess(max(energies), energies[0] + 1e-12)
        self.assertLess(energies[-1], 0.9 * energies[0])

    def test_long_span_cannot_pass_through_a_seabed_crest(self):
        world = World(20)
        world.terrain = SeabedTerrain(20, 42, 1.0)
        world.terrain.depths[:] = 20.0
        world.terrain.depths[20, :] = 19.0
        x = np.array([[-10., 0., 19.02], [-5., 0., 19.02], [5., 0., 19.02], [10., 0., 19.02]])
        radius = 0.01
        c = tether_contact.build(world, x, [], False, radius, 0.25, 0.01)
        self.assertTrue(np.any(c.dist0 < 0))
        tether_solver.project(x, False, c.seg, c.s, c.anchor, c.dist0, c.normal, radius)
        probes = np.linspace(x[1], x[2], 501)
        self.assertTrue(np.all(world.seabed_at_many(probes) - probes[:, 2] >= radius - 1e-8))

    def test_rotating_vehicle_carries_offset_gland_and_feels_its_moment(self):
        p = TetherParams(density=RHO, reel_mode="hold")
        offset = np.array([0., 0.4, 0.])
        pos = np.array([5., 0., 8.])
        cable = Tether(World(40), np.array([0., 0.4, 8.]), pos + offset, 5., p, gland_body=offset)
        omega = np.array([0., 0., -0.6])
        wrench = cable.step(0.01, 0., pos, np.array([1., 0., 0., 0.]), np.zeros(3), omega)
        np.testing.assert_allclose(cable.x[-1], pos + offset + 0.01 * np.cross(omega, offset))
        self.assertLess(wrench[0], 0.)
        np.testing.assert_allclose(wrench[3:], np.cross(offset, wrench[:3]))

    def test_long_payouts_replay_identically_in_crossflow(self):
        from qysim.tether_reference import CableCase, run_from_bight

        for length in (60, 120):
            case = CableCase("repeat", length, 0.8 * length, 50., 0.3)
            first = run_from_bight(case, 5.0)
            second = run_from_bight(case, 5.0)
            self.assertFalse(first.broken)
            self.assertTrue(np.isfinite(first.v).all())
            np.testing.assert_array_equal(first.x, second.x)
            np.testing.assert_array_equal(first.force_on_rov, second.force_on_rov)

    def test_deck_friction_resists_both_tender_directions(self):
        from qysim._cable_accel import REEL_DRIVE, REEL_KINETIC, REEL_STATIC
        from qysim.reel import Reel

        for mode in ("pay_out", "haul_in"):
            p = TetherParams(deck_drag_n=3.0)
            line = Reel(p.reel_params(), p.mass, p.max_length, mode).prepare(60.0)
            bare = TetherParams(deck_drag_n=0.0)
            free = Reel(bare.reel_params(), bare.mass, bare.max_length, mode).prepare(60.0)
            self.assertEqual(line[REEL_DRIVE], free[REEL_DRIVE])
            self.assertAlmostEqual(line[REEL_STATIC] - free[REEL_STATIC], 3.0)
            self.assertAlmostEqual(line[REEL_KINETIC] - free[REEL_KINETIC], 3.0)
