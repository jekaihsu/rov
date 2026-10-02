"""Manipulator loads, shared work items and route/coordinate safety."""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from qysim.navigation import GeoFrame, Navigator
from qysim.operations import VehicleOperations, arm_points, enu_to_ned, ned_to_enu, step_objects
from qysim.physics import G, Vehicle
from qysim.rc import RCState
from qysim.world import Cylinder, Wall, World


def operator(world=None, ident="alpha", model="falcon"):
    world = world or World(20)
    vehicle = Vehicle(model_id=model)
    vehicle.s.pos[:] = [0, 0, 8]
    sim = SimpleNamespace(world=world, vehicle=vehicle, vehicle_id=ident, model_id=model,
                          scenario=SimpleNamespace(start_pos=(0,0,3), seed=42), t=0., yaw=0., paused=False,
                          controller=SimpleNamespace(depth_hold=8), rc=RCState(), nav=Navigator(GeoFrame()))
    sim.operations = VehicleOperations(sim)
    return sim


def item_at_tip(sim, mass=2., buoyancy=1.5):
    pos = sim.vehicle.s.pos + arm_points(sim.operations.joints)[-1]
    item = dict(id="sample", label="sample", pos=pos, vel=np.zeros(3), mass=mass,
                buoyancy_kg=buoyancy, radius=.12, held_by=None)
    sim.world.work_objects = {"sample": item}
    sim.operations.grip = sim.operations.grip_target = 0.
    return item


class TestOperations(unittest.TestCase):
    def test_arm_limits_speed_and_atomic_rejection(self):
        sim = operator()
        op = sim.operations
        self.assertTrue(op.command({"action":"arm", "joints":[500,-500,500,-500], "grip":-3})["ok"])
        np.testing.assert_allclose(op.target, [95,-65,120,-100])
        self.assertEqual(op.grip_target, 0)
        before = op.joints.copy()
        op.step(.01)
        self.assertLessEqual(np.max(abs(op.joints-before)), .25001)
        target = op.target.copy()
        self.assertFalse(op.command({"action":"arm","joints":[0,0,0,0],"grip":float("nan")})["ok"])
        np.testing.assert_equal(op.target,target)
        self.assertFalse(operator(model="x1").operations.command({"action":"arm"})["ok"])

    def test_arm_obstacle_blocks_joint_motion(self):
        sim = operator()
        op = sim.operations
        p = sim.vehicle.s.pos + arm_points(op.joints)[1]
        sim.world.obstacles.append(Cylinder("obstacle",tuple(p),tuple(p),.1))
        before = op.joints.copy()
        op.command({"action":"arm","joints":[0,10,20,0]})
        op.step(.01)
        np.testing.assert_equal(op.joints,before)
        self.assertIn("接觸",op.status)

    def test_exclusive_grab_release_and_load_wrench(self):
        a = operator()
        b = operator(a.world,"beta")
        item = item_at_tip(a)
        b.operations.grip = b.operations.grip_target = 0.
        force = a.operations.step(.01)
        b.operations.step(.01)
        self.assertEqual(item["held_by"],"alpha")
        self.assertIsNone(b.operations.held)
        self.assertAlmostEqual(force[2], .5*G)
        self.assertLess(force[4],0)  # Front payload pitches the bow down in FRD.
        a.vehicle.s.vel[:] = [.3,.1,0]
        a.operations.release()
        self.assertIsNone(item["held_by"])
        np.testing.assert_allclose(item["vel"],a.vehicle.world_velocity())
        b.operations.step(.01)
        self.assertEqual(item["held_by"],"beta")

    def test_heavy_item_and_dynamic_overload_release(self):
        sim = operator()
        item = item_at_tip(sim,14,2)
        np.testing.assert_equal(sim.operations.step(.01),np.zeros(6))
        self.assertIsNone(item["held_by"])
        self.assertIn("10 kg",sim.operations.status)
        item["mass"], item["buoyancy_kg"] = 2.,1.5
        sim.operations.step(.01)
        sim.vehicle.s.vel[:] = [10,0,0]
        np.testing.assert_equal(sim.operations.step(.01),np.zeros(6))
        self.assertIsNone(item["held_by"])
        self.assertIn("超載",sim.operations.status)

    def test_held_radius_does_not_pass_wall(self):
        sim = operator()
        item = item_at_tip(sim)
        sim.operations.step(.01)
        tip = item["pos"].copy()
        sim.world.obstacles.append(Wall("wall",tuple(tip+[.08,0,0]),180))
        sim.operations.step(.01)
        self.assertIsNone(item["held_by"])
        self.assertGreaterEqual(sim.world.sdf(item["pos"])[0],item["radius"]-1e-8)

    def test_route_rejects_obstacle_between_clear_endpoints(self):
        sim = operator()
        sim.world.obstacles.append(Cylinder("pile",(4,0,0),(4,0,20),.6))
        op = sim.operations
        self.assertTrue(op.command({"action":"waypoint","pos":[8,0,8]})["ok"])
        self.assertFalse(op.command({"action":"route_start"})["ok"])
        self.assertEqual(sim.nav.mode,"IDLE")
        self.assertFalse(op.command({"action":"waypoint","pos":[0,0,float("nan")]})["ok"])
        self.assertFalse(op.command({"action":"coverage","spacing":0})["ok"])

    def test_coverage_orientation_and_coordinate_roundtrip(self):
        sim = operator()
        sim.yaw = math.pi/2
        self.assertTrue(sim.operations.command({"action":"coverage","width":4,"length":6,"spacing":2})["ok"])
        route = np.asarray(sim.operations.waypoints)
        np.testing.assert_allclose(route[1]-route[0],[0,6,0],atol=1e-12)
        np.testing.assert_allclose(route[2]-route[1],[-2,0,0],atol=1e-12)
        self.assertEqual(enu_to_ned([11,22,3]),[22,11,-3])
        self.assertEqual(ned_to_enu(enu_to_ned([11,22,3])),[11,22,3])
        with self.assertRaises(ValueError):
            ned_to_enu([1,float("inf"),3])

    def test_altitude_tracks_terrain_not_fixed_initial_depth(self):
        sim = operator()
        self.assertTrue(sim.operations.command({"action":"altitude","metres":3})["ok"])
        with patch.object(sim.world,"depth_at",return_value=12.):
            sim.operations.step(.01)
            self.assertEqual(sim.controller.depth_hold,9)
        with patch.object(sim.world,"depth_at",return_value=15.):
            sim.operations.step(.01)
            self.assertEqual(sim.controller.depth_hold,12)
        self.assertFalse(sim.operations.command({"action":"altitude","metres":float("nan")})["ok"])
        self.assertEqual(sim.operations.altitude,3)

    def test_room_integrates_shared_work_item_once(self):
        from qysim.room import Room
        a = operator()
        b = operator(a.world,"beta")
        item = item_at_tip(a)
        item["pos"] = np.array([5.,0.,5.])
        room = Room(a)
        room.vehicles["v2"] = b
        # Isolate free-item dynamics from vehicle integration, preserving real room ordering.
        a.step = b.step = lambda dt,update_world=False: None
        with patch("qysim.operations.step_objects",wraps=step_objects) as integrate:
            room.step(.01)
            integrate.assert_called_once()
        self.assertAlmostEqual(item["pos"][2],5 + .5*G/3 * .01**2)
        self.assertAlmostEqual(a.world.time,.01)


if __name__ == "__main__":
    unittest.main()
