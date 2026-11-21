"""End-to-end recovery of a synthetic pool folder, and the checks that block a bad log."""
import json
import shutil
from pathlib import Path
import tempfile
import unittest

import numpy as np

from qysim.vehicles import X1_PARAMETERS
from tools.sysid.core import fit_track, plotting_available
from tools.sysid.field import read_table, summarise_speeds
from tools.sysid.fit_x1 import fit_x1
from tools.sysid.osd import paint_readout, read_frame
from tools.sysid.synthetic import generate_field
from tools.sysid.__main__ import main


class FieldPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.source = Path(cls.temp.name) / 'field'
        generate_field(cls.source)
        manifest_path = cls.source / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        cls.truth = manifest.pop('truth')
        manifest_path.write_text(json.dumps(manifest) + '\n', encoding='utf-8')
        cls.vehicles = Path(__file__).resolve().parents[1] / 'qysim' / 'vehicles.py'
        cls.vehicles_bytes = cls.vehicles.read_bytes()
        cls.catalogue = json.loads(json.dumps({
            key: X1_PARAMETERS[key]['value'] for key in ('mass', 'thruster_max', 'added_mass', 'vmax')
        }))
        cls.output = Path(cls.temp.name) / 'report'
        cls.report = fit_x1(cls.source, cls.output)

    def test_recovers_mass_drag_and_thrust(self):
        self.assertIs(self.report['applied_to_vehicles_py'], False)
        self.assertTrue(self.report['synthetic'])
        self.assertEqual(self.report['suggestions']['evidence_level'], 'estimated')
        fit = self.report['fit']['axes']
        for index, axis in enumerate(('surge', 'sway', 'heave')):
            actual = fit[axis]
            truth_added = self.truth['added_mass'][index]
            truth_linear = self.truth['linear_drag'][index]
            truth_quadratic = self.truth['quadratic_drag'][index]
            self.assertLess(abs(actual['added_mass'] / truth_added - 1), 0.05)
            self.assertLess(abs(actual['linear_drag'] / truth_linear - 1), 0.05)
            self.assertLess(abs(actual['quadratic_drag'] / truth_quadratic - 1), 0.05)
            self.assertLess(actual['ci95']['added_mass'][0], actual['ci95']['added_mass'][1])
            decay = actual['model_decay_time_s']['positive']
            truth_decay = self.truth['coast'][axis]['positive']['one_over_e_s']
            self.assertLess(abs(decay - truth_decay), 0.15)
        self.assertTrue(self.report['suggestions']['thruster_max_consistent'])
        suggested = self.report['suggestions']['thruster_max_n']
        self.assertLess(abs(suggested / self.truth['thruster_max'] - 1), 0.05)
        self.assertIsNone(self.report['suggestions']['linear_drag'][3])

    def test_timing_yaw_coast_and_osd(self):
        for row in self.report['terminal_speed']:
            if not row['used_for_vmax']:
                continue
            index = ('surge', 'sway', 'heave').index(row['axis'])
            self.assertEqual(row['gear'], 'A')
            self.assertLess(abs(row['speed_m_s'] / self.truth['vmax'][index] - 1), 0.02)
        for axis in ('surge', 'sway', 'heave'):
            speeds = {row['gear']: row['speed_m_s'] for row in self.report['terminal_speed']
                      if row['axis'] == axis and row['direction'] == 'positive'}
            self.assertLess(abs(speeds['S']), abs(speeds['A']))
        yaw = [row for row in self.report['yaw'] if row['used_for_wmax']]
        self.assertEqual(len(yaw), 1)
        self.assertLess(abs(yaw[0]['rate_rad_s'] / self.truth['wmax_yaw'] - 1), 0.02)
        negative = [row for row in self.report['yaw'] if row['direction'] == 'negative'][0]
        self.assertLess(negative['rate_rad_s'], 0)
        for axis in ('surge', 'sway', 'heave'):
            coast = [row for row in self.report['coast']
                     if row['axis'] == axis and row['previous_command'] == 1.0][0]
            truth = self.truth['coast'][axis]['positive']['distance_m']
            self.assertLess(abs(coast['coast_distance_m'] - truth), 0.02)
            self.assertTrue(coast['settled'])
            self.assertGreater(coast['glide_time_s'], 0.05)
            self.assertLess(coast['glide_time_s'], coast['coast_duration_s'])
        readings = self.report['osd']['readings']
        self.assertEqual(self.report['osd']['low_confidence'], 0)
        self.assertEqual(len(readings), len(self.truth['osd']))
        for actual, truth in zip(readings, self.truth['osd']):
            self.assertAlmostEqual(actual['depth_m'], truth['depth_m'])
            self.assertAlmostEqual(actual['heading_deg'], truth['heading_deg'])
        text = (self.output / 'REPORT.md').read_text(encoding='utf-8')
        self.assertIn('合成資料', text)
        self.assertIn('不要貼進', text)
        self.assertIn('estimated', text)
        if plotting_available():
            for axis in ('surge', 'sway', 'heave'):
                image = self.output / f'{axis}-residual.png'
                self.assertEqual(image.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_catalogue_is_untouched(self):
        self.assertEqual(self.vehicles.read_bytes(), self.vehicles_bytes)
        self.assertEqual(X1_PARAMETERS['mass']['value'], self.catalogue['mass'])
        self.assertEqual(X1_PARAMETERS['thruster_max']['value'], self.catalogue['thruster_max'])
        self.assertEqual(X1_PARAMETERS['added_mass']['value'], tuple(self.catalogue['added_mass']))
        self.assertIsNone(X1_PARAMETERS['quadratic_drag']['value'])

    def test_command_and_missing_thrust_scale(self):
        cli_out = Path(self.temp.name) / 'cli'
        main(['fit-x1', str(self.source), '--output', str(cli_out)])
        self.assertTrue((cli_out / 'REPORT.md').exists())
        copied = Path(self.temp.name) / 'no-thrust'
        shutil.copytree(self.source, copied)
        (copied / 'thrust.csv').unlink()
        reduced = fit_x1(copied, Path(self.temp.name) / 'no-thrust-report')
        self.assertIsNone(reduced['fit'])
        self.assertIsNone(reduced['suggestions']['added_mass'])
        self.assertTrue(any('Absolute fit skipped' in warning for warning in reduced['warnings']))
        self.assertIsNotNone(reduced['suggestions']['vmax'])


class FieldFormatTests(unittest.TestCase):
    def test_chinese_headers_and_refuses_bad_inputs(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / 'timing.csv').write_text(
            '軸向,檔位,方向,距離,時間\nsurge,A,正,4,2\n', encoding='utf-8')
        summary = summarise_speeds(read_table(folder / 'timing.csv'), 'A')
        self.assertAlmostEqual(summary[0]['speed_m_s'], 2.0)
        self.assertTrue(summary[0]['used_for_vmax'])
        rows = [
            {'time_s': 0.0, 'position_m': 0.0, 'command': 1.0},
            {'time_s': 0.1, 'position_m': 0.1, 'command': 1.0},
            {'time_s': 0.2, 'position_m': 0.2, 'command': 0.0},
        ]
        with self.assertRaises(ValueError):
            fit_track(rows, [], 30.0, 0.08, 0.0)
        image, depth_box, _heading_box = paint_readout('-12.50', '000.0')
        roi = {'confirmed': False, 'depth': depth_box, 'heading': depth_box}
        with self.assertRaises(ValueError):
            read_frame(image, roi)
        roi['confirmed'] = True
        reading = read_frame(image, roi)
        self.assertAlmostEqual(reading['depth_value'], -12.5)
        self.assertTrue(np.isfinite(reading['heading_value']))


if __name__ == '__main__':
    unittest.main()
