"""Real launch-menu/gameplay checks; never teleports a vehicle to fake completion."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1]/'output'/'gameplay-validation'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8094/'
WS = 'ws://127.0.0.1:8794'
room = f'gameplay{int(time.time())}'
errors = []


def wait_state(page, mode):
    page.wait_for_function('(mode)=>window.__viewer?.S?.mission?.mode===mode && window.__modelLoaded', arg=mode,
                           timeout=90000)


with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--enable-unsafe-swiftshader'])
    contexts = []
    def new_page():
        context = browser.new_context(viewport={'width':1366,'height':768}, accept_downloads=True)
        contexts.append(context)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.add_init_script("""window.__testMessages=[];window.__testSockets=[];
          const Native=window.WebSocket;window.WebSocket=class extends Native{
            constructor(...args){super(...args);window.__testSockets.push(this);
              this.addEventListener('message',e=>{try{const value=JSON.parse(e.data);if(!['state','world'].includes(value.type))window.__testMessages.push(value);}catch{}});}
          };""")
        return page

    main = new_page()
    main.goto(f'{BASE}?ws={WS}&room={room}&model=falcon&scene=coral_reef&mission=inspection_coop', wait_until='domcontentloaded')
    main.wait_for_function('window.__menu?.ready', timeout=90000)
    main.select_option('#menuScene','coral_reef')
    main.select_option('#menuMode','inspection_coop')
    main.locator('#menuIntro').evaluate('(el)=>{el.checked=false}')
    main.wait_for_function('window.__menu.ready')
    assert main.locator('#menuHardware').inner_text().strip()
    box = main.locator('#startDive').bounding_box()
    start_visible = bool(box and box['y'] >= 0 and box['y']+box['height'] <= 768)
    print('Start button visibility:',start_visible,box,flush=True)
    main.screenshot(path=str(OUT/'launch-1366.png'))
    main.click('#startDive')
    wait_state(main,'inspection_coop')
    main.wait_for_function('window.__viewer.S.mission.targets.length===3')
    assert main.locator('.mission-photo').is_visible()
    assert main.evaluate('document.querySelector("#score").closest(".sec").hidden')
    target_ids = main.evaluate('window.__viewer.S.mission.targets.map(t=>t.id)')
    print('Cooperative launch has three targets', flush=True)

    guest = new_page()
    guest.goto(f'{BASE}?ws={WS}&room={room}&model=x1&mission=free_explore&play=1&nointro', wait_until='domcontentloaded')
    wait_state(guest,'inspection_coop')
    main.wait_for_function('window.__viewer.S.vehicles.length===2')
    assert guest.evaluate('window.__viewer.S.mission.targets.map(t=>t.id)') == target_ids
    guest.evaluate("window.__testSockets.find(s=>s.readyState===1).send(JSON.stringify({type:'operation',action:'mission_mode',mode:'free_explore'}))")
    guest.wait_for_function('window.__testMessages.some(m=>m.code==="host_only" || m.error==="host_only")')
    assert guest.evaluate('window.__viewer.S.mission.mode') == 'inspection_coop'
    print('Guest shares mission and mode change is denied', flush=True)

    main.bring_to_front()
    with main.expect_download(predicate=lambda d:d.suggested_filename.endswith('.png'), timeout=30000) as capture:
        main.click('.mission-photo')
    capture.value.save_as(OUT/'not-ready-photo.png')
    main.wait_for_function('window.__viewer.S.mission.last_photo !== null')
    state = main.evaluate('window.__viewer.S.mission')
    assert state['completed'] == 0 and state['last_photo']['target_id'] is None, state
    assert (OUT/'not-ready-photo.png').stat().st_size > 1000
    guest.wait_for_function('window.__viewer.S.mission.last_photo !== null')
    assert guest.evaluate('window.__viewer.S.mission.last_photo.vehicle_id') == state['last_photo']['vehicle_id']
    assert main.locator('.mission-mode-feedback').inner_text().strip()
    main.screenshot(path=str(OUT/'cooperative-1366.png'))
    print('Photo downloads while unready station remains incomplete', flush=True)
    guest.close()

    for mode in ('free_explore','scenario_training'):
        main.click('#returnMenu')
        main.wait_for_function('window.__menu?.ready', timeout=90000)
        main.select_option('#menuMode',mode)
        main.locator('#menuIntro').evaluate('(el)=>{el.checked=false}')
        main.click('#startDive')
        wait_state(main,mode)
        hidden = main.evaluate('document.querySelector("#score").closest(".sec").hidden')
        if mode == 'free_explore':
            assert hidden
            assert main.evaluate('window.__viewer.S.mission.remaining') is None
            assert '無倒數' in main.locator('.mission-mode-summary').inner_text()
        else:
            assert not hidden
            assert main.locator('.mission-mode-panel').is_hidden()
        main.screenshot(path=str(OUT/f'{mode}-1366.png'))
        print(mode,'round trip passed', flush=True)
    assert not errors, errors
    assert start_visible, f'Start button outside 1366x768 viewport: {box}'
    result = dict(status='passed', cooperative_targets=target_ids, two_peer_shared_mission=True,
        guest_mode_denied=True, unready_photo_downloaded=True, unready_station_not_completed=True,
        free_no_timer=True, training_legacy_score_visible=True, start_button_visible_1366=True,
        errors=errors, completion_validation='Backend unit tests only; browser did not complete stations')
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
    print(json.dumps(result,ensure_ascii=False))
