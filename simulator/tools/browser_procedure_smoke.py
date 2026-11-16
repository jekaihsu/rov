"""Exercise the deck pre-dive check, launch, water confirmation, recovery and dive-log export in a real browser.

The real fidelity preset selects the full procedure; the server runs its deck flow. Run one plants a cracked
thruster guard (?predive_defect): the walk-around camera visits every station, the defect is drawn, reported,
marked and fixed; power lights the status LEDs, each thruster pulse spins its prop, the lamp test lights the
lamps on deck until confirmed, the camera check cuts to the onboard feed, and the crew reports the routine items by radio. The
column must sit on the --z-controls layer, keep clear of the middle third and stay off screen during the dive,
where recovery is reached through the pause menu. Run two plants a fouled line and walks past it: after launch
the fouled thruster loses thrust and the supervisor calls the fault. Screenshots go to output/procedure-validation/.
Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _campaign_drive import unlock_again, wait_condition

OUT = Path(__file__).resolve().parents[1] / 'output' / 'procedure-validation'
STATIONS = 5
SETTLE_MS = 2500
# Keys that drive different thrusters in the console layout; the missed-line run holds them all at once.
DRIVE_KEYS = ('ArrowUp', 'KeyW', 'KeyD', 'ArrowRight', 'KeyE')
FAULT = 'return v.S.procedure.events.some((e) => e.action === "fault" && e.defect === "line_fouled");'
P = 'window.__viewer.S.procedure'


def assert_title(panel, text, wait=None):
    """The current step is the column's large title."""
    panel.locator('.pp-title', has_text=text).wait_for(state='visible', timeout=wait)


def stage(page):
    return page.evaluate('window.__procedure().stage')


def open_deck(page, room, defect):
    page.goto(f'{http_base()}/?play=1&fidelity=real&room={room}&model=bluerov2_heavy&quality=performance'
              f'&predive_defect={defect}&ws={ws_base()}')
    panel = page.locator('#procedurePanel')
    panel.wait_for(state='visible', timeout=timeout(90000))
    # The vehicle is on the aft deck during the checks: the launch intro opens there and holds.
    page.wait_for_function('window.__intro?.()?.held === true', timeout=timeout(90000))
    assert page.evaluate('window.__intro().t') == 0, 'the held deck frame must not advance'
    assert page.evaluate('window.__viewer.S.pos[2]') < 0, 'the full procedure starts on deck, above the water'
    assert page.evaluate(f'{P}.flow') == 'deck', 'the server runs the deck flow'
    page.wait_for_function('window.__procedure().stage.attached', timeout=timeout(30000))
    return panel


def walk(page, panel, report, shots):
    """Walk the five stations; report and fix the defect when ``report``. Returns the defect station."""
    defect = page.evaluate(f'{P}.defect')
    assert defect and not defect['found'], defect
    assert_title(panel, '繞機目視檢查')
    page.keyboard.press('Space')                      # the primary action holds focus: Space starts the walk
    for station in range(STATIONS):
        page.wait_for_function(f'{P}.seen.includes({station})')
        page.wait_for_function(f'window.__procedure().stage.shot === "station"')
        fixed = page.evaluate(f'{P}.defect.fixed')
        assert stage(page)['defect'] != fixed, 'the planted defect is drawn on the vehicle until it is fixed'
        if station == defect['station']:
            page.wait_for_timeout(SETTLE_MS)
            page.screenshot(path=str(OUT / shots['defect']))
            if report:
                panel.locator('#procedureReport').click()
                page.wait_for_function(f'{P}.defect.found === true')
                page.wait_for_function('window.__procedure().stage.marked')
                page.wait_for_function('window.__procedure().radio.text.includes("先處理掉")')
                page.screenshot(path=str(OUT / shots['found']))
                assert_title(panel, '推進器護罩裂了')
                panel.locator('#procedurePrimary').click()
                page.wait_for_function(f'{P}.defect.fixed === true', timeout=timeout(30000))
                page.wait_for_function('!window.__procedure().stage.defect')
                print('Defect found and fixed at station', station, flush=True)
        elif station == 0 and 'clean' in shots:
            page.wait_for_timeout(SETTLE_MS)
            page.screenshot(path=str(OUT / shots['clean']))
        panel.locator('#procedurePrimary').click()
    page.wait_for_function(f'{P}.checked.includes("walkaround")')
    return defect['station']


def run_checks(page, panel):
    assert_title(panel, '載具上電')
    assert not stage(page)['leds']
    page.keyboard.press('Enter')                      # Enter on the focused primary powers the vehicle
    page.wait_for_function(f'{P}.powered === true')
    page.wait_for_function('window.__procedure().stage.leds')
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / 'power.png'))
    page.wait_for_function(f'{P}.checked.includes("power")', timeout=timeout(30000))
    # Routine items come over the radio, not as clicks.
    page.wait_for_function(f'["trim", "instruments", "communication"].every((k) => {P}.crew.includes(k))',
                           timeout=timeout(30000))
    assert_title(panel, '推進器短測')
    thrusters = page.evaluate(f'{P}.thrusters')
    primary = panel.locator('#procedurePrimary')
    for motor in range(thrusters):
        before = page.evaluate(f'window.__viewer.rotorOf[{motor}]?.ang ?? null')
        assert primary.text_content() == f'短測 T{motor + 1}', primary.text_content()
        primary.click()
        # The pulse lasts 2 simulated seconds; a slow page may only see it finished.
        page.wait_for_function(f'{P}.diagnostic_index === {motor} || {P}.tests.includes({motor})')
        if motor == 0:
            page.screenshot(path=str(OUT / 'thruster.png'))
        page.wait_for_function(f'{P}.tests.includes({motor}) && !({P}.diagnostic > 0)', timeout=timeout(30000))
        if before is not None:
            # The prop turned during the pulse (the vehicle is locked on deck, so only the pulse can turn it).
            page.wait_for_function(f'Math.abs(window.__viewer.rotorOf[{motor}].ang - {before}) > 1',
                                   timeout=timeout(15000))
        print('Motor pulsed and spun', motor + 1, flush=True)
    assert_title(panel, '燈光測試')
    assert not stage(page)['lamps']
    primary.click()
    page.wait_for_function(f'{P}.lamps === true')
    page.wait_for_function('window.__procedure().stage.lamps')
    page.wait_for_timeout(SETTLE_MS)
    page.screenshot(path=str(OUT / 'lights.png'))
    assert not page.evaluate(f'{P}.checked.includes("lights")'), 'the lamps stay on until the operator confirms'
    primary.click()
    page.wait_for_function(f'{P}.checked.includes("lights")', timeout=timeout(30000))
    page.wait_for_function('!window.__procedure().stage.lamps')
    assert_title(panel, '機載影像')
    page.wait_for_function('window.__procedure().stage.feed')
    assert page.locator('#procedureFeed').is_visible()
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / 'camera.png'))
    primary.click()
    page.wait_for_function(f'{P}.phase === "launch"')
    assert page.locator('#procedureFeed').is_hidden()


def lower(page, panel):
    assert_title(panel, '緩放入水')
    page.wait_for_function(f'{P}.confirmed === true', timeout=timeout(30000))
    page.wait_for_function('window.__procedure().radio.text.includes("隨時可以放")', timeout=timeout(30000))
    held = page.evaluate('window.__intro()')
    assert held['held'] and held['t'] == 0, 'the launch intro must wait on deck for the lowering step'
    panel.locator('#procedurePrimary').click()
    # The A-frame launch cinematic plays at the lowering step; skip it to keep the check short.
    page.wait_for_function('window.__intro?.()?.starts > 0 && window.__intro().held === false',
                           timeout=timeout(90000))
    assert not page.evaluate('window.__procedure().stage.attached'), 'the deck props leave with the launch'
    page.evaluate('document.querySelector("#skipIntro").click()')
    page.wait_for_function('!window.__intro().playing', timeout=timeout(60000))
    assert_title(panel, '入水確認')
    panel.locator('#procedurePrimary').click()
    page.wait_for_function(f'{P}.phase === "diving"')
    panel.wait_for(state='hidden')


def found_run(page):
    panel = open_deck(page, 't23', 'guard_cracked')
    z_index = panel.evaluate('(el) => getComputedStyle(el).zIndex')
    controls = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--z-controls").trim()')
    assert z_index == controls, (z_index, controls)
    page.screenshot(path=str(OUT / 'checks.png'))
    box = panel.bounding_box()
    assert box['x'] + box['width'] <= 1600 / 3, ('the column keeps clear of the middle third', box)
    page.wait_for_function('window.__procedure().radio.text.includes("配重")', timeout=timeout(30000))
    walk(page, panel, True, {'defect': 'walkaround-defect.png', 'found': 'walkaround-found.png',
                             'clean': 'walkaround.png'})
    run_checks(page, panel)
    deck_time = page.evaluate(f'{P}.elapsed')
    print('Time on deck (simulated s):', deck_time, flush=True)
    lower(page, panel)
    assert page.evaluate(f'{P}.penalty') == 0
    page.screenshot(path=str(OUT / 'water.png'))
    page.keyboard.press('Escape')
    recover = page.locator('#pauseMenu [data-action="procedure-recover"]')
    recover.wait_for(state='visible')
    assert recover.text_content() == '收纜回收', recover.text_content()
    recover.click()
    page.wait_for_function(f'{P}.phase !== "diving"')
    primary = panel.locator('#procedurePrimary')
    assert_title(panel, '已以淡水沖洗', timeout(120000))
    primary.click()
    page.wait_for_function(f'{P}.phase === "inspect"')
    assert_title(panel, '潛後檢查完成')
    primary.click()
    page.wait_for_function(f'{P}.phase === "log"')
    panel.get_by_role('textbox', name='潛水註記').fill('T23 browser full procedure')
    panel.get_by_role('button', name='儲存日誌').click()
    page.wait_for_function(f'{P}.phase === "complete"')
    with page.expect_download() as download:
        panel.get_by_role('button', name='匯出日誌').click()
    download.value.save_as(OUT / 'dive-log.json')
    exported = json.loads((OUT / 'dive-log.json').read_text(encoding='utf-8'))
    assert exported.get('pilot_log'), 'dive-log export must carry the pilot log lines'
    page.screenshot(path=str(OUT / 'complete.png'))
    assert page.evaluate(f'{P}.notes') == 'T23 browser full procedure'


def missed_run(page):
    panel = open_deck(page, 't23-missed', 'line_fouled')
    walk(page, panel, False, {'defect': 'walkaround-missed.png'})
    panel.locator('.pp-link[data-focus=skip]').click()
    page.wait_for_function(f'{P}.phase === "launch"')
    lower(page, panel)
    index = page.evaluate(f'{P}.defect.thruster')
    assert page.evaluate(f'window.__viewer.S.health[{index}]') == 1
    unlock_again(page, 'Space')
    for _ in range(4):
        # Every stick at once: one of them runs the fouled thruster, whatever its place in the allocation.
        for key in DRIVE_KEYS:
            page.keyboard.down(key)
        result = wait_condition(page, FAULT, budget=6)
        for key in DRIVE_KEYS:
            page.keyboard.up(key)
        if result['status'] == 'done':
            break
        if page.evaluate('window.__viewer.S.locked'):
            unlock_again(page, 'Space')
    else:
        raise AssertionError('no drive key ran the fouled thruster')
    page.wait_for_function(f'window.__viewer.S.health[{index}] < 0.5')
    prompt = page.locator('#procedurePrompt')
    prompt.wait_for(state='visible')
    assert '推力掉了' in prompt.text_content(), prompt.text_content()
    page.wait_for_function('window.__procedure().radio.speaker.startsWith("林岑")', timeout=timeout(30000))
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / 'fault.png'))
    print('Missed line fouled thruster', index + 1, flush=True)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1600, 'height': 900}, accept_downloads=True)
        page.set_default_timeout(timeout(60000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        found_run(page)
        missed_run(page)
        assert not errors, errors
        browser.close()
    print('Deck checks (walk-around, defect found and fixed, power, thruster spin, lamps, camera feed, crew radio),'
          ' launch, recovery, log export and the missed-defect fault passed.')


if __name__ == '__main__':
    sys.exit(run())
