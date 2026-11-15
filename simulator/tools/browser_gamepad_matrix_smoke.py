"""Verify standard, database and calibrated pads via fake navigator.getGamepads (no hardware).

Checks: Xbox-family glyph, Logitech D-mode DB hit, unknown HOTAS becomes known after custom mapping,
menu D-pad focus, and no page errors. Launched through _browser.py.
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'gamepad-matrix'
OUT.mkdir(parents=True, exist_ok=True)

PROFILES = {
    'xbox_standard': {
        'id': 'Xbox 360 Controller (STANDARD GAMEPAD Vendor: 045e Product: 028e)',
        'mapping': 'standard',
        'axes': 4,
        'buttons': 17,
    },
    'logitech_dmode': {
        'id': 'Logitech Logitech Dual Action (Vendor: 046d Product: c216)',
        'mapping': '',
        'axes': 4,
        'buttons': 12,
    },
    'hotas_unknown': {
        'id': 'HOTAS matrix Vendor: 9999 Product: 9999',
        'mapping': '',
        'axes': 6,
        'buttons': 20,
    },
}

INIT = """
window.__matrix = { buttons: Array(17).fill(0), axes: [0, 0, 0, 0], id: '', mapping: 'standard' };
const fakePad = {
  get id() { return window.__matrix.id; },
  index: 0,
  connected: true,
  get mapping() { return window.__matrix.mapping; },
  vibrationActuator: null,
  get axes() { return window.__matrix.axes.slice(); },
  get buttons() {
    return window.__matrix.buttons.map(value => ({pressed: value > 0.5, touched: value > 0, value}));
  },
  get timestamp() { return performance.now(); },
};
Object.defineProperty(navigator, 'getGamepads', {
  value: () => [fakePad, null, null, null], configurable: true
});
window.__setPad = function setPad(profile) {
  window.__matrix.id = profile.id;
  window.__matrix.mapping = profile.mapping;
  window.__matrix.axes = Array(profile.axes).fill(0);
  window.__matrix.buttons = Array(Math.max(17, profile.buttons)).fill(0);
};
"""


def frames(page, count=4):
    page.evaluate(
        'n => new Promise(done => { let left = n; (function tick() { if (--left <= 0) done(); '
        'else requestAnimationFrame(tick); })(); })',
        count,
    )


def set_profile(page, name):
    page.evaluate('([profiles, name]) => window.__setPad(profiles[name])', [PROFILES, name])
    frames(page, 3)


def press(page, button, hold_ms=0):
    """Down for one frame by default; hold_ms keeps the button for flight edge detection."""
    if hold_ms:
        page.evaluate('i => { window.__matrix.buttons[i] = 1; }', button)
        time.sleep(hold_ms / 1000)
        frames(page, 3)
        page.evaluate('i => { window.__matrix.buttons[i] = 0; }', button)
    else:
        page.evaluate(
            'i => new Promise(resolve => { window.__matrix.buttons[i] = 1; '
            'requestAnimationFrame(() => { window.__matrix.buttons[i] = 0; resolve(); }); })',
            button,
        )
    frames(page, 3)


def stick(page, axis, value, hold_ms=200):
    page.evaluate('([a, v]) => { window.__matrix.axes[a] = v; }', [axis, value])
    time.sleep(hold_ms / 1000)
    frames(page, 4)
    page.evaluate('a => { window.__matrix.axes[a] = 0; }', axis)
    frames(page, 2)


with sync_playwright() as playwright:
    browser = launch(playwright)
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(INIT)
    page.goto(
        f'{http_base(8092)}/?ws={ws_base(8792)}&room=padmatrix{int(time.time())}'
        '&quality=performance&mission=free_explore'
    )
    page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    results = {}

    set_profile(page, 'xbox_standard')
    press(page, 13)
    page.wait_for_function('document.documentElement.dataset.menuInput === "pad"', timeout=timeout(10000))
    glyph = page.evaluate(
        'document.querySelector("#menuPrompts [data-action=\\"accept\\"] svg")?.getAttribute("aria-label") || ""'
    )
    assert glyph == 'A', f'Xbox family glyph was {glyph!r}'
    results['xbox_glyph'] = glyph
    results['xbox_menu_focus'] = True

    set_profile(page, 'logitech_dmode')
    known = page.evaluate("""async () => {
      const mod = await import('./input/devices.js');
      const db = await fetch('./input/controller-db.json').then(r => r.json());
      return mod.normalize(navigator.getGamepads()[0], db).known;
    }""")
    assert known is True
    results['logitech_db'] = True

    set_profile(page, 'hotas_unknown')
    before = page.evaluate("""async () => {
      const mod = await import('./input/devices.js');
      const db = await fetch('./input/controller-db.json').then(r => r.json());
      return mod.normalize(navigator.getGamepads()[0], db).known;
    }""")
    assert before is False
    page.evaluate("""() => {
      const settings = JSON.parse(localStorage.getItem('rov.input.v1') || '{}');
      settings.custom = settings.custom || {};
      settings.custom[window.__matrix.id] = {
        axes: ['a0', 'a1', 'a2', 'a3'],
        buttons: Array.from({length: 17}, (_, i) => 'b' + i)
      };
      localStorage.setItem('rov.input.v1', JSON.stringify(settings));
    }""")
    after = page.evaluate("""async () => {
      const mod = await import('./input/devices.js');
      const db = await fetch('./input/controller-db.json').then(r => r.json());
      const custom = JSON.parse(localStorage.getItem('rov.input.v1')).custom;
      return mod.normalize(navigator.getGamepads()[0], db, custom).known;
    }""")
    assert after is True
    results['hotas_calibrated'] = True

    # Jump into a dive with the standard pad: unlock (Y / b3) then thrust (left stick).
    page.goto(
        f'{http_base(8092)}/?ws={ws_base(8792)}&room=padmatrixfly{int(time.time())}'
        '&quality=performance&mission=free_explore&play=1&nointro'
    )
    page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(120000))
    set_profile(page, 'xbox_standard')
    # Nudge D-pad so devices.js marks this pad active before flight samples it.
    press(page, 13)
    page.wait_for_timeout(300)
    if page.evaluate('window.__viewer?.S?.locked') is not False:
        press(page, 3, hold_ms=250)
        page.wait_for_function('window.__viewer?.S?.locked === false', timeout=timeout(15000))
    stick(page, 1, -0.9, hold_ms=500)
    page.wait_for_function(
        '() => (window.__viewer?.S?.thrust || []).some(v => Math.abs(v) > 0.05)',
        timeout=timeout(15000),
    )
    results['unlock_and_thrust'] = True
    assert errors == [], errors
    results['no_page_errors'] = True
    (OUT / 'matrix.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Gamepad matrix smoke passed:', json.dumps(results))
    browser.close()
