"""Verify the quick-launch animation, its skip button and the ?nointro bypass when the procedure is not wanted (T23).

Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import sys

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base


def run():
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        base = (f'{http_base()}/?play=1&procedure=quick&quality=performance&model=bluerov2_heavy'
                f'&ws={ws_base()}')
        page.goto(base + '&room=t23-animation')
        page.wait_for_function('window.__intro?.()?.starts > 0', timeout=timeout(90000))
        assert not page.evaluate('window.__viewer.S.procedure.active')
        assert page.locator('#procedurePanel').is_hidden()
        page.evaluate('document.querySelector("#skipIntro").click()')
        page.wait_for_function('!window.__intro().playing', timeout=timeout(30000))
        # The real preset defaults to the full procedure, but ?nointro always skips it.
        page.goto(f'{http_base()}/?play=1&nointro&fidelity=real&room=t23-nointro&ws={ws_base()}')
        page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(90000))
        page.wait_for_timeout(1500)
        assert page.evaluate('window.__intro()') is None
        assert not page.evaluate('window.__viewer.S.procedure.active')
        assert not errors, errors
        browser.close()
    print('Quick-launch animation, skip and ?nointro compatibility passed.')


if __name__ == '__main__':
    sys.exit(run())
