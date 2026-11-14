"""Onboard optical controls, captures, delay bounds, and same-camera comparison."""
import base64
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'output' / 't14b'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=which('chromium') or which('google-chrome'),
                                args=['--enable-unsafe-swiftshader'], headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda msg: errors.append(msg.text)
            if msg.type == 'error' and '404' not in msg.text else None)
    page.add_init_script("""const schedule = window.requestAnimationFrame;
      window.requestAnimationFrame = function(callback) {
        return schedule.call(window, function(time) { if (!window.freezeFrames) callback(time); });
      };""")
    page.goto('http://127.0.0.1:8092/?play=1&nointro&ws=ws://127.0.0.1:8792&room=onboardcheck')
    page.wait_for_function('window.__viewer?.S')
    page.evaluate("window.__viewer.setCam('onboard')")
    page.wait_for_timeout(1500)
    page.evaluate('window.freezeFrames = true')
    page.wait_for_timeout(200)
    page.evaluate('''() => {
      window.__skipRender = true;
      const v = window.__viewer;
      v.rovG.position.set(0, -22, 0);
      v.rovG.traverse(function light(object) { if (object.isSpotLight) object.intensity = 260; });
      v.camera.position.set(0, -22, 0);
      v.camera.lookAt(0, -25, 8);
      v.camera.updateMatrixWorld();
      window.beforeCamera = v.camera.matrixWorld.toArray();
      v.onboardVideo.settings.osd = false;
      v.onboardVideo.render();
    }''')
    (OUT / 'normal.png').write_bytes(base64.b64decode(page.evaluate(
        'window.__viewer.onboardVideo.render(); window.__viewer.camera; '
        'window.__viewer.onboardVideo.render(); '
        'document.querySelector("#vp canvas").toDataURL().split(",")[1]')))
    page.evaluate('window.__viewer.onboardVideo.settings.real = true')
    for _ in range(6):
        page.wait_for_timeout(100)
        page.evaluate('window.__viewer.onboardVideo.render()')
    (OUT / 'real.png').write_bytes(base64.b64decode(page.evaluate(
        'window.__viewer.onboardVideo.render(); '
        'document.querySelector("#vp canvas").toDataURL().split(",")[1]')))
    page.evaluate('''() => {
      const v = window.__viewer;
      if (JSON.stringify(window.beforeCamera) !== JSON.stringify(v.camera.matrixWorld.toArray()))
        throw Error('Optics changed camera geometry');
      v.onboardVideo.settings.osd = true;
      v.onboardVideo.settings.burn = true;
      v.onboardVideo.render({capture:true});
    }''')
    page.screenshot(path=str(OUT / 'osd.png'))
    for delay in (0, 80, 150):
        page.evaluate('(delay) => {window.__viewer.onboardVideo.settings.delay=delay; '
                      'window.__viewer.onboardVideo.render();}', delay)
    page.evaluate("window.__viewer.setCam('chase'); window.__viewer.onboardVideo.render()")
    assert not errors, errors
    browser.close()
from PIL import Image, ImageDraw
images = [Image.open(OUT / name).resize((1600, 900)) for name in ('normal.png', 'real.png')]
comparison = Image.new('RGB', (3200, 940), '#08121a')
for index, image in enumerate(images):
    comparison.paste(image, (1600 * index, 40))
ImageDraw.Draw(comparison).text((20, 10), 'Normal onboard / Real video - same camera', fill='white')
comparison.save(OUT / 'comparison.png')
print('PASS: optics, OSD burn-in, delays, camera invariant, same-camera screenshots')
