"""Chapter 1 C1-1…C1-4: documentary beats + a real physics turn, flown with scripted controls.

Each mission opens the career contract URL (director via story/chapter1.js), waits through black /
establish / handover, flies far enough for the scene-data turn, then finishes deliverables so the
report card can settle. Screenshots and a contact sheet go to docs/design/chapter1-r2/.

  python tools/run_browser_checks.py browser_chapter1_smoke
  python tools/browser_chapter1_smoke.py --mission c1_pier_level2
  python tools/browser_chapter1_smoke.py --mission all   # default; run twice in CI by invoking twice

Requires the server on ROV_HTTP_PORT / ROV_WS_PORT (run_browser_checks sets these).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, skip_render, timeout, ws_base
from _menu import open_main, wait_screen
from browser_cold_open_smoke import contact_sheet

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'chapter1-r2'
DOCS = ROOT.parents[0] / 'docs' / 'design' / 'chapter1-r2'

MISSIONS = (
    'c1_pier_level2',
    'c1_hull_fouling',
    'c1_dropped_object',
    'c1_signoff_exam',
)

# Career seed: prologue + Level I done; money for the laser scaler; cold open already seen.
SEEDED = {
    'version': 1,
    'money': 25000,
    'reputation': {'harbor': 30, 'shipping': 10, 'marine_works': 5, 'aquaculture': 0, 'yx': 15},
    'licence': 'trainee',
    'endorsements': [],
    'owned': ['laser_scaler', 'imaging_sonar'],
    'vehicles': {'x1': {'block': 1}, 'bluerov2_heavy': {'block': 1}, 'falcon': {'block': 1}},
    'contracts': {
        'p1_pool_checkout': {'completed': 1, 'attempts': 1, 'best': 100, 'medal': 'gold'},
        'p2_open_water': {'completed': 1, 'attempts': 1, 'best': 100, 'medal': 'gold'},
        'c1_pier_level1': {'completed': 1, 'attempts': 1, 'best': 85, 'medal': 'silver'},
    },
    'logbook': [],
    'hours': {'real_s': 7200, 'assisted_s': 0},
    'activeDive': None,
    'fidelityStash': None,
}

# Injected poses that finish each contract's deliverables after the physics turn (NED).
FINISH = {
    'c1_pier_level2': [
        [[19.35, -10, 4], 0, 20, False],
        [[19.35, -10, 8], 0, 20, False],
        [[19.35, -10, 12], 0, 20, False],
        [[31.35, -10, 4], 0, 20, False],
        [[31.35, -10, 8], 0, 20, False],
        [[31.35, -10, 12], 0, 20, False],
        [[26.35, 9, 4], 90, 20, False],
        [[26.35, 9, 8], 90, 20, False],
        [[26.35, 9, 12], 90, 20, False],
        [[-2, 0, 0.5], 0, 10, False],
    ],
    'c1_hull_fouling': [
        [[55, 2, 7.5], 0, 15, True],
        [[40, -2, 7.5], 0, 15, True],
        [[35, 0, 7.8], 0, 15, True],
        [[48, -2, 8.5], 0, 20, False],
        [[48, 2, 8.5], 0, 20, False],
        [[48, 8.5, 7.5], 90, 15, True],
        [[48, -8.5, 7.5], -90, 15, True],
        [[11.8, 0.3, 5], 180, 15, True],
        [[14.4, 1.5, 5.6], 180, 20, True],
        [[0, 0, 0.5], 0, 10, False],
    ],
    'c1_dropped_object': [
        [[16, 5, 13], 0, 30, False],
        [[17, 5, 13], 0, 20, True],
        [[-3, 0, 0.5], 0, 10, False],
    ],
    'c1_signoff_exam': [
        [[27, -10, 10], 0, 20, True],
        [[33, 10, 14], 0, 20, True],
        [[42, -6, 12], 180, 20, True],
        [[-2, 0, 0.5], 0, 10, False],
    ],
}

FLY = {
    # Short scripted fly toward the physics-turn landmark (surge seconds, yaw deg absolute).
    'c1_pier_level2': {'target': (19.3, -10.0, 8.0), 'yaw': 0.0, 'seconds': 8},
    'c1_hull_fouling': {'target': (12.0, 0.0, 5.5), 'yaw': 0.0, 'seconds': 10},
    'c1_dropped_object': {'target': (14.0, 5.0, 13.0), 'yaw': 0.0, 'seconds': 12},
    'c1_signoff_exam': {'target': (33.0, 12.0, 14.0), 'yaw': 90.0, 'seconds': 14},
}

DRIVE = '''(steps) => {
  const base = window.__viewer.S;
  let t = base.t + 1;
  for (const [pos, heading, frames, photo, extra] of steps) {
    let state = null;
    for (let i = 0; i < frames; i++) {
      t += 0.1;
      // career/deliverables.aim treats euler[2] as degrees (same as browser_career_smoke).
      state = {...base, t, pos, euler: [0, 0, heading], vel: [0, 0, 0],
        locked: false, keep_depth: true, paused: false, events: base.events,
        tether: {...base.tether, warn: false, wraps: {}},
        turbidity: base.turbidity, ...(extra || {})};
      window.__career.observe(state);
    }
    if (photo) window.__career.photoAt(state);
  }
  return window.__career.snapshot();
}'''

BEAT = 'window.__chapter1?.debug?.().beat || ""'
STATE = '''() => {
  const s = window.__viewer?.S || {};
  const d = window.__chapter1?.debug?.() || {};
  return {pos: s.pos || [0,0,0], yaw: (s.euler || [0,0,0])[2], locked: s.locked,
          tension: s.tether?.tension_rov || 0, snags: (s.tether?.snags || []).map(h => h.name),
          wraps: Object.keys(s.tether?.wraps || {}), beat: d.beat, hint: d.hint,
          lines: d.lines || [], missionId: d.missionId || ''};
}'''


def arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--mission', default='all',
                        choices=['all', *MISSIONS],
                        help='one Chapter 1 contract, or all four')
    parser.add_argument('--shots', type=Path, default=OUT, help='screenshot directory')
    parser.add_argument('--docs', type=Path, default=DOCS, help='docs contact-sheet directory')
    parser.add_argument('--size', default='1600x900', help='viewport WxH')
    parser.add_argument('--quality', default='performance')
    return parser.parse_args()


def capture(page, path):
    skip_render(page, False)
    page.evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))')
    page.screenshot(path=str(path), type='jpeg', quality=82)
    skip_render(page)


def seed(page, mission):
    save = json.loads(json.dumps(SEEDED))
    # Prerequisites so each mission can be accepted.
    if mission == 'c1_signoff_exam':
        save['contracts']['c1_pier_level2'] = {
            'completed': 1, 'attempts': 1, 'best': 85, 'medal': 'silver',
        }
        save['contracts']['c1_hull_fouling'] = {
            'completed': 1, 'attempts': 1, 'best': 80, 'medal': 'silver',
        }
        save['reputation']['harbor'] = 40
    page.evaluate(
        '(save) => { localStorage.setItem("rov.career.v1", JSON.stringify(save));'
        ' localStorage.setItem("rov.coldOpen.v1", JSON.stringify({seen:true}));'
        ' localStorage.setItem("rov.intro.seen.v1", "1"); }',
        save,
    )


def wait_beat(page, name, seconds=40):
    page.wait_for_function(
        f'() => (window.__chapter1?.debug?.().beat || "") === {name!r}',
        timeout=timeout(seconds * 1000),
    )


def fly_toward(page, target, yaw_deg, seconds):
    """Hold surge toward a horizontal target with depth hold; uses real keyboard bindings."""
    keys = page.evaluate('''() => {
      const c = window.__chapter1.controls();
      return {surge: c.surge.keys, yaw: c.yaw.keys, heave: c.heave.keys, photo: c.photo.keys};
    }''')
    end = time.monotonic() + seconds
    held = set()
    while time.monotonic() < end:
        state = page.evaluate(STATE)
        pos = state['pos']
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        want_yaw = math.degrees(math.atan2(dy, dx)) if math.hypot(dx, dy) > 0.4 else yaw_deg
        err = (want_yaw - math.degrees(state['yaw']) + 540) % 360 - 180
        want = set()
        if abs(err) > 12:
            want.add(keys['yaw'][0] if err > 0 else keys['yaw'][1])
        else:
            want.add(keys['surge'][0])
        depth_err = target[2] - pos[2]
        if abs(depth_err) > 0.5:
            # heave: keys[0] up (shallower / negative down), keys[1] deeper
            want.add(keys['heave'][1] if depth_err > 0 else keys['heave'][0])
        for key in held - want:
            page.keyboard.up(key)
        for key in want - held:
            page.keyboard.down(key)
        held = want
        page.wait_for_timeout(120)
    for key in held:
        page.keyboard.up(key)


def rate_pending(page):
    page.evaluate('''() => {
      const snap = window.__career.snapshot();
      for (const item of (snap?.items || [])) {
        if (item.pendingRating) window.__career.rate(item.id, 2);
      }
    }''')


def finish_deliverables(page, mission):
    if mission == 'c1_hull_fouling':
        page.evaluate('window.__career.confirm("loto")')
        page.wait_for_function('window.__career.blocksUnlock() === false', timeout=timeout(5000))
    steps = FINISH[mission]
    snap = page.evaluate(DRIVE, steps)
    if mission == 'c1_hull_fouling':
        rate_pending(page)
        # Re-observe recover after ratings.
        snap = page.evaluate(DRIVE, [[[0, 0, 0.5], 0, 15, False]])
    if mission == 'c1_dropped_object':
        page.evaluate('window.__career.confirm("mark")')
        page.evaluate('window.__career.confirm("lift")')
        snap = page.evaluate(DRIVE, [[[-3, 0, 0.5], 0, 15, False]])
    if mission == 'c1_pier_level2':
        # Laser measures: inject thickness readings for each measure id.
        page.evaluate('''() => {
          const snap = window.__career.snapshot();
          for (const item of (snap?.items || [])) {
            if (item.kind === 'measure' && !item.done) {
              window.__career.setMeasureResult(item.id, {
                id: item.id, thickness_cm: 4.2, growth: 'soft',
              });
            }
          }
        }''')
        snap = page.evaluate(DRIVE, [[[-2, 0, 0.5], 0, 20, False]])
    return snap


def accept_mission(page, mission):
    """Open the YX board and accept the contract (launches with play=1&contract=…)."""
    open_main(page)
    page.click('#entry-contracts')
    wait_screen(page, 'board')
    page.click('#board-tab-ch1')
    page.wait_for_timeout(400)
    page.click(f'[data-contract="{mission}"]')
    wait_screen(page, 'contract')
    page.wait_for_timeout(400)
    page.click('#contractAccept')
    # Exams need a second confirm click; accept may already have navigated away.
    try:
        if page.locator('#contractAccept').count() and \
                page.locator('#contractAccept').get_attribute('data-confirming') == 'true':
            page.click('#contractAccept')
    except Exception:
        pass
    page.wait_for_function(
        f'window.__career?.contract?.id === {mission!r} && window.__viewer',
        timeout=timeout(120000),
    )
    page.wait_for_function('window.__chapter1?.debug', timeout=timeout(60000))


def run_mission(page, mission, shots, docs):
    mission_shots = shots / mission
    mission_shots.mkdir(parents=True, exist_ok=True)
    frames = []
    page.goto(f'{http_base()}/?nointro&ws={ws_base()}&quality=performance&fidelity=assisted')
    page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
    seed(page, mission)
    page.reload()
    page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
    accept_mission(page, mission)
    page.evaluate('window.__career.skipEvent?.()')

    # Opening beats (director may already be past black by the time debug is ready).
    opening = ('black', 'establish', 'handover', 'work')
    seen = []
    deadline = time.monotonic() + timeout(60000) / 1000
    while time.monotonic() < deadline and 'work' not in seen:
        beat = page.evaluate(BEAT)
        if beat in opening and beat not in seen:
            seen.append(beat)
            path = mission_shots / f'{beat}.jpg'
            page.wait_for_timeout(350)
            capture(page, path)
            frames.append((path, beat))
            print(mission, beat, flush=True)
        if beat == 'work':
            break
        page.wait_for_timeout(120)
    assert 'work' in seen or page.evaluate(BEAT) == 'work', (mission, seen, page.evaluate(BEAT))
    if 'work' not in seen:
        path = mission_shots / 'work.jpg'
        capture(page, path)
        frames.append((path, 'work'))
        print(mission, 'work', flush=True)

    # Unlock thrusters once the player owns the sticks (handover → work).
    lock_key = page.evaluate('''async () => {
      const {currentKeyRows} = await import('/input/keyboard_layout.js');
      return currentKeyRows().find(r => r.action === 'lock')?.keys?.[0] || 'KeyU';
    }''')
    for _ in range(3):
        state = page.evaluate(STATE)
        if not state.get('locked'):
            break
        page.keyboard.press(lock_key)
        page.wait_for_timeout(400)

    if mission == 'c1_hull_fouling':
        page.evaluate('window.__career.confirm("loto")')
        page.wait_for_function('window.__career.blocksUnlock() === false', timeout=timeout(5000))

    plan = FLY[mission]
    fly_toward(page, plan['target'], plan['yaw'], plan['seconds'])
    turn_path = mission_shots / 'turn.jpg'
    capture(page, turn_path)
    frames.append((turn_path, 'turn'))
    after = page.evaluate(STATE)
    print(mission, 'after-fly', after['beat'], after['pos'], 'snags', after['snags'], flush=True)

    # Finish the work order so the director can take report → card.
    snap = finish_deliverables(page, mission)
    print(mission, 'finish', 'complete' if snap and snap.get('complete') else f"done={snap.get('done') if snap else None}", flush=True)
    # Wait for report from completed deliverables; otherwise skip to the closing card.
    deadline = time.monotonic() + timeout(12000) / 1000
    while time.monotonic() < deadline:
        beat = page.evaluate(BEAT)
        if beat in ('report', 'fade', 'card', 'done'):
            break
        page.wait_for_timeout(200)
    if page.evaluate(BEAT) not in ('report', 'fade', 'card', 'done'):
        page.evaluate('window.__chapter1.skip()')

    # Wait for report / card / done.
    deadline = time.monotonic() + timeout(45000) / 1000
    seen_close = set()
    while time.monotonic() < deadline:
        beat = page.evaluate(BEAT)
        if beat in ('report', 'fade', 'card', 'done', 'waiting') and beat not in seen_close:
            seen_close.add(beat)
            if beat in ('report', 'card'):
                path = mission_shots / f'{beat}.jpg'
                page.wait_for_timeout(400)
                capture(page, path)
                frames.append((path, beat))
                print(mission, beat, flush=True)
        if beat in ('card', 'done', 'waiting') and ('report' in seen_close or 'card' in seen_close):
            break
        if page.evaluate('window.__chapter1?.report?.done === true'):
            break
        page.wait_for_timeout(200)

    report = page.evaluate('window.__chapter1?.report || null')
    assert report and report.get('beats'), report
    assert any(entry.get('beat') == 'establish' for entry in report['beats']), report
    docs.mkdir(parents=True, exist_ok=True)
    for path, _name in frames:
        shutil.copy(path, docs / f'{mission}-{path.name}')
    sheet = mission_shots / 'contact-sheet.jpg'
    contact_sheet(frames, sheet)
    if sheet.exists():
        shutil.copy(sheet, docs / f'{mission}-contact-sheet.jpg')
    else:
        # Pillow missing: stitch a simple note file so the docs folder still has a sheet name.
        sheet.write_text('contact sheet skipped (Pillow unavailable)\n')
    print('Chapter 1 mission passed:', mission, 'frames', len(frames))
    return True


def run():
    args = arguments()
    missions = list(MISSIONS) if args.mission == 'all' else [args.mission]
    args.shots.mkdir(parents=True, exist_ok=True)
    args.docs.mkdir(parents=True, exist_ok=True)
    width, height = (int(part) for part in args.size.lower().split('x'))
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for mission in missions:
            run_mission(page, mission, args.shots, args.docs)
        assert not errors, errors
        browser.close()
    print('Chapter 1 smoke passed:', args.shots)


if __name__ == '__main__':
    run()
