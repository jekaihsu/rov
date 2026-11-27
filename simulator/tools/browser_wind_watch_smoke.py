"""Fly the three season-end watches using touch sticks and the onboard shutter, including both endings."""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch, skip_render, timeout, ws_base
from browser_cold_open_smoke import contact_sheet


def capture(page, path):
    # Draw a single frame. The compositor retains it while the touch input heartbeat keeps running.
    page.evaluate("""() => new Promise(resolve => requestAnimationFrame(() => {
      const {renderer, scene, camera} = window.__viewer;
      renderer.render(scene,camera);
      resolve();
    }))""")
    page.screenshot(path=str(path), type='jpeg', quality=82)


OUT = Path(__file__).resolve().parents[2] / 'docs/design/chapter3-u1'
ROUTES = {
    'wind_set': 'window station logged',
    'wind_shadow': 'veil edge evidence',
    'wind_return': 'slack anode north catch reverse clear sign licence end',
}
# Drive the viewer's touch channels. Positions, camera evidence, hooks and failure all come back from the host.
FLY = """async hard => {
  const {axisChannel} = await import('/input/bindings.js');
  const v = window.__viewer, s = v.S, beat = s.campaign.node?.id;
  const clip = (x, limit) => Math.min(limit, Math.max(-limit, x));
  const axes = {surge:0, sway:0, heave:0, yaw:0};
  const target = s.mission.targets?.[0];
  if (target && ['station','edge','anode','north','reverse'].includes(beat)) {
    if (s.locked) v.rc.rc_lock = s.input_latched ? 1 : 0;
    v.rc.keep_depth = 1;
    const transit = beat === 'north' || (beat === 'reverse' && hard);
    let [n,e,d] = transit ? s.mission.targets[1].point : target.point;
    if (beat === 'reverse' && !hard && (window.pastAnode || Math.hypot(n-s.pos[0],e-s.pos[1]) < 1.8)) {
      window.pastAnode = true;
      [n,e] = [-12,-9];
    }
    const heading = s.euler[2] * Math.PI / 180;
    const dn = n-s.pos[0];
    // Accumulate a small cross-current trim from observed station error.
    if (beat === 'station' && !s.locked && Math.hypot(dn,e-s.pos[1]) < 3) {
      const dt = clip(s.t - (window.trimTime ?? s.t),.3);
      window.eastTrim = clip((window.eastTrim || 0) + (e-s.pos[1])*dt*.16,1.4);
    }
    window.trimTime = s.t;
    const de = e-s.pos[1] + (beat === 'station' ? window.eastTrim || 0 : 0);
    const [fn,fe] = target.face_point;
    const want = transit ? Math.atan2(de,dn) : beat === 'reverse' ? 0 : Math.atan2(fe-s.pos[1],fn-s.pos[0]);
    axes.yaw = clip(Math.atan2(Math.sin(want-heading), Math.cos(want-heading))*.85,.7);
    axes.heave = clip((s.pos[2]-d)*.55,.4);
    axes.surge = clip((Math.cos(heading)*dn + Math.sin(heading)*de)*.36,.55);
    axes.sway = clip((-Math.sin(heading)*dn + Math.cos(heading)*de)*.36,.55);
    if (beat === 'north') {
      axes.surge = clip(axes.surge,.30);
      axes.sway = clip(axes.sway,.30);
    }
    if (hard && beat === 'reverse') axes.surge=1;
    if (target.ready && !target.completed && performance.now() > (window.lastShot || 0)+1500) {
      window.lastShot = performance.now();
      v.takePhoto();
    }
  }
  for (const [axis,value] of Object.entries(axes)) {
    const {channel,sign} = axisChannel(axis,s.operation_mode);
    v.touch[channel] = s.locked ? 0 : sign*value;
  }
  return {beat, status:s.campaign.status, p:s.pos, target:target?.point, ready:target?.ready,
          broken:s.tether.broken, tension:s.tether.tension_rov, completed:target?.completed, t:s.t, locked:s.locked};
}"""


def fly(browser, chapter, hard=False):
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    print('launch', chapter, 'hard pull' if hard else 'survey', flush=True)
    page.on('pageerror', lambda error: print('PAGE ERROR', error, flush=True))
    page.add_init_script("""window.__skipRender=true; localStorage.setItem('rov.campaign.v1',JSON.stringify({
      completed:['prologue','harbor','hull','harbor_signoff','wind_set','wind_shadow']}))""")
    page.goto(f'{http_base()}/?play=1&mission=campaign&chapter={chapter}&scenario={chapter}&nointro'
              f'&room=wind{time.time_ns()}&quality=performance&ws={ws_base()}', wait_until='commit')
    page.wait_for_function('document.querySelector("#windWatch")', polling=50, timeout=timeout(90000))
    skip_render(page)
    folder = OUT / chapter
    folder.mkdir(parents=True, exist_ok=True)
    controller = '''hard => {
      const drive = DRIVE_FUNCTION;
      async function tick() { window.windFlightState = await drive(hard); }
      setInterval(tick, 100);
      return tick();
    }'''
    page.evaluate(controller.replace('DRIVE_FUNCTION', FLY), hard)
    frames = []
    expected = ROUTES[chapter].split()
    if hard:
        expected = expected[:5] + ['parted', 'end']
    seen = []
    next_sample = 0
    deadline = time.monotonic() + timeout(240000) / 1000
    while time.monotonic() < deadline:
        state = page.evaluate('window.windFlightState')
        if state['t'] > next_sample:
            print('pilot', state, flush=True)
            next_sample = state['t'] + 10
        if state['status'] == 'completed':
            break
        beat = state['beat']
        if beat not in seen:
            seen.append(beat)
            print(chapter, state, flush=True)
            assert seen == expected[:len(seen)], seen
            page.wait_for_timeout(400)
            if beat == 'licence':
                assert page.locator('.brand-licence[data-grade="grade1"]').count()
            if beat == 'end':
                assert page.locator('.brand-card-title').last.inner_text() == '完'
            suffix = '-pull' if hard else ''
            path = folder / f'{len(seen):02}-{beat}{suffix}.jpg'
            capture(page, path)
            frames.append((path, beat))
        page.wait_for_timeout(100)
    assert seen == expected and state['status'] == 'completed' and state['completed'], state
    assert state['broken'] == hard, state
    campaign = page.evaluate('window.__viewer.S.campaign')
    result = campaign['results'][-1]
    assert result['outcome'] == ('aborted' if hard else 'signed'), result
    assert result['photos_accepted'] == result['photos_required'] == 1, result
    assert ('wind_grade1' in campaign['rewards']) == (chapter == 'wind_return' and not hard)
    page.close()
    return frames


def main():
    with sync_playwright() as pw:
        browser = launch(pw)
        for chapter in ROUTES:
            frames = fly(browser, chapter)
            if chapter == 'wind_return':
                frames.extend(fly(browser, chapter, True)[-2:])
            contact_sheet(frames, OUT / chapter / 'contact-sheet.jpg')
        browser.close()


if __name__ == '__main__':
    main()
