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
    'overview': ((-1.85, -.72, 12.43), (0, -.72, 12.89)),
    'close': ((-1.85, .72, 12.43), (0, .72, 12.79)),
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
    previous_heading = None
    last_press = -10
    next_trace = 0
    channels = page.evaluate("""async () => {
        const {axisChannel} = await import('/input/bindings.js');
        const {currentOperationMode} = await import('/input/keyboard_layout.js');
        return Object.fromEntries(['surge','sway','yaw','heave'].map(axis => [axis, axisChannel(axis, currentOperationMode())]));
    }""")
    photo_beats = {"frame": "housing", "overview": "shore_end", "close": "sea_end"}
    deadline = time.monotonic() + timeout(420000) / 1000
    while time.monotonic() < deadline:
        state = page.evaluate("""() => {const s=window.__viewer.S;
          return {beat:s.campaign.node?.id,status:s.campaign.status,t:s.t,pos:s.pos,vel:s.vel,yaw:s.euler[2],locked:s.locked,
            light:s.rc.right_switch,report:s.repair_report};}""")
        if state['status'] == 'completed':
            break
        beat = state['beat']
        if beat not in [name for _, name in frames]:
            print(chapter, beat, state['pos'], state['report'], flush=True)
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
        sticks = dict(surge=0., sway=0., yaw=0., heave=0.)
        tap = None
        if beat in STATIONS:
            station, subject = STATIONS[beat]
            x, y, z = state['pos']
            north, east = station[0] - x, station[1] - y
            yaw = math.radians(state['yaw'])
            forward = north * math.cos(yaw) + east * math.sin(yaw)
            right = -north * math.sin(yaw) + east * math.cos(yaw)
            u, v, w = state['vel']
            bearing = math.degrees(math.atan2(subject[1] - y, subject[0] - x))
            error = (bearing - state['yaw'] + 540) % 360 - 180
            if state['locked']:
                tap = 'lock'
            elif not state['light']:
                tap = 'light'
            else:
                yaw_rate = 0
                if previous_heading and state['t'] > previous_heading[0]:
                    turn = (state['yaw'] - previous_heading[1] + 540) % 360 - 180
                    yaw_rate = turn / (state['t'] - previous_heading[0])
                sticks.update(surge=.55 * forward - 1.2 * u, sway=.6 * right - 1.3 * v,
                              yaw=(error - .65 * yaw_rate) / 53, heave=.85 * (z - station[2]) + 1.3 * w)
                if (beat in photo_beats and math.hypot(north, east) < .72
                        and abs(z - station[2]) < .3 and abs(error) < 14):
                    tap = 'photo'
        if previous_heading is None or state['t'] > previous_heading[0]:
            previous_heading = (state['t'], state['yaw'])
        if beat in STATIONS and state['t'] >= next_trace:
            next_trace = state['t'] + 10
            print('pilot', beat, state['t'], state['pos'], state['yaw'], tap, flush=True)
        # The published viewer harness exposes the touch joystick. Its channels feed the
        # same input curve, websocket heartbeat, mixer and thrusters as the physical pad.
        axes = {channels[axis]['channel']: channels[axis]['sign'] * max(-.65, min(.65, value))
                for axis, value in sticks.items()}
        page.evaluate('axes => Object.assign(window.__viewer.touch, axes)', axes)
        if tap and state['t'] - last_press > 1:
            if tap == 'photo':
                page.evaluate('() => window.__viewer.takePhoto()')
            else:
                page.keyboard.press(keys[tap])
            last_press = state['t']
        page.wait_for_timeout(80)
    page.evaluate('() => { const touch = window.__viewer.touch; for (const key in touch) touch[key] = 0; }')
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
