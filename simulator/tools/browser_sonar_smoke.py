"""Check the imaging sonar panel against a live server (T15).

Loads the low-visibility sonar_search scenario, opens the sonar with its bound key (`sonarPeek`, Digit5), waits for
subscribed scans to arrive in state.sonar, checks the panel layer and frame format, that a shown HUD range read-out
names sonar as its source, and that closing the panel stops the scans.
Screenshot: output/t15/sonar.png. Addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 't15'
TAP = '''(code) => {
  for (const type of ['keydown', 'keyup']) document.body.dispatchEvent(new KeyboardEvent(type, {code, bubbles: true}));
}'''


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base()}/?play=1&nointro&scenario=sonar_search&room=sonarcheck&ws={ws_base()}',
                  wait_until='domcontentloaded')
        page.wait_for_function('window.__viewer?.W?.scenario?.key === "sonar_search"', timeout=timeout(90000))
        assert page.evaluate('window.__viewer.S.sonar') is None
        # Open and pin in one task: the peek closes itself after 3 s, which software rendering can outlast.
        page.evaluate('''(tap) => {
          eval(tap)('Digit5');
          const pin = document.querySelector('.sonar-panel input[type=checkbox]');
          pin.checked = true;
          pin.dispatchEvent(new Event('change'));
        }''', TAP)
        page.wait_for_function('!document.querySelector(".sonar-panel").hidden', timeout=timeout(15000))
        page.wait_for_function('window.__viewer.S?.sonar?.beams === 256', timeout=timeout(30000))
        layer = page.locator('.sonar-panel').evaluate('(el) => getComputedStyle(el).zIndex')
        controls = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--z-controls").trim()')
        assert layer == controls, (layer, controls)
        frame = page.evaluate('window.__viewer.S.sonar')
        assert len(frame['distance_m']) == 256 and all(0 <= value <= 255 for value in frame['intensity'])
        page.wait_for_timeout(1500)
        reading = page.locator('#flightRange').inner_text()
        assert reading == '' or reading.startswith('聲納'), reading
        page.screenshot(path=str(OUT / 'sonar.png'))
        page.evaluate(TAP, 'Digit5')
        page.wait_for_function('document.querySelector(".sonar-panel").hidden')
        page.wait_for_function('!window.__viewer.S.sonar', timeout=timeout(15000))
        assert not errors, errors
        browser.close()
    print('Sonar peek key, scans, panel layer and unsubscribe passed.')


if __name__ == '__main__':
    sys.exit(run())
