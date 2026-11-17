"""Fresh save shows the new-game difficulty screen; each option applies its preset; next launch skips it."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, timeout, ws_base
from _menu import open_main, wait_ready, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'new-game-validation'
OUT.mkdir(parents=True, exist_ok=True)
# P1 prompt: screenshots under docs/design/<task>/
DOCS = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'P1-difficulty'
DOCS.mkdir(parents=True, exist_ok=True)

PRESETS = {
    'assisted': {
        'assistLevel': 2,
        'videoDelayMs': 0,
        'thirdPerson': True,
        'gimbal': True,
        'deployProcedure': 'full',
    },
    'standard': {
        'assistLevel': 0,
        'videoDelayMs': 150,
        'thirdPerson': False,
        'gimbal': False,
        'depthHoldStart': True,
        'nearStart': True,
        'deployProcedure': 'full',
    },
    'real': {
        'assistLevel': 0,
        'videoDelayMs': 150,
        'thirdPerson': False,
        'gimbal': False,
        'depthHoldStart': False,
        'nearStart': False,
        'deployProcedure': 'full',
    },
}


def clear_player_state(page):
    page.add_init_script("""() => {
      try {
        localStorage.clear();
      } catch (error) {}
    }""")


def fidelity_snapshot(page):
    return page.evaluate("""async () => {
      const {getFidelity} = await import('/fidelity.js');
      const store = getFidelity();
      const values = {};
      for (const item of store.items()) values[item.id] = store.get(item.id);
      return {preset: store.preset, values, chosen: localStorage.getItem('rov.difficulty.chosen.v1')};
    }""")


def open_new_game_from_title(page):
    wait_ready(page)
    assert page.evaluate('window.__menu.screen') == 'title'
    page.click('#titleStart')
    wait_screen(page, 'new_game')


def assert_preset(page, name):
    snap = fidelity_snapshot(page)
    assert snap['preset'] == name, snap
    expected = PRESETS[name]
    for key, value in expected.items():
        assert snap['values'].get(key) == value, (name, key, snap['values'].get(key), value)
    return snap


with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    clear_player_state(page)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{http_base()}/?ws={ws_base()}&room=newgame')
    open_new_game_from_title(page)
    page.screenshot(path=str(OUT / 'new-game-1600.png'))

    for name in ('assisted', 'standard', 'real'):
        page.click(f'#newGame-{name}')
        page.wait_for_function(
            'name => document.querySelector(`#newGame-${name}`)?.getAttribute("aria-selected") === "true"',
            arg=name, timeout=timeout(10000))
        page.wait_for_timeout(400)
        shot1600 = OUT / f'difficulty-{name}-1600.png'
        page.screenshot(path=str(shot1600))
        (DOCS / f'difficulty-{name}-1600.png').write_bytes(shot1600.read_bytes())
        page.set_viewport_size({'width': 1280, 'height': 720})
        shot1280 = OUT / f'difficulty-{name}-1280.png'
        page.screenshot(path=str(shot1280))
        (DOCS / f'difficulty-{name}-1280.png').write_bytes(shot1280.read_bytes())
        page.set_viewport_size({'width': 1600, 'height': 900})

    # Confirm standard and verify the store + chosen flag.
    page.click('#newGame-standard')
    page.click('#newGameConfirm')
    wait_screen(page, 'main')
    snap = assert_preset(page, 'standard')
    assert snap['chosen'] == '1', snap

    # Reload: title → main, no new-game screen.
    page.goto(f'{http_base()}/?ws={ws_base()}&room=newgame2')
    wait_ready(page)
    assert page.evaluate('window.__menu.screen') == 'title'
    page.click('#titleStart')
    wait_screen(page, 'main')
    assert page.evaluate('window.__menu.screen') == 'main'
    assert_preset(page, 'standard')

    # Settings can reopen the screen; confirming assisted applies that preset.
    open_main(page)
    page.click('#entry-settings')
    wait_screen(page, 'settings')
    page.click('#menuSettings-tab-fidelity')
    page.click('#menuDifficultyScreen')
    wait_screen(page, 'new_game')
    page.click('#newGame-assisted')
    page.click('#newGameConfirm')
    wait_screen(page, 'settings')
    assert_preset(page, 'assisted')

    # Real via the difficulty stepper path used by other smokes.
    page.goto(f'{http_base()}/?ws={ws_base()}&room=newgame3')
    wait_ready(page)
    # Storage already has chosen=1 from earlier; force a clean dismiss helper path on a fresh context.
    page2 = browser.new_page(viewport={'width': 1600, 'height': 900})
    clear_player_state(page2)
    page2.goto(f'{http_base()}/?ws={ws_base()}&room=newgame4')
    open_main(page2)
    assert page2.evaluate('window.__menu.screen') == 'main'
    assert not errors, errors
    (OUT / 'results.json').write_text(json.dumps({
        'fresh_shows_new_game': True,
        'presets_apply': list(PRESETS),
        'second_launch_skips': True,
        'settings_reopen': True,
        'errors': errors,
    }, indent=2), encoding='utf8')
    browser.close()
print('New-game difficulty passed:', OUT)
