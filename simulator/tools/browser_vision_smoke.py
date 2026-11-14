"""AI vision overlay (T13): analytic box centre, oracle degradation statistics, key toggle and overlay layer.

Checks that a known box projects to the frame centre within 2 px, that the oracle detector's miss and false-positive
rates match their settings over 10,000 seeded trials, that the bound key (`visionToggle`, KeyN) flips the `aiOverlay`
fidelity item, that the overlay canvas sits on --z-scene-mark, and draws the production overlay on a fixture for
output/vision/after.png. Addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'vision'
CHECK = """async () => {
  const {THREE} = window.__viewer;
  const {inspectObservation} = await import('./observation_camera.js');
  const {OracleDetector} = await import('./vision/detector.js');
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, 1600 / 900, .01, 100);
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial());
  mesh.position.z = -3;
  scene.add(mesh);
  const context = {scene, camera, camMode: 'onboard', all: true,
    targets: [{entity_id: 'test', category: 'engineering', mesh}]};
  const truth = inspectObservation(context);
  if (truth.length !== 1) throw Error('missing analytical target');
  const box = truth[0].box;
  const error = Math.hypot((box[0] + box[2] / 2 - .5) * 1600, (box[1] + box[3] / 2 - .5) * 900);
  if (error >= 2) throw Error('box center error ' + error);
  let seed = 13;
  function random() {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 4294967296;
  }
  const detector = new OracleDetector({miss: .3, falsePositive: .2, random});
  let missed = 0;
  let falsePositives = 0;
  for (let i = 0; i < 10000; i++) {
    const detections = await detector.detect({truth});
    if (!detections.some(d => d.entity_id === 'test')) missed++;
    if (detections.some(d => d.cls === 'unknown')) falsePositives++;
  }
  if (Math.abs(missed / 10000 - .3) > .02 || Math.abs(falsePositives / 10000 - .2) > .02) {
    throw Error('oracle distribution');
  }
  window.__fixtureTruth = truth;
  return {error, missRate: missed / 10000, falsePositiveRate: falsePositives / 10000};
}"""
TAP = """() => {
  for (const type of ['keydown', 'keyup']) {
    document.body.dispatchEvent(new KeyboardEvent(type, {code: 'KeyN', bubbles: true}));
  }
}"""


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base()}/?play=1&nointro&cam=onboard&room=visioncheck&ws={ws_base()}',
                  wait_until='domcontentloaded')
        page.wait_for_function('window.__viewer?.S && window.rovVision', timeout=timeout(90000))
        assert page.evaluate('window.rovVision.enabled') is False, 'aiOverlay must be off in the real preset'
        page.evaluate(TAP)
        page.wait_for_function('window.rovVision.enabled === true', timeout=timeout(10000))
        layer = page.evaluate('getComputedStyle(document.querySelector("#vision-overlay")).zIndex')
        mark = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--z-scene-mark").trim()')
        assert layer == mark, (layer, mark)
        result = page.evaluate(CHECK)
        page.evaluate('''async () => {
          const {drawDetections} = await import('./vision/overlay.js');
          window.rovVision.update = () => {};
          const canvas = window.rovVision.overlay;
          canvas.width = 1600;
          canvas.height = 900;
          const truth = window.__fixtureTruth.map(t => ({...t, cls: t.category, score: 1}));
          drawDetections(canvas.getContext('2d'), truth, 1600, 900);
        }''')
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT / 'after.png'))
        page.evaluate(TAP)
        assert page.evaluate('window.rovVision.enabled') is False
        assert not errors, errors
        browser.close()
    print('Vision overlay passed:', result)


if __name__ == '__main__':
    sys.exit(run())
