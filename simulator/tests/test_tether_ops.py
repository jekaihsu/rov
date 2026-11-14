"""Cable operations observer (T21): radio calls, twist warning, procedure scoring, payout discipline.

Unit cases drive ``TetherOperations`` with a stand-in exposing the solver fields it reads; the scenario cases run
the real tether solver in ``tether_untangle``.
"""
import json
import math
import unittest
from types import SimpleNamespace

import numpy as np

from qysim.tether_ops import TetherOperations


def fake_tether(wrap=1.25, tension=0.0, turns=0.0, length=15.0, hooks=()):
    """Stand-in with the Tether attributes the observer reads (gland working load 445 N, as X1)."""
    return SimpleNamespace(
        x=np.array([[0.0, 0, 0], [8, 0, 10], [8, 3, 10]]), length=length, tension_rov=tension,
        tension_max=tension, broken=False, snag_names=[], wraps={'Pile P1': wrap} if wrap else {},
        turns=turns, twist_torque_nm=-0.1 * math.tau * turns / length, over_working_load=tension > 445.0,
        p=SimpleNamespace(gland_warn_n=445.0), reel=SimpleNamespace(mode='free', stalled=False),
        snags=SimpleNamespace(hooks=list(hooks)))


class TetherOpsTest(unittest.TestCase):
    def test_procedure(self):
        def run(tension, returned):
            ops = TetherOperations()
            ops.step(.01, fake_tether(), [8, 3, 10], -math.pi / 2)
            pos = [8, 1, 10] if returned else [8, 4, 10]
            ops.step(2, fake_tether(.7, tension), pos, -math.pi / 2)
            ops.step(.01, fake_tether(0, tension), pos, -math.pi / 2)
            return ops.result
        good = run(0, True)
        bad = run(1000, False)
        self.assertGreaterEqual(good['score'], 90)
        self.assertLess(bad['score'], 30)
        self.assertTrue(good['correct'])
        self.assertEqual(good['kind'], 'wrap')

    def test_contact_alone_is_not_wrap(self):
        ops = TetherOperations()
        tether = fake_tether(0)
        tether.snag_names = ['Pile P1']
        ops.step(.01, tether, [8, 3, 10], 0)
        self.assertIsNone(ops.episode)
        self.assertEqual(ops.events[-1]['code'], 'structure')

    def test_twist_is_a_warning_from_the_solver_turns_not_a_force(self):
        ops = TetherOperations()
        self.assertIsNone(ops.step(.01, fake_tether(0, turns=1.5), [8, 3, 10], 0))
        self.assertFalse(any(event['code'] == 'twist' for event in ops.events))
        ops.step(.01, fake_tether(0, turns=2.2), [8, 3, 10], 0)
        state = ops.state()
        self.assertEqual(state['turns'], 2.2)
        self.assertTrue(state['twist_warning'])
        self.assertLess(state['torque_nm'], 0)                  # the solver's GJ moment, reported only
        self.assertEqual(ops.events[-1]['code'], 'twist')

    def test_snag_hook_episode_uses_the_solver_tracker(self):
        hook = SimpleNamespace(name='Harbor rubble', target=np.array([8.0, 1.0, 10.0]))
        ops = TetherOperations()
        ops.step(.01, fake_tether(0, hooks=[hook]), [8, 4, 10], -math.pi / 2)
        self.assertEqual(ops.state()['snag']['kind'], 'snag')
        ops.step(1, fake_tether(0, hooks=[hook]), [8, 2, 10], -math.pi / 2)
        ops.step(.01, fake_tether(0), [8, 2, 10], -math.pi / 2)
        self.assertTrue(ops.result['returned'])
        self.assertTrue(ops.result['correct'])
        self.assertGreaterEqual(ops.result['score'], 90)

    def test_reel_mode_and_stall_calls(self):
        ops = TetherOperations()
        tether = fake_tether(0)
        ops.step(.01, tether, [8, 3, 10], 0)
        tether.reel.mode = 'haul_in'
        ops.step(.01, tether, [8, 3, 10], 0)
        tether.reel.stalled = True
        ops.step(.01, tether, [8, 3, 10], 0)
        codes = [event['code'] for event in ops.events]
        self.assertEqual(codes[-2:], ['reel', 'stall'])
        self.assertEqual(ops.events[-2]['mode'], 'haul_in')

    def test_simulator_reports_tether_ops(self):
        from qysim.engine import Simulator
        sim = Simulator('tether_untangle', seed=1)
        for _ in range(20):
            sim.step()
        ops = sim.viewer_state()['tether_ops']
        self.assertEqual(ops['turns'], round(sim.tether.turns, 2))
        self.assertTrue(any(event['code'] == 'length' for event in ops['events']))
        json.dumps(ops)

    def test_break_and_discipline(self):
        ops = TetherOperations()
        tether = fake_tether(tension=3000)
        ops.step(5, tether, [8, 3, 10], 0)
        tether.broken = True
        ops.step(.01, tether, [8, 3, 10], 0)
        self.assertEqual(ops.result['score'], 0)
        self.assertLess(ops.state()['discipline_score'], 100)

    def test_length_radio_is_bounded(self):
        ops = TetherOperations()
        tether = fake_tether(0)
        for length in range(5, 200, 5):
            tether.length = length
            ops.step(.01, tether, [8, 3, 10], 0)
        self.assertEqual(len(ops.events), 20)
        self.assertEqual(ops.events[-1]['metres'], 195)


def drive_untangle(path, seconds, reel='hold'):
    """Move the vehicle along a scripted path in the stock tether_untangle scenario with the real cable solver.

    The pose is prescribed (kinematic) rather than flown through RC input, so this checks the scoring against the
    solver's wrap counts, not the pilot controller. The reel is braked, as a tender holds the line during a recovery.
    """
    from qysim.engine import Simulator
    from qysim.physics import q_from_euler
    sim = Simulator('tether_untangle', seed=1)
    state = sim.vehicle.s
    # Start from the path's first pose: re-lay the scenario's wrap there instead of teleporting a wrapped cable.
    x, y, yaw = path(0.0)
    state.pos[0] = x
    state.pos[1] = y
    state.q = q_from_euler(0, 0, yaw)
    sim._prewrap(sim.scenario.prewrap)
    sim.tether.settle(2.0, state.pos, state.q)
    sim.tether.reel_command(reel)
    for index in range(int(seconds / sim.dt)):
        x, y, yaw = path(index * sim.dt)
        state.pos[0] = x
        state.pos[1] = y
        state.q = q_from_euler(0, 0, yaw)
        state.vel[:] = 0
        state.omega[:] = 0
        sim.step()
        if sim.tether_ops.result or sim.tether.broken:
            break
    return sim.tether_ops.result


class TetherUntangleScenarioTest(unittest.TestCase):
    def test_correct_procedure_scores_high_and_hard_pull_low(self):
        def unwind(t):
            angle = math.pi / 2 - 0.4 / 2.8 * t
            return 8 + 2.8 * math.cos(angle), 2.8 * math.sin(angle), angle - math.pi / 2

        def pull(t):
            return 8.0, 2.8 + t, math.pi / 2

        correct = drive_untangle(unwind, 120)
        hard = drive_untangle(pull, 120)
        self.assertIsNotNone(correct)
        self.assertIsNotNone(hard)
        self.assertGreaterEqual(correct['score'], 80)
        self.assertTrue(correct['returned'])
        self.assertLess(hard['score'], 30)
        self.assertGreater(hard['peak_n'], correct['peak_n'])


if __name__ == '__main__':
    unittest.main()
