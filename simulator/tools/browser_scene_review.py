"""Capture each dive site from a fixed overview camera and an onboard-style camera, and time the scene.

Not a pass/fail check: it writes review JPEGs and a JSON performance report.

  python tools/run_browser_checks.py browser_scene_review        # through the runner (free ports)
  ROV_SCENE_TAG=after python tools/browser_scene_review.py       # tag selects the file suffix
  ROV_SCENE_SITES=hull_inspection ROV_SCENE_TIERS=medium ...     # subsets (comma-separated)

Views are free cameras placed in the running viewer (window.__viewer): the "third" view is an overview with
the long training fog, the "onboard" view sits at the first inspection stand-off with the operator's real
fog (visibility_m * 1.35) and the onboard field of view. The ROV is not flown there; the tether and the ROV
stay at the start position. Output: output/scene-review/<site>-<view>-<tag>.jpg and perf-<tag>.json; copy the
chosen images into docs/design/scenes/ by hand.

Performance: for each quality tier (performance / medium / high, stored in localStorage `rov.quality` before
the page loads so the scene is built for that tier) the script renders both views 15 times at 800x450 with a
pixel read-back after each frame and reports the mean ms per frame, draw calls and triangles. SwiftShader
timings are only comparable with each other on the same machine.
"""
import base64
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'scene-review'
TAG = os.environ.get('ROV_SCENE_TAG', 'after')
# NED points: third = (camera, target) overview; onboard = (camera, target) at an inspection stand-off.
SITES = {
    'jacket_inspection': {'third': ((4, -17, 7), (20, 0, 15)), 'onboard': ((26.6, 6.6, 6), (25.1, 5.1, 6.3))},
    'monopile_current': {'third': ((-2, -14, 5), (15, 0, 16)), 'onboard': ((10.5, 0, 12), (15, 0, 12.4))},
    'tether_untangle': {'third': ((-4, -9, 6), (8, 0, 14)), 'onboard': ((8, 2.8, 10), (8, 0, 10.3))},
    'hull_inspection': {'third': ((2, -22, 13), (40, 0, 6)), 'onboard': ((18, 0, 9.5), (30, 0, 7.5))},
    'wreck_survey': {'third': ((8, -12, 20), (25, 5, 27)), 'onboard': ((41.4, 16.5, 26), (30, 9, 27))},
    'korean_castle': {'third': ((-6, -20, 14), (20, -40, 26)), 'onboard': ((13.2, -24.5, 26), (17.6, -24.5, 26))},
    'harbor_inspection': {'third': ((14, -18, 6), (36, 0, 12)), 'onboard': ((39, 0, 10), (42, 0, 10.3))},
    'tutorial_pool': {'third': ((-9, -9, 2), (8, 6, 7)), 'onboard': ((6, 0, 4), (12, 0, 5))},
    'coral_reef': {'third': ((2, -18, 6), (18, -6, 13)), 'onboard': ((16, -12, 9), (22, -10, 12.5))},
    'seagrass_meadow': {'third': ((0, -14, 3), (16, -6, 8.5)), 'onboard': ((14, -9, 6), (20, -8, 8.5))},
    'open_water': {'third': ((-6, -10, 6), (14, 4, 22)), 'onboard': ((10, 0, 6), (16, 2, 12))},
}
TIERS = ('performance', 'medium', 'high')

CAPTURE = '''([view, real, width, height, quality, frames]) => {
  const v = window.__viewer, THREE = v.THREE, renderer = v.renderer, camera = v.camera, scene = v.scene;
  const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
  window.__skipRender = true;
  const keep = {ratio: renderer.getPixelRatio(), size: renderer.getSize(new THREE.Vector2()),
    pos: camera.position.clone(), q: camera.quaternion.clone(), fov: camera.fov, aspect: camera.aspect,
    near: scene.fog.near, far: scene.fog.far};
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  if (real) camera.fov = 70;
  camera.position.copy(P(view[0]));
  camera.lookAt(P(view[1]));
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  const vis = v.W?.scenario?.visibility_m || 12;
  scene.fog.near = real ? .3 : 5;
  scene.fog.far = real ? vis * 1.35 : 70;
  const gl = renderer.getContext(), pixel = new Uint8Array(4);
  renderer.render(scene, camera);
  const t0 = performance.now();
  for (let i = 0; i < frames; i++) {
    renderer.render(scene, camera);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  }
  const ms = frames ? (performance.now() - t0) / frames : 0;
  const info = {calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, ms};
  const image = quality ? renderer.domElement.toDataURL('image/jpeg', quality) : null;
  renderer.setPixelRatio(keep.ratio);
  renderer.setSize(keep.size.x, keep.size.y, false);
  camera.position.copy(keep.pos);
  camera.quaternion.copy(keep.q);
  camera.fov = keep.fov;
  camera.aspect = keep.aspect;
  camera.updateProjectionMatrix();
  scene.fog.near = keep.near;
  scene.fog.far = keep.far;
  window.__skipRender = false;
  return {image, info};
}'''


def open_site(browser, key, tier):
    page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(f"try{{localStorage.setItem('rov.quality','{tier}')}}catch(e){{}}")
    room = f'rv{abs(hash((key, tier))) % 10**8}'
    url = f'{http_base(8092)}/?play=1&ws={ws_base(8792)}&nointro&nopip&room={room}&scenario={key}&seed=1'
    page.goto(url)
    page.wait_for_function(f'window.__viewer?.W?.scenario?.key==="{key}" && !!window.__viewer?.renderer',
                           timeout=timeout(60000))
    page.wait_for_timeout(timeout(5000))
    return page, errors


def save_jpeg(data_url, path):
    path.write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
    return path.stat().st_size


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = [s for s in os.environ.get('ROV_SCENE_SITES', '').split(',') if s]
    sites = {k: v for k, v in SITES.items() if not only or k in only}
    report = {'tag': TAG, 'sites': {}}
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        for key, views in sites.items():
            entry = report['sites'].setdefault(key, {})
            tiers = [t for t in os.environ.get('ROV_SCENE_TIERS', ','.join(TIERS)).split(',') if t in TIERS]
            for tier in tiers:
                page, errors = open_site(browser, key, tier)
                for name, view in views.items():
                    real = name == 'onboard'
                    if tier == 'medium':
                        shot = page.evaluate(CAPTURE, [view, real, 1600, 900, 0.8, 0])
                        size = save_jpeg(shot['image'], OUT / f'{key}-{name}-{TAG}.jpg')
                        if size > 400_000:
                            shot = page.evaluate(CAPTURE, [view, real, 1600, 900, 0.6, 0])
                            size = save_jpeg(shot['image'], OUT / f'{key}-{name}-{TAG}.jpg')
                        entry[f'{name}_jpeg_bytes'] = size
                    timing = page.evaluate(CAPTURE, [view, real, 800, 450, 0, 15])['info']
                    entry[f'{tier}_{name}'] = {k: round(v, 2) for k, v in timing.items()}
                entry[f'{tier}_errors'] = errors
                page.close()
            print(key, json.dumps(entry), flush=True)
        browser.close()
    (OUT / f'perf-{TAG}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('scene review written to', OUT)


if __name__ == '__main__':
    main()
