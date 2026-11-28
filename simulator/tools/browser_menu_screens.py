"""Capture every launch-menu screen and the pause menu at 1600x900 (device scale 2) for design review.

Usage: start a simulator (defaults http 8092 / ws 8792, see _browser.py), then python tools/browser_menu_screens.py.
A full software-GL run takes about 20 minutes, longer than run_browser_checks.py allows one script.
Writes PNGs to docs/design/menu-redesign/ (or the directory given as the first argument). A capture larger than
1.5 MB is re-encoded with a palette (256 colours or fewer) so review images stay small. Not a pass/fail check.
"""
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_internal, open_main, set_intro, to_briefing, wait_ready, wait_screen

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'docs' / 'design' / 'menu-redesign'
LIMIT = 1_500_000
VIEW = {'width': 1600, 'height': 900}
ROOM = f'review{int(time.time())}'
PAD = """
window.__pad = {buttons: Array(17).fill(0), axes: [0, 0, 0, 0]};
const reviewPad = {
  id: 'Xbox 360 Controller (STANDARD GAMEPAD Vendor: 045e Product: 028e)', index: 0, connected: true,
  mapping: 'standard', vibrationActuator: null,
  get axes() { return window.__pad.axes.slice(); },
  get buttons() { return window.__pad.buttons.map(value => ({pressed: value > 0.5, touched: value > 0, value})); },
  get timestamp() { return performance.now(); },
};
Object.defineProperty(navigator, 'getGamepads', {value: () => [reviewPad, null, null, null], configurable: true});
"""


def shrink(path):
    """Re-encode an oversized capture with an ever smaller palette until it fits under LIMIT."""
    image = Image.open(path).convert('RGB')
    attempts = [(256, Image.Quantize.FASTOCTREE, Image.Dither.FLOYDSTEINBERG)]
    attempts += [(colors, Image.Quantize.FASTOCTREE, Image.Dither.NONE) for colors in (256, 192, 128, 96, 64)]
    for colors, method, dither in attempts:
        if path.stat().st_size <= LIMIT:
            return
        image.quantize(colors=colors, method=method, dither=dither).save(path, optimize=True)


def save(page, name, settle=1500):
    page.wait_for_timeout(settle)
    data = page.screenshot(timeout=timeout(120000))
    path = OUT / f'{name}.png'
    Image.open(io.BytesIO(data)).save(path, optimize=True)
    shrink(path)
    print(f'{name}.png {path.stat().st_size // 1024} KB', flush=True)


def press(page, button):
    page.evaluate('i => new Promise(resolve => { window.__pad.buttons[i] = 1; '
                  'requestAnimationFrame(() => { window.__pad.buttons[i] = 0; resolve(); }); })', button)
    page.wait_for_timeout(300)


def menu_page(browser, query=''):
    context = browser.new_context(viewport=VIEW, device_scale_factor=2)
    page = context.new_page()
    # Device scale 2 under software GL renders slowly; clicks wait for stable frames.
    page.set_default_timeout(timeout(120000))
    page.add_init_script(PAD)
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&quality=medium&room={ROOM}{query}')
    return page


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        # Loading: hold the catalogue back so the progress screen is visible.
        context = browser.new_context(viewport=VIEW, device_scale_factor=2)
        page = context.new_page()
        held = []

        def hold(route):
            held.append(route)

        page.route('**/menu_catalogue.json', hold)
        page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}', wait_until='commit')
        page.wait_for_function('getComputedStyle(document.querySelector("#menuLoading")).getPropertyValue("--progress")'
                               ' !== ""')
        save(page, '00-loading', settle=800)
        for route in held:
            route.continue_()
        context.close()

        page = menu_page(browser, '&mission=free_explore')
        wait_ready(page, timeout=timeout(120000))
        save(page, '01-title', settle=3000)
        press(page, 0)
        wait_screen(page, 'main')
        press(page, 13)
        save(page, '02-main-gamepad-focus')
        open_internal(page)
        page.click('#entry-dive')
        wait_screen(page, 'modes')
        save(page, '03-modes')
        page.click('[data-mode="free_explore"]')
        wait_screen(page, 'hangar')
        save(page, '04-hangar-x1-provisional', settle=2500)
        page.click('[data-vehicle="falcon"]')
        page.wait_for_function('window.__menu.ready && window.__menu.model === "falcon"', timeout=timeout(90000))
        page.click('[data-sticker="hazard"]')
        page.wait_for_function('window.__menu.stickerMeshes > 0')
        save(page, '05-hangar-falcon-sticker', settle=2500)
        page.click('#hangarNext')
        wait_screen(page, 'sites')
        page.hover('[data-site="jacket_inspection"]')
        page.wait_for_function('window.__menu.scene === "jacket_inspection"', timeout=timeout(60000))
        save(page, '06-sites', settle=3000)
        page.click('[data-site="jacket_inspection"]')
        wait_screen(page, 'briefing')
        save(page, '07-briefing', settle=2500)
        open_main(page)
        page.click('#entry-training')
        page.click('#training-tab-story')
        wait_screen(page, 'training')
        save(page, '08-training-story')
        page.click('#training-tab-drills')
        save(page, '09-training-drills')
        page.click('#training-tab-scenarios')
        save(page, '10-training-scenarios')
        open_main(page)
        page.click('#entry-settings')
        wait_screen(page, 'settings')
        for index, tab in enumerate(['fidelity', 'controls', 'audio', 'quality', 'interface']):
            page.click(f'#menuSettings-tab-{tab}')
            save(page, f'{11 + index}-settings-{tab}')
        open_internal(page)
        page.click('#menuCollection')
        page.wait_for_selector('dialog.collection-panel[open]')
        save(page, '16-collection')
        page.locator('.collection-close').click()

        # A teammate in the room so the multiplayer screen lists players.
        mate = browser.new_context(viewport={'width': 640, 'height': 360}).new_page()
        mate.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room={ROOM}&play=1&nointro&name=%E9%9A%8A%E5%8F%8BA'
                  '&model=bluerov2_heavy&quality=performance')
        mate.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(120000))
        open_internal(page)
        page.click('#entry-multiplayer')
        wait_screen(page, 'multiplayer')
        page.wait_for_selector('#mpPlayers li', timeout=timeout(30000))
        save(page, '17-multiplayer')
        mate.context.close()

        to_briefing(page, mode='free_explore', site='coral_reef', model='x1')
        set_intro(page, False)
        page.click('#startDive')
        page.wait_for_function('window.__viewer?.S?.vehicle_id && window.__modelLoaded', timeout=timeout(120000))
        page.wait_for_timeout(2000)
        page.keyboard.press('Escape')
        page.wait_for_selector('#pauseMenu:not([hidden])')
        save(page, '18-pause')
        page.click('#pauseSettings')
        save(page, '19-pause-settings')
        browser.close()


if __name__ == '__main__':
    run()
