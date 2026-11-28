"""First dives of a fresh profile: the launch cinematic, its skip prompt and the new-player hints.

Fresh browser profile, free dive through the launch menu (assisted preset, quick launch so the cinematic plays at
once). Checks: the briefing's 下水動畫 switch is on, the cinematic plays with a glyph-aware skip prompt, holding the
pad's back button skips it (through the input layer), the first hint asks to unlock with the bound button, unlocking
ticks it off and the move hint follows, and stick input ticks off its parts. The second dive (快速開始) plays the
cinematic again, Esc skips it, the hints continue where the first dive stopped instead of repeating, and the pause
menu lists the steps under 操作教學. With --pad none the keyboard drives everything and the keyboard caps are shown.

Screenshots go to output/onboarding/ (or --shots DIR, with --size WxH and --pad xbox|playstation|none).
Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

from _browser import http_base, launch, timeout, without_render, ws_base
from _campaign_drive import unlock_again
from _menu import open_internal, soft_click, to_briefing, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'onboarding'
PADS = {
    'xbox': 'Xbox 360 Controller (STANDARD GAMEPAD Vendor: 045e Product: 028e)',
    'playstation': 'Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 09cc)',
}
# Standard-mapping indices; captions per family come from input/glyphs.js.
B, Y, LT, START = 1, 3, 6, 9
LOCK_CAP = {'xbox': 'Y', 'playstation': '△', 'none': 'T'}
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
HINT = 'document.querySelector("#onboardingHint.visible")?.dataset.hint || ""'
# The ticked state of a finished hint lasts about two seconds of wall time; a slow page may not be polled inside
# it, so an observer records it as it happens.
WATCH_DONE = '''(() => {
  const card = document.getElementById('onboardingHint');
  new MutationObserver(() => {
    if (!card.hidden && card.dataset.done === 'true') window.__hintDone = card.dataset.hint;
  }).observe(card, {attributes: true});
})()'''
SNAPSHOT = 'window.__onboarding?.snapshot()'


def arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--shots', type=Path, default=OUT, help='screenshot directory')
    parser.add_argument('--size', default='1600x900', help='viewport WxH')
    parser.add_argument('--pad', choices=['xbox', 'playstation', 'none'], default='xbox')
    return parser.parse_args()


class Run:
    """One browser page with an optional fake pad, and the screenshot naming of this run."""

    def __init__(self, page, pad, shots, size):
        self.page = page
        self.pad = pad
        self.shots = shots
        self.suffix = f'{size}-{pad}'

    def shot(self, name):
        self.page.screenshot(path=str(self.shots / f'{name}-{self.suffix}.jpg'), type='jpeg', quality=82)

    def frames(self, count=4):
        self.page.evaluate('n => new Promise(done => { let left = n; (function tick() { if (--left <= 0) done(); '
                           'else requestAnimationFrame(tick); })(); })', count)

    def button(self, index, value):
        self.page.evaluate('([i, v]) => { window.__pad.buttons[i] = v; }', [index, value])

    def axis(self, index, value):
        self.page.evaluate('([i, v]) => { window.__pad.axes[i] = v; }', [index, value])

    def tap(self, index, hold_ms=250):
        """Press long enough for a slow renderer's input sample to see it, short of the 650 ms hold gesture."""
        self.button(index, 1)
        time.sleep(hold_ms / 1000)
        self.frames(3)
        self.button(index, 0)
        self.frames(3)

    def hint(self, name, wait=60000):
        self.page.wait_for_function(f'{HINT} === {name!r}', timeout=timeout(wait))

    def progress(self, expression):
        return self.page.evaluate(f'(() => {{ const p = {SNAPSHOT}.progress; return {expression}; }})()')

    def wait_progress(self, expression, wait=60000):
        self.page.wait_for_function(f'(() => {{ const p = {SNAPSHOT}?.progress; return !!p && ({expression}); }})()',
                                    timeout=timeout(wait))


def wait_cinematic(run):
    page = run.page
    page.wait_for_function('window.__intro?.()?.playing && !window.__intro().held', timeout=timeout(120000))
    page.wait_for_selector('#skipIntro:not([hidden])', timeout=timeout(30000))
    assert page.locator('#skipIntro svg[aria-label="Esc"]').count() == 1, 'the skip prompt shows the Esc cap'


def skip_with_pad(run):
    """Hold the pad's back button until the cinematic ends; the input layer owns that button meanwhile."""
    page = run.page
    family = 'xbox' if run.pad == 'xbox' else 'playstation'
    page.wait_for_function('f => document.getElementById("skipIntro").dataset.family === f', arg=family,
                           timeout=timeout(30000))
    cap = 'B' if family == 'xbox' else '○'
    assert page.locator(f'#skipIntro svg[aria-label="{cap}"]').count() == 1, f'the hold prompt shows {cap}'
    assert '按住跳過' in page.inner_text('#skipIntro'), page.inner_text('#skipIntro')
    run.shot('01-intro-skip-prompt')
    run.button(B, 1)
    page.wait_for_function('!window.__intro().playing', timeout=timeout(30000))
    run.button(B, 0)
    run.frames(3)
    skipped = page.evaluate('document.getElementById("skipIntro").dataset.skipped')
    assert skipped == 'pad', f'the cinematic was skipped by {skipped!r}, not the pad hold'


def skip_with_key(run):
    page = run.page
    page.keyboard.press('Escape')
    page.wait_for_function('!window.__intro().playing', timeout=timeout(30000))
    skipped = page.evaluate('document.getElementById("skipIntro").dataset.skipped')
    assert skipped == 'key', f'the cinematic was skipped by {skipped!r}, not Esc'


def unlock(run):
    if run.pad == 'none':
        run.page.keyboard.press('KeyT')
    else:
        run.tap(Y)


def ensure_unlocked(run):
    """A page starved past the heartbeat hold is relocked by the server failsafe (AGENTS.md); unlock again."""
    if run.page.evaluate('window.__viewer.S.locked !== false || !!window.__viewer.S.input_latched'):
        unlock_again(run.page, lambda: unlock(run))


def hold_part(run, part, value):
    """Press (value 1) or release (value 0) the control of one move part."""
    if run.pad == 'none':
        key = {'surge': 'KeyW', 'yaw': 'KeyE', 'heave': 'KeyC'}[part]
        (run.page.keyboard.down if value else run.page.keyboard.up)(key)
    elif part == 'heave':
        run.button(LT, value)
    else:
        run.axis(3 if part == 'surge' else 0, (-value if part == 'surge' else value))
    run.frames(3)


def drive(run, part, attempts=3):
    """Hold the control of one move part until it ticks off; heave goes down, away from the surface.

    A relock by the failsafe stops the tick; like a pilot the check releases, unlocks again and retries.
    """
    with without_render(run.page):
        for attempt in range(attempts):
            ensure_unlocked(run)
            hold_part(run, part, 1)
            try:
                run.wait_progress(f'p.moves.{part}', wait=20000)
                return
            except PlaywrightTimeout:
                if attempt == attempts - 1:
                    raise
            finally:
                hold_part(run, part, 0)


def first_dive(run, base):
    page = run.page
    page.goto(f'{base}&room=onboard{time.time_ns()}')
    to_briefing(page)
    assert page.locator('#menuIntro').is_checked(), 'a fresh profile launches with the cinematic'
    soft_click(page, '#startDive')
    wait_cinematic(run)
    if run.pad == 'none':
        run.shot('01-intro-skip-prompt')
        skip_with_key(run)
    else:
        skip_with_pad(run)
    run.hint('unlock', wait=120000)
    run.frames(20)
    cap = LOCK_CAP[run.pad]
    assert page.locator(f'#onboardingHint .ob-caps svg[aria-label="{cap}"]').count() == 1, \
        f'the unlock hint shows the bound control {cap}'
    run.shot('02-first-hint-unlock')
    page.evaluate(WATCH_DONE)
    # Software rendering on a busy host can starve the input heartbeat; draws are skipped while the input acts.
    with without_render(page):
        unlock_again(page, lambda: unlock(run))
        page.wait_for_function('window.__hintDone === "unlock"', timeout=timeout(15000))
    run.shot('03-unlock-hint-cleared')
    run.hint('move')
    run.frames(20)
    run.shot('04-hint-move')
    drive(run, 'surge')
    page.wait_for_selector('#onboardingHint li[data-done="true"]', timeout=timeout(15000))
    run.shot('05-hint-progress')
    drive(run, 'yaw')
    drive(run, 'heave')
    run.wait_progress('p.steps.move')
    run.hint('depth')
    run.frames(20)
    run.shot('06-hint-depth')


def second_dive(run, base):
    page = run.page
    page.goto(f'{base}&room=onboard{time.time_ns()}')
    open_internal(page)
    soft_click(page, '#quickStart')
    wait_cinematic(run)
    run.shot('07-second-dive-intro')
    skip_with_key(run)
    run.wait_progress('true')
    assert run.progress('p.steps.unlock && p.steps.move'), 'progress from the first dive is kept'
    expected = run.progress('Object.keys(p.steps).find((step) => !p.steps[step])')
    assert expected not in ('unlock', 'move'), expected
    run.hint(expected, wait=120000)
    run.frames(20)
    run.shot('08-second-dive-hint')
    if run.pad == 'none':
        page.keyboard.press('Escape')
    else:
        run.button(START, 1)
        page.wait_for_timeout(900)
        run.frames(4)
        run.button(START, 0)
    page.wait_for_selector('#pauseMenu:not([hidden])', timeout=timeout(30000))
    soft_click(page, '#pauseTutorial')
    page.wait_for_selector('#pauseTutorial:not([hidden]) .onboarding-tutorial', timeout=timeout(15000))
    assert page.locator('.onboarding-tutorial li').count() == 7, 'the tutorial lists every basic step'
    assert page.locator('.onboarding-tutorial li[data-done="true"]').count() >= 2
    run.wait_progress('p.steps.pause')
    run.shot('09-pause-tutorial')


def main():
    args = arguments()
    args.shots.mkdir(parents=True, exist_ok=True)
    width, height = (int(value) for value in args.size.split('x'))
    base = f'{http_base(8092)}/?ws={ws_base(8792)}&quality=performance&fidelity=assisted&procedure=quick'
    with sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={'width': width, 'height': height})
        page = context.new_page()
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        if args.pad != 'none':
            page.add_init_script(FAKE_PAD % PADS[args.pad])
        run = Run(page, args.pad, args.shots, args.size)
        first_dive(run, base)
        second_dive(run, base)
        assert not errors, errors
        browser.close()
    print('Onboarding smoke passed:', args.shots)


if __name__ == '__main__':
    main()
