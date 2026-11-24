"""Voice extract and synthesize CLI guards."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / 'tools' / 'voice' / 'extract_lines.py'
SYNTH = ROOT / 'tools' / 'voice' / 'synthesize.py'


class VoiceToolsTests(unittest.TestCase):
    def test_extract_prologue_ids_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'manifest.json'
            result = subprocess.run(
                [sys.executable, str(EXTRACT), '-o', str(out), '--chapter', 'prologue', '--language', 'zh-TW'],
                cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertIn('Wrote', result.stdout)
            manifest = json.loads(out.read_text(encoding='utf-8'))
            self.assertGreaterEqual(manifest['count'], 7)
            first = manifest['lines'][0]
            again = subprocess.run(
                [sys.executable, str(EXTRACT), '-o', str(out), '--chapter', 'prologue', '--language', 'zh-TW'],
                cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertEqual(again.returncode, 0)
            second = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual([row['id'] for row in manifest['lines']],
                             [row['id'] for row in second['lines']])
            self.assertEqual(first['speaker'], '林岑')

    def test_synthesize_requires_api_key(self):
        env = {key: value for key, value in os.environ.items() if key != 'OPENAI_API_KEY'}
        result = subprocess.run(
            [sys.executable, str(SYNTH), '--chapter', 'prologue', '--language', 'zh-TW'],
            cwd=ROOT, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn('OPENAI_API_KEY', result.stderr)


if __name__ == '__main__':
    unittest.main()
