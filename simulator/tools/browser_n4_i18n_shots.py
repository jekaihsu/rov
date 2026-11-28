"""N4 acceptance screenshots: main menu, contract board, pre-dive checklist, settlement.

Four languages at 1600x900. Writes to docs/i18n/screenshots/n4/ when ROV_I18N_UPDATE_DOCS=1,
otherwise simulator/output/n4-i18n-screenshots/.
"""
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_internal, open_main, set_intro, wait_ready, wait_screen

DOCS = Path(__file__).resolve().parents[2] / 'docs' / 'i18n' / 'screenshots' / 'n4'
RUN = Path(__file__).resolve().parents[1] / 'output' / 'n4-i18n-screenshots'
OUT = DOCS if os.environ.get('ROV_I18N_UPDATE_DOCS') == '1' else RUN
OUT.mkdir(parents=True, exist_ok=True)

INIT = "localStorage.setItem('rov.intro.seen.v1', '1');"
POOL_SCRIPT = [
    [[0, 3.8, 3], 0, 230, False],
    [[6, 0, 4], 0, 2, True],
    [[0, 6, 4], 90, 2, True],
    [[-6, 0, 4], 180, 2, True],
    [[0, 0, 0.6], 0, 5, False],
]
DRIVE = '''(steps) => {
  const base = window.__viewer.S;
  let t = base.t + 1;
  for (const [pos, heading, frames, photo] of steps) {
    let state = null;
    for (let i = 0; i < frames; i++) {
      t += 0.1;
      state = {...base, t, pos, euler: [0, 0, heading], vel: [0, 0, 0], locked: false, keep_depth: true, paused: false,
        events: base.events, tether: {...base.tether, warn: false, wraps: {}}};
      window.__career.observe(state);
    }
    if (photo) window.__career.photoAt(state);
  }
  return window.__career.snapshot();
}'''


def shot(page, language, screen):
    page.set_viewport_size({'width': 1600, 'height': 900})
    page.wait_for_timeout(400)
    path = OUT / f'{language}-{screen}-1600.jpg'
    page.screenshot(path=str(path), type='jpeg', quality=78)
    print(path.name, flush=True)


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        for language in ['zh-Hant', 'en', 'zh-Hans', 'ja']:
            page = browser.new_page(viewport={'width': 1600, 'height': 900}, locale='zh-TW')
            page.set_default_timeout(timeout(30000))
            page.add_init_script(INIT)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            room = f'n4{language}{time.time_ns()}'
            page.goto(
                f'{http_base()}/?lang={language}&nointro&quality=performance'
                f'&fidelity=assisted&procedure=full&room={room}&ws={ws_base()}'
            )
            wait_ready(page)
            assert page.locator('html').get_attribute('lang') == language
            open_main(page)
            page.wait_for_timeout(500)
            shot(page, language, 'menu')

            open_internal(page)
            page.click('#entry-contracts')
            wait_screen(page, 'board')
            page.wait_for_timeout(600)
            shot(page, language, 'board')

            page.click('[data-contract="p1_pool_checkout"]')
            wait_screen(page, 'contract')
            page.click('#contractAccept')
            page.wait_for_function('window.__viewer?.S', timeout=timeout(90000))
            page.wait_for_timeout(1500)
            # Pre-dive checklist column when procedure=full.
            if page.locator('.pp-column, #procedurePanel, .procedure-panel').count():
                page.wait_for_timeout(800)
            shot(page, language, 'predive')

            # Finish the pool checkout via career hooks when available; otherwise skip settle shot.
            if page.evaluate('!!window.__career?.observe'):
                page.evaluate(DRIVE, POOL_SCRIPT)
                page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(20000))
                page.wait_for_timeout(800)
                shot(page, language, 'settle')
            assert not errors, (language, errors)
            page.close()
        browser.close()
    print('N4 screenshots written to', OUT)


if __name__ == '__main__':
    run()
