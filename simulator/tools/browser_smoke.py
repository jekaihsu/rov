"""Real-browser smoke checks against a separately running simulator."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'upgrade-validation'
OUT.mkdir(parents=True, exist_ok=True)

def run():
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True, args=['--enable-unsafe-swiftshader'])
        contexts=[]
        pages=[]
        for i in range(3):
            print('Connecting browser',i+1,flush=True)
            context=browser.new_context(viewport={'width':960,'height':720})
            page=context.new_page();contexts.append(context);pages.append(page)
            page.on('pageerror',lambda error: (errors.append(str(error)),print('PAGE ERROR',error,flush=True)))
            page.on('requestfailed',lambda request: print('REQUEST FAILED',request.url,request.failure,flush=True))
            page.on('console',lambda msg: print('CONSOLE',msg.text,flush=True) if msg.type=='error' else None)
            page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&play=1&model=falcon&nointro&room=browsercheck',wait_until='domcontentloaded',timeout=90000)
            try:page.wait_for_function('window.__viewer?.S?.vehicle_id',timeout=60000)
            except Exception:
                print('DIAGNOSTICS',page.evaluate('({title:document.title,ready:!!window.__viewer,state:window.__viewer?.S,notice:document.querySelector("#operationNotice")?.textContent,connection:document.querySelector("#conn")?.textContent})'),flush=True)
                page.screenshot(path=str(OUT/f'failed-{i}.png'))
                raise
        main=pages[0]
        main.wait_for_function('window.__viewer.S.vehicles.length===3')
        assert main.locator('#pip').is_hidden()
        main.evaluate("const option=document.querySelector('#optPip');option.checked=true;option.dispatchEvent(new Event('change'))")
        main.wait_for_function('document.querySelector(".pilot-pip-canvas")',timeout=60000)
        main.locator('#closePip').click()
        assert main.locator('#pip').is_hidden()
        assert main.evaluate('localStorage.getItem("rov.operatorVisible")')=='false'
        # Vehicle is selected before entering the game via the launch URL.
        main.wait_for_function('window.__viewer.S.model_id==="falcon"')
        main.wait_for_timeout(1000)
        assert main.locator('#armPanel').is_visible()
        main.locator('#armPanel summary').click()
        main.click('#gripClose')
        main.wait_for_function('window.__viewer.S.operations.arm.grip<.5')
        main.evaluate('window.__viewer.setCam("onboard");window.__viewer.rc.right_switch=2')
        main.wait_for_function('window.__viewer.S.rc.right_switch===2')
        lights=main.evaluate('window.__viewer.rovG.children.filter(g=>g.children.some(o=>o.isSpotLight)).map(g=>({visible:g.visible,intensity:g.children.filter(o=>o.isSpotLight).map(l=>l.intensity)}))')
        assert any(x['visible'] and max(x['intensity'])>0 for x in lights),lights
        main.screenshot(path=str(OUT/'onboard-lights.png'))
        main.evaluate('window.__viewer.setCam("orbit")')
        main.screenshot(path=str(OUT/'fleet-cockpit.png'))
        identities=[page.evaluate('window.__viewer.S.vehicle_id') for page in pages]
        assert len(set(identities))==3,identities
        assert not errors,errors
        (OUT/'browser-results.json').write_text(json.dumps({'players':identities,'errors':errors,'lights':lights,'status':'passed'},ensure_ascii=False,indent=2),encoding='utf8')
        browser.close()
    print('Browser smoke passed:',OUT)

if __name__=='__main__':run()
