"""PlayStation pads start to finish with a fake navigator.getGamepads only (no keyboard, no mouse, no hardware).

Four profiles: DualSense and DualShock 4 as Chromium reports them with the standard mapping (USB and Bluetooth on
Windows), a DualSense in the raw HID order (mapping "", hat switch on axis 9, as on Windows/macOS when the browser
does not know the product) and a DualShock 4 in the Linux evdev order (mapping "", hat as axes 6/7). The test
holds a logical standard-layout state and converts it to each profile's raw arrays, so every step presses the
same physical button on every profile.

Per profile: ✕ starts from the title, the prompts show ×○□△ and L1/R1, the D-pad and the left stick move focus,
○ goes back, a dive is chosen and started, the deck checklist (real fidelity: full procedure) is walked with ✕
and the D-pad, △ unlocks, both sticks and the triggers/shoulders move surge, sway, heave and yaw (checked on the
echoed RC channels), Options (tap) cycles the light, L3 cycles the camera view, ✕ takes a photo, holding Options
opens the pause menu, the D-pad walks it, ✕ resumes, and the pause menu's main-menu entry returns to the menu.
No page errors. Usage: python tools/browser_playstation_smoke.py [profile ...]. Evidence: output/playstation-pad/.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'playstation-pad'
CROSS, CIRCLE, SQUARE, TRIANGLE, L1, R1, L2, R2, SHARE, OPTIONS, L3, R3 = range(12)
UP, DOWN, LEFT, RIGHT, PS, TOUCHPAD = 12, 13, 14, 15, 16, 17
PROFILES = {
    'dualsense_standard': {
        'id': 'DualSense Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 0ce6)',
        'mapping': 'standard', 'layout': 'standard', 'axes': 4, 'buttons': 18,
    },
    'dualsense_raw_hid': {
        'id': 'Wireless Controller (Vendor: 054c Product: 0ce6)',
        'mapping': '', 'layout': 'hid', 'axes': 10, 'buttons': 15,
    },
    'ds4_standard': {
        'id': 'Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 09cc)',
        'mapping': 'standard', 'layout': 'standard', 'axes': 4, 'buttons': 18,
    },
    'ds4_raw_evdev': {
        'id': '054c-05c4-Sony Computer Entertainment Wireless Controller',
        'mapping': '', 'layout': 'evdev', 'axes': 8, 'buttons': 13,
    },
}
# Standard-layout sources of the stick channels (input/bindings.js) as [index, sign] on axes or [plus, minus] buttons.
CHANNEL_SOURCES = {
    'left_lr': ('axis', 0, 1), 'left_ud': ('axis', 1, -1), 'right_lr': ('axis', 2, 1), 'right_ud': ('axis', 3, -1),
    'left_wave': ('buttons', R2, L2), 'right_wave': ('buttons', R1, L1),
}
FAKE_PAD = """
window.__ps = {profile: null, buttons: Array(18).fill(0), axes: [0, 0, 0, 0]};
// Hat positions clockwise from up as Chromium's Windows/macOS raw axis reports them; released reads 9/7.
function psHat(b) {
  const up = b[12] > 0.5, down = b[13] > 0.5, left = b[14] > 0.5, right = b[15] > 0.5;
  const steps = [[up && !left && !right, 0], [up && right, 1], [right && !up && !down, 2], [down && right, 3],
    [down && !left && !right, 4], [down && left, 5], [left && !up && !down, 6], [up && left, 7]];
  const hit = steps.find(entry => entry[0]);
  return hit ? -1 + hit[1] * 2 / 7 : 9 / 7;
}
function psRaw() {
  const p = window.__ps.profile, b = window.__ps.buttons, a = window.__ps.axes;
  if (!p) return {axes: [], buttons: []};
  if (p.layout === 'standard') return {axes: a.slice(), buttons: b.slice(0, p.buttons)};
  const buttons = Array(p.buttons).fill(0);
  const axes = Array(p.axes).fill(0);
  if (p.layout === 'hid') {
    // raw □ ✕ ○ △ L1 R1 L2 R2 Share Options L3 R3 PS touchpad mute
    [2, 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 17].forEach((std, raw) => { buttons[raw] = b[std] > 0.1 ? 1 : 0; });
    axes[0] = a[0]; axes[1] = a[1]; axes[2] = a[2]; axes[5] = a[3];
    axes[3] = b[6] * 2 - 1; axes[4] = b[7] * 2 - 1; axes[9] = psHat(b);
  } else {
    // raw ✕ ○ △ □ L1 R1 L2 R2 Share Options PS L3 R3
    [0, 1, 3, 2, 4, 5, 6, 7, 8, 9, 16, 10, 11].forEach((std, raw) => { buttons[raw] = b[std] > 0.1 ? 1 : 0; });
    axes[0] = a[0]; axes[1] = a[1]; axes[3] = a[2]; axes[4] = a[3];
    axes[2] = b[6] * 2 - 1; axes[5] = b[7] * 2 - 1;
    axes[6] = (b[15] > 0.5 ? 1 : 0) - (b[14] > 0.5 ? 1 : 0);
    axes[7] = (b[13] > 0.5 ? 1 : 0) - (b[12] > 0.5 ? 1 : 0);
  }
  return {axes, buttons};
}
const fakePad = {
  get id() { return window.__ps.profile?.id || ''; },
  index: 0,
  connected: true,
  get mapping() { return window.__ps.profile?.mapping ?? 'standard'; },
  vibrationActuator: null,
  get axes() { return psRaw().axes; },
  get buttons() { return psRaw().buttons.map(value => ({pressed: value > 0.5, touched: value > 0, value})); },
  get timestamp() { return performance.now(); },
};
Object.defineProperty(navigator, 'getGamepads', {value: () => [fakePad, null, null, null], configurable: true});
// Longest page-timer and frame gaps since the vehicle was unlocked (printed with the thrust diagnostics): a gap
// beyond the 2 s worker hold lets the server's input failsafe lock the vehicle.
window.__gaps = {interval: 0, frame: 0, last: performance.now(), lastFrame: performance.now()};
setInterval(function timerGap() {
  const now = performance.now();
  window.__gaps.interval = Math.max(window.__gaps.interval, now - window.__gaps.last);
  window.__gaps.last = now;
}, 33);
requestAnimationFrame(function frameGap(now) {
  window.__gaps.frame = Math.max(window.__gaps.frame, now - window.__gaps.lastFrame);
  window.__gaps.lastFrame = now;
  requestAnimationFrame(frameGap);
});
window.__setPs = function setPs(profile) {
  window.__ps.profile = profile;
};
"""


TAP_SCRIPT = """i => new Promise(resolve => {
  function release() {
    document.removeEventListener('rov-input-device', release);
    window.__ps.buttons[i] = 0;
    resolve();
  }
  document.addEventListener('rov-input-device', release);
  window.__ps.buttons[i] = 1;
  setTimeout(release, 3000);
})"""


# Frame times for 10 s right after the launch (evidence for the input failsafe under load; not asserted).
FRAME_STATS = """() => new Promise(resolve => {
  const gaps = [];
  let last = performance.now();
  const end = last + 10000;
  (function frame(now) {
    gaps.push(now - last);
    last = now;
    if (now < end) requestAnimationFrame(frame);
    else {
      gaps.sort((a, b) => a - b);
      resolve({frames: gaps.length, median: Math.round(gaps[gaps.length >> 1]), max: Math.round(gaps.at(-1))});
    }
  })(last);
})"""


def frames(page, count=4):
    """Let the page render a few frames so its polling loops see the current pad state."""
    page.evaluate('n => new Promise(done => { let left = n; (function tick() { if (--left <= 0) done(); '
                  'else requestAnimationFrame(tick); })(); })', count)


def press(page, button, hold_ms=0):
    """Menu presses last one rendered frame; flight presses are held across the 33 ms input sampling."""
    if hold_ms:
        page.evaluate('i => { window.__ps.buttons[i] = 1; }', button)
        time.sleep(hold_ms / 1000)
        frames(page, 3)
        page.evaluate('i => { window.__ps.buttons[i] = 0; }', button)
    else:
        page.evaluate('i => new Promise(resolve => { window.__ps.buttons[i] = 1; '
                      'requestAnimationFrame(() => { window.__ps.buttons[i] = 0; resolve(); }); })', button)
    frames(page, 3)


def tap(page, button, until, arg=None, attempts=10):
    """A short flight press (shared tap/hold buttons fire on a release before 650 ms), retried until `until`.

    Under loaded software GL one frame can outlast the 650 ms tap window, so a single tap may read as nothing.
    """
    for _ in range(attempts):
        # Release right after the input layer has sampled the press (it reports every pad change), so even a slow
        # software-rendered frame cannot stretch the tap into a hold.
        page.evaluate(TAP_SCRIPT, button)
        frames(page, 3)
        try:
            page.wait_for_function(until, arg=arg, timeout=timeout(4000))
            return
        except Exception:
            close_pause(page)
    raise AssertionError(f'button {button} never satisfied {until}')


def close_pause(page):
    """A stalled frame can stretch a short press past the 650 ms hold: then it opened the pause menu; ○ closes it."""
    for _ in range(4):
        if page.locator('#pauseMenu').is_hidden():
            return
        press(page, CIRCLE)
        frames(page, 3)
    assert page.locator('#pauseMenu').is_hidden(), 'the pause menu does not close with ○'


def stick_nudge(page, axis, value):
    page.evaluate('([a, v]) => new Promise(resolve => { window.__ps.axes[a] = v; '
                  'requestAnimationFrame(() => { window.__ps.axes[a] = 0; resolve(); }); })', [axis, value])
    frames(page, 3)


def focused(page):
    return page.evaluate('document.activeElement?.id || document.activeElement?.dataset?.mode || '
                         'document.activeElement?.dataset?.site || document.activeElement?.dataset?.vehicle || '
                         'document.activeElement?.dataset?.focus || ""')


def screen(page, name):
    page.wait_for_function('n => window.__menu?.screen === n', arg=name, timeout=timeout(60000))


def press_until(page, button, target, limit=16):
    for _ in range(limit):
        if focused(page) == target:
            return
        press(page, button)
    assert focused(page) == target, f'focus stopped at {focused(page)!r}, wanted {target!r}'


def wait_focus(page, target):
    page.wait_for_function('t => (document.activeElement?.id || "") === t', arg=target, timeout=timeout(20000))


def prompt_text(page):
    return page.evaluate('[...document.querySelectorAll("#menuPrompts .menu-prompt, #titleStart .menu-prompt")]'
                         '.map(node => node.textContent + (node.querySelector("svg")?.getAttribute("aria-label")'
                         ' || "")).join(" ")')


def title_to_briefing(page, results):
    page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    screen(page, 'title')
    press(page, CROSS)
    page.wait_for_function('document.documentElement.dataset.menuInput === "pad"', timeout=timeout(10000))
    glyph = page.locator('#titleStart [data-action="accept"] svg').get_attribute('aria-label')
    assert glyph == '×', f'accept prompt shows {glyph!r} for a PlayStation pad'
    results['title_glyph'] = glyph
    for _ in range(4):
        if page.evaluate('window.__menu.screen') != 'title':
            break
        press(page, CROSS)
    screen(page, 'main')
    wait_focus(page, 'entry-dive')
    stick_nudge(page, 1, 0.95)
    assert focused(page) != 'entry-dive', 'the left stick moves focus'
    press_until(page, UP, 'entry-dive')
    press_until(page, DOWN, 'entry-settings')
    press(page, CROSS)
    screen(page, 'settings')
    prompts = prompt_text(page)
    assert '○' in prompts and 'R1' in prompts, f'settings prompts {prompts!r}'
    results['settings_prompts'] = prompts
    press(page, R1)
    page.wait_for_function('document.querySelector("#menuSettings-tab-controls")?.getAttribute("aria-selected")'
                           ' === "true"', timeout=timeout(10000))
    press(page, CIRCLE)
    screen(page, 'main')
    press_until(page, UP, 'entry-dive')
    press(page, CROSS)
    screen(page, 'modes')
    press(page, CIRCLE)
    screen(page, 'main')
    press(page, CROSS)
    screen(page, 'modes')
    press_until(page, RIGHT, 'free_explore')
    press(page, CROSS)
    screen(page, 'hangar')
    press_until(page, DOWN, 'hangarNext', limit=24)
    press(page, CROSS)
    screen(page, 'sites')
    press_until(page, RIGHT, 'seagrass_meadow', limit=12)
    press(page, CROSS)
    screen(page, 'briefing')
    assert page.evaluate('document.querySelector("#menuIntro").checked'), 'the deck procedure needs the intro on'
    wait_focus(page, 'startDive')
    page.screenshot(path=str(OUT / f'{results["profile"]}-briefing.png'))
    # This press navigates to the game, so it is released on the new page.
    page.evaluate('i => { window.__ps.buttons[i] = 1; }', CROSS)
    page.wait_for_url('**play=1**', timeout=timeout(60000))


# Everything a deck step can change: the classic checklist fields and the hands-on deck flow (walk-around stop,
# power, lamps, camera, fixes, crew reports). A press that changes none of these did nothing.
PROCEDURE_FIELDS = ('[p.phase, (p.checked || []).length, (p.tests || []).length, p.confirmed, p.diagnostic > 0, '
                    'p.order, p.stations, p.seen, p.crew, p.powered, p.boot, p.lamps, p.fix, p.diagnostic_index]')


def procedure_signature(page):
    return page.evaluate('(() => { const p = window.__viewer?.S?.procedure; if (!p) return ""; '
                         'return JSON.stringify(' + PROCEDURE_FIELDS + '); })()')


def walk_checklist(page, results):
    """Confirm every deck step with ✕; the checklist keeps focus on the next thing to press."""
    page.wait_for_selector('#procedurePanel:not([hidden])', timeout=timeout(120000))
    page.wait_for_function('window.__intro?.()?.held === true', timeout=timeout(120000))
    page.evaluate('i => { window.__ps.buttons[i] = 0; }', CROSS)
    frames(page, 4)
    steps = 0
    for _ in range(80):
        phase = page.evaluate('window.__viewer.S.procedure.phase')
        if phase == 'diving':
            break
        if page.evaluate('!!window.__intro?.()?.playing && !window.__intro().held'):
            # The launch cinematic plays after lowering; the pad waits for it like the keyboard would.
            page.wait_for_function('!window.__intro().playing', timeout=timeout(180000))
            frames(page, 4)
            continue
        if page.evaluate('window.__viewer.S.procedure.diagnostic > 0'):
            page.wait_for_function('window.__viewer.S.procedure.diagnostic <= 0', timeout=timeout(30000))
            frames(page, 4)
        assert focused(page) != 'skip', 'the checklist never puts the pad on the skip action'
        before = procedure_signature(page)
        press(page, CROSS, hold_ms=120)
        try:
            page.wait_for_function('b => { const p = window.__viewer.S.procedure; '
                                   'return JSON.stringify(' + PROCEDURE_FIELDS + ') !== b; }',
                                   arg=before, timeout=timeout(15000))
            steps += 1
        except Exception:
            print('Checklist waiting', focused(page), procedure_signature(page),
                  page.locator('#procedurePanel').inner_text(), flush=True)
            # Nothing happened: the focus is on a control with nothing to do; step it with the D-pad.
            press(page, DOWN, hold_ms=120)
    assert page.evaluate('window.__viewer.S.procedure.phase') == 'diving', procedure_signature(page)
    skipped = page.evaluate('window.__viewer.S.procedure.events.filter(e => e.action === "skip").length')
    assert skipped == 0, 'no check was skipped'
    results['checklist_presses'] = steps


def rc_channel(page, channel):
    return page.evaluate('c => window.__viewer.S.rc?.[c]', channel)


def drive_channel(page, channel, direction):
    """Deflect the standard source of a stick channel and wait for the echoed PWM to follow."""
    kind, first, second = CHANNEL_SOURCES[channel]
    if kind == 'axis':
        page.evaluate('([a, v]) => { window.__ps.axes[a] = v; }', [first, 0.85 * second * direction])
    else:
        page.evaluate('i => { window.__ps.buttons[i] = 0.85; }', first if direction > 0 else second)
    compare = '>' if direction > 0 else '<'
    page.wait_for_function(f'c => (window.__viewer.S.rc?.[c] ?? 1500) {compare} 1500 {"+" if direction > 0 else "-"}'
                           ' 100', arg=channel, timeout=timeout(20000))
    value = rc_channel(page, channel)
    page.evaluate('() => { window.__ps.axes.fill(0); window.__ps.buttons.fill(0); }')
    page.wait_for_function('c => Math.abs((window.__viewer.S.rc?.[c] ?? 1500) - 1500) < 30', arg=channel,
                           timeout=timeout(20000))
    return value


def flight_state(page):
    """What the server and the input layer say when the vehicle does not respond (printed on failure only)."""
    return page.evaluate("""() => {
      const S = window.__viewer.S || {};
      const p = S.procedure || {};
      return {locked: S.locked, paused: S.paused, depth: S.depth, pos: S.pos, rc: S.rc, thrust: S.thrust,
        health: S.health, controller: S.controller, failsafe: S.failsafe, input_latched: S.input_latched,
        procedure: {phase: p.phase, flow: p.flow, missed: p.missed, events: (p.events || []).slice(-6)},
        local: window.__viewer.rc, gaps: window.__gaps, generation: S.control_generation,
        log: (S.log || []).slice(-6), pad: window.__ps.axes};
    }""")


FAILSAFE_REARMS = 2


def failsafe_locked(page, generation):
    """True when the vehicle is locked by a server failsafe since `generation`, not by a lock press."""
    return page.evaluate('g => window.__viewer.S.locked === true && window.__viewer.S.control_generation !== g',
                         generation)


def fly(page, results):
    page.wait_for_function('window.__viewer.S.locked === true || window.__viewer.S.locked === false')
    if page.evaluate('window.__viewer.S.locked') is not False:
        press(page, TRIANGLE, hold_ms=250)
        page.wait_for_function('window.__viewer.S.locked === false', timeout=timeout(20000))
    results['unlocked'] = True
    generation = page.evaluate('window.__viewer.S.control_generation')
    page.evaluate('() => { window.__gaps.interval = 0; window.__gaps.frame = 0; }')
    mode = page.evaluate('window.__viewer.S.operation_mode || "ROV_USA"')
    channels = page.evaluate("""async mode => {
      const mod = await import('./input/bindings.js');
      const result = {};
      for (const axis of ['surge', 'sway', 'heave', 'yaw']) result[axis] = mod.axisChannel(axis, mode);
      return result;
    }""", mode)
    moved = {}
    for axis, drive in channels.items():
        channel = drive['channel']
        moved[axis] = [channel, drive_channel(page, channel, 1), drive_channel(page, channel, -1)]
    results['operation_mode'] = mode
    results['axes'] = moved
    results['failsafe_rearms'] = 0
    for attempt in range(FAILSAFE_REARMS + 1):
        page.evaluate('() => { window.__ps.axes[3] = -0.9; }')
        try:
            page.wait_for_function('(window.__viewer.S.thrust || []).some(v => Math.abs(v) > 0.05)',
                                   timeout=timeout(20000))
            break
        except Exception:
            print('THRUST DIAGNOSTICS', json.dumps(flight_state(page), ensure_ascii=False), flush=True)
            if attempt == FAILSAFE_REARMS or not failsafe_locked(page, generation):
                raise
        # The server's input failsafe locked the vehicle (a page frame outlasted the 2.6 s heartbeat hold; see
        # AGENTS.md). A pilot centres the sticks and unlocks again; so does the test, and it says so.
        page.evaluate('() => { window.__ps.axes[3] = 0; }')
        results['failsafe_rearms'] += 1
        press(page, TRIANGLE, hold_ms=250)
        page.wait_for_function('window.__viewer.S.locked === false', timeout=timeout(20000))
        generation = page.evaluate('window.__viewer.S.control_generation')
    page.evaluate('() => { window.__ps.axes[3] = 0; }')
    results['thrust'] = True


def feature_buttons(page, results):
    light = page.evaluate('window.__viewer.rc.right_switch')
    tap(page, OPTIONS, 'l => window.__viewer.rc.right_switch !== l', light)
    assert page.locator('#pauseMenu').is_hidden(), 'a short Options press is the light, not the pause menu'
    results['light'] = [light, page.evaluate('window.__viewer.rc.right_switch')]
    # The real preset keeps the onboard camera only; the third-person training aid gives L3 views to cycle through.
    page.evaluate("async () => (await import('./fidelity.js')).getFidelity().set('thirdPerson', true)")
    frames(page, 3)
    view = page.evaluate('document.querySelector("#camBtn")?.dataset.mode || ""')
    tap(page, L3, 'v => (document.querySelector("#camBtn")?.dataset.mode || "") !== v', view)
    results['camera'] = [view, page.evaluate('document.querySelector("#camBtn")?.dataset.mode || ""')]
    page.evaluate('i => { window.__ps.buttons[i] = 1; }', CROSS)
    page.wait_for_function('document.querySelector("#bPhoto")?.classList.contains("on")', timeout=timeout(10000))
    page.evaluate('i => { window.__ps.buttons[i] = 0; }', CROSS)
    page.wait_for_function('!document.querySelector("#bPhoto")?.classList.contains("on")', timeout=timeout(10000))
    results['photo'] = True


def open_pause(page):
    """Hold Options until the pause menu appears, as a player would; the hold needs two samples 650 ms apart."""
    page.evaluate('i => { window.__ps.buttons[i] = 1; }', OPTIONS)
    try:
        page.wait_for_selector('#pauseMenu:not([hidden])', timeout=timeout(30000))
    finally:
        page.evaluate('i => { window.__ps.buttons[i] = 0; }', OPTIONS)
    frames(page, 3)


def pause_and_leave(page, results):
    open_pause(page)
    page.wait_for_function('window.__viewer.S.paused === true', timeout=timeout(30000))
    wait_focus(page, 'pauseResume')
    prompts = page.evaluate('document.querySelector("#pauseMenu")?.textContent || ""')
    results['pause_prompts_cross'] = '×' in page.evaluate(
        '[...document.querySelectorAll("#pauseMenu svg")].map(s => s.getAttribute("aria-label")).join("")')
    assert results['pause_prompts_cross'], prompts
    press(page, DOWN)
    assert focused(page) != 'pauseResume', 'the D-pad moves through the pause menu'
    press_until(page, UP, 'pauseResume')
    page.screenshot(path=str(OUT / f'{results["profile"]}-pause.png'))
    press(page, CROSS)
    page.wait_for_selector('#pauseMenu', state='hidden', timeout=timeout(30000))
    page.wait_for_function('window.__viewer.S.paused === false', timeout=timeout(30000))
    results['resume'] = True
    open_pause(page)
    wait_focus(page, 'pauseResume')
    press_until(page, DOWN, 'pauseHome')
    # This press leaves the game page, so it is not released from it.
    page.evaluate('i => { window.__ps.buttons[i] = 1; }', CROSS)
    page.wait_for_url(lambda url: 'play=1' not in url, timeout=timeout(60000))
    page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    results['back_to_menu'] = True


def run_profile(playwright, name):
    profile = PROFILES[name]
    results = {'profile': name}
    browser = launch(playwright)
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    page.set_default_timeout(timeout(60000))
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(FAKE_PAD)
    page.add_init_script(f'window.__setPs({json.dumps(profile)});')
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=ps{name}{int(time.time())}&quality=performance'
              '&mission=free_explore')
    started = time.monotonic()
    seconds = {}
    title_to_briefing(page, results)
    page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(120000))
    seconds['menu'] = round(time.monotonic() - started)
    walk_checklist(page, results)
    results['dive_frames'] = page.evaluate(FRAME_STATS)
    seconds['checklist'] = round(time.monotonic() - started)
    fly(page, results)
    feature_buttons(page, results)
    seconds['flight'] = round(time.monotonic() - started)
    pause_and_leave(page, results)
    seconds['pause'] = round(time.monotonic() - started)
    results['seconds'] = seconds
    assert not errors, errors
    results['errors'] = errors
    browser.close()
    print(name, json.dumps(results, ensure_ascii=False), flush=True)
    return results


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    unknown = [name for name in names if name not in PROFILES]
    assert not unknown, f'unknown profiles {unknown}; choose from {list(PROFILES)}'
    summary = {}
    with sync_playwright() as playwright:
        for name in names or list(PROFILES):
            summary[name] = run_profile(playwright, name)
    (OUT / 'results.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf8')
    print('PlayStation pad walk passed:', ', '.join(summary))


if __name__ == '__main__':
    main(sys.argv[1:])
