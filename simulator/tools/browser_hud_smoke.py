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
    if not args.screenshots:
        # Isolate HUD timing from software WebGL and WebSocket leases. --screenshots uses the live game.
        page.route('**/boot.js', lambda route: route.fulfill(content_type='text/javascript', body="""
          import {updateFlightHUD} from '/hud/flight_hud.js';
          const S = {pos:[0,0,2], euler:[0,0,0], speed_kn:0, battery:100,
            vehicle_id:'self', vehicles:[], tether:{length:30,nodes:[[0,0,0],[0,0,2]]},
            score:{current_index:0,objectives:[{label:'Checkpoint',progress:0}]}};
          const W = {seabed_depth:25, obstacles:[], objectives:[]};
          document.documentElement.classList.add('in-game');
          document.getElementById('offline').hidden = true;
          window.__viewer = {S,W};
          function frame() { updateFlightHUD(S,W,1/60); requestAnimationFrame(frame); }
          frame();
        """))
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
      Object.defineProperty(navigator, 'getGamepads', {configurable:true, value:()=>[{
        mapping:'standard', buttons:Array.from({length:16}, (_, i)=>({pressed:i===12||i===15}))
      }]});
      try { return readHUDButtons(); } finally { delete navigator.getGamepads; }
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
print('HUD geometry, tap timeout, hold/release, D-pad adapter, hiding and drawer persistence passed.')
