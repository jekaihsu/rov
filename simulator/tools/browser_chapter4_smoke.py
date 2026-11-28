"""Fly both chapter-four deployments via browser controls, saving each directed beat."""
import base64
import math
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, skip_render, timeout, ws_base
from browser_cold_open_smoke import contact_sheet
from browser_prologue_smoke import flight_keys

OUT = Path(__file__).resolve().parents[2] / 'docs/design/chapter4-k4'
FLIGHTS = {
    'c4_sheets': ('watch overview close haul receipt crosscheck', 'finale'),
    'c4_frame': ('bay frame retreat receipt night', 'c4_sheets'),
}
# NED camera stations and subjects in the fictional worksite.
STATIONS = {
    'overview': ((-1.45, -.72, 12.73), (0, -.72, 12.89)),
    'close': ((-1.4, .72, 12.62), (0, .72, 12.79)),
    'haul': ((1, 2, 11.6), (2, 2.9, 11.7)),
    'frame': ((-.45, 2.35, 12.37), (1.3, 2.16, 12.78)),
    'retreat': ((-3.2, 2, 12), (-5, 2, 12)),
}


def capture(page, path):
    # Present two real frames, then leave their composited image up during JPEG readback.
    skip_render(page, False)
    page.evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))')
    skip_render(page)
    page.screenshot(path=str(path), quality=84, timeout=timeout(90000))


def fly(page, chapter):
    expected, prerequisite = FLIGHTS[chapter]
    out = OUT / chapter
    out.mkdir(exist_ok=True)
    page.goto(f'{http_base()}/?play=1&nointro&quality=medium&fidelity=real&cam=onboard'
              f'&room=k4{time.time_ns()}&ws={ws_base()}', wait_until='commit')
    page.wait_for_function('window.__viewer?.S?.campaign?.status === "idle"', timeout=timeout(90000))
    skip_render(page)
    keys = flight_keys(page)
    keys['light'] = page.evaluate(
        "async () => (await import('/input/keyboard_layout.js')).currentKeyRows().find(r=>r.action==='light').keys[0]")
    page.evaluate("""id => window.__viewer.send({type:'operation',action:'campaign_restore',
        save:{completed:[id]}})""", prerequisite)
    page.wait_for_function('id=>window.__viewer.S.campaign.completed.includes(id)', arg=prerequisite)
    page.evaluate("""chapter=>window.__viewer.send({type:'operation',action:'campaign_start',chapter,beats:true})""",
                  chapter)
    page.wait_for_function('id=>window.__viewer.S.campaign.chapter === id', arg=chapter, timeout=timeout(90000))
    frames = []
    held = set()
    last_press = 0
    photo_beats = {"frame": "housing", "overview": "shore_end", "close": "sea_end"}
    deadline = time.monotonic() + timeout(420000) / 1000
    while time.monotonic() < deadline:
        state = page.evaluate("""() => {const s=window.__viewer.S;
          return {beat:s.campaign.node?.id,status:s.campaign.status,pos:s.pos,yaw:s.euler[2],locked:s.locked,
            light:s.rc.right_switch,report:s.repair_report};}""")
        if state['status'] == 'completed':
            break
        beat = state['beat']
        if beat not in [name for _, name in frames]:
            print(chapter, beat, state['pos'], flush=True)
            path = out / (beat + '.jpg')
            if beat in ('watch', 'bay', 'crosscheck') or (chapter == 'c4_frame' and beat == 'receipt'):
                page.locator(f'[data-beat="{beat}"] .cable-work-order').wait_for()
                page.screenshot(path=str(path), quality=84, timeout=timeout(90000))
            elif beat == 'night':
                page.locator('#cinematicPlayer[data-shot="0"]').wait_for()
                page.wait_for_timeout(900)
                page.screenshot(path=str(path), quality=84, timeout=timeout(90000))
            elif beat not in photo_beats:
                capture(page, path)
            frames.append((path, beat))
        want = set()
        tap = None
        if beat in STATIONS:
            station, subject = STATIONS[beat]
            x, y, z = state['pos']
            travelling = math.hypot(station[0]-x, station[1]-y) > .65
            n, e, _ = station if travelling else subject
            error = (math.degrees(math.atan2(e-y, n-x)) - state['yaw'] + 540) % 360 - 180
            if state['locked']:
                tap = 'lock'
            elif not state['light']:
                tap = 'light'
            else:
                if abs(error) > 7:
                    want.add(keys['yaw'][int(error < 0)])
                if travelling and abs(error) < 20:
                    want.add(keys['surge'][0])
                if abs(z-station[2]) > .15:
                    want.add(keys['heave'][int(station[2] > z)])
                if not travelling and abs(error) < 13 and beat in ('frame', 'overview', 'close'):
                    tap = 'photo'
        for key in held - want:
            page.keyboard.up(key)
        for key in want - held:
            page.keyboard.down(key)
        held = want
        if tap and time.monotonic() - last_press > .8:
            page.keyboard.press(keys[tap])
            last_press = time.monotonic()
        page.wait_for_timeout(100)
    for key in held:
        page.keyboard.up(key)
    assert state['status'] == 'completed', state
    assert [name for _, name in frames] == expected.split(), frames
    print(chapter, state['report'], flush=True)
    observations = state['report']['observations']
    if chapter == 'c4_sheets':
        assert set(observations) == {'shore_end', 'sea_end'}, state
        assert state['report']['end_separation_m'] > 1 and state['report']['recovery_seen'], state
    else:
        assert 'from_rock_ned_m' in observations['housing'], state
        assert len(state['report']['deck_fix_interval_s']) == 2, state
    # The camera's own archived picture has the exposure and pose at shutter time.
    for beat, subject in photo_beats.items():
        if beat not in expected.split():
            continue
        original = page.evaluate("""async id => {
          const {getPhotoBlob} = await import('/collection_store.js');
          const bitmap = await createImageBitmap(await getPhotoBlob(id));
          const canvas = document.createElement('canvas');
          canvas.width = 1600; canvas.height = 900;
          canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
          bitmap.close();
          return canvas.toDataURL('image/jpeg', .9).split(',')[1];
        }""", observations[subject]['collection_id'])
        (out / (beat + '.jpg')).write_bytes(base64.b64decode(original))
    contact_sheet(frames, out / 'contact-sheet.jpg')


def main():
    with sync_playwright() as pw:
        browser = launch(pw)
        for chapter in os.environ.get('ROV_C4_CHAPTERS', 'c4_sheets c4_frame').split():
            page = browser.new_page(viewport=dict(width=1600, height=900))
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            fly(page, chapter)
            assert not errors, errors
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
