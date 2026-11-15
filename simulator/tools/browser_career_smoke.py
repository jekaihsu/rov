"""Career loop: fresh save → YX 委託看板 → first work order → scripted completion → pay on the results screen →
buy the laser scaler at YX 裝備部 → Block 2 in the hangar → the 見習 exam launches at the real preset and the
player's own fidelity settings come back afterwards.

The work order is completed by feeding scripted states and photo events to the career runtime
(window.__career.observe / photoAt), the same state shape the server streams; everything else is real clicks.
Screenshots (1600×900) go to output/career-validation.
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'career-validation'
OUT.mkdir(parents=True, exist_ok=True)
ASSISTED = json.dumps({'version': 1, 'base': 'assisted', 'overrides': {}})
# The launch cinematic only plays on a first dive; this check is about the career, not the cinematic.
INIT = "localStorage.setItem('rov.intro.seen.v1', '1');"
# Pool checkout: [position NED, heading deg, frames of 0.1 s, photo?]
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


def shot(page, name):
    page.screenshot(path=str(OUT / f'{name}.jpg'), type='jpeg', quality=78)


def to_board(page):
    open_main(page)
    page.click('#entry-contracts')
    wait_screen(page, 'board')


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(30000))
        page.add_init_script(INIT)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        base = (f'{http_base(8092)}/?ws={ws_base(8792)}&room=career{time.time_ns()}&quality=performance'
                '&fidelity=assisted')
        page.goto(base)
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        assert page.evaluate('window.__menu.career.money') == 0, 'fresh save'
        open_main(page)
        page.wait_for_selector('#careerSummary', timeout=timeout(10000))
        assert '學員' in page.locator('#careerSummary').inner_text()
        assert '水池檢查潛' in page.locator('#careerContinue').inner_text()
        shot(page, 'main-career-summary')

        to_board(page)
        page.wait_for_timeout(500)
        shot(page, 'board')
        page.click('#board-tab-ch1')
        assert page.locator('[data-contract="c1_pier_level1"]').get_attribute('data-status') == 'locked'
        assert '見習' in page.locator('[data-contract="c1_pier_level1"]').inner_text()
        page.click('#board-tab-prologue')
        page.click('[data-contract="p1_pool_checkout"]')
        wait_screen(page, 'contract')
        page.wait_for_timeout(800)
        assert page.locator('#contractExam').is_hidden()
        shot(page, 'contract-card')
        page.click('#contractAccept')
        page.wait_for_function('window.__career?.contract?.id === "p1_pool_checkout" && '
                               'window.__viewer?.W?.scenario?.key === "tutorial_pool"', timeout=timeout(90000))
        assert 'contract=p1_pool_checkout' in page.url
        page.wait_for_function('window.__career.snapshot() && window.__viewer.S', timeout=timeout(30000))
        page.wait_for_selector('#objectiveCard:not([hidden]) .career-checklist', timeout=timeout(30000))
        shot(page, 'dive-checklist')
        snapshot = page.evaluate(DRIVE, POOL_SCRIPT)
        assert snapshot is None or snapshot['complete'], snapshot
        page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(15000))
        outcome = page.evaluate('window.__results.outcome')
        assert outcome['kind'] == 'career' and outcome['success'], outcome
        pay = outcome['career']['pay']
        assert pay['outcome'] == 'complete' and pay['net'] > 0, pay
        assert '元' in page.locator('#resultsPay').inner_text()
        assert page.locator('#resultsLicence').is_visible()
        assert '開放水域熟悉' in page.locator('#resultsUnlocks').inner_text()
        page.wait_for_function('document.activeElement?.id === "resultsNext"', timeout=timeout(5000))
        shot(page, 'results-pay')
        page.click('#resultsNext')
        page.wait_for_function('window.__menu?.ready && window.__menu.screen === "board"', timeout=timeout(90000))
        assert 'contract=' not in page.url, page.url
        career = page.evaluate('window.__menu.career')
        assert career['money'] == pay['net'], career
        assert career['logbook'][-1]['outcome'] == 'complete'

        open_main(page)
        page.click('#entry-shop')
        wait_screen(page, 'shop')
        page.click('[data-item="laser_scaler"]')
        page.click('[data-item="laser_scaler"]')
        page.wait_for_function('window.__menu.career.owned.includes("laser_scaler")', timeout=timeout(5000))
        page.wait_for_timeout(500)
        shot(page, 'shop')
        open_main(page)
        page.click('#entry-dive')
        wait_screen(page, 'modes')
        page.click('[data-mode="free_explore"]')
        wait_screen(page, 'hangar')
        page.click('[data-vehicle="x1"]')
        page.wait_for_function('document.querySelector(".menu-vehicle-name")?.textContent.includes("Block 2")',
                               timeout=timeout(10000))

        page.evaluate(f'localStorage.setItem("rov.fidelity.v1", {json.dumps(ASSISTED)})')
        to_board(page)
        page.click('[data-contract="p2_open_water"]')
        wait_screen(page, 'contract')
        assert page.locator('#contractExam').is_visible(), 'the exam says it forces the real preset'
        page.click('#contractAccept')
        assert page.locator('#contractAccept').get_attribute('data-confirming') == 'true'
        page.click('#contractAccept')
        page.wait_for_function('window.__career?.contract?.id === "p2_open_water"', timeout=timeout(90000))
        assert 'fidelity=real' in page.url and 'exam=1' in page.url, page.url
        page.wait_for_function('window.__viewer?.S && window.__career.exam', timeout=timeout(60000))
        page.wait_for_function('window.__career.real === true', timeout=timeout(30000))
        stash = page.evaluate('JSON.parse(localStorage.getItem("rov.career.v1")).fidelityStash')
        assert stash == ASSISTED, stash
        # The real preset starts on deck with the full pre-dive procedure in front of the drawer; use the same
        # return path the results and pause menus use.
        page.evaluate('document.getElementById("returnMenu").click()')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        assert 'exam=' not in page.url and 'fidelity=real' not in page.url, page.url
        assert page.evaluate('localStorage.getItem("rov.fidelity.v1")') == ASSISTED
        assert page.evaluate('window.__menu.career.fidelityStash') is None
        assert not errors, errors
        browser.close()
    print('Career smoke passed:', OUT)


if __name__ == '__main__':
    run()
