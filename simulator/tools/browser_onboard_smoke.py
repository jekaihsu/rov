"""Onboard camera look (T14b) as the optics pipeline's camera pass.

In an optics tier (quality=medium) renders the same frozen onboard frame with the `cameraLook` fidelity item off
and on, saves both side by side to output/t14b/comparison.png, and checks that the pass sits right after
auto-exposure, changes the picture, leaves the camera transform alone, is bypassed in chase view, adds no overlay
canvas or text layer, and that the low tier (quality=performance) has no camera look. Prints the average frame time of the
optics pipeline with the look off and on at the page size (`--size 1920x1080` for the cost measurement).
Addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import argparse
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
RENDER = '''(args) => {
  const [enabled, frames] = args;
  const v = window.__viewer;
  const optics = window.__underwaterOptics;
  window.__fidelity.set('cameraLook', enabled);
  v.cameraLook.update();
  optics.renderer.render(v.scene, v.camera);
  const gl = optics.renderer.getContext();
  const pixel = new Uint8Array(4);
  const start = performance.now();
  for (let i = 0; i < frames; i++) {
    v.cameraLook.update();
    optics.renderer.render(v.scene, v.camera);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);   // wait for the frame (finish() does not)
  }
  const ms = (performance.now() - start) / frames;
  return {ms, image: document.querySelector("#vp canvas").toDataURL().split(",")[1]};
}'''


def open_viewer(page, quality):
    page.goto(f'{http_base()}/?play=1&nointro&cam=onboard&quality={quality}&room=onboard-{quality}&ws={ws_base()}',
              wait_until='domcontentloaded')
    page.wait_for_function('window.__viewer?.S && window.__viewer.cameraLook', timeout=timeout(90000))
    page.evaluate("async () => { window.__fidelity = (await import('/fidelity.js')).getFidelity(); }")
    page.evaluate("window.__viewer.setCam('onboard')")
    page.wait_for_timeout(2000)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--size', default='1280x720')
    parser.add_argument('--frames', type=int, default=3)
    args = parser.parse_args()
    width, height = (int(value) for value in args.size.split('x'))
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': width, 'height': height})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script(FREEZE)
        open_viewer(page, 'medium')
        page.wait_for_function('window.__underwaterOptics?.composer', timeout=timeout(60000))
        page.evaluate('window.freezeFrames = true; window.__skipRender = true')
        page.wait_for_timeout(300)
        before = page.evaluate('window.__viewer.camera.matrixWorld.toArray()')
        canvases = page.evaluate('document.querySelectorAll("canvas").length')
        plain = page.evaluate(RENDER, [False, args.frames])
        looked = page.evaluate(RENDER, [True, args.frames])
        plain_again = page.evaluate(RENDER, [False, args.frames])
        assert page.evaluate('window.__viewer.camera.matrixWorld.toArray()') == before, 'camera moved'
        assert page.evaluate('window.__viewer.cameraLook.active() === false')
        order = page.evaluate('''() => {
          const optics = window.__underwaterOptics;
          window.__fidelity.set('cameraLook', true);
          window.__viewer.cameraLook.update();
          const passes = optics.composer.passes;
          return passes.indexOf(window.__viewer.cameraLook.pass) - passes.indexOf(optics.exposurePass);
        }''')
        assert order == 1, f'camera pass must follow auto-exposure directly, offset {order}'
        assert plain['image'] != looked['image'], 'camera look did not change the onboard picture'
        page.evaluate("window.__viewer.setCam('chase'); window.__viewer.cameraLook.update()")
        assert not page.evaluate('window.__viewer.cameraLook.active()'), 'chase view must bypass the camera look'
        overlays = page.evaluate('document.querySelectorAll("canvas").length')
        assert overlays == canvases, f'the camera look must not add canvases or text layers: {canvases} -> {overlays}'
        low = browser.new_page(viewport={'width': 640, 'height': 360})
        low.on('pageerror', lambda error: errors.append(str(error)))
        open_viewer(low, 'performance')
        low.evaluate("window.__fidelity.set('cameraLook', true); window.__viewer.cameraLook.update()")
        assert not low.evaluate('window.__viewer.cameraLook.active()'), 'the low tier must not run the camera look'
        assert not errors, errors
        browser.close()
    from PIL import Image
    images = [Image.open(io.BytesIO(base64.b64decode(shot['image']))).convert('RGB') for shot in (plain, looked)]
    comparison = Image.new('RGB', (images[0].width * 2, images[0].height))
    for index, image in enumerate(images):
        comparison.paste(image, (images[0].width * index, 0))
    comparison.save(OUT / 'comparison.png')
    off = (plain['ms'] + plain_again['ms']) / 2
    print(f'frame time {width}x{height}: look off {off:.0f} ms, on {looked["ms"]:.0f} ms '
          f'({(looked["ms"] / off - 1) * 100:+.0f}%)')
    print('PASS: camera pass after exposure, picture changes, camera unchanged, chase and low tier bypass, no overlay')


if __name__ == '__main__':
    sys.exit(run())
