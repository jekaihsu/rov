"""Startup line that tells the operator which tether path is active."""
from pathlib import Path
import unittest
from unittest.mock import patch

from qysim import _cable_accel

SIM_DIR = Path(__file__).resolve().parents[1]


class SolverStatusTests(unittest.TestCase):
    def test_compiled_line(self):
        line = _cable_accel.solver_status_line(compiled=True)
        self.assertTrue(line.startswith('[qysim] tether solver: compiled'))
        self.assertNotIn('\n', line)

    def test_fallback_line_names_the_fix(self):
        line = _cable_accel.solver_status_line(compiled=False)
        self.assertIn('NumPy fallback', line)
        self.assertIn('pip install -r requirements-fast.txt', line)
        self.assertNotIn('\n', line)

    def test_default_follows_the_importable_path(self):
        with patch.object(_cable_accel, 'advance_batch', None):
            self.assertFalse(_cable_accel.compiled_available())
            self.assertIn('NumPy fallback', _cable_accel.solver_status_line())
        with patch.object(_cable_accel, 'advance_batch', object()):
            self.assertTrue(_cable_accel.compiled_available())
            self.assertIn('compiled', _cable_accel.solver_status_line())

    def test_fast_requirements_keep_numba_optional(self):
        fast = (SIM_DIR / _cable_accel.FAST_REQUIREMENTS).read_text(encoding='utf-8')
        base = (SIM_DIR / 'requirements.txt').read_text(encoding='utf-8')
        self.assertIn('numba', fast)
        self.assertIn('-r requirements.txt', fast)
        self.assertNotIn('numba', base)


if __name__ == '__main__':
    unittest.main()
