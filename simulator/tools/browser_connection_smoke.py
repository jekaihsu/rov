"""Exercise model preference and server/room navigation through the UI."""
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base, ws_port

with sync_playwright() as p:
    browser=launch(p, headless=True,args=['--enable-unsafe-swiftshader'])
    context=browser.new_context(viewport={'width':1280,'height':800})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&room=preference_check&model=falcon')
    page.wait_for_function('window.__viewer?.S?.model_id==="falcon"')
    page.click('#flightDrawer')
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
    page.fill('#serverAddress',f'ws://localhost:{ws_port(8792)}')
    page.fill('#roomCode','connection_check')
    page.click('#joinRoom')
    page.wait_for_function('window.__viewer?.S?.room?.id==="connection_check"')
    assert page.evaluate('window.__viewer.S.model_id')=='bluerov2_heavy'
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&room=preference_next')
    page.wait_for_function('window.__viewer?.S?.model_id==="bluerov2_heavy"')
    assert not errors,errors
    browser.close()
print('Server address, room navigation, query selection, and model persistence passed.')
