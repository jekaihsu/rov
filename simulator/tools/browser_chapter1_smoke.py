"""Chapter 1 C1-1 key path: unlock trainee → buy laser scaler → accept pier Level II → scripted measures
on harbor_inspection_turbid (1.5 m) → results. Also asserts LOTO blocks unlock on the hull contract card path
via __career.blocksUnlock after accepting a prepared hull dive when save already has prerequisites.

Screenshots (1600×900) go to docs/design/P3-chapter1/ and output/chapter1-validation.
"""
import json
import shutil
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'chapter1-validation'
DOCS = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'P3-chapter1'
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
INIT = "localStorage.setItem('rov.intro.seen.v1', '1');"
# Seed a career that already finished prologue + pier Level I, with money for the laser scaler.
SEEDED = {
    'version': 1,
    'money': 20000,
    'reputation': {'harbor': 20, 'shipping': 0, 'marine_works': 0, 'aquaculture': 0, 'yx': 10},
    'licence': 'trainee',
    'endorsements': [],
    'owned': [],
    'vehicles': {'x1': {'block': 1}, 'bluerov2_heavy': {'block': 1}, 'falcon': {'block': 1}},
    'contracts': {
        'p1_pool_checkout': {'completed': 1, 'attempts': 1, 'best': 100, 'medal': 'gold'},
        'p2_open_water': {'completed': 1, 'attempts': 1, 'best': 100, 'medal': 'gold'},
        'c1_pier_level1': {'completed': 1, 'attempts': 1, 'best': 85, 'medal': 'silver'},
    },
    'logbook': [],
    'hours': {'real_s': 3600, 'assisted_s': 0},
    'activeDive': None,
    'fidelityStash': None,
}
DRIVE = '''(steps) => {
  const base = window.__viewer.S;
  let t = base.t + 1;
  for (const [pos, heading, frames, photo, extra] of steps) {
    let state = null;
    for (let i = 0; i < frames; i++) {
      t += 0.1;
      state = {...base, t, pos, euler: [0, 0, heading], vel: [0, 0, 0], locked: false, keep_depth: true,
        paused: false, events: base.events, tether: {...base.tether, warn: false, wraps: {}},
        turbidity: {visibility_m: 1.5, mg_l: 2, c: 3}, ...(extra || {})};
      window.__career.observe(state);
    }
    if (photo) window.__career.photoAt(state);
  }
  return window.__career.snapshot();
}'''
# A1 / A3 / B2 × three elevations, then recover. Heading faces the pile from standoff ~1.0 m.
LEVEL2 = [
    [[19.35, -10, 4], 0, 40, False],
    [[19.35, -10, 8], 0, 40, False],
    [[19.35, -10, 12], 0, 40, False],
    [[31.35, -10, 4], 0, 40, False],
    [[31.35, -10, 8], 0, 40, False],
    [[31.35, -10, 12], 0, 40, False],
    [[26.35, 9, 4], 90, 40, False],
    [[26.35, 9, 8], 90, 40, False],
    [[26.35, 9, 12], 90, 40, False],
    [[-2, 0, 0.5], 0, 10, False],
]


def shot(page, name):
    path = OUT / f'{name}.jpg'
    page.screenshot(path=str(path), type='jpeg', quality=78)
    shutil.copy(path, DOCS / f'{name}.jpg')


def seed_career(page):
    page.evaluate(
        '(save) => { localStorage.setItem("rov.career.v1", JSON.stringify(save)); }',
        SEEDED,
    )


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(30000))
        page.add_init_script(INIT)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        base = (f'{http_base(8093)}/?ws={ws_base(8793)}&room=chapter1{time.time_ns()}&quality=performance'
                '&fidelity=assisted')
        page.goto(base)
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        seed_career(page)
        page.reload()
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        open_main(page)
        page.click('#entry-shop')
        wait_screen(page, 'shop')
        page.click('[data-item="laser_scaler"]')
        page.click('[data-item="laser_scaler"]')
        page.wait_for_function('window.__menu.career.owned.includes("laser_scaler")', timeout=timeout(5000))
        shot(page, 'after-laser-shop')

        open_main(page)
        page.click('#entry-contracts')
        wait_screen(page, 'board')
        page.click('#board-tab-ch1')
        page.wait_for_timeout(400)
        shot(page, 'board-ch1')
        page.click('[data-contract="c1_pier_level2"]')
        wait_screen(page, 'contract')
        page.wait_for_timeout(600)
        title = page.locator('#contractTitle').inner_text()
        assert 'Level II' in title or '抽樣' in title, title
        assert page.locator('.bp-screen[data-screen="contract"][data-contract="c1_pier_level2"]').count() == 1
        shot(page, 'contract-level2')
        page.click('#contractAccept')
        page.wait_for_function(
            'window.__career?.contract?.id === "c1_pier_level2" && '
            'window.__viewer?.W?.scenario?.key === "harbor_inspection_turbid"',
            timeout=timeout(90000),
        )
        page.wait_for_function('window.__career.snapshot() && window.__viewer.S', timeout=timeout(30000))
        page.wait_for_selector('#objectiveCard:not([hidden]) .career-checklist', timeout=timeout(30000))
        vis = page.evaluate('window.__viewer.W.scenario.visibility_m')
        assert abs(float(vis) - 1.5) < 0.05, vis
        page.evaluate('window.__career.skipEvent?.()')
        shot(page, 'dive-level2-checklist')
        snapshot = page.evaluate(DRIVE, LEVEL2)
        assert snapshot and snapshot.get('complete'), snapshot
        page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(20000))
        outcome = page.evaluate('window.__results.outcome')
        assert outcome['kind'] == 'career' and outcome['success'], outcome
        shot(page, 'results-level2')
        page.click('#resultsNext')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))

        # Hull LOTO gate: seed pier level2 done, accept hull, confirm blocksUnlock before LOTO.
        page.evaluate('''(money) => {
          const raw = JSON.parse(localStorage.getItem('rov.career.v1'));
          raw.contracts.c1_pier_level2 = {completed: 1, attempts: 1, best: 85, medal: 'silver'};
          raw.owned = Array.from(new Set([...(raw.owned || []), 'laser_scaler']));
          raw.money = money;
          localStorage.setItem('rov.career.v1', JSON.stringify(raw));
        }''', 25000)
        open_main(page)
        page.click('#entry-contracts')
        wait_screen(page, 'board')
        page.click('#board-tab-ch1')
        page.click('[data-contract="c1_hull_fouling"]')
        wait_screen(page, 'contract')
        shot(page, 'contract-hull')
        page.click('#contractAccept')
        page.wait_for_function(
            'window.__career?.contract?.id === "c1_hull_fouling"',
            timeout=timeout(90000),
        )
        page.wait_for_function('window.__career.snapshot()', timeout=timeout(30000))
        page.wait_for_timeout(500)
        assert page.evaluate('window.__career.blocksUnlock()') is True
        page.evaluate('window.__career.confirm("loto")')
        page.wait_for_function('window.__career.blocksUnlock() === false', timeout=timeout(5000))
        shot(page, 'dive-hull-loto')
        assert not errors, errors
        browser.close()
    print('Chapter 1 smoke passed:', OUT)


if __name__ == '__main__':
    run()
