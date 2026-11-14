"""Procedure order, opt-in compatibility, fault injection and safety regression tests."""
import unittest
from qysim.engine import Simulator
from qysim.procedure import CHECKS


class ProcedureTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator('open_water', seed=1)
        self.p = self.sim.procedure

    def act(self, action, **kw):
        return self.p.action(dict(action=action, **kw))

    def checks(self):
        self.act('begin')
        for key in CHECKS:
            if key == 'thrusters':
                for i in range(len(self.sim.health)):
                    self.act('test', index=i)
                    self.p.step(2.)
            self.act('check', key=key)

    def test_order_and_gate(self):
        self.act('begin')
        with self.assertRaises(ValueError):
            self.act('check', key='camera')
        self.sim.rc_physical.rc_lock = 0
        self.sim.step()
        self.assertEqual(self.sim.rc.rc_lock, 1)
        self.assertFalse(self.p.can_unlock)

    def test_complete_flow(self):
        self.checks()
        with self.assertRaises(ValueError):
            self.act('lower', point='upstream')
        self.act('tender')
        self.act('lower', point='upstream')
        self.assertFalse(self.p.can_unlock)
        self.act('water_confirm')
        self.assertTrue(self.p.can_unlock)
        self.sim.vehicle.s.pos[2] = 2
        with self.assertRaises(ValueError):
            self.act('recover')
        self.sim.vehicle.s.pos[2] = .5
        self.sim.rc_physical.rc_lock = 0
        with self.assertRaises(ValueError):
            self.act('recover')
        self.sim.rc_physical.rc_lock = 1
        self.act('recover')
        self.sim.vehicle.s.pos[2] = -.5
        self.p.step(5.)
        self.p.step(5.)
        self.act('rinse')
        self.act('inspect')
        self.act('save', notes='tested')
        self.assertEqual(self.p.state()['notes'], 'tested')
        self.assertEqual(self.p.phase, 'complete')

    def test_skip_fault_and_score(self):
        self.act('begin')
        self.act('skip')
        self.assertTrue(self.p.failures)
        self.assertEqual(self.p.penalty, 10)
        self.p.failures = ['connector']
        self.act('tender')
        self.act('lower', point='upstream')
        self.act('water_confirm')
        self.sim.vehicle.s.pos[2] = 2
        self.p.step(.01)
        self.assertEqual(self.p.phase, 'recovering')
        self.assertEqual(self.sim.rc.rc_lock, 1)

    def test_dry_time_cumulative(self):
        self.act('begin')
        for key in CHECKS[:7]:
            self.act('check', key=key)
        for _ in range(16):
            self.act('test', index=0)
            self.p.step(2)
        self.assertEqual(self.p.dry_seconds, 32)
        self.assertEqual(self.p.penalty, 10)
        self.p.step(2)
        self.assertEqual(self.p.penalty, 10)

    def test_quick_unchanged_and_reset(self):
        self.assertTrue(self.p.can_unlock)
        self.assertFalse(self.p.active)
        self.act('begin')
        self.sim.load_scenario('open_water')
        self.assertFalse(self.sim.procedure.active)

    def test_score_and_recovery_environment(self):
        self.sim.world.current.sample = lambda *_: self.sim.vehicle.current_ned
        self.act('begin')
        self.p.penalty = 10
        self.assertEqual(self.p.score({'score': 80, 'penalty_total': 2})['score'], 70)
        self.p.phase = 'recovering'
        self.sim.vehicle.s.pos[:2] = self.sim.scenario.spool_pos[:2]
        self.sim.vehicle.s.pos[2] = 0
        self.sim.vehicle.current_ned[:] = 0
        self.p.step(.1)
        calm = self.p.recovered
        self.p.recovered = 0
        self.sim.vehicle.current_ned[:] = 2
        self.p.step(.1)
        self.assertLess(self.p.recovered, calm)

    def test_deck_supported_and_motor_output(self):
        self.act('begin')
        for key in CHECKS[:7]:
            self.act('check', key=key)
        self.act('test', index=0)
        self.sim.step(.01)
        self.assertGreater(self.sim.vehicle.s.thrust[0], 0)
        for _ in range(220):
            self.sim.step(.01)
        self.assertFalse(self.sim.tether.broken)
        self.assertEqual(self.sim.depth, -.5)
        self.assertIn(0, self.p.tests)

    def test_hauling_can_recover_against_current(self):
        self.act('begin')
        self.p.phase = 'recovering'
        self.sim.vehicle.s.pos[2] = 2.
        self.sim.vehicle.current_ned[:] = 1.
        self.sim.world.current.sample = lambda *_: self.sim.vehicle.current_ned
        for _ in range(300):
            self.sim.step(.1)
        self.assertEqual(self.p.phase, 'post')
        self.assertFalse(self.sim.tether.broken)
