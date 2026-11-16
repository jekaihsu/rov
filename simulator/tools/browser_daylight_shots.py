"""Capture the above-water views (deployment intro, surface views of the sites) for the daylight review.

Not a pass/fail check: it writes review JPEGs and a JSON report with draw calls and frame times.

  python tools/run_browser_checks.py browser_daylight_shots           # through the runner (free ports)
  ROV_DAYLIGHT_TAG=before python tools/browser_daylight_shots.py      # tag selects the file suffix
  ROV_DAYLIGHT_VIEWS=intro-deck,jacket-surface ...                    # subset (comma-separated)
  ROV_DAYLIGHT_TIER=medium                                            # quality tier stored before load
  ROV_DAYLIGHT_OUT=output/wind-farm                                   # output directory (default output/daylight)

The page runs in capture mode (window.__advance), so the deployment intro is stepped to fixed times
independent of how slowly software GL renders. Surface views freeze the main camera on a fixed pose and let
the app's own frame loop render it. The last second before each capture is rendered so the camera's
auto-exposure has settled. Output: output/daylight/<view>-<tag>.jpg and perf-<tag>.json.
"""
import base64
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

SIMULATOR = Path(__file__).resolve().parents[1]
OUT = SIMULATOR / os.environ.get('ROV_DAYLIGHT_OUT', 'output/daylight')
TAG = os.environ.get('ROV_DAYLIGHT_TAG', 'after')
TIER = os.environ.get('ROV_DAYLIGHT_TIER', 'medium')
WIDTH = 1600
HEIGHT = 900
FPS = 30
SETTLE_S = float(os.environ.get('ROV_DAYLIGHT_SETTLE', '1.0'))
MAX_JPEG = 300_000
# Intro views: (scenario, intro time in seconds). The intro's own camera path frames them.
INTRO_VIEWS = {
    'intro-deck': ('jacket_inspection', 1.6),
    'intro-luff': ('jacket_inspection', 4.4),
    'intro-setdown': ('jacket_inspection', 6.9),
    'intro-harbour': ('harbor_inspection', 4.4),
}
# Surface views: (scenario, camera NED, target NED). Camera a couple of metres above the water.
SURFACE_VIEWS = {
    'jacket-surface': ('jacket_inspection', (-6, -9, -2.2), (20, 4, -9)),
    'hull-surface': ('hull_inspection', (2, -16, -2.5), (34, 0, -3)),
    'harbour-surface': ('harbor_inspection', (12, -16, -2.0), (40, 0, -2)),
    # Wind farm review: a chase-height view over the vehicle's start, and a raised view across the farm.
    'chase-surface': ('jacket_inspection', (-9, 3, -3.2), (40, -14, -4)),
    'farm-wide': ('jacket_inspection', (-60, -40, -38), (1400, 900, -60)),
    'monopile-surface': ('monopile_current', (-8, -6, -2.4), (30, 10, -8)),
    'open-surface': ('open_water', (-6, -6, -2.4), (30, 10, -6)),
}
# What the above-water set placed (surface_set.js), in NED, for aiming review cameras; null before it existed.
SURFACE_SET = '''() => {
  const set = window.__viewer.scene.getObjectByName('surface-set');
  if (!set) return null;
  const c = set.userData.farmCentre;
  return {kind: set.userData.plan?.kind, turbines: set.userData.turbines || 0,
          farmCentreNed: c ? [c.z, -c.x, -c.y].map(Math.round) : null};
}'''
GRAB = '''(quality) => document.querySelector('canvas.gl').toDataURL('image/jpeg', quality)'''

ADVANCE = '''([seconds, settle, fps]) => {
  const steps = Math.round(seconds * fps);
  const lit = Math.round(settle * fps);
  for (let i = 0; i < steps; i++) {
    window.__skipRender = i < steps - lit;
    window.__advance(1 / fps);
  }
  window.__skipRender = false;
  return window.__intro && window.__intro();
}'''

PLACE = '''([view, settle, fps]) => {
  // Freeze the main camera on the review pose: the camera rig writes to it every frame, so the components
  // return fixed values and ignore writes. The page is closed after the capture.
  const v = window.__viewer, THREE = v.THREE, camera = v.camera;
  const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
  camera.up.set(0, 1, 0);
  camera.position.copy(P(view[0]));
  camera.lookAt(P(view[1]));
  const fixed = {x: camera.position.x, y: camera.position.y, z: camera.position.z};
  for (const axis of ['x', 'y', 'z']) {
    Object.defineProperty(camera.position, axis, {get: () => fixed[axis], set: () => {}});
  }
  const q = camera.quaternion;
  const turn = {_x: q._x, _y: q._y, _z: q._z, _w: q._w};
  for (const key of Object.keys(turn)) {
    Object.defineProperty(q, key, {get: () => turn[key], set: () => {}});
  }
  camera.fov = 55;
  camera.updateProjectionMatrix();
  const frames = Math.round(settle * fps);
  for (let i = 0; i < frames; i++) window.__advance(1 / fps);
  return true;
}'''

MEASURE = '''([frames]) => {
  // Whole frame: every pass of the composer and the shadow map, not just the last full-screen pass.
  const v = window.__viewer, renderer = v.renderer, gl = renderer.getContext(), pixel = new Uint8Array(4);
  const times = [];
  let calls = 0;
  let triangles = 0;
  renderer.info.autoReset = false;
  for (let i = 0; i < frames; i++) {
    renderer.info.reset();
    const t0 = performance.now();
    window.__advance(1 / 30);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    times.push(performance.now() - t0);
    calls = renderer.info.render.calls;
    triangles = renderer.info.render.triangles;
  }
  renderer.info.autoReset = true;
  times.sort((a, b) => a - b);
  return {calls, triangles, minMs: Math.round(times[0]), medianMs: Math.round(times[Math.floor(frames / 2)])};
}'''


def open_page(browser, name, scenario, intro):
    page = browser.new_page(viewport={'width': WIDTH, 'height': HEIGHT}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda msg: errors.append(msg.text[:300]) if msg.type == 'error' else None)
    page.add_init_script(f"try{{localStorage.setItem('rov.quality','{TIER}')}}catch(e){{}}")
    room = f'dl{abs(hash((name, TAG))) % 10**8}'    # a fresh room per view: a joining player gets no intro
    # Quick launch: the intro plays at once instead of holding on deck for the pre-dive checklist.
    flags = '&procedure=quick' if intro else '&nointro'
    url = (f'{http_base(8092)}/?play=1&capture&ws={ws_base(8792)}{flags}&nopip&room={room}'
           f'&scenario={scenario}&seed=1')
    page.goto(url)
    page.wait_for_function(f'window.__viewer?.W?.scenario?.key==="{scenario}" && !!window.__advance',
                           timeout=timeout(90000))
    if intro:
        page.wait_for_function('window.__intro && window.__intro() && window.__intro().playing',
                               timeout=timeout(90000))
    page.wait_for_timeout(timeout(2000))
    return page, errors


def grab(page, path):
    """Read the canvas right after the last rendered frame (same task, so the drawing buffer is intact)."""
    for quality in (0.86, 0.72, 0.6):
        data = page.evaluate(f'''() => {{ window.__advance(1 / {FPS}); return ({GRAB})({quality}); }}''')
        path.write_bytes(base64.b64decode(data.split(',', 1)[1]))
        if path.stat().st_size <= MAX_JPEG:
            break
    return path.stat().st_size


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = [s for s in os.environ.get('ROV_DAYLIGHT_VIEWS', '').split(',') if s]
    report = {'tag': TAG, 'tier': TIER, 'views': {}}
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        for name, (scenario, seconds) in INTRO_VIEWS.items():
            if only and name not in only:
                continue
            page, errors = open_page(browser, name, scenario, True)
            state = page.evaluate(ADVANCE, [seconds, SETTLE_S, FPS])
            size = grab(page, OUT / f'{name}-{TAG}.jpg')
            perf = page.evaluate(MEASURE, [5])
            report['views'][name] = {'intro': state, 'jpeg_bytes': size, 'perf': perf, 'errors': errors}
            print(name, json.dumps(report['views'][name]), flush=True)
            page.close()
        for name, (scenario, at, look) in SURFACE_VIEWS.items():
            if only and name not in only:
                continue
            page, errors = open_page(browser, name, scenario, False)
            page.evaluate(PLACE, [[at, look], SETTLE_S, FPS])
            size = grab(page, OUT / f'{name}-{TAG}.jpg')
            perf = page.evaluate(MEASURE, [5])
            report['views'][name] = {'jpeg_bytes': size, 'perf': perf, 'errors': errors,
                                     'set': page.evaluate(SURFACE_SET)}
            print(name, json.dumps(report['views'][name]), flush=True)
            page.close()
        browser.close()
    (OUT / f'perf-{TAG}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('daylight shots written to', OUT)


if __name__ == '__main__':
    main()
