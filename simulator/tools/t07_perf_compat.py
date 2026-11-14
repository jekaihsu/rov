"""Run the existing perf scripts with this environment's Chromium.

Usage: python tools/t07_perf_compat.py REPO fleet|expedition [performance]
The expedition adapter invokes the current camera API instead of clicking the
hidden engineering-panel button. No product source or benchmark loops change.
"""
from pathlib import Path
from shutil import which
import sys
from playwright.sync_api import BrowserType

root = Path(sys.argv[1]).resolve()
kind = sys.argv[2]
if kind not in ('fleet', 'expedition'):
    raise ValueError('Expected fleet or expedition')
script = root/'simulator'/'tools'/f'browser_{kind}_perf.py'
sys.path.insert(0, str(script.parent))
original_launch = BrowserType.launch


def launch_with_chromium(self, *args, **kwargs):
    if kwargs.get('channel') == 'chrome' and which('chromium'):
        kwargs.pop('channel')
        kwargs['executable_path'] = which('chromium')
    return original_launch(self, *args, **kwargs)


BrowserType.launch = launch_with_chromium
source = script.read_text()
if kind == 'expedition':
    source = source.replace("page.locator('.exp-onboard').click()",
                            "page.evaluate('window.__viewer.setCam(\"onboard\")')")
    if len(sys.argv) > 3 and sys.argv[3] == 'performance':
        source = source.replace('quality=medium', 'quality=performance')
        source = source.replace('===\"medium\"', '===\"performance\"')
        source = source.replace('medium quality', 'performance quality')
exec(compile(source, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})
