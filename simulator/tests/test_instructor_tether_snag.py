"""Instructor tether_snag uses the existing Simulator._prewrap helix around a pile."""
import unittest

from qysim.engine import Simulator
from qysim.room import Room


class InstructorTetherSnagTests(unittest.TestCase):
    def test_prewrap_on_nearest_pile(self):
        room = Room(Simulator('monopile_current', 42))
        instructor = room.instructor
        sim = room.primary
        instructor.inject({'kind': 'tether_snag', 'strength': 0.5, 'duration': 30})
        self.assertEqual(instructor.active[0]['kind'], 'tether_snag')
        self.assertEqual(instructor.active[0]['pile'], 'Monopile M1')
        for _ in range(100):
            sim.step(0.01)
        self.assertIn('Monopile M1', sim.tether.wraps)
        self.assertGreater(abs(sim.tether.wraps['Monopile M1']), 0.25)
        # Expiry does not unwind the cable; the student must clear it or reset the scene.
        instructor.update(31)
        self.assertFalse(instructor.active)
        self.assertIn('Monopile M1', sim.tether.wraps)

    def test_rejects_when_no_wrapable_pile(self):
        room = Room(Simulator('open_water', 42))
        with self.assertRaises(ValueError):
            room.instructor.inject({'kind': 'tether_snag', 'strength': 0.5, 'duration': 10})


if __name__ == '__main__':
    unittest.main()
