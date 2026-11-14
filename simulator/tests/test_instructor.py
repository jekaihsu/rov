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
        for kind in ('thruster', 'battery', 'current', 'visibility', 'freeze'):
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

    def supervised_host(self):
        host = SimHost(self.room.primary)
        self.pilot = host.room.join(now=0)
        host.room.instructor.supervised = True
        return host

    def test_supervision_blocks_shared_scene_commands(self):
        host = self.supervised_host()
        blocked = [{'type': 'scenario', 'key': 'coral_reef'}, {'type': 'reset'}, {'type': 'pause', 'value': True},
                   {'type': 'current', 'surface_kn': 3}, {'type': 'model', 'model_id': 'falcon'},
                   {'type': 'operation', 'action': 'campaign_start'},
                   {'type': 'operation', 'action': 'mission_mode', 'mode': 'free_explore'}]
        scenario = host.room.primary.scenario.key
        for msg in blocked:
            with self.subTest(msg=msg):
                reply = host.handle_viewer(msg, room=host.room, player=self.pilot)
                self.assertEqual(reply['code'], 'instructor_override')
        self.assertEqual(host.room.primary.scenario.key, scenario)
        self.assertFalse(host.room.primary.paused)
        self.assertEqual(host.room.campaign.status, 'idle')

    def test_override_alone_blocks_shared_scene_commands(self):
        host = SimHost(self.room.primary)
        pilot = host.room.join(now=0)
        host.room.instructor.inject({'kind': 'battery', 'duration': 5})
        self.assertFalse(host.room.instructor.supervised)
        reply = host.handle_viewer({'type': 'reset'}, room=host.room, player=pilot)
        self.assertEqual(reply['code'], 'instructor_override')
        self.assertIsNone(host.handle_viewer({'type': 'payout', 'metres': 1}, room=host.room, player=pilot))

    def test_supervision_keeps_vehicle_operations(self):
        host = self.supervised_host()
        sim = host.room.vehicles[self.pilot.vehicle_id]

        def send(msg):
            return host.handle_viewer(msg, room=host.room, player=self.pilot)

        length = sim.tether.length
        self.assertIsNone(send({'type': 'payout', 'metres': 2}))
        self.assertGreater(sim.tether.length, length)
        self.assertIsNone(send({'type': 'auto_payout', 'value': False}))
        self.assertFalse(sim.tether.auto_payout)
        self.assertIsNone(send({'type': 'operation_mode', 'value': 'UAV_CHN'}))
        self.assertEqual(sim.operation_mode, 'UAV_CHN')
        self.assertIsNone(send({'type': 'shaping', 'throttle_limit': 40}))
        self.assertEqual(sim.shaping.throttle_limit, 40)
        self.assertIsNone(send({'type': 'remote_release'}))
        self.assertIsNone(send({'type': 'rc', 'seq': 0, 'rc': {'rc_lock': 1}}))
        arm = send({'type': 'operation', 'action': 'arm', 'joints': [20, 0, 0, 0], 'grip': 1})
        self.assertEqual(arm['type'], 'operation_result')
        for action in ('mission_photo', 'campaign_advance', 'campaign_restore'):
            with self.subTest(action=action):
                reply = send({'type': 'operation', 'action': action})
                self.assertEqual(reply['type'], 'operation_result')
                self.assertNotEqual(reply.get('code'), 'instructor_override')
