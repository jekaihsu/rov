"""Exercise model preference and server/room navigation through the UI."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    context=browser.new_context(viewport={'width':1280,'height':800})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&nointro&room=preference_check&model=falcon')
    page.wait_for_function('window.__viewer?.S?.model_id==="falcon"')
    page.select_option('#vehicleSelect','bluerov2_heavy')
    page.click('#changeVehicle')
    page.wait_for_function('window.__viewer.S.model_id==="bluerov2_heavy"')
    assert page.evaluate('localStorage.getItem("rov.vehicle")')=='bluerov2_heavy'
    assert 'model=bluerov2_heavy' in page.url
    prior=page.url
    page.fill('#serverAddress','ftp://invalid.example')
    page.click('#joinRoom')
    assert page.url==prior
    assert '有效' in page.locator('#operationNotice').inner_text()
    page.fill('#serverAddress','ws://localhost:8792')
    page.fill('#roomCode','connection_check')
    page.click('#joinRoom')
    page.wait_for_function('window.__viewer?.S?.room?.id==="connection_check"')
    assert page.evaluate('window.__viewer.S.model_id')=='bluerov2_heavy'
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&nointro&room=preference_next')
    page.wait_for_function('window.__viewer?.S?.model_id==="bluerov2_heavy"')
    assert not errors,errors
    browser.close()
print('Server address, room navigation, query selection, and model persistence passed.')
