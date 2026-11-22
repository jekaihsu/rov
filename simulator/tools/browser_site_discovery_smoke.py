"""Fly up to a colony on the cold-open jacket in free dive and photograph it for the field guide.

Uses the keyboard bindings of the selected vehicle, the physical onboard shutter and the regular
room server. Reloading the page must retain both the full-size image and its field-guide entry.
"""
import base64
import math
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, without_render, ws_base
from browser_prologue_smoke import flight_keys

OUT = Path(__file__).resolve().parents[1] / 'output' / 'site-discovery'
SITE = 'cold_open_jacket'


def approach(page, keys, target):
    page.evaluate("""async id => {
      const {listCollection} = await import('/collection_store.js');
      window.addEventListener('rov:collection-changed', async function checkPhoto() {
        const {photos} = await listCollection();
        window.__foundSubject = photos.some(p => p.observation?.entity_id === id);
      });
    }""", target['id'])
    held = set()
    started = time.monotonic()
    last_press = 0
    last_photo = 0
    while time.monotonic() - started < timeout(90000) / 1000:
        s = page.evaluate("""() => {
          const s = window.__viewer.S;
          return {pos:s.pos, vel:s.vel, yaw:s.euler[2], locked:s.locked,
                  hold:s.keep_depth, found:window.__foundSubject};
        }""")
        n, e, d = (a - b for a, b in zip(target['pos'], s['pos']))
        distance = math.hypot(n, e)
        heading = math.degrees(math.atan2(e, n))
        error = (heading - s['yaw'] + 540) % 360 - 180
        want = set()
        now = time.monotonic()
        if s['locked'] and now - last_press > 1.5:
            page.keyboard.press(keys['lock'])
            last_press = now
        elif not s['hold'] and now - last_press > 1.5:
            page.keyboard.press(keys['depth'])
            last_press = now
        if abs(d) > .25:
            want.add(keys['heave'][int(d > 0)])
        if abs(error) > 6:
            want.add(keys['yaw'][int(error < 0)])
        # Hold station on the exposed side, allowing for momentum as the vehicle approaches.
        yaw = math.radians(s['yaw'])
        tn = n + 1.65 * target['normal'][0]
        te = e + 1.65 * target['normal'][1]
        forward = math.cos(yaw) * tn + math.sin(yaw) * te - 1.2 * s['vel'][0]
        right = -math.sin(yaw) * tn + math.cos(yaw) * te - 1.2 * s['vel'][1]
        for axis, offset in [('surge', forward), ('sway', right)]:
            if abs(offset) > .32:
                want.add(keys[axis][int(offset < 0)])
        for key in held - want:
            page.keyboard.up(key)
        for key in want - held:
            page.keyboard.down(key)
        held = want
        if math.hypot(tn, te) < .8 and abs(d) < .35 and abs(error) < 14 and now - last_photo > 2:
            print('shutter', s['pos'], 'range', round(distance, 2), flush=True)
            page.keyboard.press(keys['photo'], delay=250)
            last_photo = now
        if s.get('found'):
            for key in held:
                page.keyboard.up(key)
            return
        page.wait_for_timeout(120)
    message = page.evaluate("window.__viewer.S.expedition?.last_observation")
    raise AssertionError(f"Photo {target['id']} from {s}: range {distance:.2f}, yaw error {error:.1f}, {message}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': 960, 'height': 540})
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.goto(f'{http_base()}/?play=1&nointro&cam=onboard&quality=performance&room=detail{time.time_ns()}'
                  f'&scenario={SITE}&mission=free_explore&seed=1&ws={ws_base()}', wait_until='domcontentloaded')
        page.wait_for_function('window.__viewer?.W?.habitat?.discoveries?.length && window.__viewer.S',
                               timeout=timeout(90000))
        target = page.evaluate('window.__viewer.W.habitat.discoveries[0]')
        assert target['kind'] == 'mussels', target
        keys = flight_keys(page)
        page.keyboard.press(keys['light'])
        with without_render(page):
            approach(page, keys, target)
        page.reload(wait_until='domcontentloaded')
        result = page.evaluate("""async id => {
          const {listCollection, getPhotoBlob} = await import('/collection_store.js');
          const {photos, guides} = await listCollection();
          const photo = photos.find(p => p.observation?.entity_id === id);
          if (!photo) return null;
          const blob = await getPhotoBlob(photo.id);
          const image = await createImageBitmap(blob);
          const reader = new FileReader();
          const data = new Promise(done => { reader.onload = () => done(reader.result.split(',')[1]); });
          reader.readAsDataURL(blob);
          return {guide: guides.some(g => g.photoId === photo.id), view: photo.metadata.cameraMode,
                  site: photo.metadata.scene, kind: photo.observation.category, width: image.width, image: await data};
        }""", target['id'])
        assert result is not None
        (OUT / 'mussels.png').write_bytes(base64.b64decode(result.pop('image'), validate=True))
        assert result['site'] == SITE and result['view'] == 'onboard', result
        assert result['guide'] and result['kind'] == target['kind'] and result['width'] > 0, result
        assert not errors, errors
        print('Accepted onboard photograph persisted after reload:', target['id'], result, flush=True)
        browser.close()


if __name__ == '__main__':
    main()
