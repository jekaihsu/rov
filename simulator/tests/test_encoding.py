"""Backend text files must load under a non-UTF-8 locale (Windows code pages, LC_ALL=C)."""
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

SIM_DIR = Path(__file__).resolve().parents[1]
ROOM_PROBE = (
    "import locale, sys\n"
    "assert sys.flags.utf8_mode == 0, 'probe must not run in UTF-8 mode'\n"
    "assert locale.getpreferredencoding(False).lower().replace('-', '') != 'utf8', 'locale is still UTF-8'\n"
    "from qysim.engine import Simulator\n"
    "from qysim.room import Room\n"
    "room = Room(Simulator('open_water', 42))\n"
    "assert room.campaign.scripts['prologue']['title'] == '\\u5e8f\\u7ae0\\uff5c\\u898b\\u7fd2\\u4e4b\\u524d'\n"
    "print('room-ok')\n"
)
# A text read whose encoding is left to the platform default.
IMPLICIT_READ = re.compile(r"\.read_text\(\s*\)|json\.load\(open\([^)]*\)\)")


def non_utf8_environment():
    env = dict(os.environ)
    for name in ('PYTHONUTF8', 'PYTHONIOENCODING', 'LANG', 'LANGUAGE'):
        env.pop(name, None)
    env['LC_ALL'] = 'C'
    env['PYTHONCOERCECLOCALE'] = '0'
    return env


class NonUtf8LocaleTests(unittest.TestCase):
    def test_room_starts_without_utf8_locale(self):
        result = subprocess.run([sys.executable, '-X', 'utf8=0', '-c', ROOM_PROBE], cwd=str(SIM_DIR),
                                env=non_utf8_environment(), capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        self.assertIn(b'room-ok', result.stdout)

    def test_backend_sources_name_their_encoding(self):
        offenders = []
        for folder in ('qysim', 'sdk_mock', 'tools'):
            for path in sorted((SIM_DIR / folder).rglob('*.py')):
                if path.name.startswith('browser_'):
                    continue
                source = path.read_text(encoding='utf-8')
                for number, line in enumerate(source.splitlines(), 1):
                    if IMPLICIT_READ.search(line):
                        offenders.append(f'{path.relative_to(SIM_DIR)}:{number}')
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
