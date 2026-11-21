"""Fly the training pool using real keyboard bindings. Capture the whole watch and its three survey photos."""
import math
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch, skip_render, timeout, ws_base
from browser_cold_open_smoke import contact_sheet

OUT = Path(__file__).resolve().parents[1] / 'output' / 'prologue-r1'
STATE = """() => {
  const s = window.__viewer.S;
  return {beat:s.campaign.node?.id, status:s.campaign.status, p:s.pos, yaw:s.euler[2],
          locked:s.locked, hold:s.keep_depth, target:s.campaign.node?.target};
}"""


def capture(page, path):
    skip_render(page, False)
    page.evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))')
    page.screenshot(path=str(path), quality=82)
    skip_render(page)


def flight_keys(page):
    return page.evaluate("""async () => {
      const {currentKeyRows, currentOperationMode} = await import('/input/keyboard_layout.js');
      const {axisChannel} = await import('/input/bindings.js');
      const rows = currentKeyRows();
      const pairs = {};
      for (const axis of ['surge','sway','yaw','heave']) {
        const d = axisChannel(axis,currentOperationMode());
        const own = rows.find(r => r.action === axis && r.keys.length === 2);
        const pair = [...(own || rows.find(r => r.action === d.channel)).keys];
        pairs[axis] = !own && d.sign < 0 ? pair.reverse() : pair;
      }
      for (const id of ['lock','depth','light','photo']) pairs[id] = rows.find(r => r.action === id).keys[0];
      return pairs;
    }""")

def play_prologue(page, shots=None, keys=None):
    keys = keys or flight_keys(page)
    page.wait_for_function('document.querySelector("#prologue")?.dataset.beat', polling=30, timeout=timeout(90000))
    skip_render(page)
    frames = []
    seen = []
    held = set()
    last_press = 0
    deadline = time.monotonic() + timeout(420000) / 1000
    while time.monotonic() < deadline:
        state = page.evaluate(STATE)
        if state['status'] == 'completed':
            break
        beat = state['beat']
        want = set()
        tap = None
        if beat not in seen:
            seen.append(beat)
            print(beat, state['p'], flush=True)
            if shots and beat not in ('A', 'B', 'C'):
                path = shots / f'{len(seen):02}-{beat}.jpg'
                page.wait_for_timeout(380)
                capture(page, path)
                frames.append((path, beat))
            if beat == 'report':
                assert '3/3' in page.locator('#prologue .cold-open-words').inner_text()
        if beat == 'unlock' or beat in ('approach', 'descend', 'hold', 'A', 'B', 'C') and state['locked']:
            if state['locked']:
                tap = 'lock'
        elif beat == 'approach':
            want.add(keys['surge'][0])
        elif beat == 'descend':
            want.add(keys['heave'][1])
        elif beat == 'hold' and not state['hold']:
            tap = 'depth'
        elif state['target']:
            north, east, down = (a-b for a, b in zip(state['target'], state['p']))
            tn, te, _ = state['target']
            distance = math.hypot(tn, te)
            stand_off = (north * tn + east * te) / distance
            # Approach a camera station five metres out from the wall, then yaw toward the printed plate.
            travel_n = north - 5 * tn / distance
            travel_e = east - 5 * te / distance
            station = math.hypot(travel_n, travel_e) > 1.6
            bearing = math.atan2(travel_e, travel_n) if station else math.atan2(east, north)
            error = (math.degrees(bearing) - state['yaw'] + 540) % 360 - 180
            if abs(error) > 9:
                want.add(keys['yaw'][int(error < 0)])
            if station and abs(error) < 22:
                want.add(keys['surge'][0])
            if abs(down) > 0.45:
                want.add(keys['heave'][int(down > 0)])
            if not station and abs(error) < 10 and stand_off > 2.5 and abs(down) < 0.7:
                tap = 'photo'
        for key in held - want:
            page.keyboard.up(key)
        for key in want - held:
            page.keyboard.down(key)
        held = want
        if tap and time.monotonic() - last_press > 1:
            if shots and tap == 'photo' and not any(name == beat for _, name in frames):
                path = shots / f'{len(seen):02}-{beat}.jpg'
                capture(page, path)
                frames.append((path, beat))
            page.keyboard.press(keys[tap])
            last_press = time.monotonic()
        page.wait_for_timeout(110)
    skip_render(page, False)
    assert state['status'] == 'completed', state
    expected = 'black establish unlock approach descend coast hold trim A B C report licence harbor'.split()
    # The results smoke attaches after menu navigation. Only the dedicated capture must witness the first frame.
    if not shots:
        assert seen[0] in expected[:3], seen
        expected = expected[expected.index(seen[0]):]
    assert seen == expected, seen
    if shots:
        contact_sheet(frames, shots / 'contact-sheet.jpg')


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        errors = []
        page.on('pageerror', lambda err: (errors.append(str(err)), print(err, flush=True)))
        page.goto(f'{http_base()}/?play=1&scenario=tutorial_pool&nointro&control=UAV_CHN'
                  f'&room=pool{time.time_ns()}&quality=performance&ws={ws_base()}', wait_until='commit')
        page.wait_for_function('window.__viewer?.S?.campaign?.status === "idle"', timeout=timeout(90000))
        keys = flight_keys(page)
        skip_render(page)
        page.locator('.story-menu button').filter(has_text='序章｜見習之前').evaluate('button => button.click()')
        play_prologue(page, OUT, keys)
        assert not errors, errors
        browser.close()


if __name__ == '__main__':
    run()
