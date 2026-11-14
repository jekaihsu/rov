"""Verify full-frame HUD geometry, peek lifecycle and the preserved engineering drawer."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'output' / 't04'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=which('google-chrome') or which('chromium'),
                                headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8092/?play=1&nointro&ws=ws://127.0.0.1:8792&room=hudcheck')
    page.wait_for_function('window.__viewer?.S && document.querySelector("#flightCable")')
    assert page.locator('#engineering').is_hidden()
    assert page.locator('#sticks').is_hidden()
    for width, height in [(1280, 720), (1920, 1080), (2560, 1080), (3440, 1440), (1600, 900)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(300)
        bounds = page.locator('#vp').bounding_box()
        assert bounds == {'x': 0, 'y': 0, 'width': width, 'height': height}, bounds
        page.screenshot(path=str(OUT / f'{width}x{height}.png'), timeout=120000)
    page.set_viewport_size({'width': 1280, 'height': 720})
    # Send a tap in one task; software WebGL stalls otherwise turn CDP key presses into holds.
    page.evaluate('''()=>{
      for (const type of ['keydown', 'keyup']) {
        document.body.dispatchEvent(new KeyboardEvent(type, {code:'Digit1', bubbles:true}));
      }
    }''')
    page.wait_for_function('document.querySelector("#flightPeek").classList.contains("visible")')
    page.wait_for_function('!document.querySelector("#flightPeek").classList.contains("visible")')
    page.keyboard.down('Digit2')
    page.wait_for_timeout(3300)
    assert page.locator('#flightPeek').evaluate('(el)=>el.classList.contains("visible")')
    page.keyboard.up('Digit2')
    page.wait_for_function('!document.querySelector("#flightPeek").classList.contains("visible")')
    page.keyboard.press('Tab')
    assert page.locator('#engineering').is_visible()
    page.screenshot(path=str(OUT / 'drawer.png'), timeout=120000)
    page.reload()
    page.wait_for_selector('#engineering')
    page.keyboard.press('Tab')
    assert page.locator('#engineering').is_hidden()
    assert not errors, errors
    browser.close()
print('HUD geometry, tap timeout, hold/release, drawer persistence passed.')
