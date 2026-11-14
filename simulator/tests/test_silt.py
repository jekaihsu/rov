"""Silt model: jet source direction, altitude and threshold; mass budget; settling; clearing; optics."""
import math
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_rot
from qysim.silt import GRAIN_CLASSES, SETTLING, settling_velocity
from qysim.world import World

DOWN = np.array([0.0, 0.0, 1.0])
UP = np.array([0.0, 0.0, -1.0])
NORTH = np.array([1.0, 0.0, 0.0])


def mud_world(seabed=20.0, kind="mud"):
    world = World(seabed)
    world.configure_silt(kind)
    world.visibility_m = 7.0
    return world


def jet_rate(world, altitude, direction, thrust=148.0):
    origin = np.array([[0.0, 0.0, world.seabed_depth - altitude]])
    rate, tau, impact, x_bed, _ = world.silt_field.jet_erosion(origin, np.array([direction]), np.array([thrust]))
    return float(rate[0]), float(tau[0]), impact[0], float(x_bed[0])


def calm(world):
    world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 0.0
    world.current.turbulence = 0.0


def run_transport(world, seconds, vehicles=None, dt=0.1):
    for _ in range(int(round(seconds / dt))):
        world.time += dt
        world.silt_field.step_transport(dt, vehicles)


class JetSourceTests(unittest.TestCase):
    def test_jet_toward_bed_erodes_and_away_does_not(self):
        world = mud_world()
        down, _, _, _ = jet_rate(world, 0.5, DOWN)
        up, _, _, _ = jet_rate(world, 0.5, UP)
        self.assertGreater(down, 1e-3)
        self.assertEqual(up, 0.0)

    def test_horizontal_jet_is_far_weaker_than_vertical(self):
        world = mud_world()
        down, _, _, _ = jet_rate(world, 0.5, DOWN)
        flat, flat_tau, impact, x_bed = jet_rate(world, 0.5, NORTH)
        self.assertLess(flat, 0.05 * down)
        # The weak horizontal footprint lies metres downstream along the jet, not under the outlet.
        if flat_tau > 0:
            self.assertGreater(impact[0], 1.0)
            self.assertGreater(x_bed, 1.0)

    def test_erosion_falls_with_altitude(self):
        world = mud_world()
        rates = [jet_rate(world, h, DOWN)[0] for h in (0.5, 1.0, 2.0, 4.0)]
        self.assertTrue(all(a > b for a, b in zip(rates, rates[1:])), rates)
        self.assertGreater(rates[0], 4.0 * rates[2])

    def test_impact_point_is_on_the_jet_axis_not_the_vehicle(self):
        world = mud_world()
        slant = np.array([1.0, 0.0, 1.0]) / math.sqrt(2.0)
        _, _, impact, x_bed = jet_rate(world, 1.0, slant)
        self.assertAlmostEqual(impact[2], world.seabed_depth, places=6)
        self.assertAlmostEqual(impact[0], 1.0, delta=0.1)
        self.assertAlmostEqual(x_bed, math.sqrt(2.0), delta=0.1)

    def test_critical_shear_threshold_and_rock(self):
        world = mud_world()
        weak, tau, _, _ = jet_rate(world, 4.0, DOWN, thrust=5.0)
        self.assertLess(tau, world.silt_field.bed["tau_cr"])
        self.assertEqual(weak, 0.0)
        rock = mud_world(kind="rock")
        self.assertEqual(jet_rate(rock, 0.3, DOWN)[0], 0.0)
        gravel = mud_world(kind="gravel")
        self.assertLess(jet_rate(gravel, 1.0, DOWN)[0], 0.01 * jet_rate(world, 1.0, DOWN)[0])

    def test_rock_never_silts_under_full_thrust_or_contact(self):
        world = mud_world(kind="rock")
        jets = [(np.array([0.0, 0.0, world.seabed_depth - 0.4]), DOWN, 148.0)] * 4
        for _ in range(300):
            world.step(0.01, [{"id": "v1", "pos": np.array([0.0, 0.0, 19.6]), "jets": jets}])
        world.silt_field.contact(np.array([0.0, 0.0, 19.8]), 1.0, "v1", impact=True)
        self.assertEqual(world.silt_field.emitted, 0.0)
        self.assertEqual(world.silt_concentration_at([0, 0, 19.5]), 0.0)

    def test_single_vehicle_simulator_step_passes_thrusters(self):
        sim = Simulator("open_water", 1)
        sim.world.configure_silt("mud")
        sim.vehicle.s.pos[:] = [0.0, 0.0, sim.world.seabed_depth - 0.5]
        tmax = sim.vehicle.p.thruster_max
        # T1/T2 push up and T3/T4 push down at the bow/stern pairs: an ascent command throws all four jets down.
        sim.vehicle.s.thrust[:] = np.array([1.0, 1.0, -1.0, -1.0, 0.0, 0.0]) * tmax
        jets = sim.world_source()["jets"]
        self.assertTrue(all(jet[1][2] > 0.5 for jet in jets[:4]))
        sim.world.step(0.05, [sim.world_source()])
        self.assertGreater(sim.world.silt_field.emitted, 0.0)
        sim.step(0.01)
        self.assertIn("turbidity", sim.viewer_state())


class TransportTests(unittest.TestCase):
    def test_mass_is_conserved_through_settling_drift_merge_and_range(self):
        world = mud_world()
        world.current.surface_kn = world.current.mid_kn = world.current.bottom_kn = 1.0
        field = world.silt_field
        field.params["max_puffs"] = 12
        rng = np.random.default_rng(3)
        for i in range(40):
            pos = np.array([rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(18.5, 19.8)])
            field.emit_mix(pos, 0.02, field.bed["mix"], 0.4, 0.3, f"src{i}")
        self.assertLessEqual(field.count, 12)
        vehicle = [np.array([0.0, 0.0, 19.0])]
        run_transport(world, 120.0, vehicle)
        budget = field.budget()
        total = budget["suspended"] + budget["deposited"] + budget["removed"]
        self.assertAlmostEqual(total, budget["emitted"], places=9)
        self.assertGreater(budget["deposited"], 0.0)

    def test_settling_time_orders_by_grain_class(self):
        self.assertTrue(SETTLING[0] > SETTLING[1] > SETTLING[2])
        self.assertAlmostEqual(settling_velocity(15e-6), 1.65 * 9.81 * 15e-6 ** 2 / (18 * 1.05e-6), delta=2e-5)
        half_lives = []
        for grain in range(len(GRAIN_CLASSES)):
            world = mud_world()
            calm(world)
            world.silt_field.add_puff([0, 0, 19.0], 1.0, grain, 0.5, 0.3)
            elapsed = 0.0
            while world.silt_field.suspended() > 0.5 and elapsed < 4000:
                run_transport(world, 1.0)
                elapsed += 1.0
            half_lives.append(elapsed)
        self.assertLess(half_lives[0], 60.0)
        self.assertLess(half_lives[0], half_lives[1])
        self.assertLess(half_lives[1], half_lives[2])

    def test_fine_fraction_lingers_minutes_in_slack_water(self):
        world = mud_world()
        calm(world)
        site = np.array([0.0, 0.0, 19.3])
        world.silt_field.emit_mix([0, 0, 19.2], 0.3, world.silt_field.bed["mix"], 0.6, 0.4, "burst")
        run_transport(world, 300.0, [site])
        self.assertLess(world.visibility_at(site), 0.5 * 7.0)

    def test_current_clears_the_site_faster_than_slack_water(self):
        results = {}
        for knots in (0.0, 0.5):
            world = mud_world()
            calm(world)
            world.current.mid_kn = world.current.bottom_kn = knots
            site = np.array([0.0, 0.0, 18.8])
            world.silt_field.emit_mix([0, 0, 19.0], 0.3, world.silt_field.bed["mix"], 0.6, 0.4, "burst")
            run_transport(world, 60.0, [site])
            results[knots] = world.silt_concentration_at(site)
        self.assertGreater(results[0.0], 1.0)
        self.assertLess(results[0.5], 0.2 * results[0.0])

    def test_legacy_clouds_follow_the_puffs(self):
        world = mud_world()
        world.emit_silt([0, 0, 10], 1, "alpha")
        cloud = world.environment_state()["silt_clouds"][0]
        self.assertEqual(set(cloud), {"pos", "strength", "radius", "age", "source"})
        self.assertEqual(cloud["source"], "alpha")
        self.assertTrue(world.environment_state()["silt_puffs"])


class OpticsTests(unittest.TestCase):
    def test_visibility_follows_four_point_eight_over_c(self):
        world = World(50)
        world.configure_silt("mud")
        field = world.silt_field
        clear = 4.8 / 0.07
        for mg_l, expected in ((1.0, 8.4), (10.0, 0.95), (50.0, 0.19)):
            field.bnl_mg_l, field.bnl_height_m = mg_l, 1e9
            self.assertAlmostEqual(world.visibility_at([0, 0, 10], clear), expected, delta=0.06 * expected)

    def test_optical_depth_is_c_times_length_in_uniform_water(self):
        world = World(50)
        world.visibility_m = 4.8
        self.assertAlmostEqual(world.optical_depth([0, 0, 5], [10, 0, 5]), 10.0, places=6)
        world.emit_silt([5, 0, 5], 1.0)
        self.assertGreater(world.optical_depth([0, 0, 5], [10, 0, 5]), 11.0)

    def test_concentration_api_and_no_floor(self):
        world = mud_world()
        world.silt_field.add_puff([0, 0, 19.0], 2.0, 2, 0.5, 0.4)
        concentration = world.silt_concentration_at([0, 0, 19.0])
        self.assertGreater(concentration, 500.0)
        self.assertLess(world.visibility_at([0, 0, 19.0]), 0.02)
        self.assertGreater(world.silt_at([0, 0, 19.0]), 0.99)
        self.assertEqual(world.silt_concentration_at([0, 0, 21.0]), 0.0)


class ValidationTargetTests(unittest.TestCase):
    """Provisional targets from silt_and_visibility.md; docs/reference/silt-validation.md has the numbers."""

    def hold(self, kind, altitude, thrust_pattern, seconds):
        sim = Simulator("open_water", 1)
        world = sim.world
        world.configure_silt(kind)
        calm(world)
        sim.vehicle.s.pos[:] = [0.0, 0.0, world.seabed_depth - altitude]
        sim.vehicle.s.thrust[:] = np.asarray(thrust_pattern, float) * sim.vehicle.p.thruster_max
        camera = sim.vehicle.s.pos + q_rot(sim.vehicle.s.q, np.asarray(sim.vehicle.definition.camera_body))
        for _ in range(int(seconds / 0.01)):
            world.step(0.01, [sim.world_source()])
        return world.visibility_at(camera, 7.0)

    def test_downward_jets_at_half_metre_silt_out_within_three_seconds(self):
        ascent = [1, 1, -1, -1, 0, 0]
        self.assertLess(self.hold("mud", 0.5, ascent, 3.0), 0.5)
        self.assertGreater(self.hold("mud", 2.0, ascent, 3.0), 0.8 * 7.0)
        self.assertGreater(self.hold("mud", 0.5, [0, 0, 0, 0, 1, 1], 3.0), 0.8 * 7.0)
        self.assertGreater(self.hold("rock", 0.5, ascent, 3.0), 6.99)

    def test_harbour_is_more_turbid_near_the_bottom(self):
        sim = Simulator("harbor_inspection", 1)
        world = sim.world
        bed = world.seabed_depth
        near = world.visibility_at([0, 0, bed - 0.5], sim.scenario.visibility_m)
        mid = world.visibility_at([0, 0, bed / 2], sim.scenario.visibility_m)
        self.assertLess(near, 0.6 * mid)
        self.assertGreater(world.silt_concentration_at([0, 0, bed - 0.5]), 0.0)
        self.assertEqual(world.silt_field.seabed_type, "mud")
        self.assertAlmostEqual(world.environment_state()["turbidity"]["c_water"], 4.8 / 7.0, places=3)

    def test_scenario_seabed_types(self):
        self.assertEqual(Simulator("tutorial_pool", 1).world.silt_field.seabed_type, "rock")
        self.assertEqual(Simulator("coral_reef", 1).world.silt_field.seabed_type, "rock")
        self.assertEqual(Simulator("seagrass_meadow", 1).world.silt_field.seabed_type, "sand")
        self.assertEqual(Simulator("open_water", 1).world.silt_field.background_mg_l([[0, 0, 29.9]])[0], 0.0)


class IncidentSiltTests(unittest.TestCase):
    def fly(self, channel, value, seconds):
        sim = Simulator("incident_silt", 1)
        sim.rc_physical.rc_lock = 0
        setattr(sim.rc_physical, channel, value)
        worst = sim.camera_turbidity()["visibility_m"]
        for _ in range(int(seconds / 0.01)):
            sim.step(0.01)
            worst = min(worst, sim.camera_turbidity()["visibility_m"])
        return sim, worst

    def test_take_off_thrust_creates_the_silt_out(self):
        sim, idle = self.fly("left_wave", 1500, 1.0)
        self.assertEqual(sim.world.silt_field.emitted, 0.0)
        self.assertGreater(idle, 1.5)
        self.assertEqual(sim.scenario.visibility_m, 3)
        self.assertEqual(sim.world.silt_field.seabed_type, "fluff")
        sim, worst = self.fly("left_wave", 1900, 1.0)
        self.assertLess(worst, 0.3)
        self.assertGreater(sim.world.silt_field.emitted, 0.05)


if __name__ == "__main__":
    unittest.main()
