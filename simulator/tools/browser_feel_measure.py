"""Collect a 60-second wall-clock cue trace and an onboard still for each R7 site."""
import argparse
import json
from pathlib import Path
from time import time_ns

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

VIDEO = Path(__file__).resolve().parents[1] / 'output/feel-measure'
OUT = Path(__file__).resolve().parents[2] / 'docs/design/game-feel-r7'
TRACE = """async () => {
  const engine = (await import('./audio/engine.js')).installAudio();
  const viewer = window.__viewer;
  const started = performance.now();
  const trace = [];
  let pending = null;
  function log(kind, value) {
    trace.push([Math.round(performance.now() - started), kind, value]);
  }
  function respond(name) {
    log('response', name);
    pending.resolve();
    pending = null;
  }
  engine.cueListeners.push(function cue(kind) {
    log('audio', kind);
    if (pending?.kinds.includes(kind) && pending.matches(engine.state)) respond(pending.name);
  });
  const update = engine.update.bind(engine);
  engine.update = function measured(state) {
    update(state);
    if (pending?.motor && state && pending.matches(state)) respond(pending.name);
  };
  const radio = document.querySelector('#crewRadio p');
  const observer = new MutationObserver(() => log('radio', radio.textContent));
  observer.observe(radio, {childList:true, subtree:true});
  const seen = new Set();
  let high = false;
  const timer = setInterval(() => {
    for (const hit of viewer.S.events || []) {
      const key = JSON.stringify(hit);
      if (!seen.has(key)) log('impact', hit);
      seen.add(key);
    }
    if (!high && viewer.S.tether?.warn) log('tension', viewer.S.tether.tension_max);
    high = !!viewer.S.tether?.warn;
  }, 80);
  function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  async function command(name, kinds, matches, apply) {
    log('input', name);
    const acknowledged = new Promise(resolve => { pending = {name, kinds, matches, motor: !kinds.length, resolve}; });
    apply();
    await Promise.race([acknowledged, wait(6500)]);
    if (pending) log('timeout', name);
    pending = null;
    await wait(300);
  }
  await command('unlock', ['back','switch'], s => !s.locked, () => { viewer.rc.rc_lock = 0; });
  const light = viewer.S.rc.right_switch === 2 ? 1 : 2;
  await command('light', ['confirm','switch'], s => s.rc.right_switch === light,
                () => { viewer.rc.right_switch = light; });
  const hold = !viewer.S.keep_depth;
  await command('depth', [hold ? 'confirm' : 'back'], s => !!s.keep_depth === hold,
                () => { viewer.rc.keep_depth = Number(hold); });
  await command('surge', [], s => s.rc.right_ud > 1525 && !s.locked && s.thrust.some(v => Math.abs(v) > 0.01),
                () => { viewer.touch.right_ud = 0.7; });
  await command('neutral', [], s => Math.abs(s.rc.right_ud - 1500) < 25,
                () => { viewer.touch.right_ud = 0; });
  await wait(Math.max(0, 60000 - (performance.now() - started)));
  clearInterval(timer);
  observer.disconnect();
  return trace.filter(row => row[0] < 60000);
}"""


def measure(label, scenes):
    with sync_playwright() as driver:
        browser = launch(driver)
        for scene in scenes:
            page = browser.new_page(viewport={'width': 800, 'height': 450}, record_video_dir=VIDEO,
                                    record_video_size={'width': 800, 'height': 450})
            url = f'{http_base()}/?ws={ws_base()}&room=r7{time_ns()}&scenario={scene}&seed=42&mission=scenario_training'
            page.goto(url + '&play=1&nointro&cam=onboard&fidelity=assisted&quality=performance')
            page.wait_for_function('(s) => window.__viewer?.W?.scenario?.key === s && window.__viewer.S',
                                   arg=scene, timeout=timeout(90000))
            page.keyboard.press('Shift')
            page.wait_for_function("import('./audio/engine.js').then(m => m.installAudio().ctx?.state === 'running')")
            page.wait_for_function("window.__modelLoaded && window.__viewer.S.locked && "
                                   "!window.__viewer.S.input_latched", timeout=timeout(30000))
            page.wait_for_timeout(1500)
            trace = page.evaluate(TRACE)
            prefix = OUT / f'{label}-{scene}'
            prefix.with_suffix('.json').write_text(json.dumps(trace, ensure_ascii=False, indent=2) + '\n')
            page.set_viewport_size({'width': 1600, 'height': 900})
            page.screenshot(path=str(prefix.with_suffix('.jpg')), quality=75)
            print(scene, trace[:8], flush=True)
            page.close()
            Path(page.video.path()).replace(VIDEO / f'{label}-{scene}.webm')
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label', choices=['before', 'after'])
    sites = ['open_water', 'harbor_inspection', 'aquaculture_pen']
    parser.add_argument('--sites', nargs='+', choices=sites, default=sites)
    args = parser.parse_args()
    measure(args.label, args.sites)
