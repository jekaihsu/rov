"""Chapter 2 R3 smoke: C2-1 / C2-2 / C2-3 with beat-stage screenshots and scripted deliverables.

Seeds a career save with 二級執照 so chapter 2 is open. Screenshots (1600×900) go to
output/chapter2-r3 and docs/design/chapter2-r3/. Each mission is flown twice by the caller.
"""
import json
import math
import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'chapter2-r3'
DOCS = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'chapter2-r3'
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
        'c2_net_inspection': {'completed': 1, 'attempts': 1, 'best': 85},
        'c2_mort_recovery': {'completed': 1, 'attempts': 1, 'best': 85},
    },
    'logbook': [],
    'hours': {'real_s': 3600, 'assisted_s': 0},
    'activeDive': None,
    'fidelityStash': None,
    'migration': None,
}

INIT = (
    "localStorage.setItem('rov.intro.seen.v1', '1');"
    "localStorage.setItem('rov.coldOpen.v1', JSON.stringify({seen:true}));"
    f"localStorage.setItem('rov.career.v1', {json.dumps(json.dumps(INIT_CAREER))});"
)


def shot(page, name):
    path = OUT / f'{name}.jpg'
    page.screenshot(path=str(path), type='jpeg', quality=78)
    shutil.copy2(path, DOCS / f'{name}.jpg')
    return path


def contact_sheet(paths, name):
    try:
        from PIL import Image
    except ImportError:
        return
    images = [Image.open(path) for path in paths if path.exists()]
    if not images:
        return
    w, h = images[0].size
    cols = min(3, len(images))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new('RGB', (w * cols, h * rows), (8, 16, 24))
    for index, image in enumerate(images):
        sheet.paste(image, ((index % cols) * w, (index // cols) * h))
    out = DOCS / f'{name}.jpg'
    sheet.save(out, quality=80)
    shutil.copy2(out, OUT / f'{name}.jpg')


def open_contract(page, contract_id, scenario_key):
    open_main(page)
    page.click('#entry-contracts')
    wait_screen(page, 'board')
    page.click('#board-tab-ch2')
    page.wait_for_timeout(400)
    page.click(f'[data-contract="{contract_id}"]')
    wait_screen(page, 'contract')
    page.wait_for_timeout(300)
    page.click('#contractAccept')
    page.wait_for_function(
        f'window.__career?.contract?.id === "{contract_id}" && '
        f'window.__viewer?.W?.scenario?.key === "{scenario_key}"',
        timeout=timeout(90000))
    page.wait_for_function('window.__career.snapshot() && window.__viewer.S', timeout=timeout(30000))
    page.wait_for_timeout(800)


def wait_beat(page, name, seconds=12):
    page.wait_for_function(
        f'() => document.body.dataset.coldReveal != null || document.querySelector("#chapter2")',
        timeout=timeout(15000))
    deadline = time.time() + seconds
    while time.time() < deadline:
        beat = page.evaluate('() => window.__viewer?.S?.__chapter2Beat || null')
        if beat == name:
            return beat
        page.wait_for_timeout(200)
    return page.evaluate('() => window.__viewer?.S?.__chapter2Beat || null')


def drive_net(page):
    steps = []
    for i in range(24):
        a = (i + 0.5) * math.tau / 24
        steps.append([[24 + 21 * math.cos(a), 21 * math.sin(a), 7], 0, 2, False])
    steps.append([[4.0, 1.17, 7], 0, 3, False])
    steps.append([[4.0, 1.17, 7], 0, 2, True])
    page.evaluate('''(steps) => {
      const base = window.__viewer.S;
      let t = base.t + 1;
      for (const [pos, heading, frames, photo] of steps) {
        let state = null;
        for (let i = 0; i < frames; i++) {
          t += 0.1;
          state = {...base, t, pos, euler: [0, 0, heading], vel: [0, 0, 0], locked: false,
            keep_depth: true, paused: false, events: base.events,
            tether: {...base.tether, warn: false, wraps: {}, snags: []}};
          window.__career.observe(state);
        }
        if (photo) window.__career.photoAt(state);
      }
      return window.__career.snapshot();
    }''', steps)
    page.evaluate('() => window.__career.report("hole_upper_report", {clock: 6, depth: 7})')
    page.evaluate('''() => {
      const base = window.__viewer.S;
      let t = base.t + 1;
      const steps = [];
      for (const band of [10, 13.5]) {
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
            tether: {...base.tether, warn: false, wraps: {}, snags: []}};
          window.__career.observe(state);
        }
        if (photo) window.__career.photoAt(state);
      }
      window.__career.report("hole_lower_report", {clock: 6, depth: 13});
      t += 0.1;
      const home = {...base, t, pos: [-2, 0, 0.5], euler: [0, 0, 0], vel: [0, 0, 0], locked: false,
        keep_depth: true, paused: false, events: base.events,
        tether: {...base.tether, warn: false, wraps: {}, snags: []}};
      window.__career.observe(home);
    }''')


def drive_mort(page):
    page.evaluate('''() => {
      const base = window.__viewer.S;
      let t = base.t + 1;
      const fish = (base.operations?.objects || []).filter((o) => o.kind === "dead_fish").slice(0, 3);
      const basket = (base.operations?.objects || []).find((o) => o.kind === "collection_basket");
      const basketPos = basket?.pos || [16, 0, 15.5];
      for (const item of fish) {
        let state = {...base, t, pos: item.pos, euler: [0, 0, 0], vel: [0, 0, 0], locked: false,
          keep_depth: true, paused: false,
          operations: {...base.operations, arm: {...(base.operations?.arm || {}), held: item.id}},
          turbidity: {visibility_m: 1.2, mg_l: 8, c: 4}};
        for (let i = 0; i < 4; i++) {
          t += 0.1;
          state = {...state, t, pos: [item.pos[0], item.pos[1], 14.5]};
          window.__career.observe(state);
        }
        const objects = (base.operations?.objects || []).map((entry) => (
          entry.id === item.id ? {...entry, pos: basketPos} : entry
        ));
        t += 0.1;
        window.__career.observe({
          ...state, t, pos: basketPos,
          operations: {...base.operations, arm: {...(base.operations?.arm || {}), held: null}, objects},
        });
      }
      t += 0.1;
      window.__career.observe({
        ...base, t, pos: [16, 0, 0.5], euler: [0, 0, 0], vel: [0, 0, 0], locked: false,
        keep_depth: true, paused: false,
      });
      return window.__career.snapshot();
    }''')


def drive_escape(page):
    page.evaluate('''() => {
      const base = window.__viewer.S;
      let t = base.t + 1;
      let state = {...base, t, pos: [4.5, 1.2, 7], euler: [0, 0, 0], vel: [0, 0, 0], locked: false,
        keep_depth: true, paused: false};
      for (let i = 0; i < 6; i++) {
        t += 0.1;
        state = {...state, t};
        window.__career.observe(state);
      }
      window.__career.photoAt(state);
      window.__career.report("priority_report", {clock: 6, depth: 7});
      state = {...state, t: t + 0.2, pos: [4.0, -1.17, 13]};
      window.__career.observe(state);
      window.__career.photoAt(state);
      for (let i = 0; i < 25; i++) {
        t += 0.1;
        state = {...state, t, pos: [4.5, 1.2, 7], vel: [0, 0, 0]};
        window.__career.observe(state);
      }
      t += 0.1;
      window.__career.observe({
        ...state, t, pos: [-2, 0, 0.5],
      });
      return window.__career.snapshot();
    }''')


def run_mission(page, contract_id, scenario_key, prefix, driver):
    paths = []
    open_contract(page, contract_id, scenario_key)
    paths.append(shot(page, f'{prefix}-01-enter'))
    page.wait_for_timeout(3500)
    paths.append(shot(page, f'{prefix}-02-establish'))
    page.wait_for_timeout(4000)
    paths.append(shot(page, f'{prefix}-03-handover'))
    driver(page)
    page.wait_for_timeout(500)
    paths.append(shot(page, f'{prefix}-04-work'))
    page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(25000))
    outcome = page.evaluate('window.__results.outcome')
    assert outcome and outcome.get('kind') == 'career', outcome
    paths.append(shot(page, f'{prefix}-05-results'))
    contact_sheet(paths, f'contact-sheet-{prefix}')
    return outcome


def run():
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(30000))
        page.add_init_script(INIT)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        base = (f'{http_base(8092)}/?ws={ws_base(8792)}&room=c2r3{time.time_ns()}&quality=performance'
                '&fidelity=assisted&nointro=1')
        page.goto(base)
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))

        # C2-1: unlock later missions by completing prerequisites in the seeded save already.
        career = json.loads(json.loads(page.evaluate("localStorage.getItem('rov.career.v1')")))
        career['contracts']['c2_net_inspection'] = {'completed': 0, 'attempts': 0, 'best': 0}
        career['contracts'].pop('c2_mort_recovery', None)
        page.evaluate(
            f"localStorage.setItem('rov.career.v1', {json.dumps(json.dumps(career))})")
        page.reload()
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        run_mission(page, 'c2_net_inspection', 'aquaculture_pen_slack', 'c21', drive_net)

        # Seed C2-1 done for C2-2.
        career = json.loads(json.loads(page.evaluate("localStorage.getItem('rov.career.v1')")))
        career['contracts']['c2_net_inspection'] = {'completed': 1, 'attempts': 1, 'best': 85}
        career['contracts']['c2_mort_recovery'] = {'completed': 0, 'attempts': 0, 'best': 0}
        page.evaluate(
            f"localStorage.setItem('rov.career.v1', {json.dumps(json.dumps(career))})")
        page.goto(base + '&_=' + str(time.time_ns()))
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        run_mission(page, 'c2_mort_recovery', 'aquaculture_pen_inside', 'c22', drive_mort)

        career = json.loads(json.loads(page.evaluate("localStorage.getItem('rov.career.v1')")))
        career['contracts']['c2_mort_recovery'] = {'completed': 1, 'attempts': 1, 'best': 85}
        career['contracts']['c2_escape_event'] = {'completed': 0, 'attempts': 0, 'best': 0}
        page.evaluate(
            f"localStorage.setItem('rov.career.v1', {json.dumps(json.dumps(career))})")
        page.goto(base + '&_=' + str(time.time_ns()))
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        run_mission(page, 'c2_escape_event', 'aquaculture_pen_escape', 'c23', drive_escape)

        assert not errors, errors
        browser.close()
        print('chapter2-r3 smoke OK', flush=True)


if __name__ == '__main__':
    run()
