"""Capture the scanned-material review shots of docs/design/scan-materials/ in the real viewer (not pass/fail).

Underwater shots are one-frame replays of the real simulator (browser_scene_looks.py): the vehicle is placed at a
fixed pose and the page runs the onboard camera, optics, exposure and white balance (`fidelity=real`), with the
lamps off (level 0) and on (level 2). Above-water shots use a live session and a frozen main camera
(browser_daylight_shots.py). The quality tier is stored before the page loads (default medium), so the scene's
structure and seabed detail follow it. The same poses on two servers give before / after pairs.

  python tools/run_browser_checks.py browser_scan_materials
  ROV_LOOKS_TAG=before ROV_HTTP_PORT=8101 ROV_WS_PORT=8801 python tools/browser_scan_materials.py
  ROV_LOOKS_ONLY=sand-lamps,jacket1m-lamps ROV_SCAN_TIER=performance python tools/browser_scan_materials.py
  ROV_SCAN_BUDGET=1 ROV_SCAN_BUDGET_OUT=/tmp/budget python tools/browser_scan_materials.py   # per-tier cost table
"""
import json
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser_daylight_shots as daylight
import browser_scene_looks as looks
from _browser import http_base, launch, timeout, ws_base

OUT = Path(os.environ.get('ROV_LOOKS_OUT') or Path(__file__).resolve().parents[2] / 'docs/design/scan-materials')
TAG = os.environ.get('ROV_LOOKS_TAG', 'after')
TIER = os.environ.get('ROV_SCAN_TIER', 'medium')
OPEN = ('open_water', 42)
HARBOUR = ('harbor_inspection', 42)
REEF = ('coral_reef', 42)
JACKET = ('jacket_inspection', 42)
MONOPILE = ('monopile_current', 42)
# Jacket leg 3 at 10 m depth (scenario geometry: (15.2, -4.8, -3) -> (14.0, -6.0, 33), radius 0.6 m).
LEG = (14.77, -5.23, 10.0)
PILE = (21.0, -10.0, 8.0)
CAMERA_AHEAD = 0.35        # onboard camera ahead of the vehicle centre (m, approximate)


def facing(point, radius, gap, bearing_deg=180.0, rise=0.0):
    """Eye at `gap` metres from a vertical tube's surface, on the given bearing from its axis, looking at it."""
    b = math.radians(bearing_deg)
    d = radius + gap + CAMERA_AHEAD
    eye = (point[0] + d * math.cos(b), point[1] + d * math.sin(b), point[2] - rise)
    return eye, (point[0], point[1], point[2] + 0.2)


# name, site, eye NED, target NED (or None + coral distance), lamp level
UNDERWATER = (
    ('sand', OPEN, (6.0, 3.0, 23.3), (9.0, 4.0, 25.0)),
    ('sandwide', OPEN, (0.0, 0.0, 21.5), (7.0, 2.0, 25.0)),
    ('mud', HARBOUR, (0.0, -8.0, 16.3), (3.0, -7.0, 18.0)),
    ('harbourrock', HARBOUR, (8.0, 0.0, 16.3), (11.0, 1.0, 18.0)),
    ('reef', REEF, None, 1.8),
    ('jacket1m', JACKET, *facing(LEG, 0.6, 1.0)),
    ('jacket3m', JACKET, *facing(LEG, 0.6, 3.0, rise=0.4)),
    ('pile1m', HARBOUR, *facing(PILE, 0.65, 1.0)),
    ('pile3m', HARBOUR, *facing(PILE, 0.65, 3.0, rise=0.4)),
    ('scour', MONOPILE, (6.0, -3.0, 25.6), (10.5, -1.0, 27.6)),
    ('tpsplash', MONOPILE, (9.6, 0.0, 1.6), (15.0, 0.0, 2.4)),
)
# name, scenario, camera NED, target NED (above the water: negative down)
SURFACE = (
    ('jacket-surface', 'jacket_inspection', (-6, -9, -2.2), (20, 4, -9)),
    ('jacket-deck-under', 'jacket_inspection', (6, -14, -3.0), (20, 0, -17)),
    ('monopile-surface', 'monopile_current', (-8, -6, -2.4), (30, 10, -8)),
    ('monopile-platform-under', 'monopile_current', (4, -8, -3.0), (15, 0, -19)),
)


# Texture memory actually allocated on the GPU: WebGL texture uploads and storage are summed per texture object
# (all mip levels; render targets included and reported separately). Measurement only, nothing is changed.
TEXTURE_HOOK = """(() => {
  const BYTES = {0x8058: 4, 0x8C43: 4, 0x881A: 8, 0x8814: 16, 0x8C3A: 4, 0x81A6: 4, 0x88F0: 4, 0x8D48: 1,
    0x1908: 4, 0x1907: 3, 0x8229: 1, 0x822B: 2, 0x822F: 4, 0x8230: 8};
  const sizes = new Map();
  const bound = new Map();
  let unit = 0;
  const proto = WebGL2RenderingContext.prototype;
  const wrap = (name, fn) => { const original = proto[name]; proto[name] = function (...a) { fn.call(this, a);
    return original.apply(this, a); }; };
  wrap('activeTexture', (a) => { unit = a[0]; });
  wrap('bindTexture', (a) => { if (a[0] === 0x0DE1) bound.set(unit, a[1]); });
  wrap('deleteTexture', (a) => { sizes.delete(a[0]); });
  const record = (level, bytes, target) => {
    const texture = bound.get(unit);
    if (!texture || target !== 0x0DE1) return;
    const entry = sizes.get(texture) || {levels: new Map(), image: false};
    entry.levels.set(level, bytes);
    sizes.set(texture, entry);
    return entry;
  };
  wrap('texStorage2D', (a) => { const [target, levels, format, w, h] = a; let total = 0;
    for (let l = 0; l < levels; l++) total += Math.max(1, w >> l) * Math.max(1, h >> l) * (BYTES[format] || 4);
    record(0, total, target); });
  wrap('texImage2D', (a) => { let w, h, format = a[2];
    if (a.length >= 8) { w = a[3]; h = a[4]; } else { w = a[5]?.width; h = a[5]?.height; }
    const entry = record(a[1], (w || 0) * (h || 0) * (BYTES[format] || 4), a[0]);
    if (entry && a.length < 8) entry.image = true; });
  wrap('texSubImage2D', (a) => { if (a.length < 8) { const e = sizes.get(bound.get(unit)); if (e) e.image = true; } });
  wrap('generateMipmap', (a) => { const e = sizes.get(bound.get(unit)); if (e) {
    const base = e.levels.get(0) || 0; e.levels.set('mips', base / 3); } });
  window.__textureMemory = () => { let image = 0, other = 0, count = 0;
    for (const e of sizes.values()) { const bytes = [...e.levels.values()].reduce((s, v) => s + v, 0);
      if (e.image) { image += bytes; count++; } else other += bytes; }
    return {imageMB: +(image / 1048576).toFixed(1), imageTextures: count, targetsMB: +(other / 1048576).toFixed(1)}; };
})()"""
BUDGET_SHOTS = ('sand-lamps', 'mud-lamps', 'reef-lamps', 'jacket3m-lamps', 'pile3m-lamps', 'scour-lamps')


def measure(page):
    perf = page.evaluate(daylight.MEASURE, [3])
    perf['texture'] = page.evaluate('window.__textureMemory ? window.__textureMemory() : null')
    return perf


def shoot_underwater(browser, report, only, size, tier=TIER, suffix=''):
    for name, site, eye, target in UNDERWATER:
        for view, lamp in (('dark', 0), ('lamps', 2)):
            shot = f'{name}-{view}'
            if only and shot not in only:
                continue
            page = browser.new_page(viewport={'width': size[0], 'height': size[1]}, device_scale_factor=1)
            page.add_init_script(f"try{{localStorage.setItem('rov.quality','{tier}')}}catch(e){{}}")
            page.add_init_script(TEXTURE_HOOK)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            replay, meta = looks.build_replay(shot, site, eye, target, lamp)
            query = looks.REAL.replace('quality=medium', f'quality={tier}')
            meta.update(looks.capture(page, query, f'{shot}{suffix}-{TAG}', replay, None))
            meta['perf'] = measure(page)
            meta['tier'] = tier
            report[shot + suffix] = meta
            print(shot + suffix, json.dumps(meta), flush=True)
            page.close()
            assert not errors, errors


def open_surface(browser, name, scenario, tier):
    """browser_daylight_shots.open_page with the texture-memory hook installed before the page loads."""
    page = browser.new_page(viewport={'width': daylight.WIDTH, 'height': daylight.HEIGHT}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(f"try{{localStorage.setItem('rov.quality','{tier}')}}catch(e){{}}")
    page.add_init_script(TEXTURE_HOOK)
    room = f'sm{abs(hash((name, TAG, tier))) % 10**8}'
    page.goto(f'{http_base(8092)}/?play=1&capture&ws={ws_base(8792)}&nointro&nopip&room={room}'
              f'&scenario={scenario}&seed=1')
    page.wait_for_function(f'window.__viewer?.W?.scenario?.key==="{scenario}" && !!window.__advance',
                           timeout=timeout(90000))
    page.wait_for_timeout(timeout(2000))
    return page, errors


def shoot_surface(browser, report, only, tier=TIER, suffix=''):
    for name, scenario, at, look in SURFACE:
        if only and name not in only:
            continue
        page, errors = open_surface(browser, name, scenario, tier)
        page.evaluate(daylight.PLACE, [[at, look], daylight.SETTLE_S, daylight.FPS])
        size = daylight.grab(page, OUT / f'{name}{suffix}-{TAG}.jpg')
        report[name + suffix] = {'jpeg_bytes': size, 'perf': measure(page), 'tier': tier, 'errors': errors}
        print(name + suffix, json.dumps(report[name + suffix]), flush=True)
        page.close()
        assert not errors, errors


def budget(browser, size):
    """Draw calls, triangles and texture memory per tier for a few views; JPEGs go to ROV_SCAN_BUDGET_OUT."""
    global OUT
    OUT = Path(os.environ.get('ROV_SCAN_BUDGET_OUT') or OUT / 'budget')
    looks.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for tier in ('performance', 'medium', 'high'):
        shoot_underwater(browser, report, BUDGET_SHOTS, size, tier, f'-{tier}')
        shoot_surface(browser, report, ('monopile-surface',), tier, f'-{tier}')
    return report


def main():
    looks.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    only = [name for name in os.environ.get('ROV_LOOKS_ONLY', '').split(',') if name]
    size = tuple(int(v) for v in os.environ.get('ROV_LOOKS_SIZE', '1600x900').split('x'))
    report_path = OUT / f'report-{TAG}.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        if os.environ.get('ROV_SCAN_BUDGET'):
            report_path = OUT / f'budget-{TAG}.json'
            report = budget(browser, size)
        else:
            shoot_underwater(browser, report, only, size)
            shoot_surface(browser, report, only)
        browser.close()
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
