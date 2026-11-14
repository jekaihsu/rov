"""PROTOCOL.md examples that must track the server: capacity, vehicle ids and error codes."""
from pathlib import Path
import re
import unittest

from qysim.room import Room

SIM_DIR = Path(__file__).resolve().parents[1]
PROTOCOL = (SIM_DIR / 'PROTOCOL.md').read_text(encoding='utf-8')
SERVER = (SIM_DIR / 'qysim' / 'server.py').read_text(encoding='utf-8')


class ProtocolDocumentTests(unittest.TestCase):
    def test_capacity_examples_match_the_room(self):
        capacities = [int(value) for value in re.findall(r'"capacity":(\d+)', PROTOCOL)]
        self.assertTrue(capacities)
        self.assertEqual(set(capacities), {Room.capacity})
        self.assertIn(f'v1–v{Room.capacity} (room-local)', PROTOCOL)

    def test_error_code_list_covers_the_server(self):
        listed = re.search(r'"type":"error","code":"([a-z_|]+)"', PROTOCOL).group(1).split('|')
        emitted = set(re.findall(r'"type": "error", "code": "([a-z_]+)"', SERVER))
        self.assertIn('instructor_override', emitted)
        self.assertIn('controller_only', emitted)
        self.assertEqual(emitted - set(listed), set())

    def test_viewer_default_is_manual_in_the_real_preset(self):
        self.assertNotIn('The viewer defaults to `assist:2`', PROTOCOL)
        self.assertIn('sends `assist:0`', PROTOCOL)
        self.assertNotIn('disables authentication', PROTOCOL)


if __name__ == '__main__':
    unittest.main()
