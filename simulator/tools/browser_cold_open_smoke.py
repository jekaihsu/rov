"""New game: the cold open from a fresh profile, flown with real inputs, into the prologue.

Fresh browser profile (no stored cold-open record), launch menu, the title's 開始: a new game goes straight into the
cold open (viewer/story/cold_open.js) instead of the main menu. Checks every beat with the player's own controls:
black opening with the first radio line, the establishing shot, the handover with only depth and heading on the
HUD and one hint, flying to leg C's anode and taking the photo (stamp and praise), heading north for leg B until
the tether really snags on the anode (server physics), the tension read-out and the back-out call, backing out the
way it came until the snag lets go, the 三個月前 title card, and the prologue starting in the same tab (the YX
prologue work order). Afterwards the title's 開始 opens the main menu: the cold open plays once.

  python tools/run_browser_checks.py browser_cold_open_smoke         # keyboard, then the pad-only variant
  python tools/browser_cold_open_smoke.py --pad playstation --size 1366x768 --shots DIR

The default run does both variants (keyboard; PlayStation pad only). Screenshots of each beat go to
output/cold-open/ (or --shots), plus a contact sheet of frames taken through the run when Pillow is available.
"""
import argparse
import json
import math
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, without_render, ws_base
from _menu import wait_ready

OUT = Path(__file__).resolve().parents[1] / 'output' / 'cold-open'
PADS = {
    'xbox': 'Xbox 360 Controller (STANDARD GAMEPAD Vendor: 045e Product: 028e)',
    'playstation': 'Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 09cc)',
}
FAKE_PAD = """
window.__pad = {buttons: Array(17).fill(0), axes: [0, 0, 0, 0]};
const fakePad = {
  id: %r, index: 0, connected: true, mapping: 'standard', vibrationActuator: null,
  get axes() { return window.__pad.axes.slice(); },
  get buttons() { return window.__pad.buttons.map(value => ({pressed: value > 0.5, touched: value > 0, value})); },
  get timestamp() { return performance.now(); },
};
Object.defineProperty(navigator, 'getGamepads', {value: () => [fakePad, null, null, null], configurable: true});
"""
BEAT = 'window.__coldOpen?.debug?.().beat || ""'
STATE = '''() => {
  const s = window.__viewer?.S || {};
  const d = window.__coldOpen?.debug?.() || {};
  return {pos: s.pos, heading: (s.euler || [0, 0, 0])[2], locked: s.locked, latched: s.input_latched,
          tension: s.tether?.tension_rov || 0, snags: (s.tether?.snags || []).map(h => h.name),
          beat: d.beat, hint: d.hint, lines: d.lines || []};
}'''
STEER_DT = 0.25
DEPTH = 12.0                 # m, the anodes' depth at the cold-open jacket (qysim/cold_open.py)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--shots', type=Path, default=OUT, help='screenshot directory')
    parser.add_argument('--size', default='1600x900', help='viewport WxH')
    parser.add_argument('--quality', default='performance', help='render tier of the dive (performance, medium…)')
    parser.add_argument('--pad', choices=['xbox', 'playstation', 'none', 'both'], default='both',
                        help='device to fly with; both runs the keyboard and then the PlayStation pad')
    return parser.parse_args()


class Pilot:
    """Holds the player's controls: keys from the bindings the game reports, or a fake standard pad."""

    def __init__(self, page, pad):
        self.page = page
        self.pad = pad
        self.controls = page.evaluate('window.__coldOpen.controls()')
        self.held = {}

    def axis(self, name, value):
        """value in -1..1 along the pilot axis (surge forward, yaw right)."""
        control = self.controls[name]
        if self.pad == 'none':
            keys = control['keys']
            want = keys[0] if value > 0 else keys[1] if value < 0 else None
            before = self.held.get(name)
            if before == want:
                return
            if before:
                self.page.keyboard.up(before)
            if want:
                self.page.keyboard.down(want)
            self.held[name] = want
            return
        source = control['pad']
        if isinstance(source, list):
            # A pair of buttons (heave on the triggers): [positive, negative].
            positive, negative = (int(str(entry).lstrip('b')) for entry in source)
            self.page.evaluate('([p, n, v]) => { window.__pad.buttons[p] = v > 0 ? 1 : 0; '
                               'window.__pad.buttons[n] = v < 0 ? 1 : 0; }', [positive, negative, value])
            return
        index = int(source.lstrip('+-a').rstrip('~'))
        flip = -1 if source.startswith('-') else 1
        self.page.evaluate('([i, v]) => { window.__pad.axes[i] = v; }', [index, flip * value])

    def stop(self):
        self.axis('surge', 0)
        self.axis('yaw', 0)
        self.axis('heave', 0)

    def hold_depth(self, state, depth):
        """Correct the depth like a pilot taps the vertical control (a stalled page can leave it off the anode)."""
        error = depth - state['pos'][2]
        self.axis('heave', 0 if abs(error) < 0.6 else (-1 if error > 0 else 1))

    def photo(self):
        if self.pad == 'none':
            self.page.keyboard.press(self.controls['photo']['keys'][0])
            return
        index = int(str(self.controls['photo']['pad']).lstrip('b'))
        self.page.evaluate('i => { window.__pad.buttons[i] = 1; }', index)
        time.sleep(0.3)
        self.page.evaluate('i => { window.__pad.buttons[i] = 0; }', index)


class Run:
    def __init__(self, page, pad, shots, suffix):
        self.page = page
        self.pad = pad
        self.shots = shots
        self.suffix = suffix
        self.frames = []
        self.last_frame = 0.0

    def shot(self, name):
        path = self.shots / f'{name}-{self.suffix}.jpg'
        self.page.screenshot(path=str(path), type='jpeg', quality=82)
        print('shot', path.name, flush=True)

    def frame(self, every=6.0):
        """A small frame for the contact sheet, at most one every `every` seconds of wall time."""
        if time.monotonic() - self.last_frame < every:
            return
        self.last_frame = time.monotonic()
        path = self.shots / 'frames' / f'{self.suffix}-{len(self.frames):03d}.jpg'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path), type='jpeg', quality=60)
        self.frames.append((path, self.state()['beat']))

    def state(self):
        return self.page.evaluate(STATE)

    def wait_beat(self, names, wait=180000):
        names = [names] if isinstance(names, str) else names
        self.page.wait_for_function(f'{json.dumps(names)}.includes({BEAT})', timeout=timeout(wait))


def bearing_error(state, target):
    north = target[0] - state['pos'][0]
    east = target[1] - state['pos'][1]
    bearing = math.degrees(math.atan2(east, north))
    return (bearing - state['heading'] + 540) % 360 - 180, math.hypot(north, east)


def ensure_unlocked(run, pilot):
    """A page starved past the heartbeat hold is relocked by the server failsafe (AGENTS.md); unlock like a pilot."""
    state = run.state()
    if not state['locked'] and not state['latched']:
        return
    pilot.stop()
    if pilot.pad == 'none':
        run.page.keyboard.press('Space')
    else:
        run.page.evaluate('() => { window.__pad.buttons[3] = 1; }')
        time.sleep(0.3)
        run.page.evaluate('() => { window.__pad.buttons[3] = 0; }')
    run.page.wait_for_timeout(600)


def steer(run, pilot, target, done, limit_s, radius=0.8, reverse=False):
    """Fly to `target` (north, east) until done(state) or the radius; returns the last state."""
    deadline = time.monotonic() + timeout(int(limit_s * 1000)) / 1000
    state = run.state()
    while time.monotonic() < deadline:
        state = run.state()
        if done(state):
            break
        ensure_unlocked(run, pilot)
        error, distance = bearing_error(state, target)
        if reverse:
            error = (error + 360) % 360 - 180
        if distance < radius:
            pilot.stop()
            break
        pilot.hold_depth(state, DEPTH)
        turn = max(-1.0, min(1.0, error / 35.0))
        pilot.axis('yaw', turn if abs(error) > 8 else 0)
        drive = 0.0 if abs(error) > 35 else min(1.0, 0.35 + distance / 4)
        pilot.axis('surge', -drive if reverse else drive)
        run.frame()
        run.page.wait_for_timeout(int(STEER_DT * 1000))
    pilot.stop()
    return state


def face(run, pilot, heading, limit_s=20):
    deadline = time.monotonic() + timeout(int(limit_s * 1000)) / 1000
    while time.monotonic() < deadline:
        state = run.state()
        error = (heading - state['heading'] + 540) % 360 - 180
        if abs(error) < 6 and abs(DEPTH - state['pos'][2]) < 0.6:
            break
        pilot.hold_depth(state, DEPTH)
        pilot.axis('yaw', max(-0.6, min(0.6, error / 40.0)))
        run.page.wait_for_timeout(int(STEER_DT * 1000))
    pilot.stop()


def start_new_game(run, quality):
    page = run.page
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=coldopen{time.time_ns()}&quality={quality}')
    wait_ready(page)
    assert page.evaluate('window.__menu.screen') == 'title'
    assert page.evaluate("localStorage.getItem('rov.coldOpen.v1')") is None, 'a fresh profile'
    if run.pad == 'none':
        page.click('#titleStart')
    else:
        page.wait_for_timeout(800)
        page.evaluate('() => { window.__pad.buttons[0] = 1; }')
        time.sleep(0.35)
        page.evaluate('() => { window.__pad.buttons[0] = 0; }')
    page.wait_for_url('**coldOpen=1**', timeout=timeout(60000))
    query = parse_qs(urlparse(page.url).query)
    assert query['chapter'] == ['cold_open'] and query['scenario'] == ['cold_open_jacket'], query
    follow = parse_qs(urlparse(query['next'][0]).query)
    assert follow.get('contract') == ['p0_induction'] and follow.get('chapter') == ['prologue'], follow
    page.wait_for_function('window.__coldOpen && window.__viewer?.S', timeout=timeout(120000))


def opening(run):
    page = run.page
    run.wait_beat('black', 120000)
    page.wait_for_selector('.cold-open-radio.speaking', timeout=timeout(60000))
    assert page.evaluate('getComputedStyle(document.querySelector(".cold-open-black")).opacity') == '1'
    run.shot('01-black')
    run.wait_beat('establish')
    page.wait_for_function('document.querySelector(".cold-open-super.visible") && '
                           'Number(getComputedStyle(document.querySelector(".cold-open-black")).opacity) < 0.05',
                           timeout=timeout(60000))
    run.shot('02-establish')
    run.wait_beat('approach')
    page.wait_for_selector('#coldOpenHint.visible[data-hint="move"]', timeout=timeout(30000))
    page.wait_for_timeout(800)
    caps = page.locator('#coldOpenHint .ob-caps').inner_html()
    assert '<svg' in caps or 'ob-cap-name' in caps, caps
    if run.pad != 'none':
        assert 'ob-cap-name' in caps, 'the pad hint names the stick'
    hud = page.evaluate('''() => ({
      depth: getComputedStyle(document.querySelector('#flightOsd .osd-tl')).visibility,
      heading: getComputedStyle(document.querySelector('#flightOsd .osd-heading')).visibility,
      tether: getComputedStyle(document.querySelector('#flightOsd .osd-br')).display,
      map: getComputedStyle(document.querySelector('#flightMapBox')).display,
      card: getComputedStyle(document.querySelector('#objectiveCard')).display,
    })''')
    assert hud == {'depth': 'visible', 'heading': 'visible', 'tether': 'none', 'map': 'none', 'card': 'none'}, hud
    run.shot('03-first-hint')


def photo(run, pilot):
    page = run.page
    spot = page.evaluate('window.__viewer.W.objectives[0].point')
    # A little further out than the objective, as a pilot frames a whole anode: the jacket stands at (0, 0).
    out = math.hypot(spot[0], spot[1])
    stand = [spot[0] * (1 + 0.8 / out), spot[1] * (1 + 0.8 / out)]
    with without_render(page):
        steer(run, pilot, stand, lambda s: s['beat'] != 'approach', 120, radius=0.5)
        face(run, pilot, math.degrees(math.atan2(-spot[1], -spot[0])) % 360)
    page.wait_for_selector('#coldOpenHint.visible[data-hint="photo"]', timeout=timeout(60000))
    pilot.photo()
    run.wait_beat('payoff', 60000)
    page.wait_for_selector('.cold-open-stamp.visible', timeout=timeout(30000))
    page.wait_for_timeout(600)
    run.shot('04-photo-payoff')


def snag(run, pilot):
    page = run.page
    run.wait_beat('transit', 60000)
    leg_b = page.evaluate('window.__viewer.W.objectives[1].point')
    with without_render(page):
        state = steer(run, pilot, leg_b, lambda s: s['beat'] != 'transit', 150, radius=0.5)
        if state['beat'] == 'transit':
            # Pressed against leg B without a snag yet: keep pushing north as a pilot would.
            steer(run, pilot, [leg_b[0] + 6, leg_b[1]], lambda s: s['beat'] != 'transit', 60, radius=0.3)
    assert run.state()['beat'] == 'incident', run.state()
    # 先停: a pilot who keeps pulling at full thrust can part the tether at its termination (tether.py).
    pilot.stop()
    page.wait_for_selector('#coldOpenTension.visible', timeout=timeout(30000))
    page.wait_for_timeout(600)
    run.shot('05-snag-incident')
    with without_render(page):
        page.wait_for_function('window.__coldOpen.debug().lines.includes("backOut")', timeout=timeout(90000))


def back_out(run, pilot):
    page = run.page
    anode = page.evaluate('window.__viewer.W.objectives[0].point')
    start = [-12.0, -9.0]
    with without_render(page):
        steer(run, pilot, anode, lambda s: s['beat'] != 'incident', 30, radius=1.5, reverse=True)
    run.shot('06-backing-out')
    with without_render(page):
        state = steer(run, pilot, anode, lambda s: s['beat'] != 'incident', 120, radius=0.6, reverse=True)
        if state['beat'] == 'incident':
            steer(run, pilot, start, lambda s: s['beat'] != 'incident', 120, radius=0.6, reverse=True)
    run.wait_beat(['relief', 'fade', 'card'], 120000)
    outcome = page.evaluate('window.__coldOpen.debug().outcome')
    assert outcome['released'] and not outcome['broken'], outcome
    page.wait_for_selector('.cold-open-radio.speaking', timeout=timeout(30000))
    run.shot('07-relief')


def ending(run):
    page = run.page
    page.wait_for_selector('.brand-card-overlay', timeout=timeout(120000))
    page.wait_for_timeout(900)
    assert '三個月前' in page.inner_text('.brand-card-overlay')
    run.shot('08-title-card')
    report = page.evaluate('window.__coldOpen.report')
    page.wait_for_url('**contract=p0_induction**', timeout=timeout(90000))
    page.wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=timeout(120000))
    page.wait_for_timeout(2500)
    run.shot('09-prologue-start')
    record = json.loads(page.evaluate("localStorage.getItem('rov.coldOpen.v1')") or '{}')
    assert record.get('seen') is True, record
    return report


def once_only(run):
    page = run.page
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=coldagain{time.time_ns()}&quality=performance')
    wait_ready(page)
    page.click('#titleStart')
    page.wait_for_function('window.__menu.screen === "main"', timeout=timeout(30000))
    assert 'coldOpen' not in page.url


def replay(run):
    """重玩開場 from the story list: the cold open again, skippable with Esc, back to the story list."""
    page = run.page
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=coldreplay{time.time_ns()}&quality=performance'
              '&menu=training&tab=story')
    wait_ready(page)
    page.wait_for_function('window.__menu.screen === "training"', timeout=timeout(30000))
    page.click('#coldOpenReplay')
    page.wait_for_url('**coldOpen=replay**', timeout=timeout(60000))
    page.wait_for_function('window.__coldOpen && window.__viewer?.S', timeout=timeout(120000))
    run.wait_beat(['black', 'establish'], 120000)
    page.wait_for_selector('#skipIntro:not([hidden])', timeout=timeout(30000))
    assert '跳過開場' in (page.get_attribute('#skipIntro', 'aria-label') or ''), 'the skip prompt names the opening'
    page.keyboard.press('Escape')
    page.wait_for_selector('.brand-card-overlay', timeout=timeout(60000))
    assert page.evaluate('window.__coldOpen.report.skipped') == 'key'
    page.wait_for_url('**menu=training**', timeout=timeout(90000))
    wait_ready(page)
    page.wait_for_function('window.__menu.screen === "training"', timeout=timeout(30000))


def contact_sheet(frames, path):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print('SKIP contact sheet: Pillow is not installed', flush=True)
        return
    if not frames:
        return
    columns = 4
    width = 400
    height = None
    tiles = []
    for frame, beat in frames:
        image = Image.open(frame)
        height = height or round(image.height * width / image.width)
        tile = image.resize((width, height))
        ImageDraw.Draw(tile).text((8, 6), beat or '', fill=(255, 255, 255))
        tiles.append(tile)
    rows = math.ceil(len(tiles) / columns)
    sheet = Image.new('RGB', (columns * width, rows * height), (0, 0, 0))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * width, (index // columns) * height))
    sheet.save(path, quality=80)
    print('contact sheet', path, flush=True)


def fly(browser, pad, shots, size, quality):
    width, height = (int(value) for value in size.split('x'))
    page = browser.new_page(viewport={'width': width, 'height': height}, cold_open=True)
    page.set_default_timeout(timeout(30000))
    if pad != 'none':
        page.add_init_script(FAKE_PAD % PADS[pad])
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    run = Run(page, pad, shots, f'{size}-{pad}')
    start_new_game(run, quality)
    opening(run)
    pilot = Pilot(page, pad)
    photo(run, pilot)
    snag(run, pilot)
    back_out(run, pilot)
    report = ending(run)
    contact_sheet(run.frames, shots / f'contact-sheet-{run.suffix}.jpg')
    once_only(run)
    if pad == 'none':
        replay(run)
    assert not errors, errors
    page.close()
    return report


def main():
    args = arguments()
    args.shots.mkdir(parents=True, exist_ok=True)
    pads = ['none', 'playstation'] if args.pad == 'both' else [args.pad]
    results = {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for pad in pads:
            results[pad] = fly(browser, pad, args.shots, args.size, args.quality)
            print(pad, 'beats', [(entry['beat'], entry['at']) for entry in results[pad]['beats']], flush=True)
        browser.close()
    (args.shots / f'report-{args.size}.json').write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                                           encoding='utf-8')
    print('Cold open browser check passed:', ', '.join(pads))


if __name__ == '__main__':
    main()
