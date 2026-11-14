"""Injected standard, database and unknown controller paths plus setup screenshots."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'output/t02'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    page.set_default_timeout(90000)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script("""window.fakePads=[];
      Object.defineProperty(navigator,'getGamepads',{value:()=>window.fakePads});""")
    page.goto('http://127.0.0.1:8080/?play=1&nointro')
    page.wait_for_function('window.__viewer?.S?.vehicle_id')
    page.screenshot(path=str(OUT / 'after.png'))
    result = page.evaluate("""async () => {
      const {normalize}=await import('/input/devices.js');
      const db=await (await fetch('/input/controller-db.json')).json();
      const pad={id:'generic',mapping:'standard',index:0,connected:true,
        axes:[.5,0,0,0],buttons:Array.from({length:17},()=>({value:0,pressed:false}))};
      window.fakePads=[pad];
      const standard=normalize(pad,db);
      const key=Object.keys(db)[0];
      const known=normalize({...pad,mapping:'',id:key},db);
      const unknown=normalize({...pad,mapping:'',id:'HOTAS unknown',axes:Array(20).fill(0)},db);
      return {standard:standard.known,known:known.known,unknown:unknown.known};
    }""")
    assert result == {'standard': True, 'known': True, 'unknown': False}, result
    print('Mapping paths passed', flush=True)
    page.click('#inputSettingsButton')
    page.wait_for_timeout(200)
    page.screenshot(path=str(OUT / 'settings.png'))
    page.evaluate("window.fakePads[0].mapping='';window.fakePads[0].id='HOTAS unknown';window.fakePads[0].axes=Array(20).fill(0)")
    page.get_by_text('對應精靈', exact=True).click()
    page.wait_for_timeout(100)
    assert 'leftx' in page.locator('#inputSettings').inner_text()
    print('Wizard started', flush=True)
    # Push each requested axis in its positive direction and release.
    for i in range(4):
        print("axis", i, flush=True)
        page.evaluate('(i)=>{window.fakePads[0].axes[i]=1}', i)
        page.wait_for_function('(n)=>+document.querySelector("#inputSettings p").dataset.step>n', arg=i)
        page.evaluate('(i)=>{window.fakePads[0].axes[i]=0}', i)
        page.wait_for_function('document.querySelector("#inputSettings p").dataset.ready==="true"')
    for i in range(17):
        print("button", i, flush=True)
        page.evaluate('(i)=>{window.fakePads[0].buttons[i]={value:1,pressed:true}}', i)
        page.wait_for_function('(n)=>+document.querySelector("#inputSettings p").dataset.step>n+4', arg=i)
        page.evaluate('(i)=>{window.fakePads[0].buttons[i]={value:0,pressed:false}}', i)
        if i < 16:
            page.wait_for_function('document.querySelector("#inputSettings p").dataset.ready==="true"')
    assert page.evaluate("JSON.parse(localStorage.getItem('rov.input.v1')).custom['HOTAS unknown'].buttons.length") == 17
    assert not errors, errors
    page.goto('http://127.0.0.1:8093/?play=1&nointro&ws=ws://127.0.0.1:8793')
    page.wait_for_function('window.__viewer?.S?.vehicle_id')
    page.screenshot(path=str(OUT / 'before.png'))
    browser.close()
print('Input smoke passed:', json.dumps(result), '; wizard stored 4 axes and 17 buttons; no page errors')
