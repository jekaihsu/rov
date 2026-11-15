"""Real-browser smoke checks against a separately running simulator.

Three software-rendered viewers share one CPU here, so each can drop to about one frame per second. Steps that
depend on render speed are marked below; scale every timeout with ROV_BROWSER_TIMEOUT_SCALE on slower machines.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base, timeout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'upgrade-validation'
OUT.mkdir(parents=True, exist_ok=True)

# Arm speed is 1 unit per simulated second: half the travel takes 0.5 s; allow state-sampling slack.
ARM_BUDGET_S = 2.0


def run():
    errors=[]
    with sync_playwright() as p:
        browser=launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
        contexts=[]
        pages=[]
        for i in range(3):
            print('Connecting browser',i+1,flush=True)
            context=browser.new_context(viewport={'width':960,'height':720})
            context.set_default_timeout(timeout(60000))
            page=context.new_page();contexts.append(context);pages.append(page)
            page.on('pageerror',lambda error: (errors.append(str(error)),print('PAGE ERROR',error,flush=True)))
            page.on('requestfailed',lambda request: print('REQUEST FAILED',request.url,request.failure,flush=True))
            page.on('console',lambda msg: print('CONSOLE',msg.text,flush=True) if msg.type=='error' else None)
            page.goto(
                f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&model=falcon&nointro&room=browsercheck&quality=performance',
                wait_until='domcontentloaded', timeout=timeout(90000))
            # Render-speed dependent: the first state needs the model and scene loaded while other viewers render.
            try:page.wait_for_function('window.__viewer?.S?.vehicle_id',timeout=timeout(120000))
            except Exception:
                print('DIAGNOSTICS',page.evaluate('({title:document.title,ready:!!window.__viewer,state:window.__viewer?.S,notice:document.querySelector("#operationNotice")?.textContent,connection:document.querySelector("#conn")?.textContent})'),flush=True)
                page.screenshot(path=str(OUT/f'failed-{i}.png'))
                raise
        main=pages[0]
        # Three soft-GL tabs share one CPU: pause draws on guests so state / arm waits can pump.
        for guest in pages[1:]:
            guest.evaluate('window.__skipRender = true')
        main.wait_for_function('window.__viewer.S.vehicles.length===3', timeout=timeout(120000))
        assert main.locator('#pip').is_hidden()
        main.evaluate("const option=document.querySelector('#optPip');option.checked=true;option.dispatchEvent(new Event('change'))")
        main.wait_for_function('document.querySelector(".pilot-pip-canvas")',timeout=timeout(60000))
        # Render-speed dependent: a click waits for the element to hold still across animation frames. None of
        # these clicks navigate, so do not also wait for a navigation that never happens.
        main.locator('#closePip').click(force=True, no_wait_after=True)
        assert main.locator('#pip').is_hidden()
        assert main.evaluate('localStorage.getItem("rov.operatorVisible")')=='false'
        # Vehicle is selected before entering the game via the launch URL.
        main.wait_for_function('window.__viewer.S.model_id==="falcon"', timeout=timeout(60000))
        main.wait_for_timeout(1000)
        main.click('#flightDrawer',no_wait_after=True)
        assert main.locator('#armPanel').is_visible()
        main.locator('#armPanel summary').click(no_wait_after=True)
        # Wait on sim time + arm state, not a fixed wall sleep: grip closes at 1 unit per sim-second.
        main.click('#gripClose',no_wait_after=True)
        main.evaluate('window.__skipRender = true')
        # Timed in simulated seconds from the moment the grip starts to move (the click itself may take long
        # under software GL): it must pass .5 within ARM_BUDGET_S. The wall timeout is only a stalled-server
        # watchdog, so a slow host cannot hide an arm that never closes or closes too slowly.
        arm = main.wait_for_function("""budget => {
          const state = window.__viewer.S;
          const grip = state.operations.arm.grip;
          if (grip >= 1) return false;
          window.__armStart ??= state.t;
          const elapsed = state.t - window.__armStart;
          if (grip >= .5 && elapsed <= budget) return false;
          return {grip, elapsed, latched: state.input_latched};
        }""", arg=ARM_BUDGET_S, timeout=timeout(180000)).json_value()
        assert arm['grip'] < .5, f'arm did not close within {ARM_BUDGET_S} simulated s: {arm}'
        main.evaluate('window.__viewer.setCam("onboard")')
        # Same direct switch write as before; a failsafe lock on a starved host resynchronises the page's
        # switches from the server, so the write is repeated until the server reports level 2.
        main.wait_for_function("""() => {
          const viewer = window.__viewer;
          if (viewer.S.rc.right_switch === 2) return true;
          if (!viewer.S.input_latched) viewer.rc.right_switch = 2;
          return false;
        }""", timeout=timeout(120000))
        main.evaluate('window.__skipRender = false')
        # Lamp meshes update on a drawn frame; wait for intensity after leaving __skipRender.
        main.wait_for_function("""() => {
          const groups = window.__viewer.rovG.children.filter(g => g.children.some(o => o.isSpotLight));
          return groups.some(g => g.visible && g.children.some(o => o.isSpotLight && o.intensity > 0));
        }""", timeout=timeout(60000))
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
