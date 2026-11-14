"""Exercise model persistence and validated server/room navigation via the staged frontend."""
import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('ROV_BROWSER', '/opt/google/chrome/chrome'),
                                headless=True, args=['--enable-unsafe-swiftshader'])
    context = browser.new_context(viewport={'width':1280,'height':800})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&nointro&room=preference_check&model=falcon')
    page.wait_for_function('window.__menu?.ready')
    page.get_by_role('button', name='進入主選單').click()
    page.get_by_role('button', name='開始潛航', exact=True).click()
    page.get_by_role('button', name='探索與工程 ·', exact=False).click()
    page.click('[data-vehicle="bluerov2_heavy"]')
    page.wait_for_function('window.__menu.ready && window.__menu.model==="bluerov2_heavy"')
    for _ in range(2):
        page.get_by_role('button', name='下一步', exact=True).click()
    page.click('#startDive')
    page.wait_for_function('window.__viewer?.S?.model_id==="bluerov2_heavy"')
    assert page.evaluate('localStorage.getItem("rov.vehicle")') == 'bluerov2_heavy'
    assert 'model=bluerov2_heavy' in page.url
    page.click('#returnMenu')
    page.wait_for_function('window.__menu?.ready')
    page.get_by_role('button', name='進入主選單').click()
    page.get_by_role('button', name='多人連線').click()
    page.fill('#menuServer', 'ftp://invalid.example')
    page.fill('#menuRoom', 'connection_check')
    page.get_by_role('button', name='返回', exact=True).click()
    prior = page.url
    page.get_by_role('button', name='快速開始').click()
    assert page.url == prior
    assert '有效' in page.locator('#menuStatus').inner_text()
    page.get_by_role('button', name='多人連線').click()
    page.fill('#menuServer', 'ws://localhost:8792')
    page.get_by_role('button', name='返回', exact=True).click()
    page.get_by_role('button', name='快速開始').click()
    page.wait_for_function('window.__viewer?.S?.room?.id==="connection_check"')
    assert page.evaluate('window.__viewer.S.model_id') == 'bluerov2_heavy'
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&play=1&nointro&room=preference_next')
    page.wait_for_function('window.__viewer?.S?.model_id==="bluerov2_heavy"')
    assert not errors, errors
    browser.close()
print('Connection flow passed')
