"""Onboard camera look (T14b): same-camera comparison, fidelity toggle, camera invariance and no OSD text.

Renders the same frozen onboard frame with the `cameraLook` fidelity item off and on, saves both side by side to
output/t14b/comparison.png, checks that the effect changes the picture, that the camera transform is untouched,
that chase view bypasses the effect and that the module adds no text overlay.
Addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import base64
import io
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 't14b'
FREEZE = """const schedule = window.requestAnimationFrame;
window.requestAnimationFrame = function frozen(callback) {
  return schedule.call(window, function maybe(time) { if (!window.freezeFrames) callback(time); });
};"""
CANVAS = 'document.querySelector("#vp canvas").toDataURL().split(",")[1]'


def grab(page, enabled):
    return base64.b64decode(page.evaluate(f'''(enabled) => {{
      const v = window.__viewer;
      window.__fidelity.set('cameraLook', enabled);
      for (let i = 0; i < 8; i++) v.cameraLook.render();
      return {CANVAS};
    }}''', enabled))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script(FREEZE)
        page.goto(f'{http_base()}/?play=1&nointro&cam=onboard&room=onboardcheck&ws={ws_base()}',
                  wait_until='domcontentloaded')
        page.wait_for_function('window.__viewer?.S && window.__viewer.cameraLook', timeout=timeout(90000))
        page.evaluate("async () => { window.__fidelity = (await import('/fidelity.js')).getFidelity(); }")
        page.evaluate("window.__viewer.setCam('onboard')")
        page.wait_for_timeout(1500)
        page.evaluate('window.freezeFrames = true; window.__skipRender = true')
        page.wait_for_timeout(300)
        before = page.evaluate('window.__viewer.camera.matrixWorld.toArray()')
        plain = grab(page, False)
        looked = grab(page, True)
        assert page.evaluate('window.__viewer.camera.matrixWorld.toArray()') == before, 'camera moved'
        assert plain != looked, 'camera look did not change the onboard picture'
        assert page.evaluate('window.__viewer.cameraLook.active()')
        page.evaluate("window.__viewer.setCam('chase')")
        assert not page.evaluate('window.__viewer.cameraLook.active()'), 'chase view must bypass the camera look'
        text_layers = page.evaluate('[...document.querySelectorAll("canvas")].filter(c => !c.closest("#vp")'
                                    ' && getComputedStyle(c).position === "fixed").length')
        assert text_layers == 0, f'unexpected fixed overlay canvases: {text_layers}'
        assert not errors, errors
        browser.close()
    from PIL import Image
    images = [Image.open(io.BytesIO(data)).convert('RGB') for data in (plain, looked)]
    width, height = images[0].size
    comparison = Image.new('RGB', (width * 2, height))
    for index, image in enumerate(images):
        comparison.paste(image.resize((width, height)), (width * index, 0))
    comparison.save(OUT / 'comparison.png')
    print('PASS: camera look on/off differs, camera unchanged, chase bypass, no overlay text; output/t14b/comparison.png')


if __name__ == '__main__':
    sys.exit(run())
