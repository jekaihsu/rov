"""Procedural cable score and yaw continuity regressions."""
import math
import unittest
from qysim.tether_ops import TetherOperations


def cable(wrap=1.25, tension=0):
    return dict(length=15, nodes=[[0, 0, 0], [8, 0, 10], [8, 3, 10]],
                tension_max=tension, wraps={'Pile P1': wrap} if wrap else {}, broken=False)


class TetherOpsTest(unittest.TestCase):
    def test_yaw_boundary(self):
        ops = TetherOperations()
        ops.step(.01, cable(0), [8, 3, 10], math.radians(179))
        ops.step(.01, cable(0), [8, 3, 10], math.radians(-179))
        self.assertAlmostEqual(ops.turns, 2 / 360)

    def test_procedure(self):
        def run(tension, returned):
            ops = TetherOperations()
            ops.step(.01, cable(), [8, 3, 10], -math.pi / 2)
            pos = [8, 1, 10] if returned else [8, 4, 10]
            ops.step(2, cable(.7, tension), pos, -math.pi / 2)
            ops.step(.01, cable(0, tension), pos, -math.pi / 2)
            return ops.result
        good = run(0, True)
        bad = run(1000, False)
        self.assertGreaterEqual(good['score'], 90)
        self.assertLess(bad['score'], 30)
        self.assertTrue(good['correct'])

    def test_contact_alone_is_not_wrap(self):
        ops = TetherOperations()
        ops.step(.01, cable(0), [8, 3, 10], 0)
        self.assertIsNone(ops.episode)

    def test_reverse_and_multiple_turns(self):
        ops = TetherOperations()
        for i in range(201):
            ops.step(.01, cable(0), [8, 3, 10], i * math.tau / 50)
        self.assertAlmostEqual(ops.turns, 4)
        self.assertLess(ops.state()['torque_nm'], 0)
        for i in range(200, -1, -1):
            ops.step(.01, cable(0), [8, 3, 10], i * math.tau / 50)
        self.assertAlmostEqual(ops.turns, 0)

    def test_break_and_discipline(self):
        ops = TetherOperations()
        state = cable(tension=3000)
        ops.step(5, state, [8, 3, 10], 0)
        state['broken'] = True
        ops.step(.01, state, [8, 3, 10], 0)
        self.assertEqual(ops.result['score'], 0)
        self.assertLess(ops.state()['discipline_score'], 100)

    def test_length_radio_is_bounded(self):
        ops = TetherOperations()
        state = cable(0)
        for length in range(5, 200, 5):
            state['length'] = length
            ops.step(.01, state, [8, 3, 10], 0)
        self.assertEqual(len(ops.events), 20)
        self.assertEqual(ops.events[-1]['metres'], 195)
