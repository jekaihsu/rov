"""Real menu/three-player/collection flows. Successful task physics is tested separately."""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--http-port', type=int, default=8095)
parser.add_argument('--ws-port', type=int, default=8795)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'playwright' / 'expedition'
OUT.mkdir(parents=True, exist_ok=True)
BASE = f'http://127.0.0.1:{args.http_port}/'
WS = f'ws://127.0.0.1:{args.ws_port}'
errors = []
room = 'exp' + str(int(time.time()))
instrument = """window.__testSockets=[];window.__testMessages=[];
const OriginalWebSocket=window.WebSocket;window.WebSocket=class extends OriginalWebSocket{
 constructor(...args){super(...args);window.__testSockets.push(this);this.addEventListener('message',e=>{
 try{const m=JSON.parse(e.data);if(!['world','state'].includes(m.type))window.__testMessages.push(m);}catch{}});}
};"""

def operation(page, action, **values):
    page.evaluate("m=>window.__testSockets.find(s=>s.readyState===1).send(JSON.stringify(m))", {'type':'operation','action':action,**values})

def wait_state(page):
    page.wait_for_function("window.__viewer?.S?.mission?.mode==='expedition' && window.__modelLoaded", timeout=90000)

def current_host(tabs):
    # Disconnect transfers the host; reconnecting resumes the pilot, not a lost
    # administrative role. Exercise the elected host rather than assuming v1.
    return next(tab for tab in tabs if tab.evaluate("window.__viewer.S.room.host_id===window.__testMessages.filter(m=>m.type==='session').at(-1).player_id"))

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    contexts=[]
    def page():
        context=browser.new_context(viewport={'width':1366,'height':768},accept_downloads=True)
        contexts.append(context)
        tab=context.new_page();tab.on('pageerror',lambda e:errors.append(str(e)));tab.add_init_script(instrument)
        return tab
    main=page()
    main.goto(f'{BASE}?ws={WS}&room={room}&model=falcon&scenario=coral_reef&mission=expedition',wait_until='domcontentloaded')
    main.wait_for_function('window.__menu?.ready',timeout=90000)
    assert main.locator('#menuMode').input_value()=='expedition'
    main.click('#menuCollection')
    main.wait_for_selector('.collection-panel, .collection-dialog, [role="dialog"]')
    main.screenshot(path=str(OUT/'menu-collection.png'))
    main.keyboard.press('Escape')
    main.locator('#menuIntro').evaluate('(el)=>el.checked=false')
    main.locator('#startDive').click()
    wait_state(main)
    main.wait_for_selector('.expedition-panel:not([hidden])')
    main.click('.exp-available button')
    main.wait_for_function("window.__viewer.S.expedition.active?.kind==='inspect'")
    dive_id=main.evaluate('window.__viewer.S.expedition.dive_id')
    contract_id=main.evaluate('window.__viewer.S.expedition.active.id')
    assert main.evaluate('window.__viewer.S.expedition.active.steps.length')==3
    main.screenshot(path=str(OUT/'inspection-active.png'))
    guests=[]
    for model in ('x1','bluerov2_heavy'):
        guest=page();guest.goto(f'{BASE}?ws={WS}&room={room}&model={model}&mission=expedition&play=1&nointro',wait_until='domcontentloaded');wait_state(guest);guests.append(guest)
        assert guest.evaluate('window.__viewer.S.expedition.active.id')==contract_id
    main.wait_for_function('window.__viewer.S.room.players.length===3')
    operation(guests[0],'expedition_cancel',request_id='guest-cannot-cancel')
    guests[0].wait_for_function("window.__testMessages.some(m=>m.code==='host_only'||m.error==='host_only')")
    assert guests[0].evaluate('window.__viewer.S.expedition.active.id')==contract_id
    main.reload(wait_until='domcontentloaded');wait_state(main)
    assert main.evaluate('window.__viewer.S.expedition.dive_id')==dive_id
    assert main.evaluate('window.__viewer.S.expedition.active.id')==contract_id
    host=current_host([main,*guests])
    operation(host,'expedition_cancel',request_id='cancel-inspection')
    main.wait_for_function('window.__viewer.S.expedition.active===null')
    operation(host,'expedition_start',contract='recover',request_id='recover-once')
    main.wait_for_function("window.__viewer.S.expedition.active?.kind==='recover'")
    recovery_id=main.evaluate('window.__viewer.S.expedition.active.id')
    operation(host,'expedition_start',contract='recover',request_id='recover-once')
    main.wait_for_timeout(400)
    assert main.evaluate('window.__viewer.S.expedition.active.id')==recovery_id
    main.evaluate("window.__viewer.setCam('orbit')")
    main.click('.exp-photo')
    for _ in range(100):
        saved=main.evaluate("import('./collection_store.js').then(m=>m.listCollection()).then(v=>v.photos.length)")
        if saved==1:break
        main.wait_for_timeout(200)
    else:
        raise AssertionError(main.locator('#operationNotice').inner_text())
    collection=main.evaluate("import('./collection_store.js').then(m=>m.listCollection())")
    assert collection['photos'][0]['observation'] is None
    assert collection['photos'][0]['metadata']['cameraMode']=='orbit'
    assert collection['guides']==[]
    main.click('#openCollection')
    main.screenshot(path=str(OUT/'souvenir-collection.png'))
    main.wait_for_function('window.__viewer.S.rc.rc_lock===1')
    main.keyboard.press('Escape')
    main.reload(wait_until='domcontentloaded');wait_state(main)
    assert main.evaluate("import('./collection_store.js').then(m=>m.listCollection()).then(v=>v.photos.length)")==1
    assert main.evaluate('window.__viewer.S.expedition.active.id')==recovery_id
    host=current_host([main,*guests])
    operation(host,'expedition_cancel',request_id='cancel-recovery')
    main.wait_for_function('window.__viewer.S.expedition.active===null')
    operation(host,'expedition_start',contract='deploy',request_id='deploy-once')
    main.wait_for_function("window.__viewer.S.expedition.active?.kind==='deploy'")
    main.screenshot(path=str(OUT/'deployment-active.png'))
    operation(host,'expedition_cancel',request_id='cancel-deployment')
    main.wait_for_function('window.__viewer.S.expedition.active===null')
    assert main.evaluate("window.__viewer.S.operations.objects.filter(o=>o.task_id).length")==0
    backup=main.evaluate("import('./collection_store.js').then(async m=>{const b=await m.exportCollection();return await b.text();})")
    Path(OUT/'collection-backup.json').write_text(backup,encoding='utf-8')
    # Import into a separate local profile; original photo and souvenirs remain intact.
    imported=guests[0].evaluate("text=>import('./collection_store.js').then(m=>m.importCollection(new Blob([text],{type:'application/json'})))",backup)
    assert guests[0].evaluate("import('./collection_store.js').then(m=>m.listCollection()).then(v=>v.photos.length)")==1
    assert not errors, errors
    result={'status':'passed','three_players':True,'host_only':True,'refresh_keeps_dive':True,
      'refresh_keeps_contract':True,'idempotent_start':True,'all_contracts_start_cancel':True,
      'third_person_souvenir_only':True,'collection_survives_reload':True,'backup_import':imported,'errors':errors}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    browser.close()
