"""Verify merged campaign, controller, audio and pause contracts through the frontend."""
import json
import os
import time
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'output/menu-integrations'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get('ROV_BROWSER') or which('google-chrome') or which('chromium'),
        headless=True, args=['--enable-unsafe-swiftshader'])
    context = browser.new_context(viewport={'width': 1600, 'height': 900})
    page = context.new_page()
    errors = []
    packets = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('websocket', lambda socket: socket.on('framesent', lambda raw: packets.append(json.loads(raw))))
    room = f't06-{time.time_ns()}'
    page.goto(f'http://127.0.0.1:8092/?room={room}&ws=ws://127.0.0.1:8792')
    page.wait_for_function('window.__menu?.ready', timeout=90000)
    assert page.locator('#menuMode').input_value() == 'campaign'
    assert not page.locator('#menuIntro').is_checked()
    assert not page.locator('#menuLabels').is_checked()
    page.get_by_role('button', name='進入主選單', exact=True).click()
    page.get_by_role('button', name='圖鑑與收藏', exact=True).click()
    page.wait_for_selector('dialog[open]')
    page.evaluate("""() => {
      window.collectionPad = {id:'045e:028e',index:0,connected:true,mapping:'standard',axes:[0,0,0,0],
        buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
      Object.defineProperty(navigator,'getGamepads',{configurable:true,value:()=>[collectionPad]});
      collectionPad.buttons[1] = {pressed:true,value:1};
    }""")
    page.wait_for_function('!document.querySelector("dialog[open]")')
    page.evaluate('collectionPad.buttons[1]={pressed:false,value:0}')
    page.get_by_role('button', name='圖鑑與收藏', exact=True).click()
    assert page.locator('dialog[open]').is_visible()
    page.keyboard.press('Escape')
    page.get_by_role('button', name='設定', exact=True).click()
    page.get_by_role('button', name='控制', exact=True).click()
    page.locator('#inputSettingsButton').focus()
    page.evaluate('collectionPad.buttons[0]={pressed:true,value:1}')
    page.wait_for_selector('#inputSettings[open]')
    page.wait_for_timeout(300)
    assert page.locator('#inputSettings').is_visible()
    page.evaluate('collectionPad.buttons[0]={pressed:false,value:0}')
    assert page.locator('#inputSettings').is_visible()
    page.locator('#inputSettings input[type=range]').first.focus()
    page.keyboard.press('ArrowRight')
    assert page.evaluate('JSON.parse(localStorage.getItem("rov.input.v1")).inner') > 0.08
    page.screenshot(path=str(OUT / 'controls.png'))
    page.evaluate('collectionPad.buttons[1]={pressed:true,value:1}')
    page.wait_for_function('!document.querySelector("#inputSettings").open')
    page.wait_for_timeout(300)
    assert page.locator('#launchMenu').get_attribute('data-screen') == 'settings'
    page.evaluate('collectionPad.buttons[1]={pressed:false,value:0}')
    page.get_by_role('button', name='音訊', exact=True).click()
    audio = page.locator('[data-mount=audio]')
    assert audio.locator('input[type=range]').count() == 5
    audio.locator('input[type=checkbox]').check()
    assert page.evaluate('JSON.parse(localStorage.getItem("rov.audio")).mute')
    page.screenshot(path=str(OUT / 'audio.png'))
    page.get_by_role('button', name='返回', exact=True).click()
    page.get_by_role('button', name='開始潛航', exact=True).click()
    assert 'undefined' not in page.locator('.menu-cards').first.inner_text()
    assert page.get_by_role('button', name='潮間帶工作隊', exact=False).count() == 1
    page.screenshot(path=str(OUT / 'modes.png'))
    page.get_by_role('button', name='自由探索 ·', exact=False).click()
    assert page.locator('.vehicle-specs meter').count() == 0
    assert '暫定參數' in page.locator('.vehicle-specs').inner_text()
    page.screenshot(path=str(OUT / 'vehicle.png'))
    page.get_by_role('button', name='下一步', exact=True).click()
    page.get_by_role('button', name='下一步', exact=True).click()
    page.click('#startDive')
    page.wait_for_function('window.__viewer?.S && window.__modelLoaded', timeout=90000)
    assert 'cam=onboard' in page.url
    page.keyboard.press('Escape')
    page.wait_for_function('window.__viewer.S.paused')
    page.evaluate("""() => {
      window.testMenuPad = {id:'045e:028e',index:0,connected:true,mapping:'standard',axes:[0,0,0,0],
        buttons:Array.from({length:17},()=>({pressed:false,value:0}))};
      Object.defineProperty(navigator,'getGamepads',{value:()=>[testMenuPad]});
      testMenuPad.buttons[1] = {pressed:true,value:1};
    }""")
    page.wait_for_function('!document.querySelector(".pause-menu").open')
    page.wait_for_function('!window.__viewer.S.paused')
    assert page.evaluate('window.__viewer.S.rc.record') == 0
    page.evaluate('testMenuPad.buttons[1]={pressed:false,value:0}')
    guest = context.new_page()
    guest.goto(f'http://127.0.0.1:8092/?play=1&nointro&room={room}&ws=ws://127.0.0.1:8792')
    guest.wait_for_function('window.__viewer?.S?.vehicles.length===2', timeout=90000)
    page.bring_to_front()
    page.wait_for_function('window.__viewer.S.vehicles.length===2')
    page.keyboard.down('w')
    page.wait_for_function('window.__viewer.S.rc.left_ud>1500')
    page.keyboard.press('Escape')
    assert page.locator('.pause-menu').is_visible()
    page.keyboard.up('w')
    page.wait_for_function('window.__viewer.S.rc.left_ud===1500 && window.__viewer.S.locked')
    assert not page.evaluate('window.__viewer.S.paused')
    page.keyboard.down('w')
    page.wait_for_timeout(200)
    assert page.evaluate('window.__viewer.S.rc.left_ud') == 1500
    page.keyboard.up('w')
    page.screenshot(path=str(OUT / 'pause.png'))
    assert any(packet.get('type') == 'rc' and packet['rc'].get('rc_lock') == 1
               and packet['rc'].get('left_ud') == 1500 for packet in packets)
    page.get_by_role('button', name='繼續', exact=True).click()
    assert not page.locator('.pause-menu').is_visible()
    assert not errors, errors
    browser.close()
print('PASS: campaign entry, T02 settings, T05 audio, simulation labels, FPV default, multiplayer neutral pause')
