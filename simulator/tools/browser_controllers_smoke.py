"""Exercise real flight sampling and pause-menu navigation through synthetic Gamepad API reports."""
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

# id, mapping, family, raw confirm/back, raw right-stick X, printed confirm
PROFILES = [
    ('045e-02ea-Xbox One', 'standard', 'xbox', 0, 1, 2, 'A'),
    ('045e-0b13-Xbox Series', 'standard', 'xbox', 0, 1, 2, 'A'),
    ('045e-028e-Xbox 360', '', 'xbox', 0, 1, 3, 'A'),
    ('057e-2009-Pro Controller', '', 'switch', 1, 0, 2, 'A'),
    ('8BitDo Switch Pro', 'standard', 'switch', 1, 0, 2, 'A'),
    ('8BitDo XInput', 'standard', 'xbox', 0, 1, 2, 'A'),
    ('2dc8-6006-8BitDo Pro 2', '', 'switch', 0, 1, 2, 'A'),
    ('8BitDo Pro 2 (Vendor: 2dc8 Product: 6006)', '', 'switch', 0, 1, 3, 'A'),
    ('054c-05c4-Wireless Controller', 'standard', 'playstation', 0, 1, 2, '×'),
    ('28de-1205-Steam Deck', '', 'deck', 3, 4, 2, 'A'),
    ('XInput Gamepad', 'standard', 'xbox', 0, 1, 2, 'A'),
    ('046d-c216-Dual Action', '', 'generic', 1, 2, 2, '1'),
    ('USB DirectInput', '', 'generic', 0, 1, 2, '1'),
]


def press(page, index):
    page.evaluate("""async i => {
      pad.buttons[i].value = 1;
      await new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)));
      pad.buttons[i].value = 0;
      await new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)));
    }""", index)


def check(page, profile, number):
    name, mapping, family, accept, back, axis, label = profile
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=x2{number}&quality=performance&play=1&nointro')
    page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(120000))
    page.evaluate("""([id, mapping]) => {
      window.__skipRender = true;
      // Exercise the Windows DirectInput record on the Linux browser runner as well.
      if (id.includes('Vendor:')) Object.defineProperty(navigator, 'platform', {value: 'Win32'});
      window.pad = {id, mapping, connected: true, index: 0, axes: Array(10).fill(0),
        buttons: Array.from({length: 20}, () => ({value: 0, pressed: false}))};
      Object.defineProperty(navigator, 'getGamepads', {value: () => pad.connected ? [pad] : []});
    }""", [name, mapping])
    assert page.evaluate("async () => (await import('./input/glyphs.js')).deviceFamily(pad.id)") == family
    page.evaluate('i => pad.axes[i] = 0.9', axis)
    page.wait_for_function('window.__viewer.S.rc?.right_lr > 1600')
    page.evaluate('i => pad.axes[i] = 0', axis)
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseResume:visible')
    page.wait_for_function('window.__viewer.S.paused')
    # Focus a real entry and use confirm to open its settings pane, then back to the list.
    page.locator('#pauseSettings').focus()
    await_settings = '#pauseMenu [role=tab]:visible'
    press(page, accept)
    page.wait_for_selector(await_settings)
    cap = page.locator('#pauseMenu [data-action=accept] svg').first
    assert cap.get_attribute('aria-label') == label
    press(page, back)
    page.wait_for_selector(await_settings, state='hidden')
    press(page, back)
    page.wait_for_selector('#pauseMenu', state='hidden')
    page.wait_for_function('!window.__viewer.S.paused')
    page.evaluate('pad.connected = false')
    page.wait_for_selector('#pauseResume:visible')
    page.wait_for_function('window.__viewer.S.paused')
    page.evaluate('i => { pad.axes[i] = 1; pad.connected = true; }', axis)
    press(page, accept)
    assert page.locator('#pauseResume').is_visible(), 'reconnected while the stick was deflected'
    page.evaluate('i => pad.axes[i] = 0', axis)
    page.wait_for_function('!window.__viewer.S.paused && document.querySelector("#pauseMenu").hidden')
    print(name, 'passed', flush=True)


if __name__ == '__main__':
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': 1024, 'height': 720})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        for number, profile in enumerate(PROFILES):
            check(page, profile, number)
        assert not errors, errors
        browser.close()
