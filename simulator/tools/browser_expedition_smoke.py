"""Real menu/three-player/collection flows. Successful task physics is tested separately."""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, host, http_port, ws_port, timeout
from _menu import launch_from_menu, open_main

parser = argparse.ArgumentParser()
parser.add_argument('--http-port', type=int, default=http_port(8095))
parser.add_argument('--ws-port', type=int, default=ws_port(8795))
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'playwright' / 'expedition'
OUT.mkdir(parents=True, exist_ok=True)
BASE = f'http://{host()}:{args.http_port}/'
WS = f'ws://{host()}:{args.ws_port}'
errors = []
room = 'exp' + str(int(time.time()))
instrument = """window.__testSockets=[];window.__testMessages=[];
const OriginalWebSocket=window.WebSocket;window.WebSocket=class extends OriginalWebSocket{
 constructor(...args){super(...args);window.__testSockets.push(this);this.addEventListener('message',e=>{
 try{const m=JSON.parse(e.data);if(!['world','state'].includes(m.type))window.__testMessages.push(m);}catch{}});}
};"""


def operation(page, action, **values):
    """Send an operation from a live tab. Bring it forward first so soft-GL tabs can pump sockets."""
    message = {'type': 'operation', 'action': action, **values}
    page.bring_to_front()
    sent = page.evaluate("""m => {
      const socket = [...window.__testSockets].reverse().find(s => s.readyState === 1);
      if (!socket) return false;
      socket.send(JSON.stringify(m));
      return true;
    }""", message)
    if not sent:
        raise AssertionError(f'no open viewer socket for {action}')
    return message


def wait_state(page):
    page.bring_to_front()
    page.wait_for_function(
        "window.__viewer?.S?.mission?.mode==='expedition' && window.__modelLoaded",
        timeout=timeout(120000))


def current_host(tabs):
    # Disconnect transfers the host; reconnecting resumes the pilot, not lost admin role.
    deadline = time.time() + timeout(60000) / 1000
    while time.time() < deadline:
        for tab in tabs:
            tab.bring_to_front()
            if tab.evaluate("""() => {
              const room = window.__viewer?.S?.room;
              if (!room) return false;
              const session = window.__testMessages.filter(m => m.type === 'session').at(-1);
              if (session && room.host_id === session.player_id) return true;
              const load = document.querySelector('#btnLoad');
              return !!(load && !load.disabled && room.host_id);
            }"""):
                return tab
        tabs[0].wait_for_timeout(200)
    raise AssertionError('no tab matches the elected host')


def wait_reply(page, before, request_id):
    page.bring_to_front()
    page.wait_for_function(
        """([before, request_id]) => window.__testMessages.slice(before).some(
          m => m.request_id === request_id || m.code === 'host_only' || m.error === 'host_only')""",
        arg=[before, request_id], timeout=timeout(120000))
    return page.evaluate("""([before, request_id]) => {
      const rows = window.__testMessages.slice(before);
      return rows.find(m => m.request_id === request_id)
        || rows.find(m => m.code === 'host_only' || m.error === 'host_only');
    }""", [before, request_id])


def host_operation(tabs, action, **values):
    """Send a host-only operation from the elected host while that tab is foregrounded."""
    elected = current_host(tabs)
    request_id = values.get('request_id')
    before = elected.evaluate('window.__testMessages.length')
    operation(elected, action, **values)
    if not request_id:
        return elected
    reply = wait_reply(elected, before, request_id)
    if reply.get('code') == 'host_only' or reply.get('error') == 'host_only':
        raise AssertionError(f'{action} denied as host_only from elected tab: {reply}')
    return elected


def await_active(page, predicate):
    page.bring_to_front()
    page.wait_for_function(predicate, timeout=timeout(120000))


def main_operation(page, action, **values):
    """Host ops on the foreground main tab after guests have left."""
    request_id = values.get('request_id')
    before = page.evaluate('window.__testMessages.length')
    operation(page, action, **values)
    if request_id:
        reply = wait_reply(page, before, request_id)
        if reply.get('code') == 'host_only' or reply.get('error') == 'host_only':
            raise AssertionError(f'{action} denied as host_only on main: {reply}')


with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    contexts = []

    def page():
        context = browser.new_context(viewport={'width': 1366, 'height': 768}, accept_downloads=True)
        contexts.append(context)
        tab = context.new_page()
        tab.on('pageerror', lambda e: errors.append(str(e)))
        tab.add_init_script(instrument)
        tab.set_default_timeout(timeout(60000))
        return tab

    main = page()
    main.goto(
        f'{BASE}?ws={WS}&room={room}&model=falcon&scenario=coral_reef&mission=expedition&quality=performance',
        wait_until='domcontentloaded')
    main.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    assert main.evaluate('window.__menu.mission') == 'expedition'
    open_main(main)
    main.click('#menuCollection')
    main.wait_for_selector('.collection-panel, .collection-dialog, [role="dialog"]', timeout=timeout(60000))
    main.screenshot(path=str(OUT / 'menu-collection.png'))
    main.keyboard.press('Escape')
    launch_from_menu(main, mode='expedition', site='coral_reef')
    wait_state(main)
    main.click('#flightDrawer')
    main.wait_for_selector('.expedition-panel:not([hidden])', timeout=timeout(60000))
    main.click('.exp-available button')
    await_active(main, "window.__viewer.S.expedition.active?.kind==='inspect'")
    dive_id = main.evaluate('window.__viewer.S.expedition.dive_id')
    contract_id = main.evaluate('window.__viewer.S.expedition.active.id')
    assert main.evaluate('window.__viewer.S.expedition.active.steps.length') == 3
    main.screenshot(path=str(OUT / 'inspection-active.png'))

    guests = []
    for model in ('x1', 'bluerov2_heavy'):
        guest = page()
        guest.goto(
            f'{BASE}?ws={WS}&room={room}&model={model}&mission=expedition&play=1&nointro&quality=performance',
            wait_until='domcontentloaded')
        wait_state(guest)
        guests.append(guest)
        assert guest.evaluate('window.__viewer.S.expedition.active.id') == contract_id
    main.wait_for_function('window.__viewer.S.room.players.length===3', timeout=timeout(120000))

    operation(guests[0], 'expedition_cancel', request_id='guest-cannot-cancel')
    guests[0].bring_to_front()
    guests[0].wait_for_function(
        "() => window.__testMessages.some(m => m.code === 'host_only' || m.error === 'host_only')",
        timeout=timeout(120000))
    assert guests[0].evaluate('window.__viewer.S.expedition.active.id') == contract_id

    # Reload transfers host; cancel from the elected host while guest tabs are still warm.
    main.reload(wait_until='domcontentloaded')
    wait_state(main)
    assert main.evaluate('window.__viewer.S.expedition.dive_id') == dive_id
    assert main.evaluate('window.__viewer.S.expedition.active.id') == contract_id
    tabs = [main, *guests]
    host_operation(tabs, 'expedition_cancel', request_id='cancel-inspection')
    await_active(main, 'window.__viewer.S.expedition.active===null')
    host_operation(tabs, 'expedition_start', contract='recover', request_id='recover-once')
    await_active(main, "window.__viewer.S.expedition.active?.kind==='recover'")
    recovery_id = main.evaluate('window.__viewer.S.expedition.active.id')
    host_operation(tabs, 'expedition_start', contract='recover', request_id='recover-once')
    main.wait_for_timeout(400)
    assert main.evaluate('window.__viewer.S.expedition.active.id') == recovery_id

    main.bring_to_front()
    main.evaluate("window.__viewer.setCam('orbit')")
    main.click('.exp-photo')
    for _ in range(100):
        saved = main.evaluate(
            "import('./collection_store.js').then(m=>m.listCollection()).then(v=>v.photos.length)")
        if saved == 1:
            break
        main.wait_for_timeout(200)
    else:
        raise AssertionError(main.locator('#operationNotice').inner_text())
    collection = main.evaluate("import('./collection_store.js').then(m=>m.listCollection())")
    assert collection['photos'][0]['observation'] is None
    assert collection['photos'][0]['metadata']['cameraMode'] == 'orbit'
    assert collection['guides'] == []
    main.click('#openCollection')
    main.screenshot(path=str(OUT / 'souvenir-collection.png'))
    main.wait_for_function('window.__viewer.S.rc.rc_lock===1', timeout=timeout(60000))
    main.keyboard.press('Escape')
    main.reload(wait_until='domcontentloaded')
    wait_state(main)
    assert main.evaluate(
        "import('./collection_store.js').then(m=>m.listCollection()).then(v=>v.photos.length)") == 1
    assert main.evaluate('window.__viewer.S.expedition.active.id') == recovery_id

    # Soft-GL background guests often lose a live socket after long main-only work. Leave them so
    # host returns to the foreground main tab; remaining contracts still exercise start/cancel.
    for guest in guests:
        guest.close()
    main.bring_to_front()
    main.wait_for_function(
        'window.__viewer.S.room.players.filter(p => p.connected).length===1',
        timeout=timeout(60000))
    main.wait_for_function(
        '() => { const load = document.querySelector("#btnLoad"); return load && !load.disabled; }',
        timeout=timeout(60000))

    main_operation(main, 'expedition_cancel', request_id='cancel-recovery')
    await_active(main, 'window.__viewer.S.expedition.active===null')
    main_operation(main, 'expedition_start', contract='deploy', request_id='deploy-once')
    await_active(main, "window.__viewer.S.expedition.active?.kind==='deploy'")
    main.screenshot(path=str(OUT / 'deployment-active.png'))
    main_operation(main, 'expedition_cancel', request_id='cancel-deployment')
    await_active(main, 'window.__viewer.S.expedition.active===null')
    assert main.evaluate("window.__viewer.S.operations.objects.filter(o=>o.task_id).length") == 0

    backup = main.evaluate(
        "import('./collection_store.js').then(async m=>{const b=await m.exportCollection();return await b.text();})")
    Path(OUT / 'collection-backup.json').write_text(backup, encoding='utf-8')
    peer = page()
    peer.goto(f'{BASE}?ws={WS}&room={room}peer&play=1&nointro&quality=performance',
              wait_until='domcontentloaded')
    peer.wait_for_function('window.__viewer?.S', timeout=timeout(120000))
    imported = peer.evaluate(
        "text=>import('./collection_store.js').then(m=>m.importCollection(new Blob([text],{type:'application/json'})))",
        backup)
    assert peer.evaluate(
        "import('./collection_store.js').then(m=>m.listCollection()).then(v=>v.photos.length)") == 1
    assert not errors, errors
    result = {
        'status': 'passed', 'three_players': True, 'host_only': True, 'refresh_keeps_dive': True,
        'refresh_keeps_contract': True, 'idempotent_start': True, 'all_contracts_start_cancel': True,
        'third_person_souvenir_only': True, 'collection_survives_reload': True,
        'backup_import': imported, 'errors': errors,
    }
    (OUT / 'results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    browser.close()
