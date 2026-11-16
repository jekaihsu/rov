"""Deck-flow pre-dive checks: hands-on order, crew radio reports, seeded defects, detection, fix and missed faults."""
import unittest

from qysim.engine import Simulator
from qysim.procedure import DECK_CHECKS, DEFECTS, STATIONS, LEAK_DEPTH_M, Procedure


class DeckFlowTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulator('open_water', seed=1)
        self.p = self.sim.procedure

    def act(self, action, **kw):
        return self.p.action(dict(action=action, **kw))

    def walk(self, report=None):
        for station in range(len(STATIONS)):
            self.act('look', station=station)
            if station == report:
                self.act('report', station=station)

    def run_checks(self):
        """Power, thruster pulses, lamp test and camera after the walk-around."""
        self.act('check', key='power')
        self.assertTrue(self.p.powered)
        with self.assertRaises(ValueError):
            self.act('test', index=0)                # still booting
        self.p.step(3.)
        self.assertIn('power', self.p.checked)
        for index in range(len(self.sim.health)):
            self.act('test', index=index)
            self.p.step(2.)
        self.p.step(.01)
        self.assertIn('thrusters', self.p.checked)
        self.act('check', key='lights')
        self.assertTrue(self.p.state()['lamps'])
        self.p.step(5.)
        self.assertNotIn('lights', self.p.checked)   # the lamps stay on until the operator confirms them
        self.act('check', key='lights')
        self.assertFalse(self.p.state()['lamps'])
        self.act('check', key='camera')

    def dive(self):
        self.p.step(2.5)                             # the tether hand reports ready
        self.act('lower', point='upstream')
        self.act('water_confirm')
        self.assertEqual(self.p.phase, 'diving')

    def test_legacy_begin_has_no_deck_fields(self):
        self.act('begin')
        state = self.p.state()
        self.assertNotIn('flow', state)
        self.assertNotIn('defect', state)

    def test_hands_on_order_and_crew_reports(self):
        self.act('begin', flow='deck')
        self.assertEqual(self.p.state()['order'], list(DECK_CHECKS))
        with self.assertRaises(ValueError):
            self.act('check', key='power')           # the walk-around comes first
        with self.assertRaises(ValueError):
            self.act('check', key='walkaround')      # every station must be looked at
        self.walk()
        self.act('check', key='walkaround')
        with self.assertRaises(ValueError):
            self.act('test', index=0)                # not powered yet
        self.p.step(5.)
        self.assertIn('trim', self.p.crew)
        self.run_checks()
        self.assertEqual(self.p.checked, list(DECK_CHECKS))
        self.assertEqual(self.p.phase, 'launch')
        self.assertEqual(set(self.p.crew), {'trim', 'instruments', 'communication'})
        with self.assertRaises(ValueError):
            self.act('lower', point='upstream')      # tender has not called ready yet
        self.p.step(2.5)
        self.assertIn('tender', self.p.crew)
        self.assertTrue(self.p.confirmed)
        self.act('lower', point='upstream')
        crew_events = [e['key'] for e in self.p.events if e['action'] == 'crew']
        self.assertEqual(sorted(crew_events), sorted(self.p.crew))

    def test_pulse_reports_index_and_thruster_spins(self):
        self.act('begin', flow='deck')
        self.walk()
        self.act('check', key='walkaround')
        self.act('check', key='power')
        self.p.step(3.)
        self.act('test', index=2)
        self.assertEqual(self.p.state()['diagnostic_index'], 2)
        self.sim.step(.01)
        self.assertGreater(self.sim.vehicle.s.thrust[2], 0)
        with self.assertRaises(ValueError):
            self.act('check', key='thrusters')       # completes by itself after every pulse

    def test_no_defect_without_context(self):
        for seed in range(30):
            procedure = Procedure(self.sim)
            procedure.action({'action': 'begin', 'flow': 'deck', 'seed': seed})
            self.assertIsNone(procedure.defect)

    def test_planting_is_deterministic_by_seed(self):
        planted = []
        for seed in range(40):
            first = Procedure(self.sim)
            second = Procedure(Simulator('open_water', seed=1) if seed == 0 else self.sim)
            first.action({'action': 'begin', 'flow': 'deck', 'defects': True, 'seed': seed})
            second.action({'action': 'begin', 'flow': 'deck', 'defects': True, 'seed': seed})
            self.assertEqual(first.defect, second.defect)
            planted.append(first.defect)
        kinds = {d['kind'] for d in planted if d}
        self.assertTrue(any(d is None for d in planted), 'sometimes, not always')
        self.assertEqual(kinds, set(DEFECTS))
        for defect in planted:
            if defect and defect['thruster'] is not None:
                side = self.sim.vehicle.thrusters[defect['thruster']][1][1]
                self.assertEqual(STATIONS[defect['station']], 'port' if side < 0 else 'starboard')

    def test_invalid_begin_moves_nothing(self):
        before = self.sim.vehicle.s.pos.copy()
        with self.assertRaises(ValueError):
            self.act('begin', flow='deck', defect='gremlin')
        self.assertFalse(self.p.active)
        self.assertEqual(list(before), list(self.sim.vehicle.s.pos))

    def test_found_defect_must_be_fixed_and_causes_no_fault(self):
        self.act('begin', flow='deck', defect='connector_unlocked')
        rear = STATIONS.index('rear')
        self.assertEqual(self.p.defect['station'], rear)
        self.walk(report=rear)
        self.assertTrue(self.p.defect['found'])
        with self.assertRaises(ValueError):
            self.act('check', key='walkaround')      # found but not cleared
        self.act('fix')
        self.p.step(1.)
        with self.assertRaises(ValueError):
            self.act('check', key='walkaround')
        self.p.step(2.5)
        self.assertTrue(self.p.defect['fixed'])
        self.act('check', key='walkaround')
        self.run_checks()
        self.dive()
        self.sim.vehicle.s.pos[2] = 5.
        self.p.step(20.)
        self.assertEqual(self.sim.link.severity, 0.)
        self.assertFalse(any(e['action'] == 'fault' for e in self.p.events))
        self.assertEqual(self.p.penalty, 0)

    def test_false_report_costs_points(self):
        self.act('begin', flow='deck', defect='none')
        with self.assertRaises(ValueError):
            self.act('report', station=0)            # not looked at yet
        self.act('look', station=0)
        self.act('report', station=0)
        self.assertEqual(self.p.penalty, 2)
        self.assertTrue(any(e['action'] == 'false_report' for e in self.p.events))
        with self.assertRaises(ValueError):
            self.act('fix')

    def missed(self, kind):
        self.act('begin', flow='deck', defect=kind)
        self.walk()
        self.act('check', key='walkaround')
        self.assertEqual(self.p.missed, kind)
        self.run_checks()
        self.dive()

    def assert_fault(self, kind):
        faults = [e for e in self.p.events if e['action'] == 'fault']
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0]['defect'], kind)
        self.assertEqual(faults[0]['fault'], DEFECTS[kind]['fault'])
        self.assertEqual(self.p.penalty, 10)
        self.assertIsNone(self.p.missed)

    def run_thruster(self, index, seconds):
        self.sim.vehicle.s.pos[2] = 2.
        for _ in range(int(seconds / .1)):
            self.sim.vehicle.s.thrust[index] = .5 * self.sim.vehicle.p.thruster_max
            self.p.step(.1)

    def test_missed_line_degrades_the_thruster_once_it_runs(self):
        self.missed('line_fouled')
        index = self.p.defect['thruster']
        self.sim.vehicle.s.pos[2] = 2.
        self.p.step(5.)                              # idle thruster: nothing to draw the line in
        self.assertEqual(self.sim.health[index], 1.)
        self.run_thruster(index, 2.2)
        self.assertAlmostEqual(self.sim.health[index], .35)
        self.assert_fault('line_fouled')

    def test_missed_cracked_guard_fails_the_thruster(self):
        self.missed('guard_cracked')
        index = self.p.defect['thruster']
        self.run_thruster(index, 10.)
        self.assertEqual(self.sim.health[index], 1.)
        self.run_thruster(index, 6.)
        self.assertEqual(self.sim.health[index], 0.)
        self.assert_fault('guard_cracked')

    def test_missed_oring_debris_raises_the_leak_alarm_at_depth(self):
        self.missed('oring_debris')
        self.sim.vehicle.s.pos[2] = LEAK_DEPTH_M - .5
        self.p.step(30.)
        self.assertFalse(self.sim.leak)
        self.sim.vehicle.s.pos[2] = LEAK_DEPTH_M + .1
        self.p.step(.01)
        self.assertTrue(self.sim.leak)
        self.assertTrue(self.sim.viewer_state()['leak']['detected'])
        self.assert_fault('oring_debris')

    def test_missed_connector_ring_makes_the_link_intermittent(self):
        self.missed('connector_unlocked')
        self.sim.vehicle.s.pos[2] = 3.
        self.p.step(5.)
        self.assertEqual(self.sim.link.state_name, 'healthy')
        self.p.step(4.)
        self.assertEqual(self.sim.link.state_name, 'degraded')
        self.assert_fault('connector_unlocked')

    def test_skip_leaves_a_planted_defect_on_the_vehicle(self):
        self.act('begin', flow='deck', defect='oring_debris')
        self.act('skip')
        self.assertEqual(self.p.phase, 'launch')
        self.assertEqual(self.p.missed, 'oring_debris')
        self.assertEqual(self.p.penalty, len(DECK_CHECKS))
        self.assertEqual(self.p.failures, [])        # skipping alone draws no random fault in the deck flow

    def test_crew_mode_auto_completes_without_defect(self):
        self.act('begin', flow='deck', checks='crew', defects=True, defect='oring_debris')
        self.assertEqual(self.p.phase, 'launch')
        self.assertEqual(self.p.checked, list(DECK_CHECKS))
        self.assertTrue(self.p.confirmed)
        self.assertIsNone(self.p.defect)
        self.assertIsNone(self.p.missed)
        self.assertEqual(self.p.penalty, 0)
        self.act('lower', point='upstream')
        self.act('water_confirm')
        self.assertTrue(self.p.can_unlock)

    def test_quick_and_sdk_sessions_never_plant(self):
        # Quick launch and SDK sessions never send begin: no procedure, no defect, no gate.
        self.assertFalse(self.p.active)
        self.assertIsNone(self.p.defect)
        self.sim.vehicle.s.pos[2] = 5.
        for _ in range(200):
            self.sim.step(.01)
        self.assertFalse(self.sim.leak)
        self.assertTrue(all(h == 1. for h in self.sim.health))
        self.assertNotIn('procedure', self.sim.viewer_state())


if __name__ == '__main__':
    unittest.main()
