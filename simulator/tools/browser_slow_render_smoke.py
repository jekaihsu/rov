"""Prove the vehicle stays controllable when rendering stalls the page thread, independent of GPU speed.

Slow software WebGL does not merely lower the frame rate: it keeps the page's main thread busy, which starves
the page timers that sample controls. Throttling requestAnimationFrame alone does not reproduce that (timers
keep running), so every animation frame here also busy-waits for ROV_SLOW_FRAME_MS (default 450 ms, about
2 FPS). The server locks a vehicle after 0.6 s without RC input, so without an off-thread heartbeat the
unlock never sticks.
"""
import math
import os
import sys
import time
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base, timeout

FRAME_MS = int(os.environ.get('ROV_SLOW_FRAME_MS') or 450)
HOLD_SECONDS = 6
STALL = """(() => {
  const nativeFrame = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (callback) => nativeFrame((time) => {
    const end = performance.now() + %d;
    while (performance.now() < end);
    callback(time);
  });
})()""" % FRAME_MS
SNAPSHOT = """(() => {
  const S = window.__viewer.S;
  return {locked: S.locked, latched: S.input_latched, forward: S.rc.right_ud, lock: S.rc.rc_lock,
          generation: S.control_generation, pos: S.pos, t: S.t};
})()"""


def run():
    failures = []
    with sync_playwright() as p:
        browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
        page = browser.new_page(viewport={'width': 960, 'height': 720})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script(STALL)
        room = f'slowrender{time.time_ns()}'
        page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&room={room}',
                  wait_until='domcontentloaded', timeout=timeout(90000))
        page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(120000))
        # Loading stalls may have tripped the failsafe; give the page a chance to acknowledge it first.
        try:
            page.wait_for_function('window.__viewer.S.input_latched === false && window.__viewer.S.rc.rc_lock === 1',
                                   timeout=timeout(20000))
        except Exception:
            failures.append('controls never synchronised with the server before unlocking')
        page.wait_for_timeout(1500)
        start = page.evaluate(SNAPSHOT)
        page.keyboard.press('Space')
        page.keyboard.down('ArrowUp')
        try:
            page.wait_for_function('window.__viewer.S.locked === false && window.__viewer.S.rc.right_ud > 1500',
                                   timeout=timeout(10000))
        except Exception:
            failures.append('server never reported an unlocked vehicle with forward RC')
        first = page.evaluate(SNAPSHOT)
        samples = []
        for _ in range(HOLD_SECONDS * 2):
            page.wait_for_timeout(500)
            samples.append(page.evaluate(SNAPSHOT))
        page.keyboard.up('ArrowUp')
        for sample in samples:
            print(sample, flush=True)
        relocked = [s for s in samples if s['locked'] or s['latched'] or s['lock'] != 0]
        if relocked:
            failures.append(f'vehicle locked again while forward was held ({len(relocked)}/{len(samples)} samples)')
        if any(s['forward'] <= 1500 for s in samples):
            failures.append('server lost the forward RC channel (right_ud) while the key was held')
        if samples[-1]['generation'] != first['generation']:
            change = f"{first['generation']} -> {samples[-1]['generation']}"
            failures.append(f'failsafe engaged: control_generation {change}')
        moved = math.dist(start['pos'], samples[-1]['pos'])
        if moved < 0.3:
            failures.append(f'vehicle moved only {moved:.3f} m')
        if errors:
            failures.append(f'page errors: {errors}')
        browser.close()
    if failures:
        print(f'Slow-render control smoke FAILED (frame stall {FRAME_MS} ms):')
        for failure in failures:
            print('  -', failure)
        sys.exit(1)
    print(f'Slow-render control smoke passed: frame stall {FRAME_MS} ms, moved {moved:.2f} m, no failsafe lock.')


if __name__ == '__main__':
    run()
