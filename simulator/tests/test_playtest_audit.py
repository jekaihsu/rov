"""Exercise the wall-clock audit on deterministic traces without a browser."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from playtest_audit import analyze, classify_error, controls, findings
from playtest_report import frame_stats


def cue(t, beat='hover', hints=(), radio=()):
    return dict(t=t, beat=beat, hints=list(hints), radio=list(radio))


class TimelineTest(unittest.TestCase):
    def test_thresholds_and_trailing_interval(self):
        self.assertEqual(analyze([cue(0), cue(30, 'turn')], 60), ([], [], []))
        self.assertEqual(analyze([cue(0), cue(50, radio=['提醒'])], 120),
                         ([(0, 50), (50, 120)], [(0, 120)], []))

    def test_overlap_is_an_episode_and_disappearance_is_silent(self):
        events = [cue(0, hints=['A', 'B']), cue(1, hints=['A', 'B']), cue(2, hints=['A']),
                  cue(33, hints=['A', 'B'])]
        gaps, stalls, overlaps = analyze(events, 34)
        self.assertEqual(gaps, [(0, 33)])
        self.assertEqual(stalls, [])
        self.assertEqual(overlaps, [(0, ('A', 'B')), (33, ('A', 'B'))])

    def test_identical_text_at_new_node_advances(self):
        self.assertEqual(analyze([cue(0), cue(90, 'photo')], 121),
                         ([(0, 90), (90, 121)], [], []))

    def test_photo_approach_uses_live_controls_and_standoff(self):
        state = dict(beat='wall', type=None, cold=False, locked=False, coldHint=None, goal='wall',
                     pos=[0, 0, 3], heading=0, controls={'surge': {'keys': ['ArrowUp', 'ArrowDown']}})
        job = {'deliverables': [{'id': 'wall', 'kind': 'photo', 'point': [10, 0, 3], 'standoff': [1, 3]}]}
        self.assertEqual(controls(state, job), (['ArrowUp'], None))
        self.assertEqual(controls(dict(state, pos=[8, 0, 3]), job), ([], 'p'))

    def test_partial_progress_restarts_only_stall_clock(self):
        events = [cue(0), dict(cue(70), advanced=True)]
        self.assertEqual(analyze(events, 125), ([(0, 125)], [], []))

    def test_brakes_while_approaching_hover_point(self):
        state = dict(beat='hover', type=None, cold=False, locked=False, coldHint=None, goal='hover',
                     pos=[0, 0, 3], heading=0, velocity=[1, 0, 0],
                     controls={'surge': {'keys': ['ArrowUp', 'ArrowDown']}})
        job = {'deliverables': [{'id': 'hover', 'kind': 'station_keep', 'point': [.5, 0, 3]}]}
        self.assertEqual(controls(state, job), (['ArrowDown'], None))

    def test_deck_and_loading_never_spam_space(self):
        locked = dict(beat='checks/繞機/開始繞機', type=None, cold=False, locked=True, coldHint=None,
                      goal='hover', procedure=True, pos=[0, 0, 0], heading=0, controls={})
        self.assertEqual(controls(locked, {}), ([], None))
        loading = dict(locked, beat='loading', procedure=False)
        self.assertEqual(controls(loading, {}), ([], None))

    def test_directed_prologue_unlock_and_photo_station(self):
        axes = {'surge': {'keys': ['w', 's']}, 'yaw': {'keys': ['ArrowRight', 'ArrowLeft']},
                'heave': {'keys': ['ArrowUp', 'ArrowDown']}, 'lock': {'keys': ['Space']},
                'photo': {'keys': ['p']}, 'depth': {'keys': ['h']}}
        unlock = dict(beat='unlock', directed=True, locked=True, pos=[0, 0, 3], heading=0, controls=axes)
        self.assertEqual(controls(unlock, {}), ([], 'Space'))
        approach = dict(unlock, beat='approach', locked=False)
        self.assertEqual(controls(approach, {}), (['w'], None))
        plate = dict(approach, beat='A', target=[11.75, 0, 4], pos=[0, 0, 4], heading=0)
        held, tap = controls(plate, {})
        self.assertIn('w', held)
        self.assertIsNone(tap)
        framed = dict(plate, pos=[7.75, 0, 4])
        held, tap = controls(framed, {})
        self.assertEqual(tap, 'p')

    def test_connection_errors_are_harness_findings(self):
        self.assertEqual(classify_error('無法連線到模擬器'), 'harness')
        self.assertEqual(classify_error('invalid_command 請依序完成檢查'), 'level')
        runs = {
            'a': {'status': '工具失敗（載入超時）', 'harness': True, 'errors': []},
            'b': {'status': '卡關', 'errors': [[1, 'invalid_command', 'level']]},
            'c': {'status': '完成', 'errors': []},
        }
        self.assertEqual(findings(runs), ['a', 'b'])

    def test_missing_frame_seconds_and_long_frame_threshold(self):
        frames = [(1.0, .200000000000001, 'a'), (3.5, 2.5, 'b')]
        self.assertEqual(frame_stats(frames), ({1: [1, 200.0], 2: [0, None], 3: [1, 2500.0]}, [frames[1]]))
