"""Unit tests for the third-party notices generator."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/third_party_notices.py'
spec = importlib.util.spec_from_file_location('third_party_notices', SCRIPT)
notices = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = notices
spec.loader.exec_module(notices)


class TestLicenseAllowList(unittest.TestCase):
    def test_allowed_licences(self):
        for text in ('MIT', 'BSD-3-Clause', 'Apache-2.0', 'zlib', 'CC0 1.0',
                     'Public Domain Mark 1.0', 'BSD-2-Clause AND Apache-2.0 WITH LLVM-exception'):
            self.assertTrue(notices.license_allowed(text), text)

    def test_disallowed_licences(self):
        for text in ('GPL-2.0-or-later', 'PSF License', 'Bitstream Vera License', 'unknown', ''):
            self.assertFalse(notices.license_allowed(text), text)


class TestCollectAndRender(unittest.TestCase):
    def test_collect_includes_core_entries(self):
        report = notices.collect_all()
        names = {entry.name for entry in report.notices}
        self.assertIn('three.js', names)
        self.assertIn('steamworks.js', names)
        self.assertIn('three', names)
        self.assertIn('numpy', names)
        self.assertIn('worker.glb', names)
        self.assertIn('title_goldberg_aria.opus', names)
        self.assertTrue(report.disallowed, 'expected at least one outside-allow-list item')
        text = notices.render(report)
        self.assertIn('ROV Solution — Third-Party Notices', text)
        self.assertIn('outside allow-list', text)
        self.assertIn('three.js', text)

    def test_write_updates_desktop_and_viewer_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'THIRD_PARTY_NOTICES.txt'
            viewer = Path(temp) / 'viewer-copy.txt'
            with mock.patch.object(notices, 'VIEWER_COPY', viewer):
                report = notices.write_notices(out)
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_text(encoding='utf8'), viewer.read_text(encoding='utf8'))
            self.assertGreater(len(report.notices), 10)

    def test_check_detects_stale_file(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'THIRD_PARTY_NOTICES.txt'
            viewer = Path(temp) / 'viewer-copy.txt'
            out.write_text('stale\n', encoding='utf8')
            viewer.write_text('stale\n', encoding='utf8')
            with mock.patch.object(notices, 'VIEWER_COPY', viewer):
                with mock.patch('sys.stdout', new_callable=mock.MagicMock):
                    code = notices.main(['--check', '--output', str(out)])
            self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
