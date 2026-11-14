"""Verify full-frame HUD geometry, peek lifecycle and the preserved engineering drawer."""
import argparse
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--screenshots', action='store_true')
args = parser.parse_args()

OUT = Path(__file__).resolve().parents[1] / 'output' / 't04'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=which('google-chrome') or which('chromium'),
                                headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8092/?play=1&nointro&ws=ws://127.0.0.1:8792&room=hudcheck', wait_until='domcontentloaded')
    page.wait_for_function('window.__viewer?.S && document.querySelector("#flightCable")')
    assert page.locator('#engineering').is_hidden()
    assert page.locator('#sticks').is_hidden()
    for width, height in [(1280, 720), (1920, 1080), (2560, 1080), (3440, 1440), (1600, 900)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(300)
        bounds = page.locator('#vp').bounding_box()
        assert bounds == {'x': 0, 'y': 0, 'width': width, 'height': height}, bounds
        if args.screenshots:
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
    mapping = page.evaluate('''async()=>{
      const {readHUDButtons} = await import('/hud/flight_hud.js');
      Object.defineProperty(navigator, 'getGamepads', {configurable:true, value:()=>{
        throw Error('HUD must consume actions without polling devices');
      }});
      try { return readHUDButtons({up:1, right:1}); } finally { delete navigator.getGamepads; }
    }''')
    assert mapping == [True, False, True, False], mapping
    page.click('#flightHide')
    assert page.locator('#flightDepth').is_hidden()
    page.click('#flightHide')
    page.keyboard.press('Tab')
    assert page.locator('#engineering').is_visible()
    if args.screenshots:
        page.screenshot(path=str(OUT / 'drawer.png'), timeout=120000)
    page.reload(wait_until='domcontentloaded')
    page.wait_for_selector('#engineering')
    page.keyboard.press('Tab')
    assert page.locator('#engineering').is_hidden()
    assert not errors, errors
    browser.close()
print('HUD geometry, tap timeout, hold/release, drawer persistence passed.')
