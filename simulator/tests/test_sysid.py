"""Known-parameter recovery and invalid-input checks for offline identification."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools.sysid.core import analyze, fit_axis, fit_thrust, tether, trajectory
from tools.sysid.import_data import telemetry_control, video_motion
from tools.sysid.synthetic import generate


class SysidTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.source = Path(cls.temp.name)/'data'
        generate(cls.source)
        cls.report = analyze(cls.source, Path(cls.temp.name)/'report')
        cls.meta = json.loads((cls.source/'manifest.json').read_text())

    def test_known_parameters_with_noise(self):
        for axis, truth in self.meta['truth'].items():
            actual = self.report['axes'][axis]
            for name in ('added_mass', 'linear_drag', 'quadratic_drag'):
                with self.subTest(axis=axis, name=name):
                    self.assertLess(abs(actual[name]/truth[name]-1), .05)
                    self.assertEqual(len(actual['ci95'][name]), 2)
                    self.assertLess(actual['ci95'][name][0], actual['ci95'][name][1])
            for direction in ('positive', 'negative'):
                a, b = actual['thrust_curve'][direction]['coefficients']
                self.assertLess(abs(a/truth['thrust_linear']-1), .05)
                # Relative error is undefined for the simulator's zero quadratic term.
                self.assertLess(abs(b), .1)
        self.assertLess(abs(self.report['tether']['density']['value']/1000-1), .05)
        self.assertLess(self.report['controller']['depth_rmse_m'], .01)
        self.assertLess(self.report['controller']['heading_rmse_deg'], .1)
        for image in (Path(self.temp.name)/'report').glob('*.png'):
            self.assertEqual(image.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(len(list((Path(self.temp.name)/'report').glob('*.png'))), 8)

    def test_nonzero_asymmetric_curve_and_irregular_time(self):
        anchor = [{'command': u, 'force_n': (80 if u > 0 else 60)*u+20*u*abs(u)}
                  for u in [-1, -.8, -.5, -.2, .2, .5, .8, 1]]
        curve = fit_thrust(anchor)
        self.assertAlmostEqual(curve['positive']['coefficients'][1], 20)
        self.assertAlmostEqual(curve['negative']['coefficients'][0], 60)
        time = np.cumsum(np.tile([.08, .12, .1], 150))
        command = np.repeat([0, .3, 0, .8, 0, -.4, 0, -1, 0], 50)
        velocity = trajectory(time, command, 0, [50, 12, 70], curve, .08, -2.943)
        rows = [dict(time_s=t, velocity_m_s=v, command=u) for t, v, u in zip(time, velocity, command)]
        result, _, _ = fit_axis(rows, anchor, 30, .08, -2.943)
        self.assertAlmostEqual(result['added_mass'], 20, places=3)
        bad = copy.deepcopy(rows)
        bad[1]['time_s'] = bad[0]['time_s']
        with self.assertRaises(ValueError):
            fit_axis(bad, anchor, 30, .08)
        with self.assertRaises(ValueError):
            fit_axis(rows, [], 30, .08)
        with self.assertRaises(ValueError):
            fit_axis([dict(r, command=0) for r in rows], anchor, 30, .08)
        bad[1]['velocity_m_s'] = float('nan')
        with self.assertRaises(ValueError):
            fit_axis(bad, anchor, 30, .08)

    def test_imports_and_signed_wet_weight(self):
        control = telemetry_control(self.source/'telemetry.jsonl')
        self.assertEqual(len(control), 201)
        motion = video_motion(self.source/'video.csv')
        self.assertEqual({r['axis'] for r in motion}, {'surge', 'sway', 'heave'})
        self.assertTrue(np.isfinite([r['velocity_m_s'] for r in motion]).all())
        values = tether([dict(length_m=10, dry_mass_kg=1, wet_force_n=-1,
                              diameter_m=.01, water_density_kg_m3=1025)]*3)
        self.assertAlmostEqual(values['wet_weight_n_m']['value'], -.1)
        self.assertAlmostEqual(values['buoyancy_n_m']['value'], 1.081)


if __name__ == '__main__':
    unittest.main()
