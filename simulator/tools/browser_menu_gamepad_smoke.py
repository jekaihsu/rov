"""Gamepad-only walk from the title screen into the water, then the pause menu, with a fake standard gamepad.

navigator.getGamepads is replaced before the page loads; the script only changes that pad's buttons and axes, never
uses the mouse or keyboard. Checks: focus moves with the D-pad, A confirms, B goes back, RB switches settings tabs,
the right stick turns the hangar turntable, prompts show controller glyphs, the dive launches, holding Start opens
the pause menu (simulation paused for a solo pilot) and B closes it.
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'menu-gamepad'
OUT.mkdir(parents=True, exist_ok=True)
A, B, RB, START, UP, DOWN, LEFT, RIGHT = 0, 1, 5, 9, 12, 13, 14, 15
FAKE_PAD = """
window.__pad = {buttons: Array(17).fill(0), axes: [0, 0, 0, 0]};
const fakePad = {
  id: 'Xbox 360 Controller (STANDARD GAMEPAD Vendor: 045e Product: 028e)', index: 0, connected: true,
  mapping: 'standard', vibrationActuator: null,
  get axes() { return window.__pad.axes.slice(); },
  get buttons() { return window.__pad.buttons.map(value => ({pressed: value > 0.5, touched: value > 0, value})); },
  get timestamp() { return performance.now(); },
};
Object.defineProperty(navigator, 'getGamepads', {value: () => [fakePad, null, null, null], configurable: true});
"""


def frames(page, count=4):
    """Let the page render a few frames so its polling loop sees the current pad state."""
    page.evaluate('n => new Promise(done => { let left = n; (function tick() { if (--left <= 0) done(); '
                  'else requestAnimationFrame(tick); })(); })', count)


def press(page, button, hold_ms=0):
    """Down for exactly one rendered frame (one menu sample), so a slow renderer cannot trigger auto-repeat."""
    if hold_ms:
        page.evaluate('i => { window.__pad.buttons[i] = 1; }', button)
        time.sleep(hold_ms / 1000)
        frames(page, 3)
        page.evaluate('i => { window.__pad.buttons[i] = 0; }', button)
    else:
        page.evaluate('i => new Promise(resolve => { window.__pad.buttons[i] = 1; '
                      'requestAnimationFrame(() => { window.__pad.buttons[i] = 0; resolve(); }); })', button)
    frames(page, 3)


def focused(page):
    return page.evaluate('document.activeElement?.id || document.activeElement?.dataset?.mode || '
                         'document.activeElement?.dataset?.site || document.activeElement?.dataset?.vehicle || ""')


def screen(page, name):
    page.wait_for_function('n => window.__menu?.screen === n', arg=name, timeout=timeout(30000))


def expect_focus(page, target):
    for _ in range(40):
        if focused(page) == target:
            return
        frames(page, 2)
    assert focused(page) == target, f'focus is on {focused(page)!r}, wanted {target!r}'


def press_until(page, button, target, limit=16):
    for _ in range(limit):
        if focused(page) == target:
            return
        press(page, button)
    assert focused(page) == target, f'focus stopped at {focused(page)!r}, wanted {target!r}'


with sync_playwright() as playwright:
    browser = launch(playwright)
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(FAKE_PAD)
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=padcheck{int(time.time())}&quality=performance'
              '&mission=free_explore')
    page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    press(page, DOWN)
    page.wait_for_function('document.documentElement.dataset.menuInput === "pad"')
    # The title shows its confirm key once, on the start button itself (the footer is empty there).
    glyph = page.locator('#titleStart [data-action="accept"] svg').get_attribute('aria-label')
    assert glyph == 'A', f'accept prompt shows {glyph!r} for an Xbox-family pad'
    expect_focus(page, 'titleStart')
    press(page, A)
    # Fresh storage shows the difficulty picker; Accept once to arm, Accept again to confirm.
    if page.evaluate('window.__menu?.screen') == 'new_game':
        screen(page, 'new_game')
        frames(page, 4)
        press(page, A)
        frames(page, 4)
        press(page, A)
        screen(page, 'main')
    else:
        screen(page, 'main')
    expect_focus(page, 'entry-dive')
    # Settings: RB walks the tabs, B returns.
    press_until(page, DOWN, 'entry-settings')
    press(page, A)
    screen(page, 'settings')
    press(page, RB)
    page.wait_for_function('document.querySelector("#menuSettings-tab-controls").getAttribute("aria-selected")'
                           ' === "true"')
    page.screenshot(path=str(OUT / 'settings-controls.png'))
    press(page, B)
    screen(page, 'main')
    press_until(page, UP, 'entry-dive')
    press(page, A)
    screen(page, 'modes')
    press(page, B)
    screen(page, 'main')
    press(page, A)
    screen(page, 'modes')
    press_until(page, RIGHT, 'free_explore')
    press(page, A)
    screen(page, 'hangar')
    expect_focus(page, 'x1')
    page.evaluate('window.__pad.axes[2] = 1')
    frames(page, 10)
    page.evaluate('window.__pad.axes[2] = 0')
    page.screenshot(path=str(OUT / 'hangar.png'))
    press_until(page, DOWN, 'hangarNext', limit=24)
    press(page, A)
    screen(page, 'sites')
    press_until(page, RIGHT, 'seagrass_meadow', limit=12)
    press(page, A)
    screen(page, 'briefing')
    page.locator('#menuIntro').evaluate('el => { el.checked = false; }')
    expect_focus(page, 'startDive')
    page.screenshot(path=str(OUT / 'briefing.png'))
    # This press navigates to the game, so it is not released from the menu page.
    page.evaluate('i => { window.__pad.buttons[i] = 1; }', A)
    page.wait_for_url('**play=1**', timeout=timeout(60000))
    page.wait_for_function('window.__viewer?.W?.scenario?.key === "seagrass_meadow" && window.__modelLoaded',
                           timeout=timeout(120000))
    page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(60000))
    page.wait_for_timeout(1500)
    press(page, START, hold_ms=900)
    page.wait_for_selector('#pauseMenu:not([hidden])', timeout=timeout(30000))
    page.wait_for_function('window.__viewer.S.paused === true', timeout=timeout(30000))
    expect_focus(page, 'pauseResume')
    page.screenshot(path=str(OUT / 'pause.png'))
    press(page, B)
    page.wait_for_selector('#pauseMenu', state='hidden')
    page.wait_for_function('window.__viewer.S.paused === false', timeout=timeout(30000))
    assert not errors, errors
    result = {'title_to_water_gamepad_only': True, 'back': True, 'tabs': True, 'pause_hold_start': True,
              'errors': errors}
    (OUT / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    browser.close()
print('Gamepad menu walk passed:', OUT)
