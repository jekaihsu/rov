"""Capture player-facing screens, including a physically flown prologue result."""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen
from browser_underwater_shots import build_replay
from browser_cold_open_smoke import FAKE_PAD, Pilot
from browser_prologue_smoke import flight_keys, play_prologue
from trailer.run import start_server, stop_server

ROOT = HERE.parents[2]
OUT = ROOT / 'docs/store/steam/assets/shots'


def save_flight_frame(page, name):
    """Read the actual rendered canvas in the draw call, before desktop overlays."""
    image = page.evaluate("""() => {
      window.__skipRender = false;
      window.__advance(1/30);
      return window.__viewer.renderer.domElement.toDataURL('image/jpeg', 0.94).split(',')[1];
    }""")
    (OUT / f'{name}.jpg').write_bytes(base64.b64decode(image))


def capture(browser, board, name, target):
    page = browser.new_page(viewport={k: board[k] for k in ('width', 'height')})
    page.on('pageerror', lambda error: print('viewer:', error, flush=True))
    page.set_default_timeout(timeout(120000))
    page.add_init_script("window.rovDesktop = {edition:'steam'}")
    quality = 'high' if name in ('07-menu', '08-guide', '10-gamepad') else board['quality']
    query = f"ws={ws_base()}&seed={board['seed']}&quality={quality}&room=store{name[:2]}"
    if name in board['onboard']:
        lens = board['onboard'][name]
        pose = (lens['eye'], lens['heading'], lens['pitch']) if 'eye' in lens else None
        replay, _ = build_replay(name, target, lens['subject'], lens['lamp'], pose=pose)
        page.route('**/store-pose.json', lambda route: route.fulfill(json=replay))
        page.goto(f'{http_base()}/?{query}&replay=store-pose.json&nointro&capture&trailer=1')
        page.wait_for_function('window.__advance && window.__viewer?.S && window.__trailer')
        page.wait_for_load_state('networkidle')
        if lens['subject'] == 'wreck':
            page.wait_for_function("window.__viewer.worldG.getObjectByName('Forecastle_deck')")
        page.evaluate('window.__trailer.setHud(false)')
        for _ in range(5):
            page.evaluate('window.__advance(1/30)')
        save_flight_frame(page, name)
        page.close()
        return
    if name == '06-deck':
        query += f'&play=1&scenario={target}&trailer=1&capture&nopip'
    elif name == '09-results':
        query += '&play=1&scenario=tutorial_pool&nointro&control=UAV_CHN'
    elif name in ('10-gamepad', '12-stick'):
        page.add_init_script(FAKE_PAD % 'Standard gamepad')
        if name == '12-stick':
            query += f'&play=1&mission=campaign&chapter=cold_open&coldOpen=replay&scenario={target}&trailer=1&nointro'
    elif name == '08-guide':
        page.add_init_script("localStorage.setItem('rov.campaign.v1', JSON.stringify({completed:['prologue']}))")
    page.goto(f'{http_base()}/?{query}', wait_until='domcontentloaded')
    if name == '06-deck':
        page.wait_for_function('typeof window.__advance === "function"')
        page.evaluate('window.__skipRender = true')
        page.wait_for_function('() => { window.__advance(1/30); return window.__intro?.()?.playing }')
        page.evaluate("""time => {
          while (window.__intro().t + 1/30 < time && !window.__intro().held) window.__advance(1/30);
        }""", board['deckTime'])
        save_flight_frame(page, name)
        page.close()
        return
    elif name == '12-stick':
        page.wait_for_function('window.__coldOpen && window.__viewer?.W?.scenario?.key === "cold_open_jacket"'
                               ' && window.__viewer.S?.campaign')
        page.evaluate("""() => {
          if (window.__viewer.S.campaign.status === 'idle')
            window.__viewer.send({type:'operation', action:'campaign_start', chapter:'cold_open', resume:false});
        }""")
        page.evaluate('window.__skipRender = true')
        page.wait_for_function('window.__coldOpen.debug().beat === "approach"')
        if page.evaluate('window.__viewer.S.locked'):
            page.keyboard.press(flight_keys(page)['lock'])
        pilot = Pilot(page, 'standard')
        pilot.axis('surge', 0.45)
        page.wait_for_selector('#coldOpenHint .ob-cap-name')
        page.evaluate('window.__skipRender = false')
        page.evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))')
    elif name == '09-results':
        page.wait_for_function('window.__viewer?.S?.campaign?.status === "idle"')
        page.locator('.story-menu button').filter(has_text='序章｜見習之前').evaluate('b => b.click()')
        play_prologue(page)
        page.wait_for_selector('#resultsScreen:not([hidden])')
        assert page.evaluate('window.__results.outcome.success')
    else:
        open_main(page)
        if name == '08-guide':
            page.click('#entry-freeDive')
            page.click(f'[data-site="{target}"]')
            page.wait_for_selector('.free-dive-list')
            page.wait_for_function("window.__viewer.worldG.getObjectByName('Forecastle_deck') && window.__modelLoaded")
            photo = page.evaluate('window.__viewer.takePhoto()')
            assert photo['observation']
            page.click('.free-dive-list')
            page.wait_for_selector('dialog.free-dive-log small')
        elif name == '10-gamepad':
            page.click('#entry-settings')
            wait_screen(page, 'settings')
            page.click(f'#menuSettings-tab-{target}')
    page.mouse.move(0, 0)
    page.evaluate('document.fonts.ready')
    page.screenshot(path=OUT / f'{name}.jpg', quality=91, animations='disabled')
    page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('shots', nargs='*')
    args = parser.parse_args()
    board = json.loads((HERE / 'ui.json').read_text(encoding='utf-8'))
    OUT.mkdir(parents=True, exist_ok=True)
    process, log, ports = start_server(ROOT / 'output/store' / ('ui-' + '-'.join(args.shots) + '.log'))
    try:
        os.environ['ROV_HTTP_PORT'] = str(ports['http'])
        os.environ['ROV_WS_PORT'] = str(ports['ws'])
        with sync_playwright() as playwright:
            browser = launch(playwright)
            for name in args.shots or board['shots']:
                print(name, flush=True)
                capture(browser, board, name, board['shots'][name])
            browser.close()
    finally:
        stop_server(process, log)


if __name__ == '__main__':
    main()
