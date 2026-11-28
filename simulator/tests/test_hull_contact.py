"""Vehicle contact regressions in NED metres, seconds and body-frame impulses."""
import json
import unittest

import numpy as np

from qysim import scenarios
from qysim.hull_contact import HullContact, NET_TRAVEL
from qysim.physics import Vehicle, q_from_axis_angle, q_from_euler, q_matrix, q_mul
from qysim.world import Box, Cylinder, FieldMesh, ShipHull, Wall, World


class HullContactTests(unittest.TestCase):
    def setUp(self):
        self.vehicle = Vehicle()
        self.vehicle.s.pos[:] = (0., 0., 4.)
        self.hull = HullContact(self.vehicle)
        self.world = World(10.)
        self.t = 0.

    def move(self, dt=.01):
        s = self.vehicle.s
        start, q0 = s.pos.copy(), s.q.copy()
        s.q = q_mul(q0, q_from_axis_angle(s.omega, np.linalg.norm(s.omega) * dt))
        s.pos += self.vehicle.world_velocity() * dt
        self.hull.resolve(self.world, self.vehicle, start, q0, dt, self.t, "pilot")
        self.t += dt

    def clearance(self):
        s = self.vehicle.s
        points = s.pos + self.hull.points @ q_matrix(s.q).T
        return np.min(self.world.sdf_many(points)[0] - self.hull.radii)

    def test_material_restitution_and_energy(self):
        for mat, e in (("steel", .22), ("concrete", .12), ("sand", .04), ("mud", 0.),
                       ("biofouling", .08), ("net", 0.)):
            with self.subTest(mat=mat):
                s = self.vehicle.s
                s.vel[:] = (-1., 0., 0.)
                s.omega[:] = 0.
                normal = np.array([1., 0., 0.])
                self.hull.respond(self.vehicle, np.zeros(3), normal, mat, NET_TRAVEL, .01, True)
                self.assertAlmostEqual(float(s.vel[0]), e)
                s.vel[:] = (-1., .8, .1)
                arm = np.array([-.3, .14, .05])
                before = self.vehicle.M @ s.vel**2
                self.hull.respond(self.vehicle, arm, normal, mat, .005, .01, True)
                after = self.vehicle.M @ s.vel**2 + self.vehicle.I @ s.omega**2
                self.assertLess(after, before)
                self.assertGreater(np.linalg.norm(s.omega), .01)

    def test_sweep_thin_steel_pile_hull_and_wall(self):
        for ob in (Box("plate", (1., 0., 4.), (.002, 5., 3.)),
                   Cylinder("pile", (1., 0., 1.), (1., 0., 8.), .08),
                   Wall("face", (1., 0., 0.), 180.),
                   ShipHull("ship", (2., 0., 0.), 90., 9., 1., 5.)):
            with self.subTest(ob=ob.name):
                self.setUp()
                self.world.obstacles.append(ob)
                self.vehicle.s.vel[0] = 180.
                self.move()
                self.assertLess(self.vehicle.s.pos[0], 1.5)
                self.assertGreaterEqual(self.clearance(), -1e-9)
                event, = self.world.events
                self.assertTrue(event.possible_damage)
                self.assertGreater(event.impulse_ns, 3.)
                json.dumps(event.__dict__)

    def test_sustained_slide(self):
        self.world.obstacles.append(Wall("face", (0., 0., 0.), 0.))
        s = self.vehicle.s
        s.pos[0] = np.max(self.hull.points[:, 0] + self.hull.radii)
        s.vel[1] = 1.
        clearances = []
        for _ in range(60):
            s.vel[0] -= .001
            self.move()
            clearances.append(self.clearance())
        self.assertGreater(s.pos[1], .5)
        self.assertLess(s.vel[1], 1.)
        self.assertGreaterEqual(min(clearances), -1e-9)
        self.assertLess(max(clearances), 5e-5)
        self.assertEqual(len(self.world.events), 1)

    def test_net_load_and_release(self):
        self.world.obstacles.append(Box("panel", (.5, 0., 4.), (.025, 2., 3.), kind="pen_net"))
        self.vehicle.s.vel[0] = 1.5
        deepest = 0.
        reversed_motion = False
        for _ in range(100):
            self.move()
            deepest = max(deepest, -self.clearance())
            reversed_motion |= self.vehicle.s.vel[0] < -.05
        self.assertGreater(deepest, .01)
        self.assertLessEqual(deepest, NET_TRAVEL + 1e-9)
        self.assertTrue(reversed_motion)
        self.assertIsNone(self.hull.net_load)
        self.assertEqual(len(self.world.events), 1)

    def test_terrain_touch_emits_local_silt(self):
        self.world.configure_habitat("harbor", 7)
        self.world.configure_silt("mud")
        self.vehicle.s.pos[:] = (0., 0., 9.)
        self.vehicle.s.vel[2] = 150.
        self.move()
        self.assertGreaterEqual(self.clearance(), -1e-9)
        self.assertEqual(self.world.events[0].obstacle, "seabed")
        self.assertLess(self.world.visibility_at(self.vehicle.s.pos), self.world.visibility_m)

    def test_spin_cannot_sweep_through_a_pile(self):
        self.world.obstacles.append(Cylinder("post", (0., .43, 3.), (0., .43, 5.), .02))
        s = self.vehicle.s
        q0 = s.q.copy()
        s.omega[2] = 2 * np.pi / .01
        s.q = q_from_axis_angle(s.omega, 2 * np.pi)
        self.hull.resolve(self.world, self.vehicle, s.pos, q0, .01, 0., "pilot")
        self.assertEqual(self.world.events[0].obstacle, "post")
        self.assertGreaterEqual(self.clearance(), -1e-9)

    def test_wreck_sweep_is_repeatable(self):
        sc = scenarios.build("korean_castle", 7)
        wreck = sc.obstacles[0]
        start = wreck.world_point((75., -11., 6.))
        end = wreck.world_point((75., -8., 6.))
        results = []
        for _ in range(2):
            self.setUp()
            self.world = World(sc.seabed_depth)
            self.world.obstacles = sc.obstacles
            s = self.vehicle.s
            s.pos = start.copy()
            s.vel = (end - start) / .01
            self.move()
            self.assertEqual(self.world.events[0].obstacle, wreck.name)
            self.assertLess(wreck.to_local(s.pos)[1], -9.3)
            self.assertGreaterEqual(self.clearance(), -1e-9)
            results.append((s.pos.tobytes(), s.vel.tobytes(), s.omega.tobytes(), vars(self.world.events[0])))
        self.assertEqual(*results)

    def test_net_cannot_hide_rigid_backing(self):
        net = Box("net", (.5, 0., 4.), (.02, 2., 2.), kind="pen_net")
        plate = Box("plate", (.53, 0., 4.), (.02, 2., 2.))
        self.world.obstacles.extend([net, plate])
        self.vehicle.s.vel[0] = 4.
        for _ in range(12):
            self.move()
            points = self.vehicle.s.pos + self.hull.points @ q_matrix(self.vehicle.s.q).T
            self.assertTrue(np.all(plate.sdf_many(points)[0] >= self.hull.radii - 1e-9))

    def test_engine_delivers_feedback_damage_and_vehicle_score(self):
        from qysim.engine import Simulator
        sim = Simulator("tutorial_pool", seed=7)
        s = sim.vehicle.s
        s.pos[:] = (11.5, 0., 4.)
        s.q = q_from_euler(0., 0., 0.)
        s.vel[0] = 14.
        sim.tether.layout([sim.scenario.spool_pos, s.pos.copy()])
        sim.step(.01)
        state = sim.viewer_state()
        self.assertEqual(state["score"]["collisions"], 1)
        self.assertTrue(state["events"][0]["possible_damage"])
        self.assertEqual(len(state["damage"]), 1)
        self.assertLess(state["damage"][0]["health"], 1.)

    def test_embedded_pose_recovers_from_pile_footing(self):
        sc = scenarios.build("jacket_inspection", 7)
        self.world = World(sc.seabed_depth)
        self.world.obstacles = sc.obstacles
        self.vehicle.s.pos = np.array(sc.obstacles[0].p1)
        self.move()
        self.assertGreaterEqual(self.clearance(), -1e-9)

    def test_scenario_starts_and_impacts(self):
        for key in scenarios.LIBRARY:
            with self.subTest(key=key):
                self.setUp()
                sc = scenarios.build(key, 7)
                world = self.world = World(sc.seabed_depth)
                world.obstacles = list(sc.obstacles)
                clear = [sc.start_pos, sc.spool_pos] + [o.point for o in sc.objectives if o.point is not None]
                world.configure_habitat(sc.biome, 7, keep_clear=clear)
                s = self.vehicle.s
                s.pos = np.array(sc.start_pos, float)
                s.q = q_from_euler(0., 0., np.deg2rad(sc.start_heading_deg))
                self.move()
                self.assertFalse(world.events)
                target = np.array([*s.pos[:2], sc.seabed_depth])
                if sc.obstacles:
                    ob = sc.obstacles[0]
                    if isinstance(ob, Wall):
                        target = np.array([*ob.point[:2], s.pos[2]])
                    elif isinstance(ob, Cylinder):
                        target = .5 * (np.array(ob.p0) + ob.p1)
                    elif isinstance(ob, FieldMesh):
                        grid = np.array(np.unravel_index(ob.F.argmin(), ob.F.shape))
                        target = ob.world_point(ob.lo + grid * ob.h)
                    else:
                        target = np.array(ob.center, float)
                        if isinstance(ob, ShipHull):
                            target[2] += ob.hp["draft"] / 2
                path = target - s.pos
                s.vel = (path / np.linalg.norm(path)) @ q_matrix(s.q) * 50.
                for _ in range(2 + int(np.ceil(np.linalg.norm(path) / .5))):
                    self.move()
                    if world.events:
                        break
                self.assertTrue(world.events, key)
                allowed = NET_TRAVEL if self.hull.net_load else 0.
                self.assertGreaterEqual(self.clearance(), -allowed - 1e-9)
