"""Capture every launch step and a standard-gamepad-only path into the water."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / 'docs/review/T06'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('ROV_BROWSER', '/opt/google/chrome/chrome'),
                                args=['--enable-unsafe-swiftshader'])
    context = browser.new_context(viewport={'width':1600,'height':900}, record_video_dir=str(OUT / 'video'))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""window.testButtons=Array.from({length:17},()=>({pressed:false,value:0}));
    window.padReads=0; navigator.getGamepads=()=>{window.padReads++;return [{connected:true,index:0,id:'Standard Gamepad',mapping:'standard',axes:[0,0,0,0],buttons:testButtons}];};""")
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&room=t06screens&nointro')
    page.wait_for_function('window.__menu?.ready')
    def shot(name):
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / f'{name}.png'))
    def press(index):
        page.evaluate('(i)=>testButtons[i]={pressed:true,value:1}', index)
        page.wait_for_function('(prior)=>padReads>prior+2',arg=page.evaluate('padReads'))
        page.evaluate('(i)=>testButtons[i]={pressed:false,value:0}', index)
        page.wait_for_function('(prior)=>padReads>prior+2',arg=page.evaluate('padReads'))
    def focus_button(text):
        for _ in range(60):
            if page.evaluate('(text)=>document.activeElement?.textContent===text', text):
                return
            press(13)
        raise AssertionError(f'Gamepad cannot reach {text}')
    shot('01-title')
    press(0)
    shot('02-home')
    press(0)
    shot('03-mode')
    focus_button('探索與工程 · 1–3 人 — 自由接案、探索生態與工程作業。')
    press(0)
    shot('04-vehicle')
    focus_button('下一步')
    press(0)
    shot('05-sea')
    focus_button('下一步')
    press(0)
    shot('06-brief')
    # Return through the same stack using only B.
    for _ in range(4):
        press(1)
    focus_button('多人連線')
    press(0)
    shot('07-multiplayer')
    press(1)
    focus_button('設定')
    press(0)
    for index, tab in enumerate(['quality','controls','audio','interface','language']):
        shot('08-settings-' + tab)
        press(5)
    press(1)
    focus_button('圖鑑與收藏')
    press(0)
    shot('09-collection')
    press(1)
    focus_button('快速開始')
    press(0)
    page.wait_for_function('window.__viewer?.S && window.__modelLoaded', timeout=90000)
    shot('10-water')
    press(9)
    page.wait_for_selector('.pause-menu[open]')
    shot('11-pause')
    assert not errors, errors
    context.close()
    browser.close()
print('Screenshots and controller recording:', OUT)
