"""Pilot into the prewrapped training pile, then haul the drum. Repeat with feedback muted."""
import argparse
from pathlib import Path
from time import time_ns

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from browser_playstation_smoke import FAKE_PAD, PROFILES

OUT = Path(__file__).resolve().parents[1] / 'output/feel-smoke'

OBSERVE = """async ([muted, baseline]) => {
  const viewer = window.__viewer;
  const audio = (await import('./audio/engine.js')).installAudio();
  const prefs = (await import('./fidelity.js')).getFidelity();
  for (const id of ['contactVideo','crewCalls','idleCalls','padHaptics','contactSound','strainSound']) {
    if (!baseline) prefs.set(id, !muted);
  }
  window.pulses.length = 0;
  const evidence = window.evidence = {hits: [], gain: 0, lines: [], shake: 0, pulls: 0};
  const impact = audio.impact.bind(audio);
  audio.impact = (envelope, bus) => {
    if (!bus || bus === 'underwater') evidence.hits.push(envelope);
    return impact(envelope, bus);
  };
  const noise = document.querySelector('.impact-noise');
  if (noise) {
    const animate = noise.animate.bind(noise);
    noise.animate = (...args) => { evidence.shake++; return animate(...args); };
  }
  new MutationObserver(() => evidence.lines.push(document.querySelector('#crewRadio p').textContent))
    .observe(document.querySelector('#crewRadio p'), {childList:true});
  setInterval(() => {
    evidence.gain = Math.max(evidence.gain, audio.strain?.level.gain.value || 0);
    if (viewer.S.tether?.warn) evidence.pulls++;
  }, 50);
  viewer.setCam('onboard');
  window.approach = true;
  const pile = viewer.W.obstacles.find(item => item.name === 'Pile P1');
  window.steer = setInterval(function steer() {
    const state = viewer.S;
    if (state.locked) {
      viewer.touch.right_ud = 0;
      viewer.touch.right_wave = 0;
      viewer.rc.rc_lock = state.input_latched ? 1 : 0;
      return;
    }
    const north = pile.p0[0] - state.pos[0];
    const east = pile.p0[1] + (window.approach ? 0 : 9) - state.pos[1];
    const yaw = state.euler[2] * Math.PI / 180;
    const scale = Math.max(1, Math.hypot(north, east));
    viewer.touch.right_ud = (north * Math.cos(yaw) + east * Math.sin(yaw)) / scale;
    viewer.touch.right_wave = (east * Math.cos(yaw) - north * Math.sin(yaw)) / scale;
  }, 80);
}"""


def drive(browser, muted, baseline=False, shots=None):
    width, height = (1600, 900) if shots else (800, 450)
    page = browser.new_page(viewport={'width': width, 'height': height})
    page.add_init_script(FAKE_PAD + """
        window.pulses = [];
        fakePad.vibrationActuator = {playEffect(kind, values) { window.pulses.push(values.duration); }};
    """)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    site = 'tether_untangle'
    url = f'{http_base()}/?ws={ws_base()}&scenario={site}&room=feel{time_ns()}'
    page.goto(url + '&play=1&nointro&fidelity=assisted&quality=performance')
    page.wait_for_function('(s) => window.__viewer?.W?.scenario?.key === s && window.__viewer.S', arg=site)
    page.evaluate('profile => window.__setPs(profile)', PROFILES['dualsense_standard'])
    page.keyboard.press('Shift')
    page.wait_for_function("import('./audio/engine.js').then(m => m.installAudio().ctx?.state === 'running')")
    page.evaluate('window.__skipRender = true')
    page.evaluate(OBSERVE, [muted, baseline])
    try:
        page.wait_for_function('window.__viewer.S.events?.length', timeout=timeout(45000))
        print('pile contact', muted, page.evaluate('window.__viewer.S.events.at(-1)'), flush=True)
        if not muted and not baseline:
            page.wait_for_function('evidence.lines.length > 0', timeout=timeout(12000))
        if shots and not muted:
            shots.mkdir(parents=True, exist_ok=True)
            page.evaluate('window.__skipRender = false')
            page.screenshot(path=str(shots / 'pile-contact.jpg'), quality=82)
            page.evaluate('window.__skipRender = true')
        page.evaluate("""window.approach = false;
          window.__viewer.touch.right_ud = -1;
          window.__viewer.touch.right_wave = 1;
          document.querySelector('[data-reel="haul_in"]').click();""")
        page.wait_for_function('evidence.pulls > 0', timeout=timeout(90000))
        page.evaluate('clearInterval(steer); window.__viewer.touch.right_wave = 0; window.__viewer.touch.right_ud = 0')
        page.wait_for_timeout(8500)
        result = page.evaluate('({...evidence, pulses})')
        assert not errors, errors
        if baseline:
            print('baseline', result, flush=True)
            return
        if muted:
            assert result['pulses'] == [], result
        assert bool(result['hits']) != muted, result
        assert (result['gain'] > 0.001) != muted, result
        assert bool(result['lines']) != muted, result
        assert bool(result['shake']) != muted, result
        assert any(ms in [80, 250] for ms in result['pulses']) != muted, result
        assert (180 in result['pulses']) != muted, result
        OUT.mkdir(parents=True, exist_ok=True)
        page.evaluate('window.__skipRender = false')
        destination = shots or OUT
        destination.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(destination / f'pull-muted-{muted}.jpg'), quality=75)
        print('muted', muted, result, flush=True)
    finally:
        print(page.evaluate("""() => { const s = window.__viewer.S;
          return {pos:s.pos, t:s.t, hits:s.events.length, load:s.tether.tension_max,
            warn: !!s.tether.warn, lines: evidence.lines}; }"""), flush=True)
        page.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true', help='observe the same manoeuvre on pre-R7 main')
    parser.add_argument('--shots', type=Path, help='save full-size contact and pull frames here')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for muted in ((False,) if args.baseline else (False, True)):
            drive(browser, muted, args.baseline, args.shots)
        browser.close()
