"""Photograph a live dive, end the dive and seek its local debrief to the shutter event."""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from browser_menu_gamepad_smoke import FAKE_PAD, frames

OUT = Path(__file__).resolve().parents[2] / 'docs/design/photo-replay-x3'


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': 960, 'height': 600})
        page.set_default_timeout(timeout(45000))
        page.add_init_script(FAKE_PAD)
        errors = []
        page.on('pageerror', lambda error: (errors.append(str(error)), print(error, flush=True)))
        page.goto(f'{http_base()}/?play=1&nointro&fidelity=assisted'
                  f'&control=UAV_CHN&scenario=tutorial_pool&quality=performance&room=photo{time.time_ns()}&ws={ws_base()}')
        page.wait_for_function('window.__viewer?.S?.t > 1 && window.__viewer?.W?.scenario')
        page.screenshot(path=OUT / 'flight.jpg', quality=80)
        page.keyboard.press('Escape')
        page.click('#enterPhotoMode')
        page.wait_for_function('window.__viewer.S.paused')
        page.screenshot(path=OUT / 'photo-mode.jpg', quality=80)
        page.evaluate('window.__pad.buttons[15] = 1')
        page.wait_for_function('Number(document.querySelector("#photoStudio input").value) > 35')
        page.evaluate('window.__pad.buttons[15] = 0')
        frames(page)
        with page.expect_download() as download:
            page.evaluate('window.__pad.buttons[0] = 1')
        assert download.value.path().read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        page.evaluate('window.__pad.buttons[0] = 0')
        frames(page)
        page.evaluate('window.__pad.buttons[1] = 1')
        page.wait_for_function('!document.querySelector("#photoStudio").open && !window.__viewer.S.paused')
        page.evaluate('window.__pad.buttons[1] = 0')
        frames(page)
        page.keyboard.press('Escape')
        page.click('[data-action="review-dive"]')
        page.click('#resultsDebrief')
        marker = page.locator('.debrief-marker.kind-photo')
        marker.first.click(force=True)
        page.wait_for_function('window.__viewer.rep?.playing === false')
        page.locator('.debrief-view-btn').last.click()
        assert page.locator('body').get_attribute('data-debrief-view') == 'god'
        page.select_option('#rpSpeed', '2')
        assert page.evaluate('window.__viewer.rep.playing === false')
        page.screenshot(path=OUT / 'replay.jpg', quality=80)
        assert not any('rc_worker' in worker.url for worker in page.workers), 'Replay opened a live RC worker'
        broken_url = page.evaluate("""async () => {
          const {saveReplay, diveUrl} = await import('/replay_store.js');
          return diveUrl(await saveReplay({clips:[{world:{}, frames:[null]}]})).href;
        }""")
        page.goto(broken_url)
        page.locator('#replayFailure button').click()
        page.wait_for_function('window.__menu?.ready')
        assert not errors, errors
        browser.close()
    print('Photo PNG and local dive replay passed')


if __name__ == '__main__':
    run()
