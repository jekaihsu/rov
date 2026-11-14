"""Shared sensor layer: bitwise regression with imperfections off, and the realistic sensor models.

The regression runs the current engine with ``SensorConfig(ideal=True)`` next to a frozen copy of the
pre-layer engine and controller (tests/legacy_engine_reference.py) and requires identical bytes for the
vehicle state, thruster commands and every telemetry surface. The other tests exercise the realistic path.
"""
import copy
import math
import unittest

import numpy as np

from qysim.engine import Simulator
from qysim.physics import q_from_euler
from qysim.sensors import SensorConfig, raycast_many
from tests.legacy_engine_reference import LegacySimulator

NAV = "QYRovNavigationManage"


def scrub(value):
    """Drop wall-clock timestamps, which differ between two calls by design."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k not in ("timestamp", "time")}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def drive(sim, i):
    """Scripted pilot: unlock, sticks, depth keeping, all assist levels and both control modes."""
    rc = sim.rc_physical
    rc.rc_lock = 0 if i > 5 else 1
    rc.keep_depth = int((i // 150) % 2 == 1)
    rc.left_switch = (i // 233) % 2
    rc.assist = (i // 120) % 3
    rc.profile = ("normal", "cine", "sport")[(i // 300) % 3]
    surge = 1500 + int(400 * math.sin(i / 37.0)) if (i // 60) % 3 else 1500
    rc.set_channel("right_ud", surge)
    rc.set_channel("left_lr", 1500 + (300 if (i // 90) % 4 == 1 else 0))
    rc.set_channel("left_wave", 1500 + (250 if (i // 75) % 5 == 2 else 0))
    rc.set_channel("right_wave", 1500 + (-200 if (i // 110) % 3 == 2 else 0))


class SensorRegressionTests(unittest.TestCase):
    def compare(self, key, steps, sdk_nav=False):
        ideal = SensorConfig(ideal=True)
        new = Simulator(key, 7, sensor_config=ideal)
        old = LegacySimulator(key, 7, sensor_config=ideal)
        if sdk_nav:
            for sim in (new, old):
                sim.sdk_call(NAV, "init_dr", [], {})
        for i in range(steps):
            for sim in (new, old):
                drive(sim, i)
            if sdk_nav and i == 40:
                lat, lng = new.latlng()
                for sim in (new, old):
                    sim.sdk_call(NAV, "start_h_navi", ["DVL", lat + 4e-5, lng + 2e-5, 6.0], {})
            new.step()
            old.step()
            for name in ("pos", "q", "vel", "omega", "thrust"):
                self.assertEqual(getattr(new.vehicle.s, name).tobytes(), getattr(old.vehicle.s, name).tobytes(),
                                 f"{key} step {i} {name}")
            self.assertEqual(new.controller.last_wrench.tobytes(), old.controller.last_wrench.tobytes())
            if i % 25 == 0:
                self.assertEqual(scrub(new.sdk_status()), scrub(old.sdk_status()))
                for which in ("50hz", "10hz"):
                    self.assertEqual(scrub(new.hf_status(which)), scrub(old.hf_status(which)))
                for method in ("get_rov_data", "get_navigation_status"):
                    self.assertEqual(scrub(new.sdk_call(NAV, method, [], {})),
                                     scrub(old.sdk_call(NAV, method, [], {})))
                state = new.viewer_state()
                self.assertIn("sensors", state)
                del state["sensors"]
                self.assertEqual(scrub(state), scrub(old.viewer_state()))

    def test_ideal_sensors_match_frozen_engine_bitwise(self):
        for key in ("jacket_inspection", "coral_reef", "hull_inspection"):
            with self.subTest(key=key):
                self.compare(key, 700)

    def test_ideal_sensors_match_frozen_autopilot_bitwise(self):
        self.compare("open_water", 300, sdk_nav=True)

    def test_ideal_posture_reset_and_init_dr_match(self):
        new = Simulator("open_water", 2, sensor_config=SensorConfig(ideal=True))
        old = LegacySimulator("open_water", 2, sensor_config=SensorConfig(ideal=True))
        for sim in (new, old):
            sim.vehicle.s.q = q_from_euler(0.1, 0.2, 1.3)
            sim.sdk_call("QYRovParameterManage", "set_rov_posture_original", [], {})
        self.assertEqual(new.controller.q_hold.tobytes(), old.controller.q_hold.tobytes())
        self.assertEqual(scrub(new.sdk_call(NAV, "init_dr", [24.3, 120.4], {})),
                         scrub(old.sdk_call(NAV, "init_dr", [24.3, 120.4], {})))


def hover(sim, keep_depth=True):
    rc = sim.rc_physical
    rc.rc_lock = 0
    rc.keep_depth = int(keep_depth)


def calm(sim):
    for layer in ("surface_kn", "mid_kn", "bottom_kn"):
        setattr(sim.world.current, layer, 0.0)
    sim.world.current.turbulence = 0.0


def relocate(sim, pos, reset_sensors=True):
    """Place the vehicle and re-lay a slack tether to it, as if it had been flown there."""
    from qysim.physics import q_rot
    from qysim.tether import Tether
    sim.vehicle.s.pos = np.asarray(pos, float).copy()
    sim.vehicle.s.vel[:] = 0.0
    sim.vehicle.s.omega[:] = 0.0
    gland_body = np.asarray(sim.vehicle.definition.gland_body)
    gland = sim.vehicle.s.pos + q_rot(sim.vehicle.s.q, gland_body)
    sim.tether = Tether(sim.world, np.array(sim.scenario.spool_pos, float), gland, sim.scenario.tether_length)
    sim.tether.gland_body = gland_body
    sim.tether.settle(1.0, sim.vehicle.s.pos, sim.vehicle.s.q)
    sim.controller.depth_hold = None
    if reset_sensors:
        sim.sensors.reset(sim)
    else:
        sim.sensors.frame.depth = sim.sensors._depth_reading(sim, noise=False)


def leg_point(sim, depth, name="J leg A"):
    leg = next(o for o in sim.world.obstacles if o.name == name)
    a, b = np.asarray(leg.p0, float), np.asarray(leg.p1, float)
    return leg, a + (b - a) * (depth - a[2]) / (b[2] - a[2])


class SensorModelTests(unittest.TestCase):
    def test_realistic_layer_is_the_default_and_deterministic(self):
        a = Simulator("jacket_inspection", 11)
        b = Simulator("jacket_inspection", 11)
        self.assertFalse(a.sensors.ideal)
        for sim in (a, b):
            hover(sim)
            for _ in range(200):
                sim.step()
        self.assertEqual(a.viewer_state()["sensors"], b.viewer_state()["sensors"])
        self.assertEqual(a.vehicle.s.pos.tobytes(), b.vehicle.s.pos.tobytes())
        c = Simulator("jacket_inspection", 12)
        self.assertNotEqual(a.sensors.zero_offset, c.sensors.zero_offset)

    def test_depth_quantised_noisy_and_density_scaled(self):
        sim = Simulator("open_water", 3)
        sim.vehicle.s.pos[2] = 30.0
        readings = [sim.sensors._depth_reading(sim) for _ in range(400)]
        steps = np.round(np.asarray(readings) / 0.002, 6)
        self.assertTrue(np.allclose(steps, np.round(steps)))
        self.assertLess(np.std(readings), 0.006)
        self.assertGreater(np.std(readings), 0.001)
        wrong = Simulator("open_water", 3, sensor_config=SensorConfig(water_setting="fresh"))
        wrong.vehicle.s.pos[2] = 30.0
        offset = wrong.sensors.zero_offset
        self.assertAlmostEqual(wrong.sensors._depth_reading(wrong, noise=False) - offset, 30.0 * 1029 / 997,
                               delta=0.003)
        pool = Simulator("tutorial_pool", 3)
        self.assertEqual(pool.sensors.density_ratio, 1.0)

    def test_gyro_only_heading_drifts_at_the_specified_rate(self):
        sim = Simulator("open_water", 5, sensor_config=SensorConfig(mag_rate_hz=1e-6))
        start = sim.sensors.yaw_est - sim.vehicle.euler[2]
        for _ in range(6000):
            sim.sensors.step(0.01, sim)
        drift = math.degrees(abs(sim.sensors.yaw_est - sim.vehicle.euler[2] - start))
        self.assertGreater(drift, 0.05)
        self.assertLess(drift, 0.5)

    def test_deviation_is_cube_law_in_the_far_field(self):
        sim = Simulator("hull_inspection", 1)
        steel = sim.sensors.steel
        hull = sim.world.obstacles[0]
        centre = np.asarray(hull.center, float)
        b1 = np.linalg.norm(steel.anomaly(centre + np.array([0.0, 400.0, 0.0]))[:2])
        b2 = np.linalg.norm(steel.anomaly(centre + np.array([0.0, 800.0, 0.0]))[:2])
        self.assertAlmostEqual(b1 / b2, 8.0, delta=0.4)

    def test_deviation_magnitudes_near_a_jacket_leg(self):
        sim = Simulator("jacket_inspection", 1)
        leg, centre = leg_point(sim, 12.0)

        def worst(distance):
            angles = np.linspace(0, 2 * math.pi, 36, endpoint=False)
            return max(abs(math.degrees(sim.sensors.steel.deviation(
                centre + distance * np.array([math.cos(a), math.sin(a), 0.0]))[0])) for a in angles)
        # Order of magnitude per research notes §2: tens of degrees beside steel, a few degrees at 10+ m.
        self.assertGreater(worst(leg.radius + 1.5), 10.0)
        self.assertLess(worst(leg.radius + 1.5), 60.0)
        self.assertLess(worst(60.0), 2.0)
        start = sim.sensors.steel.deviation(np.asarray(sim.scenario.start_pos, float))[0]
        self.assertLess(abs(math.degrees(start)), 3.0)

    def heading_hold_near_leg(self, deviation):
        sim = Simulator("jacket_inspection", 4, sensor_config=SensorConfig(deviation=deviation))
        calm(sim)
        hover(sim)
        for _ in range(300):
            sim.step()
        leg, centre = leg_point(sim, 12.0)
        best = None
        for a in np.linspace(0, 2 * math.pi, 36, endpoint=False):
            p = centre + (leg.radius + 1.5) * np.array([math.cos(a), math.sin(a), 0.0])
            d = abs(sim.sensors.steel.deviation(p)[0])
            if best is None or d > best[0]:
                best = (d, p)
        # Equivalent to having flown in from clean water: the estimator keeps its state, the field changes.
        relocate(sim, best[1], reset_sensors=False)
        yaw0 = sim.vehicle.euler[2]
        worst = 0.0
        # Heading hold stays engaged for 60 s with no yaw input; record the largest true heading excursion.
        for _ in range(6000):
            sim.step()
            error = (sim.vehicle.euler[2] - yaw0 + math.pi) % (2 * math.pi) - math.pi
            worst = max(worst, math.degrees(abs(error)))
        return worst, sim

    def test_heading_hold_runs_away_near_a_jacket_leg_only_with_deviation(self):
        drift_on, sim = self.heading_hold_near_leg(True)
        drift_off, _ = self.heading_hold_near_leg(False)
        self.assertGreater(drift_on, 8.0)
        self.assertLess(drift_off, 1.5)
        self.assertGreater(drift_on, 5 * drift_off)

    def test_strong_anomaly_triggers_yaw_realignment(self):
        # Re-alignment is a random event (mean 6 s while the anomaly is strong); each seeded run of 30 s has
        # roughly a 99 % chance, so require it in at least two of three seeds.
        realigned = 0
        for seed in (2, 3, 4):
            sim = Simulator("incident_compass", seed)
            calm(sim)
            hover(sim)
            sim.sensors.set_fault("compass", 1.0)
            for _ in range(3000):
                sim.step()
            if sim.sensors.realigned_at is not None:
                realigned += 1
                self.assertTrue(any("重新對準" in line["text"] for line in sim.log))
        self.assertGreaterEqual(realigned, 2)

    def test_position_hold_fails_when_the_dvl_is_too_high(self):
        sim = Simulator("incident_wreck", 3)
        calm(sim)
        relocate(sim, [30.0, 0.0, 20.0])
        hover(sim)
        sim.rc_physical.assist = 2
        for _ in range(300):
            sim.step()
        state = sim.viewer_state()
        self.assertEqual(state["sensors"]["dvl"]["status"], "lost")
        self.assertEqual(state["sensors"]["dvl"]["reason"], "too_high")
        self.assertEqual(state["assist"]["level"], 0)
        self.assertFalse(state["assist"]["holding"])
        self.assertIsNone(state["sensors"]["dvl"]["ground_speed_kn"])
        self.assertEqual(sim.sdk_status()["Accessories_Status"]["DVL_Status"], "OffLine")
        dvl = sim.sdk_call(NAV, "get_rov_data", [["dvl"]], {})["data"]["dvl"]
        self.assertFalse(dvl["velocity_valid"])
        self.assertEqual(sim.sdk_status()["QDVL"]["QDVL_Xspeed"], 0.0)

    def test_position_hold_in_the_jacket_scenario_needs_bottom_lock(self):
        sim = Simulator("jacket_inspection", 3)
        calm(sim)
        relocate(sim, [0.0, -8.0, 26.0])
        hover(sim)
        sim.rc_physical.assist = 2
        for _ in range(300):
            sim.step()
        self.assertEqual(sim.viewer_state()["sensors"]["dvl"]["status"], "locked")
        self.assertTrue(sim.viewer_state()["assist"]["holding"])
        self.assertEqual(sim.sdk_status()["Accessories_Status"]["DVL_Status"], "OnLine")
        sim.sensors.set_fault("dvl", 1.0)
        for _ in range(200):
            sim.step()
        self.assertEqual(sim.viewer_state()["sensors"]["dvl"]["status"], "lost")
        self.assertFalse(sim.viewer_state()["assist"]["holding"])
        frozen = sim.sensors.frame.pos.copy()
        sim.vehicle.s.vel[0] = 0.3
        for _ in range(100):
            sim.step()
        self.assertEqual(sim.sensors.frame.pos[:2].tobytes(), frozen[:2].tobytes())
        sim.sensors.clear_fault("dvl")
        for _ in range(200):
            sim.step()
        self.assertEqual(sim.viewer_state()["sensors"]["dvl"]["status"], "locked")

    def test_dvl_hold_matches_tank_footage_and_drifts_on_loss(self):
        # Targets: research_notes/洋流與波浪對ROV作業/real_dive_footage.md (a BlueROV2 + DVL tank demo and FIFISH
        # depth hold; neither is X1). DVL hold wanders about +-3-5 cm, depth hold stays within +-0.06 m, and
        # without DVL input the vehicle drifts 0.55-0.7 m in 3 s. The current here is 0.5 kn, not the tank's jet.
        sim = Simulator("jacket_inspection", 3)
        calm(sim)
        for layer in ("surface_kn", "mid_kn", "bottom_kn"):
            setattr(sim.world.current, layer, 0.5)
        relocate(sim, [0.0, -8.0, 26.0])
        hover(sim)
        sim.rc_physical.assist = 2
        for _ in range(1000):
            sim.step()
        anchor = sim.vehicle.s.pos.copy()
        wander, depth_error = 0.0, 0.0
        for _ in range(3000):
            sim.step()
            wander = max(wander, float(np.linalg.norm(sim.vehicle.s.pos[:2] - anchor[:2])))
            depth_error = max(depth_error, abs(float(sim.vehicle.s.pos[2] - anchor[2])))
        self.assertTrue(sim.viewer_state()["assist"]["holding"])
        self.assertLess(wander, 0.08)
        self.assertLess(depth_error, 0.06)
        sim.sensors.set_fault("dvl", 1.0)
        lost_at = sim.vehicle.s.pos.copy()
        for _ in range(300):
            sim.step()
        drift = float(np.linalg.norm(sim.vehicle.s.pos[:2] - lost_at[:2]))
        self.assertGreater(drift, 0.3)
        self.assertLess(drift, 1.0)

    def test_dvl_reacquire_needs_a_climb_after_too_low(self):
        sim = Simulator("open_water", 3)
        calm(sim)
        sim.vehicle.s.pos = np.array([0.0, 0.0, 25.0 - 0.27])
        sim.sensors.reset(sim)
        self.assertEqual(sim.sensors.frame.dvl_status, "lost")
        self.assertEqual(sim.sensors.frame.dvl_reason, "too_low")
        sim.vehicle.s.pos[2] = 25.0 - 0.6
        for _ in range(100):
            sim.sensors.step(0.01, sim)
        self.assertEqual(sim.sensors.frame.dvl_status, "lost")
        sim.vehicle.s.pos[2] = 25.0 - 1.2
        for _ in range(100):
            sim.sensors.step(0.01, sim)
        self.assertEqual(sim.sensors.frame.dvl_status, "locked")

    def test_dvl_loses_lock_over_kelp_and_in_dense_silt(self):
        sim = Simulator("open_water", 3)
        calm(sim)
        sim.vehicle.s.pos = np.array([0.0, 0.0, 22.0])
        sim.sensors.reset(sim)
        for k in range(6):   # a dense silt-out between the vehicle and the bed (silt.py puffs)
            sim.world.emit_silt(sim.vehicle.s.pos + [0, 0, 0.8 * k], 20.0, source="test")
        statuses = set()
        for _ in range(300):
            sim.sensors.step(0.01, sim)
            statuses.add(sim.sensors.frame.dvl_status)
        self.assertIn("lost", statuses)
        self.assertIn(sim.sensors.frame.dvl_reason, ("silt", None))
        steep = Simulator("monopile_current", 3)
        calm(steep)
        steep.vehicle.s.pos = np.array([11.3, 0.0, 12.0])
        steep.vehicle.s.q = q_from_euler(0.0, math.radians(-80), 0.0)
        steep.sensors.reset(steep)
        self.assertEqual(steep.sensors.frame.dvl_status, "lost")

    def test_dvl_scale_error_and_dead_reckoning_drift_are_bounded(self):
        sim = Simulator("open_water", 9)
        calm(sim)
        hover(sim)
        sim.rc_physical.assist = 1
        relocate(sim, [0.0, 0.0, 15.0])
        sim.rc_physical.set_channel("right_ud", 1800)
        for _ in range(3000):
            sim.step()
        travelled = np.linalg.norm(sim.vehicle.s.pos[:2])
        error = np.linalg.norm(sim.sensors.frame.pos[:2] - sim.vehicle.s.pos[:2])
        self.assertGreater(travelled, 5.0)
        self.assertGreater(error, 0.0)
        self.assertLess(error / travelled, 0.06)
        self.assertLessEqual(abs(sim.sensors.dvl_scale), 0.01)

    def test_altimeter_cone_blind_zone_and_terrain(self):
        sim = Simulator("coral_reef", 3)
        calm(sim)
        p = np.array([20.0, 0.0, 0.0])
        p[2] = sim.world.depth_at(p) - 0.2
        sim.vehicle.s.pos = p
        sim.sensors._sample_echo(sim)
        self.assertIsNone(sim.sensors.frame.altitude)
        self.assertTrue(sim.sensors.frame.altitude_blind)
        self.assertEqual(sim.sdk_status()["Altitude"], 0.3)
        p[2] = sim.world.depth_at(p) - 5.0
        sim.vehicle.s.pos = p
        sim.sensors._sample_echo(sim)
        reading = sim.sensors.frame.altitude
        self.assertIsNotNone(reading)
        self.assertLess(reading, 5.0 + 0.1)
        flat = sim.world.seabed_depth - p[2]
        self.assertNotAlmostEqual(reading, flat, delta=0.05)

    def test_cone_reads_nearest_echo_on_a_slope(self):
        sim = Simulator("open_water", 3)
        origin = np.array([[0.0, 0.0, 15.0]])
        straight, hit, _, _ = raycast_many(sim.world, origin, np.array([[0.0, 0.0, 1.0]]), 100.0)
        self.assertTrue(hit[0])
        self.assertAlmostEqual(straight[0], 10.0, delta=0.05)
        sim.vehicle.s.pos = origin[0].copy()
        sim.vehicle.s.q = q_from_euler(math.radians(10), 0.0, 0.0)
        sim.sensors._sample_echo(sim)
        tilted = sim.sensors.frame.altitude
        self.assertLess(tilted, 10.0 / math.cos(math.radians(10)) - 0.05)

    def test_false_returns_from_fish(self):
        sim = Simulator("coral_reef", 3)
        school = sim.world.fish_schools[0]
        sim.vehicle.s.pos = np.asarray(school["pos"], float) - np.array([0.0, 0.0, 6.0])
        sim.vehicle.s.q = q_from_euler(0.0, 0.0, 0.0)
        readings = []
        for _ in range(60):
            sim.sensors._sample_echo(sim)
            readings.append(sim.sensors.frame.altitude)
        short = [r for r in readings if r is not None and r < 5.0]
        self.assertTrue(short)
        self.assertLess(len(short), len(readings))

    def test_instructor_style_faults(self):
        sim = Simulator("open_water", 3)
        calm(sim)
        hover(sim)
        before = sim.sensors.frame.depth
        sim.sensors.set_fault("depth_sensor", 1.0)
        for _ in range(500):
            sim.step()
        self.assertGreater(sim.sensors.fault_depth_offset, 0.05)
        sim.sensors.clear_fault("depth_sensor")
        self.assertEqual(sim.sensors.fault_depth_offset, 0.0)
        sim.sensors.set_fault("altimeter", 1.0)
        values = set()
        for _ in range(20):
            sim.sensors._sample_echo(sim)
            values.add(sim.sensors.frame.altitude)
        self.assertGreater(len(values), 1)
        self.assertIn("altimeter", sim.viewer_state()["sensors"]["faults"])
        ideal = Simulator("open_water", 3, sensor_config=SensorConfig(ideal=True))
        with self.assertRaises(ValueError):
            ideal.sensors.set_fault("dvl", 1.0)
        self.assertIsNotNone(before)

    def test_estimated_values_reach_telemetry(self):
        sim = Simulator("jacket_inspection", 6)
        calm(sim)
        hover(sim)
        for _ in range(200):
            sim.step()
        state = sim.viewer_state()["sensors"]
        status = sim.sdk_status()
        self.assertEqual(status["Depth"], round(sim.sensors.frame.depth, 2))
        self.assertEqual(status["Compass"], int(round(math.degrees(sim.sensors.frame.yaw) % 360)))
        hf = sim.hf_status("50hz")["data"]
        self.assertEqual(hf["quaternion"]["w"], float(sim.sensors.frame.q[0]))
        rov = sim.sdk_call(NAV, "get_rov_data", [["rov", "dvl"]], {})["data"]
        self.assertEqual(rov["rov"]["depth"], state["depth"])
        self.assertIn("lock", rov["dvl"])
        self.assertEqual(set(state["dvl"]), {"status", "reason", "altitude", "ground_speed_kn"})
        copy.deepcopy(state)


if __name__ == "__main__":
    unittest.main()
