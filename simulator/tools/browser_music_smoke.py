"""Background music: nothing plays before the first gesture (autoplay policy), the title music starts after it and
the briefing screens switch track; in the water, `real` keeps the dive silent while `assisted` plays dive music.
"""
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, timeout, ws_base
from _menu import open_main, wait_ready, wait_screen

DEBUG = "import('./audio/music.js').then(m => m.installMusic().debug())"
PLAYING = """track => import('./audio/music.js').then(m => m.installMusic().debug().players.some(
  p => p.id.startsWith(track) && !p.paused && p.time > 0.3))"""
SILENT = """() => import('./audio/music.js').then(m => m.installMusic().debug().players.every(p => p.paused))"""
ENGINE_RUNNING = "import('./audio/engine.js').then(m => m.installAudio().ctx?.state === 'running')"


def game_url(fidelity):
    return f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&room=music-{fidelity}&fidelity={fidelity}'


def check_menu(page):
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=musiccheck')
    wait_ready(page)
    page.wait_for_timeout(timeout(800))
    before = page.evaluate(DEBUG)
    assert before['requested'] == 'title', before
    assert before['players'] == [], f'music must not load or play before a gesture: {before}'
    open_main(page)
    page.wait_for_function(ENGINE_RUNNING, timeout=timeout(15000))
    page.wait_for_function(PLAYING, arg='title_', timeout=timeout(20000))
    page.evaluate('window.__menu.go("hangar")')
    wait_screen(page, 'hangar')
    page.wait_for_function(PLAYING, arg='briefing_', timeout=timeout(20000))
    return page.evaluate(DEBUG)


def check_dive(page, fidelity):
    page.goto(game_url(fidelity))
    page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=timeout(60000))
    page.locator('canvas.gl').click(position={'x': 20, 'y': 20})
    page.wait_for_function(ENGINE_RUNNING, timeout=timeout(15000))
    page.wait_for_function("import('./audio/music.js').then(m => !!m.installMusic().debug().requested)",
                           timeout=timeout(15000))
    if fidelity == 'real':
        page.wait_for_timeout(timeout(3000))
        state = page.evaluate(DEBUG)
        assert state['requested'] in ('dive', 'tension'), state
        assert not state['allowed'], state
        assert page.evaluate(f'({SILENT})()'), f'in-dive music must stay silent in real: {state}'
        return state
    page.wait_for_function(PLAYING, arg='', timeout=timeout(20000))
    state = page.evaluate(DEBUG)
    assert state['allowed'], state
    return state


with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader', '--autoplay-policy=user-gesture-required'])
    errors = []
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    page.on('pageerror', lambda error: errors.append(str(error)))
    menu = check_menu(page)
    real = check_dive(page, 'real')
    assisted = check_dive(page, 'assisted')
    assert not errors, errors
    browser.close()
    print(f'Music smoke passed: menu after gesture {menu["context"]}, real dive silent ({real["requested"]}), '
          f'assisted dive plays {[p["id"] for p in assisted["players"] if not p["paused"]]}')
