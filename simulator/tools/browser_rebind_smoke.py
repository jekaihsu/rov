"""Rebind forward through the dialog, restart the viewer, and drive with the saved key."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_query


PAD = """
window.testPad = {
  id: 'Test controller', mapping: 'standard', index: 0, connected: true,
  axes: [0, 0, 0, 0, 0], buttons: Array.from({length: 18}, () => ({pressed: false, value: 0})),
};
Object.defineProperty(navigator, 'getGamepads', {value: () => [window.testPad]});
"""


def release_pad(page):
    """Wait until the editor sampled neutral, including when software rendering delays a frame."""
    page.wait_for_function("""() => {
      const dialog = document.querySelector('#inputSettings');
      if (!dialog.open) return true;
      const raw = dialog.querySelector('pre').textContent;
      if (!raw) return false;
      const sample = JSON.parse(raw);
      return sample.buttons?.every(v => !v) && sample.axes?.every(v => !v);
    }""", polling=20)


def pad_press(page, button, condition):
    # Respond within the page: a slow WebGL/CDP round trip can otherwise hold a D-pad press into auto-repeat.
    page.evaluate(f"""button => new Promise((resolve, reject) => {{
      const input = testPad.buttons[button];
      function observe() {{
        if (!({condition})) return;
        Object.assign(input, {{pressed: false, value: 0}});
        observer.disconnect();
        clearTimeout(timer);
        resolve();
      }}
      const observer = new MutationObserver(observe);
      observer.observe(document.querySelector('#inputSettings'), {{subtree: true, childList: true, attributes: true}});
      const timer = setTimeout(() => {{
        observer.disconnect();
        Object.assign(input, {{pressed: false, value: 0}});
        reject(new Error('Pad navigation stopped at ' + document.activeElement.outerHTML.slice(0, 150)));
      }}, {timeout(15000)});
      Object.assign(input, {{pressed: true, value: 1}});
    }})""", button)
    release_pad(page)


def check_pad_editor(page):
    page.evaluate('window.__skipRender = true')
    page.evaluate('for (const i of [8,9]) Object.assign(testPad.buttons[i], {pressed: true, value: 1})')
    page.wait_for_selector('#inputSettings[open]')
    page.evaluate('for (const i of [8,9]) Object.assign(testPad.buttons[i], {pressed: false, value: 0})')
    release_pad(page)
    for selector in ['#inputSettings h2 + button + button', '#keyboardBindings summary', '#padBindings summary']:
        pad_press(page, 13, f'document.activeElement.matches("{selector}")')
    pad_press(page, 0, 'document.querySelector("#padBindings").open')
    pad_press(page, 13, 'document.activeElement.dataset.binding === "left_lr"')
    pad_press(page, 0, 'document.querySelector("#padBindings [role=status]").textContent.includes("Press")')
    page.evaluate('testPad.axes[2] = 1')
    page.wait_for_function('document.querySelector("#padBindings [role=status]").textContent.includes("assigned")')
    assert page.locator('[data-binding=left_lr]').input_value() == 'a0'
    page.evaluate('testPad.axes[2] = 0')
    release_pad(page)
    pad_press(page, 0, 'document.querySelector("#padBindings [role=status]").textContent.includes("Press")')
    page.evaluate('testPad.axes[4] = 1')
    page.wait_for_function('document.querySelector("[data-binding=left_lr]").value === "a4"')
    page.evaluate('testPad.axes[4] = 0')
    release_pad(page)
    pad_press(page, 1, '!document.querySelector("#inputSettings").open')
    print('PASS: navigated, rejected a conflict, saved another axis and exited using only the pad.')


def run():
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True, args=['--enable-unsafe-swiftshader'])
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script(PAD)
        page.goto(f'{http_base(8080)}/?play=1&nointro&quality=performance&lang=en{ws_query()}')
        page.wait_for_function('window.__viewer?.S?.vehicle_id')
        check_pad_editor(page)
        page.keyboard.press('F9')
        assert page.locator('#inputSettings').evaluate('(node) => node.open'), page.evaluate("""() => ({
          focus: document.activeElement.outerHTML.slice(0, 140),
          dialogs: [...document.querySelectorAll('dialog[open]')].map(d => d.id),
          paused: !document.querySelector('#pauseMenu').hidden, phase: window.__viewer.S.procedure?.phase
        })""")
        group = page.locator('#keyboardBindings')
        group.locator('summary').click()
        forward = group.locator('[data-key-action=right_ud][data-key-index="0"]')
        forward.click()
        page.keyboard.press('KeyJ')
        assert 'J' in forward.inner_text()
        out = Path(__file__).resolve().parents[1] / 'output' / 'rebind'
        out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=out / 'bindings.jpg')
        page.reload()
        page.wait_for_function('window.__viewer?.S?.vehicle_id')
        page.evaluate('window.__skipRender = true')
        page.wait_for_function('window.__viewer.S.input_latched === false && window.__viewer.S.rc.rc_lock === 1')
        print('Ready', page.evaluate('''() => {
          const {locked, procedure, input_latched, remote_control} = window.__viewer.S;
          return [locked, procedure?.phase, input_latched, remote_control, document.activeElement.tagName];
        }'''), flush=True)
        page.keyboard.press('Space')
        page.wait_for_function('window.__viewer.S.locked === false')
        page.keyboard.down('ArrowUp')
        page.wait_for_timeout(350)
        assert page.evaluate('window.__viewer.S.rc.right_ud') == 1500
        page.keyboard.up('ArrowUp')
        start = page.evaluate('window.__viewer.S.pos.slice()')
        page.keyboard.down('KeyJ')
        page.wait_for_function("""start => {
          const s = window.__viewer.S;
          return !s.locked && s.rc.right_ud > 1500 && s.thrust.some(v => Math.abs(v) > .05)
            && Math.hypot(s.pos[0] - start[0], s.pos[1] - start[1]) > .1;
        }""", arg=start)
        page.keyboard.up('KeyJ')
        page.wait_for_function('window.__viewer.S.rc.right_ud === 1500')
        page.evaluate('window.__skipRender = false')
        page.screenshot(path=out / 'flight.jpg')
        assert not errors, errors
        browser.close()
        print('PASS: saved J drove forward with thrust and displacement; release returned the channel to neutral.')


if __name__ == '__main__':
    run()
