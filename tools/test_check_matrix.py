"""Regression checks for CI selection boundaries and diff handling."""
import unittest
from unittest.mock import patch

from check_matrix import DEFAULT_CHECKS, browser_checks, changed_paths, unit_checks


class SelectionTests(unittest.TestCase):
    def test_backend_never_launches_browser(self):
        for tier in ('quick', 'full'):
            self.assertEqual(browser_checks(tier, ['simulator/qysim/server.py']), [])

    def test_hud_only(self):
        selected = browser_checks('full', ['simulator/viewer/hud/flight_hud.js'])
        self.assertEqual(selected, ['browser_hud_smoke', 'browser_overlay_smoke', 'browser_attitude_smoke'])

    def test_shared_viewer_and_mixed_changes(self):
        paths = ['simulator/viewer/hud/osd.js', 'simulator/viewer/app.js']
        self.assertEqual(browser_checks('full', paths), list(DEFAULT_CHECKS))

    def test_backend_with_viewer_uses_whole_tier(self):
        paths = ['simulator/qysim/server.py', 'simulator/viewer/hud/osd.js']
        self.assertEqual(browser_checks('full', paths), list(DEFAULT_CHECKS))

    def test_docs_and_empty_diff(self):
        for paths in ([], ['docs/ci/timings.md']):
            self.assertEqual(unit_checks('full', paths), [])
            self.assertEqual(browser_checks('full', paths), [])

    def test_changed_test_selected(self):
        self.assertEqual(unit_checks('full', ['simulator/tests/test_core.py']), ['test_core'])

    def test_changed_test_added_to_quick_tier(self):
        selected = unit_checks('quick', ['simulator/tests/test_core.py'])
        self.assertEqual(selected, ['test_core'])
        selected = unit_checks('quick', ['simulator/qysim/engine.py', 'simulator/tests/test_core.py'])
        self.assertIn('test_core', selected)
        self.assertIn('test_encoding', selected)

    def test_files_read_by_python_tests_select_units(self):
        all_units = unit_checks('full')
        for path in ('simulator/viewer/app.js', 'simulator/PROTOCOL.md', 'simulator/campaign/prologue.json',
                     'simulator/examples/demo.py', 'docs/reference/fit_measurements.py',
                     'simulator/tests/fixtures/data.json'):
            self.assertEqual(unit_checks('full', [path]), all_units, path)

    def test_node_tests_do_not_select_units(self):
        self.assertEqual(unit_checks('full', ['simulator/tests/test_menu.mjs', 'AGENTS.md']), [])

    def test_diff_includes_worktree_and_untracked(self):
        with patch('check_matrix.subprocess.check_output', side_effect=[
            'mergebase\n', b'simulator/viewer/hud/osd.js\0', b'new file.py\0'
        ]) as command:
            self.assertEqual(changed_paths(), ['new file.py', 'simulator/viewer/hud/osd.js'])
            self.assertEqual(command.call_args_list[1].args[0],
                             ['git', 'diff', '--no-renames', '--name-only', '-z', 'mergebase'])


if __name__ == '__main__':
    unittest.main()
