"""Pen contact, true openings and evidence must agree with mission geometry."""
import math
import unittest
from types import SimpleNamespace
import numpy as np
from qysim.aquaculture import layout, photo, update_objective, work_objects
from qysim.scenarios import aquaculture_pen, Scorer
from qysim.world import World
from qysim.ecology import create_habitat, step_schools


class AquacultureTests(unittest.TestCase):
    def setUp(self):
        self.sc = aquaculture_pen()
        self.world = World(25)
        self.world.obstacles = self.sc.obstacles
        state = SimpleNamespace(pos=np.array([3., 0., 7.]), q=np.array([1., 0., 0., 0.]))
        self.sim = SimpleNamespace(scenario=self.sc, world=self.world,
                                  vehicle=SimpleNamespace(s=state), operations=SimpleNamespace(held=None))

    def test_openings_and_net(self):
        obstacles, data = layout()
        self.assertEqual(len(data['holes']), 2)
        self.assertEqual(len(data['dead_fish']), 4)
        edges = [ob.as_dict()["torn_edge"] for ob in obstacles if "torn_edge" in ob.as_dict()]
        self.assertCountEqual(edges, ["top", "bottom"] * len(data["holes"]))
        for hole in data['holes']:
            self.assertGreater(self.world.sdf(np.array(hole['pos']))[0], .8)
        net = next(ob for ob in obstacles if ob.kind == 'pen_net')
        self.assertLess(net.sdf(np.array(net.center))[0], 0)
        self.assertTrue(net.snag_hold)
        self.assertGreater(self.world.sdf(np.array(self.sc.start_pos))[0], .4)

    def test_stanchion_spacers_bridge_the_float_pipes(self):
        saddles = [ob for ob in self.sc.obstacles if ob.name.startswith('pen-saddle-')]
        self.assertEqual(len(saddles), 24)
        for saddle in saddles:
            for radius in (18., 18.4, 18.8):
                a = math.radians(saddle.as_dict()['yaw_deg'])
                contact = np.array([24 + radius * math.cos(a), radius * math.sin(a), -.12])
                self.assertLess(saddle.sdf(contact)[0], 0)

    def test_photo_facing(self):
        hole = np.array(layout()[1]['holes'][0]['pos'])
        self.sim.vehicle.s.pos = hole - [2, 0, 0]
        photo(self.sim)
        self.assertTrue(self.sc.objectives[1].done)
        self.sc.objectives[1].done = False
        self.sim.vehicle.s.pos = hole + [2, 0, 0]
        photo(self.sim)
        self.assertFalse(self.sc.objectives[1].done)

    def test_lap_and_lift(self):
        scorer = Scorer(self.sc)
        lap, _, recovery = self.sc.objectives
        update_objective(scorer, lap, self.sim)
        self.assertFalse(lap.done)
        for i in range(24):
            a = (i + .5) * math.tau / 24
            self.sim.vehicle.s.pos = np.array([24 + 21 * math.cos(a), 21 * math.sin(a), 7.])
            update_objective(scorer, lap, self.sim)
        self.assertTrue(lap.done)
        self.world.work_objects = work_objects()
        update_objective(scorer, recovery, self.sim)
        self.assertFalse(recovery.done)
        self.sim.operations.held = 'mort-0'
        update_objective(scorer, recovery, self.sim)
        self.assertFalse(recovery.done)
        self.world.work_objects['mort-0']['pos'][2] = 15.
        update_objective(scorer, recovery, self.sim)
        self.assertTrue(recovery.done)

    def test_school_bounds(self):
        _, self.world.fish_schools = create_habitat(self.world, 'aquaculture', 71)
        self.assertEqual(sum(s['count'] for s in self.world.fish_schools), 384)
        for i in range(30):
            self.world.time = i * .2
            step_schools(self.world, .2, [dict(pos=[24, 0, 8], light=2)])
        for school in self.world.fish_schools:
            self.assertLessEqual(np.linalg.norm(school['pos'][:2] - [24, 0]), 14.)
            self.assertLess(school['pos'][2], 14.)

    def test_real_gripper_recovers_shared_fish(self):
        from qysim.engine import Simulator
        from qysim.operations import arm_points
        sim = Simulator('aquaculture_pen', 71, model_id='falcon')
        fish = sim.world.work_objects['mort-0']
        sim.vehicle.s.q[:] = [1., 0., 0., 0.]
        sim.vehicle.s.pos[:] = fish['pos'] - arm_points(sim.operations.joints)[-1]
        sim.operations.grip = sim.operations.grip_target = 0.
        sim.operations.step(.01)
        self.assertEqual(sim.operations.held, 'mort-0')
        sim.vehicle.s.pos[2] -= 1.
        sim.operations.step(.01)
        recovery = sim.scenario.objectives[2]
        update_objective(Scorer(sim.scenario), recovery, sim)
        self.assertTrue(recovery.done)
        sim.operations.release()
        self.assertIsNone(fish['held_by'])
