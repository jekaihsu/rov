"""Check camera actions through the live T02 layer, including context and thrust ownership."""
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""window.fakePads=[];
      Object.defineProperty(navigator,'getGamepads',{value:()=>window.fakePads});""")
    page.goto('http://127.0.0.1:8092/?play=1&nointro&ws=ws://127.0.0.1:8792&room=camera-actions&thirdPerson=1')
    page.wait_for_function('window.__viewer?.S?.vehicle_id')
    # Isolate action routing from software GPU stalls; this is not a latency benchmark.
    page.evaluate('window.__skipRender=true')
    page.wait_for_timeout(1000)
    page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyV',bubbles:true}))")
    page.wait_for_function('document.querySelector("#camBtn").textContent.includes("追蹤")')
    page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyV',bubbles:true}))")
    page.wait_for_function('document.querySelector("#camBtn").textContent.includes("環繞")')
    page.wait_for_timeout(500)
    angle = page.evaluate('''() => {
      const v=window.__viewer;
      return Math.atan2(v.camera.position.x-v.rovG.position.x,v.camera.position.z-v.rovG.position.z);
    }''')
    page.evaluate('''window.fakePads=[{id:'generic',mapping:'standard',index:0,connected:true,
      axes:[0,0,.7,0],buttons:Array.from({length:17},()=>({value:0,pressed:false}))}];''')
    page.wait_for_function('''before => {
      const v=window.__viewer;
      const angle=Math.atan2(v.camera.position.x-v.rovG.position.x,v.camera.position.z-v.rovG.position.z);
      return Math.abs(Math.atan2(Math.sin(angle-before),Math.cos(angle-before)))>.1;
    }''', arg=angle)
    assert page.evaluate('window.__viewer.S.rc.right_lr===1500')
    page.evaluate('window.__viewer.setCam("onboard")')
    page.wait_for_function('window.__viewer.S.rc.right_lr>1500')
    for action in ['cameraGimbal', 'cameraPitchUp', 'cameraPitchDown', 'cameraOrbitX', 'cameraOrbitY']:
        assert page.locator(f'#inputSettings [data-binding="{action}"]').count() == 1
    profile = page.evaluate('window.__viewer.rc.profile')
    page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyB',bubbles:true}))")
    assert page.evaluate('window.__viewer.rc.profile') == profile
    page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyG',bubbles:true}))")
    assert page.evaluate('window.__viewer.rc.profile') != profile
    page.evaluate('document.querySelector("#inputSettings").showModal()')
    profile = page.evaluate('window.__viewer.rc.profile')
    page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyG',bubbles:true}))")
    assert page.evaluate('window.__viewer.rc.profile') == profile
    page.evaluate("""() => {
      const binding=document.querySelector('[data-binding="cameraGimbal"]');
      binding.value='b17';
      binding.dispatchEvent(new Event('change'));
    }""")
    assert page.evaluate("JSON.parse(localStorage.getItem('rov.input.v1')).bindings.cameraGimbal") == 'b17'
    page.evaluate("""() => {
      const binding=document.querySelector('[data-binding="cameraGimbal"]');
      binding.value='';
      binding.dispatchEvent(new Event('change'));
    }""")
    assert page.evaluate("JSON.parse(localStorage.getItem('rov.input.v1')).bindings.cameraGimbal") == ''
    page.locator('#inputSettings select').nth(1).select_option('drone')
    assert page.locator('[data-binding="cameraOrbitX"]').input_value() == 'a2'
    assert page.locator('[data-binding="cameraGimbal"]').count() == 1
    assert not errors, errors
    browser.close()
print('Live V cycle, orbit pad ownership, B/G separation and settings focus guards passed.')
