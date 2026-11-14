import os
import time
"""Verify setup precedes connection, preview choices apply, and play stays clear."""
import json
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright
out=Path(__file__).resolve().parents[1]/'output'/'menu-validation';out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    executable = os.environ.get('ROV_BROWSER') or which('google-chrome') or which('chromium')
    browser = p.chromium.launch(
        executable_path=executable, headless=True, args=['--enable-unsafe-swiftshader']
    )
    page=browser.new_page(viewport={'width':1920,'height':1080})
    sockets=[];errors=[]
    page.on('websocket',lambda ws:sockets.append(ws.url))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&room=menucheck{int(time.time())}&model=falcon')
    page.wait_for_function('window.__menu?.ready')
    assert not sockets,sockets
    page.get_by_role('button',name='進入主選單').click()
    page.locator('.menu-screen:visible').get_by_role('button',name='開始潛航',exact=True).click()
    page.get_by_role('button',name='探索與工程',exact=False).click()
    page.screenshot(path=str(out/'desktop.png'))
    page.click('[data-vehicle="bluerov2_heavy"]')
    page.wait_for_function('window.__menu.ready && window.__menu.model==="bluerov2_heavy"')
    page.get_by_role('button',name='下一步').click()
    page.select_option('#menuScene','seagrass_meadow')
    page.wait_for_function('window.__menu.ready && window.__menu.scene==="seagrass_meadow"')
    page.screenshot(path=str(out/'seagrass.png'))
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    page.set_viewport_size({'width':1920,'height':1080})
    page.get_by_role('button',name='返回',exact=True).click()
    page.get_by_role('button',name='返回',exact=True).click()
    page.get_by_role('button',name='返回',exact=True).click()
    page.get_by_role('button',name='設定',exact=True).click()
    page.get_by_role('button',name='控制',exact=True).click()
    page.select_option('#menuPad','keyboard');page.get_by_role('button',name='介面',exact=True).click();page.uncheck('#menuIntro');page.get_by_role('button',name='控制',exact=True).click()
    page.select_option('#menuControl','UAV_CHN')
    page.get_by_role('button',name='返回',exact=True).click()
    page.get_by_role('button',name='快速開始',exact=True).click()
    print('LAUNCH',page.url,flush=True)
    page.wait_for_function('window.__viewer?.S', timeout=90000)
    print('STATE',page.evaluate('({scenario:window.__viewer?.W?.scenario,model:window.__viewer?.S?.model_id,mode:window.__viewer?.S?.operation_mode})'),flush=True)
    page.wait_for_function('window.__viewer?.W?.scenario?.key==="seagrass_meadow" && window.__viewer?.S?.model_id==="bluerov2_heavy" && window.__viewer?.S?.operation_mode==="UAV_CHN" && window.__modelLoaded')
    assert not page.locator('#launchMenu').count()
    for id in ['vehicleSelect','serverAddress','roomCode','opMode','scnSel','quality']:
        assert not page.locator('#'+id).is_visible(),id
    page.screenshot(path=str(out/'game.png'))
    page.click('#flightDrawer')
    page.click('#returnMenu');page.wait_for_function('window.__menu?.ready')
    assert 'play=' not in page.url
    assert not errors,errors
    (out/'results.json').write_text(json.dumps({'no_connection_before_start':True,'model_and_scene_applied':True,'controller_applied':True,'setup_hidden_in_game':True,'return_menu':True,'errors':errors},indent=2),encoding='utf8')
    browser.close()
print('Menu flow passed:',out)
