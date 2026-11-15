"""Regression coverage for resumable cable batches and low-frequency sensor work."""
import unittest
from unittest.mock import patch

from qysim._cable_accel import compiled_available
from qysim.engine import Simulator


def use_loop(contacts, *args):
    return False, None, None, contacts


class TickPerformance(unittest.TestCase):
    @unittest.skipUnless(compiled_available(), 'optional Numba accelerator unavailable')
    def test_resumed_batches_match_substep_loop(self):
        batch = Simulator('incident_wreck', seed=42)
        reference = Simulator('incident_wreck', seed=42)
        refreshes = 0
        for tick in range(600):
            batch.step(0.01)
            with patch.object(reference.tether, '_run_batch', side_effect=use_loop):
                reference.step(0.01)
            refreshes += batch.tether.last_batch_refreshes
            for left, right in ((batch.tether.x, reference.tether.x),
                                (batch.tether.v, reference.tether.v),
                                (batch.tether.force_on_rov, reference.tether.force_on_rov),
                                (batch.vehicle.s.pos, reference.vehicle.s.pos)):
                self.assertEqual(left.tobytes(), right.tobytes(), f'tick {tick}')
        self.assertGreater(refreshes, 0)

    def test_sensor_cadence_and_lazy_flow_grid(self):
        sim = Simulator('incident_wreck', seed=42)
        with patch.object(sim.sensors, '_sample_echo', wraps=sim.sensors._sample_echo) as echo:
            with patch.object(sim.sensors, '_fuse_magnetometer', wraps=sim.sensors._fuse_magnetometer) as mag:
                for _ in range(100):
                    sim.step(0.01)
        self.assertEqual(echo.call_count, 5)
        self.assertEqual(mag.call_count, 10)
        self.assertIsNone(sim._flow_grid)
        first = sim.flow_field_state()
        with patch.object(sim.world, 'current_at_many', wraps=sim.world.current_at_many) as sample:
            self.assertIs(first, sim.flow_field_state())
        sample.assert_not_called()
