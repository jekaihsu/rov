"""Real launch-menu/gameplay checks; never teleports a vehicle to fake completion."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base, timeout, pump_until
from _menu import open_settings_tab, set_intro, soft_click, to_briefing, wait_ready

OUT = Path(__file__).resolve().parents[1]/'output'/'gameplay-validation'
OUT.mkdir(parents=True, exist_ok=True)
BASE = f'{http_base(8094)}/'
WS = ws_base(8794)
room = f'gameplay{int(time.time())}'
errors = []
QUALITY = 'quality=performance'


def wait_state(page, mode):
    page.wait_for_function('(mode)=>window.__viewer?.S?.mission?.mode===mode && window.__modelLoaded', arg=mode,
                           timeout=timeout(90000))


with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    contexts = []
    def new_page():
        context = browser.new_context(viewport={'width':1366,'height':768}, accept_downloads=True)
        contexts.append(context)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        # Do not replace WebSocket: that forces a main-thread socket and lets soft-GL starve
        # host_only / mission replies. Messages are recorded by link_inbox into __testMessages.
        page.add_init_script('window.__testMessages=[];')
        page.set_default_timeout(timeout(60000))
        return page

    main = new_page()
    main.goto(
        f'{BASE}?ws={WS}&room={room}&model=falcon&scene=coral_reef&mission=inspection_coop&{QUALITY}',
        wait_until='domcontentloaded')
    wait_ready(main, timeout=90000)
    open_settings_tab(main, 'quality')
    assert main.locator('#menuHardware').inner_text().strip()
    to_briefing(main, mode='inspection_coop', site='coral_reef')
    set_intro(main, False)
    main.wait_for_function('window.__menu.ready', timeout=timeout(90000))
    box = main.locator('#startDive').bounding_box()
    start_visible = bool(box and box['y'] >= 0 and box['y']+box['height'] <= 768)
    print('Start button visibility:',start_visible,box,flush=True)
    main.screenshot(path=str(OUT/'launch-1366.png'))
    soft_click(main, '#startDive')
    wait_state(main,'inspection_coop')
    main.wait_for_function('window.__viewer.S.mission.targets.length===3', timeout=timeout(90000))
    soft_click(main, '#flightDrawer')
    assert main.locator('.mission-photo').is_visible()
    assert main.evaluate('document.querySelector("#score").closest(".sec").hidden')
    target_ids = main.evaluate('window.__viewer.S.mission.targets.map(t=>t.id)')
    print('Cooperative launch has three targets', flush=True)

    guest = new_page()
    guest.goto(
        f'{BASE}?ws={WS}&room={room}&model=x1&mission=free_explore&play=1&nointro&{QUALITY}',
        wait_until='domcontentloaded')
    wait_state(guest,'inspection_coop')
    main.wait_for_function('window.__viewer.S.vehicles.length===2', timeout=timeout(120000))
    assert guest.evaluate('window.__viewer.S.mission.targets.map(t=>t.id)') == target_ids
    guest.bring_to_front()
    # Re-send while pumping: under load the first datagram can be dropped before the page reads it.
    # Skip render only for this wait so main's later photo path is not left permanently starved.
    pump_until(
        guest,
        """() => {
          window.__viewer?.flushLink?.();
          if (window.__testMessages.some(m => m.code === "host_only" || m.error === "host_only")) return true;
          window.__viewer?.send?.({type:'operation',action:'mission_mode',mode:'free_explore'});
          return false;
        }""",
        timeout_ms=timeout(120000), allies=(main,))
    assert guest.evaluate('window.__viewer.S.mission.mode') == 'inspection_coop'
    print('Guest shares mission and mode change is denied', flush=True)

    main.bring_to_front()
    main.evaluate('window.__skipRender = false')
    guest.evaluate('window.__skipRender = true')
    with main.expect_download(predicate=lambda d:d.suggested_filename.endswith('.png'), timeout=timeout(60000)) as capture:
        soft_click(main, '.mission-photo')
    capture.value.save_as(OUT/'not-ready-photo.png')
    # Download proves capture; last_photo proves the mission_photo operation and state sync.
    # Under load the first operation or state flush can be delayed — resend until state shows it.
    pump_until(
        main,
        """() => {
          window.__viewer?.flushLink?.();
          if (window.__viewer?.S?.mission?.last_photo) return true;
          window.__viewer?.send?.({type:'operation', action:'mission_photo'});
          return false;
        }""",
        timeout_ms=timeout(120000), allies=(guest,), skip_page_render=False)
    state = main.evaluate('window.__viewer.S.mission')
    assert state['completed'] == 0 and state['last_photo']['target_id'] is None, state
    assert (OUT/'not-ready-photo.png').stat().st_size > 1000
    pump_until(guest, '() => window.__viewer.S.mission.last_photo !== null',
               timeout_ms=timeout(120000), allies=(main,))
    assert guest.evaluate('window.__viewer.S.mission.last_photo.vehicle_id') == state['last_photo']['vehicle_id']
    assert main.locator('.mission-mode-feedback').inner_text().strip()
    main.screenshot(path=str(OUT/'cooperative-1366.png'))
    print('Photo downloads while unready station remains incomplete', flush=True)
    guest.close()

    for mode in ('free_explore','scenario_training'):
        soft_click(main, '#returnMenu')
        wait_ready(main, timeout=90000)
        to_briefing(main, mode=mode, site='coral_reef')
        set_intro(main, False)
        soft_click(main, '#startDive')
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
