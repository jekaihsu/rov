"""Capture the big-picture menu screens for design review (docs/design/big-picture/).

Usage: start a simulator (defaults http 8092 / ws 8792, see _browser.py), then
  python tools/browser_big_picture_shots.py [prefix] [output directory] [screen ...]
prefix is `after` by default (`before` was captured from the base branch). Each screen is written twice,
<prefix>-<screen>-1600.jpg (1600x900) and <prefix>-<screen>-1280.jpg (1280x720), as JPEG of at most 300 KB.

Walks title → main → mode → hangar → site → briefing, then the YX board → contract → dive (pause menu) → scripted
completion (results) → shop, with real clicks. Not a pass/fail check; under software GL a run takes minutes.
"""
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_ready, wait_screen

ROOT = Path(__file__).resolve().parents[2]
PREFIX = sys.argv[1] if len(sys.argv) > 1 else 'after'
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'docs' / 'design' / 'big-picture'
ONLY = set(sys.argv[3:])
SIZES = [(1600, 900), (1280, 720)]
LIMIT = 300_000
INIT = "localStorage.setItem('rov.intro.seen.v1', '1');"
# Pool checkout, as in browser_career_smoke.py: [position NED, heading deg, frames of 0.1 s, photo?]
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


def write_jpeg(data, path):
    image = Image.open(io.BytesIO(data)).convert('RGB')
    for quality in (84, 76, 68, 60, 50, 40):
        image.save(path, quality=quality, optimize=True, progressive=True)
        if path.stat().st_size <= LIMIT:
            return


def shot(page, name, settle=2500):
    if ONLY and name not in ONLY:
        return
    for width, height in SIZES:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(settle)
        path = OUT / f'{PREFIX}-{name}-{width}.jpg'
        write_jpeg(page.screenshot(timeout=timeout(120000)), path)
        print(f'{path.name} {path.stat().st_size // 1024} KB', flush=True)
    page.set_viewport_size({'width': SIZES[0][0], 'height': SIZES[0][1]})


def details_shot(page, button, name):
    """The 明細 sheet of a screen, when the build has one (the base branch does not)."""
    if not page.locator(button).count():
        return
    page.click(button)
    shot(page, name, settle=1200)
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)


def wait_scene(page, key):
    page.wait_for_function('key => window.__menu.scene === key', arg=key, timeout=timeout(60000))


def launch_flow(page):
    shot(page, 'title')
    open_main(page)
    shot(page, 'main')
    page.click('#entry-dive')
    wait_screen(page, 'modes')
    shot(page, 'modes')
    page.click('[data-mode="free_explore"]')
    wait_screen(page, 'hangar')
    shot(page, 'hangar')
    page.click('#hangarNext')
    wait_screen(page, 'sites')
    page.focus('[data-site="coral_reef"]')
    wait_scene(page, 'coral_reef')
    shot(page, 'sites')
    page.click('[data-site="coral_reef"]')
    wait_screen(page, 'briefing')
    shot(page, 'briefing')


def career_flow(page):
    open_main(page)
    page.click('#entry-contracts')
    wait_screen(page, 'board')
    page.hover('[data-contract="p2_open_water"]')
    if PREFIX != 'before':
        wait_scene(page, 'open_water')
    shot(page, 'board', settle=4000)
    page.click('[data-contract="p1_pool_checkout"]')
    wait_screen(page, 'contract')
    wait_scene(page, 'tutorial_pool')
    shot(page, 'contract', settle=4000)
    details_shot(page, '#contractDetails', 'contract-details')
    page.click('#contractAccept')
    page.wait_for_function('window.__career?.contract?.id === "p1_pool_checkout" && '
                           'window.__viewer?.W?.scenario?.key === "tutorial_pool" && window.__modelLoaded',
                           timeout=timeout(120000))
    page.wait_for_function('window.__career.snapshot() && window.__viewer.S', timeout=timeout(60000))
    page.wait_for_timeout(3000)
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseMenu:not([hidden])')
    shot(page, 'pause')
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseMenu', state='hidden')
    page.evaluate(DRIVE, POOL_SCRIPT)
    page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(30000))
    shot(page, 'results')
    details_shot(page, '#resultsDetails', 'results-details')
    page.click('#resultsNext')
    page.wait_for_function('window.__menu?.ready && window.__menu.screen === "board"', timeout=timeout(120000))
    open_main(page)
    page.click('#entry-shop')
    wait_screen(page, 'shop')
    page.hover('[data-item="laser_scaler"]')
    shot(page, 'shop')


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': SIZES[0][0], 'height': SIZES[0][1]})
        page.set_default_timeout(timeout(60000))
        page.add_init_script(INIT)
        page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=bigpicture{time.time_ns()}&quality=medium'
                  '&fidelity=assisted')
        wait_ready(page)
        launch_flow(page)
        career_flow(page)
        browser.close()
    print('Big-picture captures written:', OUT)


if __name__ == '__main__':
    run()
