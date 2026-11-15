"""Event extraction and printable debrief report generation."""
import unittest

from qysim.debrief import (
    SEEK_LEAD_S,
    STRINGS,
    attach_debrief,
    build_html_report,
    extract_events_from_frames,
    extract_events_from_report,
    merge_recording_events,
    report_to_replay,
    seek_time,
)


class DebriefTests(unittest.TestCase):
    def test_seek_leads_five_seconds_and_clamps(self):
        self.assertEqual(seek_time(12), 7)
        self.assertEqual(seek_time(3), 0)
        self.assertEqual(seek_time(3, lead_s=SEEK_LEAD_S, start_t=1), 1)
        with self.assertRaises(ValueError):
            seek_time(float('nan'))

    def test_extract_events_from_frames_covers_required_kinds(self):
        frames = [
            {'t': 0, 'events': [], 'tether': {'warn': False, 'broken': False, 'wraps': {}},
             'silt': 0.1, 'sensors': {'dvl': {'status': 'locked'}}, 'link': {'state': 'healthy'},
             'score': {'objectives': [{'label': 'A', 'done': False}], 'penalties': []}},
            {'t': 10, 'events': [{'t': 10, 'obstacle': 'J brace', 'severity': 'hard', 'where': 'nose'}],
             'tether': {'warn': True, 'broken': False, 'wraps': {}, 'tension_max': 200},
             'silt': 0.2, 'sensors': {'dvl': {'status': 'locked'}}, 'link': {'state': 'healthy'},
             'score': {'objectives': [{'label': 'A', 'done': False}], 'penalties': []}},
            {'t': 20, 'events': [], 'tether': {'warn': True, 'broken': False, 'wraps': {'pile': 1}},
             'silt': 0.9, 'sensors': {'dvl': {'status': 'lost', 'reason': 'too_high'}},
             'link': {'state': 'lost', 'cause': 'instructor'},
             'score': {'objectives': [{'label': 'A', 'done': True}],
                       'penalties': [{'t': 19, 'reason': '碰撞 J brace', 'points': 5}]}},
            {'t': 30, 'events': [], 'tether': {'warn': True, 'broken': True, 'wraps': {'pile': 1}},
             'silt': 0.9, 'sensors': {'dvl': {'status': 'lost'}}, 'link': {'state': 'lost'},
             'score': {'objectives': [{'label': 'A', 'done': True}], 'penalties': []}},
        ]
        injections = [{'kind': 'thruster', 'start': 8, 'vehicle_id': 'v1'}]
        kinds = [e['kind'] for e in extract_events_from_frames(frames, injections)]
        for needed in ('instructor_inject', 'collision', 'tether_warn', 'tether_snag', 'tether_break',
                       'silt_whiteout', 'dvl_lost', 'comms_loss', 'objective_done', 'penalty'):
            self.assertIn(needed, kinds)
        inject = next(e for e in extract_events_from_frames(frames, injections)
                      if e['kind'] == 'instructor_inject')
        self.assertEqual(seek_time(inject['t']), inject['t'] - SEEK_LEAD_S)

    def test_legacy_frames_without_sensors_still_extract_collisions(self):
        frames = [
            {'t': 1, 'events': [], 'tether': {'warn': False, 'broken': False, 'wraps': {}},
             'silt': 0, 'score': {'objectives': [], 'penalties': []}},
            {'t': 5, 'events': [{'t': 5, 'obstacle': 'rock', 'severity': 'touch', 'where': 'port'}],
             'tether': {'warn': False, 'broken': False, 'wraps': {}},
             'silt': 0, 'score': {'objectives': [], 'penalties': []}},
        ]
        events = extract_events_from_frames(frames)
        self.assertEqual([e['kind'] for e in events], ['collision'])

    def test_report_events_and_html_use_strings(self):
        report = {
            'vehicle_id': 'v1', 'elapsed': 40, 'provisional': True,
            'completion': {'score': 80, 'elapsed': 40, 'penalties': [
                {'t': 12, 'reason': '纜線張力過高', 'points': 10}],
                'objectives': [{'label': '檢查點 1', 'done': True}]},
            'events': [{'kind': 'visibility', 'vehicle_id': 'v1', 'start': 9, 'end': 20}],
            'collisions': [{'t': 15, 'obstacle': 'leg', 'severity': 'hard'}],
            'trajectory': [{'t': 0, 'pos': [0, 0, 1], 'wraps': {}, 'collisions': [], 'completion': {}}],
            'matrix': {'descent': {'still': {'path': {'grade': 'green'}}}},
        }
        events = extract_events_from_report(report)
        kinds = {e['kind'] for e in events}
        self.assertIn('instructor_inject', kinds)
        self.assertIn('collision', kinds)
        self.assertIn('penalty', kinds)
        html = build_html_report(report, events=events, notes='注意纜線回彈')
        self.assertIn(STRINGS['title'], html)
        self.assertIn(STRINGS['viewpointBanner'], html)
        self.assertIn('注意纜線回彈', html)
        self.assertIn(STRINGS['instructor_inject'], html)
        self.assertNotIn('QYSIM_INSTRUCTOR', html)

    def test_attach_debrief_preserves_legacy_clips(self):
        recording = {
            'format': 'qysim-replay-2', 'hz': 6,
            'clips': [{'key': 'a', 'title': 'A', 'world': {}, 'script': [], 'frames': [
                {'t': 0, 'events': [], 'tether': {'warn': False, 'broken': False, 'wraps': {}},
                 'silt': 0, 'score': {'objectives': [], 'penalties': []}},
                {'t': 6, 'events': [{'t': 6, 'obstacle': 'x', 'severity': 'hard', 'where': 'nose'}],
                 'tether': {'warn': False, 'broken': False, 'wraps': {}},
                 'silt': 0, 'score': {'objectives': [], 'penalties': []}},
            ]}],
        }
        enriched = attach_debrief(recording, notes='ok')
        self.assertEqual(enriched['format'], 'qysim-replay-2')
        self.assertEqual(len(enriched['clips'][0]['frames']), 2)
        self.assertEqual(enriched['debrief']['notes'], 'ok')
        self.assertTrue(any(e['kind'] == 'collision' for e in enriched['debrief']['events']))
        # Stored events win over recomputation.
        recording['debrief'] = {'events': [{'kind': 'penalty', 't': 1, 'detail': 'manual'}]}
        self.assertEqual(merge_recording_events(recording)[0]['kind'], 'penalty')

    def test_report_to_replay_round_trip(self):
        report = {
            'vehicle_id': 'v2', 'elapsed': 2,
            'events': [{'kind': 'dvl', 'start': 1.5, 'vehicle_id': 'v2'}],
            'completion': {'score': 10, 'objectives': [], 'penalties': []},
            'trajectory': [
                {'t': 0, 'pos': [0, 0, 1], 'tension': 1, 'wraps': {}, 'collisions': [],
                 'completion': {'score': 0}},
                {'t': 1, 'pos': [1, 0, 2], 'tension': 2, 'wraps': {'a': 1}, 'collisions': [],
                 'completion': {'score': 10}},
            ],
            'supervision': {'world': {'seabed_depth': 20, 'obstacles': []}},
        }
        replay = report_to_replay(report)
        self.assertEqual(replay['format'], 'qysim-replay-2')
        self.assertEqual(len(replay['clips'][0]['frames']), 2)
        self.assertTrue(any(e['kind'] == 'instructor_inject' for e in replay['debrief']['events']))


if __name__ == '__main__':
    unittest.main()
