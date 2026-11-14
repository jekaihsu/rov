"""Check the cable tender radio and the twist line on the HUD system card against a live server (T21).

Loads the tether_untangle scenario, waits for state.tether_ops, then checks that the tender's radio call is shown
on the story layer without covering the depth read-out, and that holding the system peek key adds the twist line.
Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import sys

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

TURNS_LABEL = '淨扭轉圈數'
SPEAKER = '甲板 · 纜線手'


def run():
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base()}/?play=1&nointro&scenario=tether_untangle&room=tethercheck&ws={ws_base()}',
                  wait_until='domcontentloaded')
        page.wait_for_function('window.__viewer?.S?.tether_ops', timeout=timeout(90000))
        page.wait_for_function('!(document.querySelector(".tether-radio")?.hidden ?? true)', timeout=timeout(30000))
        radio = page.locator('.tether-radio')
        assert SPEAKER in radio.inner_text(), radio.inner_text()
        layer = radio.evaluate('(el) => getComputedStyle(el).zIndex')
        story = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--z-story").trim()')
        assert layer == story, (layer, story)
        page.keyboard.down('Digit2')
        page.wait_for_function(f'document.querySelector("#flightPeek p")?.textContent.includes("{TURNS_LABEL}")',
                               timeout=timeout(15000))
        page.keyboard.up('Digit2')
        assert not errors, errors
        browser.close()
    print('Tether tender radio on the story layer and system-card twist line passed.')


if __name__ == '__main__':
    sys.exit(run())
