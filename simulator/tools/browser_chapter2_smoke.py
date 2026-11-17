"""Chapter 2 C2-1 smoke: board → 網衣巡檢 → lap coverage + hole photo + clock/depth report → results.

Seeds a career save with 二級執照 so chapter 2 is open. Screenshots (1600×900) go to
output/chapter2-validation and are copied into docs/design/P4-chapter2/ when present.
"""
import json
import shutil
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'chapter2-validation'
DOCS = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'P4-chapter2'
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

INIT_CAREER = {
    'version': 1,
    'createdAt': '2026-11-17T00:00:00.000Z',
    'updatedAt': '2026-11-17T00:00:00.000Z',
    'money': 50000,
    'licence': 'grade2',
    'endorsements': [],
    'reputation': {'aquaculture': 5, 'harbor': 10},
    'owned': ['laser_scaler', 'gripper'],
    'vehicles': {'x1': {'block': 2}, 'bluerov2_heavy': {'block': 1}, 'falcon': {'block': 1}},
    'contracts': {
        'p1_pool_checkout': {'completed': 1, 'attempts': 1, 'best': 90},
        'p2_open_water': {'completed': 1, 'attempts': 1, 'best': 90},
        'c1_pier_level1': {'completed': 1, 'attempts': 1, 'best': 85},
        'c1_pier_level2': {'completed': 1, 'attempts': 1, 'best': 85},
        'c1_hull_fouling': {'completed': 1, 'attempts': 1, 'best': 85},
        'c1_signoff_exam': {'completed': 1, 'attempts': 1, 'best': 88},
    },
    'logbook': [],
    'hours': {'real_s': 3600, 'assisted_s': 0},
    'activeDive': None,
    'fidelityStash': None,
    'migration': None,
}

INIT = (
    "localStorage.setItem('rov.intro.seen.v1', '1');"
    f"localStorage.setItem('rov.career.v1', {json.dumps(json.dumps(INIT_CAREER))});"
)

# Drive one full outside lap at ~7 m, then face the upper hole and photograph it.
LAP_STEPS = []
import math
for i in range(24):
    a = (i + 0.5) * math.tau / 24
    LAP_STEPS.append([[24 + 21 * math.cos(a), 21 * math.sin(a), 7], 0, 2, False])
# Approach hole-0 from the west (outside), facing east toward the panel.
LAP_STEPS.append([[4.0, 1.17, 7], 0, 3, False])
LAP_STEPS.append([[4.0, 1.17, 7], 0, 2, True])

DRIVE = '''(steps) => {
  const base = window.__viewer.S;
  let t = base.t + 1;
  for (const [pos, heading, frames, photo] of steps) {
    let state = null;
    for (let i = 0; i < frames; i++) {
      t += 0.1;
      state = {...base, t, pos, euler: [0, 0, heading], vel: [0, 0, 0], locked: false, keep_depth: true,
        paused: false, events: base.events, tether: {...base.tether, warn: false, wraps: {}}};
      window.__career.observe(state);
    }
    if (photo) window.__career.photoAt(state);
  }
  return window.__career.snapshot();
}'''


def shot(page, name):
    path = OUT / f'{name}.jpg'
    page.screenshot(path=str(path), type='jpeg', quality=78)
    shutil.copy2(path, DOCS / f'{name}.jpg')


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(30000))
        page.add_init_script(INIT)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        base = (f'{http_base(8092)}/?ws={ws_base(8792)}&room=c2{time.time_ns()}&quality=performance'
                '&fidelity=assisted')
        page.goto(base)
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        open_main(page)
        page.click('#entry-contracts')
        wait_screen(page, 'board')
        page.click('#board-tab-ch2')
        page.wait_for_timeout(400)
        assert page.locator('[data-contract="c2_net_inspection"]').count() == 1
        shot(page, 'board-ch2-before')
        page.click('[data-contract="c2_net_inspection"]')
        wait_screen(page, 'contract')
        page.wait_for_timeout(500)
        text = page.evaluate('document.body.innerText')
        assert '網衣巡檢' in text, text[:500]
        shot(page, 'contract-c2-net')
        page.click('#contractAccept')
        page.wait_for_function(
            'window.__career?.contract?.id === "c2_net_inspection" && '
            'window.__viewer?.W?.scenario?.key === "aquaculture_pen_slack"',
            timeout=timeout(90000))
        page.wait_for_function('window.__career.snapshot() && window.__viewer.S', timeout=timeout(30000))
        page.wait_for_selector('#objectiveCard:not([hidden]) .career-checklist', timeout=timeout(30000))
        shot(page, 'dive-c2-net-checklist')

        snap = page.evaluate(DRIVE, LAP_STEPS)
        assert snap is not None, snap
        hole = next(item for item in snap['items'] if item['id'] == 'hole_upper')
        assert hole['done'], snap
        lap = next(item for item in snap['items'] if item['id'] == 'lap_shallow')
        assert lap['done'] or lap['progress'] > 0.9, lap

        report = page.evaluate('''() => {
          const snap = window.__career.snapshot();
          const item = snap.items.find(entry => entry.id === "hole_upper_report");
          if (!item || !item.reportable) return {ok:false, reason:"not-reportable", item};
          return window.__career.report("hole_upper_report", {clock: 6, depth: 7});
        }''')
        assert report.get('ok'), report
        page.wait_for_timeout(300)
        shot(page, 'dive-c2-net-report')

        # Finish remaining required work with scripted shortcuts for smoke timing.
        page.evaluate('''() => {
          const base = window.__viewer.S;
          let t = base.t + 1;
          const finish = (id, patch) => {
            // Walk mid/deep laps quickly then photo+report lower hole and surface.
          };
          const steps = [];
          for (let band of [10, 13.5]) {
            for (let i = 0; i < 24; i++) {
              const a = (i + 0.5) * Math.PI * 2 / 24;
              steps.push([[24 + 21 * Math.cos(a), 21 * Math.sin(a), band], 0, 2, false]);
            }
          }
          steps.push([[4.0, -1.17, 13], 0, 3, false]);
          steps.push([[4.0, -1.17, 13], 0, 2, true]);
          for (const [pos, heading, frames, photo] of steps) {
            let state = null;
            for (let i = 0; i < frames; i++) {
              t += 0.1;
              state = {...base, t, pos, euler: [0, 0, heading], vel: [0, 0, 0], locked: false,
                keep_depth: true, paused: false, events: base.events,
                tether: {...base.tether, warn: false, wraps: {}}};
              window.__career.observe(state);
            }
            if (photo) window.__career.photoAt(state);
          }
          window.__career.report("hole_lower_report", {clock: 6, depth: 13});
          t += 0.1;
          const home = {...base, t, pos: [-2, 0, 0.5], euler: [0, 0, 0], vel: [0, 0, 0], locked: false,
            keep_depth: true, paused: false, events: base.events,
            tether: {...base.tether, warn: false, wraps: {}}};
          window.__career.observe(home);
          return window.__career.snapshot();
        }''')

        page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(20000))
        outcome = page.evaluate('window.__results.outcome')
        assert outcome['kind'] == 'career' and outcome['success'], outcome
        shot(page, 'results-c2-net-after')
        assert not errors, errors
        browser.close()


if __name__ == '__main__':
    run()
