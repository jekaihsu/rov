"""Instructor authorization, physical override expiry and assessment evidence tests."""
import unittest
from qysim.engine import Simulator
from qysim.room import Room
from qysim.instructor import Instructor, statistics, PHASES
from qysim.server import SimHost


class InstructorTests(unittest.TestCase):
    def setUp(self):
        self.room = Room(Simulator())
        self.instructor = self.room.instructor

    def test_authentication(self):
        self.assertFalse(Instructor.authorized('', ''))
        self.assertFalse(Instructor.authorized('secret', 'wrong'))
        self.assertFalse(Instructor.authorized('secret', None))
        self.assertTrue(Instructor.authorized('secret', 'secret'))

    def test_injections_restore_and_record(self):
        sim = self.room.primary
        for kind in ('thruster', 'battery', 'current', 'visibility'):
            with self.subTest(kind=kind):
                old = (sim.health.copy(), sim.battery, sim.world.current.surface_kn,
                       sim.scenario.visibility_m, sim.paused)
                self.instructor.inject({'kind': kind, 'duration': .1, 'strength': .5})
                if kind == 'thruster':
                    self.assertLess(sim.health[0], old[0][0])
                elif kind == 'battery':
                    self.assertLess(sim.battery, old[1])
                elif kind == 'current':
                    self.assertEqual(sim.world.current.surface_kn, 2)
                elif kind == 'visibility':
                    self.assertLess(sim.scenario.visibility_m, old[3])
                else:
                    self.assertTrue(sim.paused)
                self.instructor.update(.11)
                self.assertEqual(sim.health.tolist(), old[0].tolist())
                self.assertEqual(sim.battery, old[1])
                self.assertEqual(sim.world.current.surface_kn, old[2])
                self.assertEqual(sim.scenario.visibility_m, old[3])
                self.assertEqual(sim.paused, old[4])
                self.assertEqual(self.instructor.events[-1]['kind'], kind)
                self.assertIn('restored_at', self.instructor.events[-1])

    def test_report_and_statistics(self):
        self.assertEqual(statistics([0, 2], 1)['outside_fraction'], .5)
        self.instructor.update(1)
        report = self.instructor.report('v1')
        self.assertTrue(report['provisional'])
        self.assertEqual(set(report['matrix']), set(PHASES))
        self.assertIn('trajectory', report)
        self.assertIn('smoothness', report)
        self.assertIn('max_tension', report)
        self.instructor.finish()
        self.assertEqual(len(self.instructor.reports), 1)

    def test_overlap_and_invalid(self):
        for strength in (-1, 2, float('nan')):
            with self.assertRaises(ValueError):
                self.instructor.inject({'kind': 'battery', 'strength': strength})
        self.instructor.inject({'kind': 'battery'})
        with self.assertRaises(ValueError):
            self.instructor.inject({'kind': 'battery'})

    def test_instructor_seat_and_pilot_isolation(self):
        host = SimHost(self.room.primary)
        host.instructor_code = 'test-only'
        with self.assertRaises(ValueError):
            host.join_instructor('observer', {'code': 'wrong'})
        host.join_instructor('observer', {'code': 'test-only'})
        self.assertFalse(host.room.players)
        host.instructor_command('observer', {'type': 'instructor', 'action': 'inject', 'kind': 'battery'})
        reply = host.handle_viewer({'type': 'reset'})
        self.assertEqual(reply['code'], 'instructor_override')
