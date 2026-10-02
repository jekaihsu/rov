"""Verify setup precedes connection, preview choices apply, and play stays clear."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).resolve().parents[1]/'output'/'menu-validation';out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1920,'height':1080})
    sockets=[];errors=[]
    page.on('websocket',lambda ws:sockets.append(ws.url))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&room=menucheck&model=falcon')
    page.wait_for_function('window.__menu?.ready')
    assert not sockets,sockets
    page.screenshot(path=str(out/'desktop.png'))
    page.click('[data-vehicle="bluerov2_heavy"]')
    page.wait_for_function('window.__menu.ready && window.__menu.model==="bluerov2_heavy"')
    page.select_option('#menuScene','seagrass_meadow')
    page.wait_for_function('window.__menu.ready && window.__menu.scene==="seagrass_meadow"')
    page.screenshot(path=str(out/'seagrass.png'))
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    page.set_viewport_size({'width':1920,'height':1080})
    page.locator('details').filter(has=page.locator('#menuPad')).locator('summary').click()
    page.select_option('#menuPad','keyboard');page.uncheck('#menuIntro')
    page.select_option('#menuControl','UAV_CHN')
    page.click('#startDive')
    page.wait_for_function('window.__viewer?.W?.scenario?.key==="seagrass_meadow" && window.__viewer?.S?.model_id==="bluerov2_heavy" && window.__viewer?.S?.operation_mode==="UAV_CHN" && window.__modelLoaded')
    assert not page.locator('#launchMenu').count()
    for id in ['vehicleSelect','serverAddress','roomCode','opMode','scnSel','quality']:
        assert not page.locator('#'+id).is_visible(),id
    page.screenshot(path=str(out/'game.png'))
    page.click('#returnMenu');page.wait_for_function('window.__menu?.ready')
    assert 'play=' not in page.url
    assert not errors,errors
    (out/'results.json').write_text(json.dumps({'no_connection_before_start':True,'model_and_scene_applied':True,'controller_applied':True,'setup_hidden_in_game':True,'return_menu':True,'errors':errors},indent=2),encoding='utf8')
    browser.close()
print('Menu flow passed:',out)
