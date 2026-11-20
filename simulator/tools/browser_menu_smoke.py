"""Verify setup precedes connection, preview choices apply, play stays clear, and the pause menu works.

Walks the launch menu with real clicks: settings (input device, control layout) → 開始潛航 → mode → hangar
(vehicle) → dive site → briefing → launch; then opens and closes the in-game pause menu and returns to the menu.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, timeout, ws_base
from _menu import open_internal, open_settings_tab, set_intro, to_briefing, wait_ready, wait_screen

out = Path(__file__).resolve().parents[1] / 'output' / 'menu-validation'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    sockets = []
    errors = []
    page.on('websocket', lambda ws: sockets.append(ws.url))
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=menucheck&model=falcon')
    wait_ready(page)
    assert page.evaluate('window.__menu.screen') == 'title'
    assert page.evaluate('window.__menu.model') == 'falcon', 'model= preselects the hangar'
    page.screenshot(path=str(out / 'desktop.png'))
    open_settings_tab(page, 'controls')
    page.select_option('#menuPad', 'keyboard')
    page.select_option('#menuControl', 'UAV_CHN')
    page.keyboard.press('Escape')
    wait_screen(page, 'main')
    to_briefing(page, mode='free_explore', site='seagrass_meadow', model='bluerov2_heavy')
    page.wait_for_function('window.__menu.ready && window.__menu.scene==="seagrass_meadow"', timeout=timeout(60000))
    assert not sockets, sockets
    kicker = page.locator('.menu-briefing-main .menu-kicker').text_content()
    assert 'YX Model O · Block 1' in kicker and 'BlueROV' not in kicker, kicker
    page.screenshot(path=str(out / 'seagrass.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(out / 'mobile.png'), full_page=True)
    page.set_viewport_size({'width': 1920, 'height': 1080})
    set_intro(page, False)
    page.click('#startDive')
    page.wait_for_function('window.__viewer?.W?.scenario?.key==="seagrass_meadow" && '
                           'window.__viewer?.S?.model_id==="bluerov2_heavy" && '
                           'window.__viewer?.S?.operation_mode==="UAV_CHN" && window.__modelLoaded',
                           timeout=timeout(90000))
    assert not page.locator('#launchMenu').count()
    for id in ['vehicleSelect', 'serverAddress', 'roomCode', 'opMode', 'scnSel', 'quality']:
        assert not page.locator('#' + id).is_visible(), id
    page.screenshot(path=str(out / 'game.png'))
    # Pause menu: Esc opens it; a solo host also pauses the simulation, and closing resumes it.
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseMenu:not([hidden])')
    page.wait_for_function('window.__viewer.S.paused === true', timeout=timeout(30000))
    page.screenshot(path=str(out / 'pause.png'))
    page.click('#pauseSettings')
    page.wait_for_selector('#pauseSettings-tab-fidelity')
    page.keyboard.press('Escape')
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseMenu', state='hidden')
    page.wait_for_function('window.__viewer.S.paused === false', timeout=timeout(30000))
    page.click('#flightDrawer')
    page.click('#returnMenu')
    wait_ready(page)
    assert 'play=' not in page.url
    open_internal(page)
    assert page.locator('#quickStart').is_enabled(), 'a launched dive enables 快速開始'
    assert not errors, errors
    (out / 'results.json').write_text(json.dumps({
        'no_connection_before_start': True, 'model_and_scene_applied': True, 'controller_applied': True,
        'setup_hidden_in_game': True, 'pause_menu_pauses_solo': True, 'return_menu': True,
        'quick_start_enabled': True, 'errors': errors}, indent=2), encoding='utf8')
    browser.close()
print('Menu flow passed:', out)
