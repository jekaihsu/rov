"""Regression checks for flight shortcut isolation, replay pause and mixer scheduling."""
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base

BASE = f'{http_base(8092)}/'
with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + f'?play=1&nointro&ws={ws_base(8792)}&room=audio-review')
    page.wait_for_function('window.__viewer?.S?.vehicle_id')
    mode = page.evaluate('window.__viewer.S.ctrl_mode')
    page.keyboard.press('m')
    page.wait_for_function('(mode) => window.__viewer.S.ctrl_mode !== mode', arg=mode)
    assert page.evaluate("import('./audio/engine.js').then(m => !m.installAudio().settings.mute)")
    print('PASS: M changes flight mode without changing mute', flush=True)
    page.goto(BASE + '?play=1&nointro&replay=demo_recording.json')
    page.wait_for_function('window.__viewer?.S && !document.querySelector("#replayBar").hidden')
    page.keyboard.press('Shift')
    # Invoke the real replay button handler beneath the current HUD overlay.
    page.locator('#rpPlay').evaluate('(button) => button.click()')
    page.wait_for_function("import('./audio/engine.js').then(m => m.installAudio().ctx?.state === 'running')")
    page.wait_for_timeout(1000)
    assert page.evaluate("import('./audio/engine.js').then(m => m.installAudio().master.gain.value < 0.001)")
    page.keyboard.press('Shift')
    # Invoke the real replay button handler beneath the current HUD overlay.
    page.locator('#rpPlay').evaluate('(button) => button.click()')
    page.wait_for_timeout(1000)
    assert page.evaluate("import('./audio/engine.js').then(m => m.installAudio().master.gain.value > 0.6)")
    result = page.evaluate('''async () => {
      const engine = (await import('./audio/engine.js')).installAudio();
      const original = engine.smooth;
      const gains = [engine.master.gain, ...Object.values(engine.buses).map(bus => bus.gain)];
      let calls = 0;
      engine.smooth = function count(param, ...args) {
        if (gains.includes(param)) calls++;
        return original.call(this, param, ...args);
      };
      for (let i = 0; i < 120; i++) engine.update(window.__viewer.S);
      const stable = calls;
      engine.set('vehicle', 0.3);
      const changed = calls - stable;
      engine.smooth = original;
      return {stable, changed};
    }''')
    assert result == {'stable': 0, 'changed': 1}, result
    assert not errors, errors
    print('PASS: replay pause fades out, resume fades in; 120 stable frames schedule 0 bus gains; '
          'one slider change schedules 1 gain; no page errors', flush=True)
    browser.close()
