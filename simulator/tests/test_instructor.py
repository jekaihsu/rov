"""Instructor authorization, physical override expiry and assessment evidence tests."""
import math
import unittest

import numpy as np

from qysim.physics import KNOT
from qysim.engine import Simulator
from qysim.room import Room
from qysim.instructor import Instructor, statistics, PHASES, MAX_REPORTS, MAX_SAMPLES_PER_VEHICLE
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

    def test_unset_code_disables_the_instructor_feature(self):
        host = SimHost(self.room.primary)
        host.instructor_code = ''
        for code in ('', None, 'anything'):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    host.join_instructor('observer', {'code': code})
        self.assertFalse(host.room.instructor.supervised)

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
                    # The profile is ramped, not overwritten: the configured layers stay and the
                    # injection heads for strength x 4 kn at the surface.
                    self.assertEqual(sim.world.current.surface_kn, old[2])
                    self.assertAlmostEqual(sim.world.current.target_surface_knots(), 2)
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

    def test_current_injection_scales_profile_with_ramp_and_rotation(self):
        sim = self.room.primary
        current = sim.world.current
        seabed = sim.world.seabed_depth
        depths = [0.0, seabed / 2, seabed - 2.0]
        before = current.mean_many(depths, seabed)
        speeds = np.linalg.norm(before, axis=1)
        self.instructor.inject({'kind': 'current', 'duration': 200, 'strength': .5, 'ramp_s': 60,
                                'rotate_deg': 90})
        self.assertAlmostEqual(current.surface_knots(), current.surface_kn, places=6)
        seen = []
        for _ in range(60):
            current.step_gust(1.0)
            self.instructor.update(1.0)
            seen.append(current.surface_knots())
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(seen, seen[1:])))
        self.assertLess(max(np.diff(seen)), 2 * (2 - current.surface_kn) / 60 * 1.6)
        self.assertGreater(seen[29], current.surface_kn + 0.3 * (2 - current.surface_kn))
        self.assertLess(seen[29], current.surface_kn + 0.7 * (2 - current.surface_kn))
        self.assertAlmostEqual(seen[-1], 2.0, places=6)
        after = current.mean_many(depths, seabed)
        np.testing.assert_allclose(np.linalg.norm(after, axis=1) / np.linalg.norm(after[0]),
                                   speeds / speeds[0], rtol=1e-9)
        heading = lambda v: math.degrees(math.atan2(v[1], v[0]))
        self.assertAlmostEqual((heading(after[0]) - heading(before[0])) % 360, 90, places=6)
        for _ in range(141):
            current.step_gust(1.0)
            self.instructor.update(1.0)
        self.assertFalse(self.instructor.active)          # expired at 200 s, now ramping back
        self.assertGreater(current.surface_knots(), current.surface_kn + 0.01)
        for _ in range(60):
            current.step_gust(1.0)
        np.testing.assert_allclose(current.mean_many(depths, seabed), before, atol=1e-12)

    def test_current_injection_into_still_water_and_limits(self):
        sim = self.room.primary
        current = sim.world.current
        current.surface_kn = current.mid_kn = current.bottom_kn = 0.0
        self.instructor.inject({'kind': 'current', 'duration': 100, 'strength': 1, 'ramp_s': 30})
        for _ in range(31):
            current.step_gust(1.0)
        self.assertAlmostEqual(current.surface_knots(), 4.0, places=6)
        mid = np.linalg.norm(current.mean_at(sim.world.seabed_depth / 2, sim.world.seabed_depth))
        self.assertAlmostEqual(mid / KNOT, 3.2, places=6)
        self.instructor.finish()
        for bad in ({'ramp_s': 5}, {'ramp_s': 600}, {'rotate_deg': 270}, {'ramp_s': float('nan')}):
            with self.subTest(bad=bad):
                room = Room(Simulator())
                with self.assertRaises(ValueError):
                    room.instructor.inject({'kind': 'current', 'duration': 10, **bad})

    def test_host_current_override_limits(self):
        host = SimHost(self.room.primary)
        sim = host.room.primary
        host.handle_viewer({'type': 'current', 'surface_kn': 50, 'turbulence': 3})
        self.assertEqual(sim.world.current.surface_kn, 5.0)
        self.assertEqual(sim.world.current.turbulence, 0.3)

    def test_report_and_statistics(self):
        self.assertEqual(statistics([0, 2], 1)['outside_fraction'], .5)
        self.instructor.supervised = True
        self.instructor.update(1)
        report = self.instructor.report('v1')
        self.assertTrue(report['provisional'])
        self.assertEqual(set(report['matrix']), set(PHASES))
        self.assertIn('trajectory', report)
        self.assertIn('smoothness', report)
        self.assertIn('max_tension', report)
        self.instructor.finish()
        self.assertEqual(len(self.instructor.reports), 1)

    def test_unsupervised_room_records_nothing(self):
        for _ in range(1200):
            self.room.step(.01)
        self.assertEqual(self.instructor.samples, {})
        self.room.reset()
        self.assertEqual(self.instructor.reports, [])

    def test_sampling_follows_supervision_and_overrides(self):
        self.instructor.supervised = True
        for _ in range(3):
            self.instructor.update(1)
        self.assertEqual(len(self.instructor.samples['v1']), 3)
        self.instructor.supervised = False
        self.instructor.update(1)
        self.assertEqual(len(self.instructor.samples['v1']), 3)
        self.instructor.inject({'kind': 'battery', 'duration': 2.5})
        for _ in range(4):
            self.instructor.update(1)
        self.assertFalse(self.instructor.active)
        self.assertEqual(len(self.instructor.samples['v1']), 5)

    def test_samples_and_reports_are_bounded(self):
        self.instructor.supervised = True
        for _ in range(MAX_SAMPLES_PER_VEHICLE + 5):
            self.instructor.update(1)
        samples = self.instructor.samples['v1']
        self.assertEqual(len(samples), MAX_SAMPLES_PER_VEHICLE)
        self.assertEqual(samples[-1]['t'], MAX_SAMPLES_PER_VEHICLE + 5)
        report = self.instructor.report('v1')
        self.assertIsInstance(report['trajectory'], list)
        self.assertEqual(len(report['trajectory']), MAX_SAMPLES_PER_VEHICLE)
        self.instructor.finish()
        for run in range(MAX_REPORTS + 3):
            self.instructor.update(1)
            self.instructor.finish()
        self.assertEqual(len(self.instructor.reports), MAX_REPORTS)
        self.assertEqual(len(self.instructor.reports[-1]['trajectory']), 1)

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


class ConsoleExtensionTests(unittest.TestCase):
    def test_cancel_restores_each_kind_without_touching_other_events(self):
        for kind in ('thruster', 'battery', 'current', 'visibility', 'freeze'):
            with self.subTest(kind=kind):
                room = Room(Simulator())
                instructor = room.instructor
                sim = room.primary
                before = (sim.health.tolist(), sim.battery, sim.world.current.surface_kn,
                          sim.scenario.visibility_m, sim.paused)
                instructor.inject({'kind': kind, 'strength': .5, 'duration': 60})
                other = 'battery' if kind != 'battery' else 'thruster'
                instructor.inject({'kind': other, 'strength': 0, 'duration': 60})
                instructor.inject({'kind': kind, 'cancel_start': 0})
                self.assertEqual([e['kind'] for e in instructor.active], [other])
                self.assertEqual((sim.health.tolist(), sim.battery, sim.world.current.surface_kn,
                                  sim.scenario.visibility_m, sim.paused), before)
                self.assertIn('restored_at', instructor.events[-1])
                with self.assertRaises(ValueError):
                    instructor.inject({'kind': kind, 'cancel_start': 0})

    def test_cancel_rejects_stale_and_invalid_identity(self):
        instructor = Room(Simulator()).instructor
        instructor.inject({'kind': 'battery'})
        for start in (1, True, '0', float('nan')):
            with self.assertRaises(ValueError):
                instructor.inject({'kind': 'battery', 'cancel_start': start})
        self.assertEqual(len(instructor.active), 1)

    def test_supervision_is_optional_additive_public_snapshot(self):
        instructor = Room(Simulator()).instructor
        instructor.inject({'kind': 'thruster', 'index': 2})
        report = instructor.report('v1')
        supervision = report['supervision']
        self.assertEqual(supervision['phase'], 'descent')
        self.assertEqual(supervision['active'][0]['index'], 2)
        self.assertNotIn('original', supervision['active'][0])
        self.assertNotIn('controls', supervision['active'][0])
        self.assertIn('obstacles', supervision['world'])
        supervision['active'][0]['strength'] = 0
        self.assertEqual(instructor.active[0]['strength'], 1)
        self.assertEqual(set(report['matrix']), set(PHASES))
