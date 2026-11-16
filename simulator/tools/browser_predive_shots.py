"""Screenshots of each step of the deck pre-dive check for docs/design/predive-check/ (1600x900 JPEG).

Not a pass/fail check: it drives the default vehicle on a running server and saves one frame per step. Part
"found" plants a cracked thruster guard and finds it; "missed" plants a fouled line, walks past it and flies until
the fault shows; "other" shows the two other defect kinds at their stations. ROV_PREDIVE_SHOTS picks the parts
(default found,missed). One browser run at a time on a shared machine, for example:

    ROV_PREDIVE_SHOTS=found python tools/run_browser_checks.py browser_predive_shots
    ROV_PREDIVE_SHOTS=missed,other python tools/run_browser_checks.py browser_predive_shots

Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import io
import os
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _campaign_drive import unlock_again, wait_condition

OUT = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'predive-check'
P = 'window.__viewer.S.procedure'
SETTLE_MS = 3000
JPEG_QUALITY = 80
DRIVE_KEYS = ('ArrowUp', 'KeyW', 'KeyD', 'ArrowRight', 'KeyE')
FAULT = 'return v.S.procedure.events.some((e) => e.action === "fault");'


def shot(page, name):
    """Save the page as a JPEG under 300 KB."""
    image = Image.open(io.BytesIO(page.screenshot())).convert('RGB')
    quality = JPEG_QUALITY
    while True:
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=quality, optimize=True, progressive=True)
        if buffer.tell() < 300 * 1024 or quality <= 50:
            break
        quality -= 5
    (OUT / f'{name}.jpg').write_bytes(buffer.getvalue())
    print('saved', name, buffer.tell() // 1024, 'KB', flush=True)


def pause(page):
    """Toggle the simulation pause (host button); the page keeps rendering."""
    paused = page.evaluate('!!window.__viewer.S.paused')
    page.evaluate('document.getElementById("btnPause").click()')
    page.wait_for_function(f'!!window.__viewer.S.paused === {"false" if paused else "true"}')


def press(page):
    page.locator('#procedurePanel #procedurePrimary').click()


def open_deck(page, room, defect):
    page.goto(f'{http_base()}/?play=1&fidelity=real&room={room}&quality=performance&predive_defect={defect}'
              f'&ws={ws_base()}')
    page.wait_for_function('window.__intro?.()?.held === true', timeout=timeout(120000))
    page.wait_for_function('window.__procedure?.().stage?.attached', timeout=timeout(60000))
    page.wait_for_timeout(SETTLE_MS)


def walk(page, report, prefix):
    station_of_defect = page.evaluate(f'{P}.defect.station')
    press(page)
    for station in range(5):
        page.wait_for_function(f'{P}.seen.includes({station})')
        page.wait_for_timeout(SETTLE_MS)
        if station == 0 and report:
            shot(page, '02-walkaround')
        if station == station_of_defect:
            shot(page, f'{prefix}-defect')
            if report:
                page.locator('#procedureReport').click()
                page.wait_for_function('window.__procedure().stage.marked')
                page.wait_for_timeout(1500)
                shot(page, f'{prefix}-found')
                press(page)
                page.wait_for_function(f'{P}.defect.fixed === true', timeout=timeout(30000))
        press(page)
    page.wait_for_function(f'{P}.checked.includes("walkaround")')


def found_run(page):
    open_deck(page, 'shots-found', 'guard_cracked')
    shot(page, '01-deck')
    walk(page, True, '03-walkaround')
    # A software-rendered page lags the simulation by seconds: hold the simulation while a timed step is shown.
    pause(page)
    press(page)
    page.wait_for_function('window.__procedure().stage.leds')
    page.wait_for_timeout(SETTLE_MS)
    shot(page, '04-power')
    pause(page)
    page.wait_for_function(f'{P}.checked.includes("power")', timeout=timeout(30000))
    thrusters = page.evaluate(f'{P}.thrusters')
    for motor in range(thrusters):
        if motor == 0:
            pause(page)
        press(page)
        if motor == 0:
            # The pulse waits while the simulation is held: the frame shows the prop turning.
            page.wait_for_function(f'{P}.diagnostic_index === 0')
            page.wait_for_timeout(SETTLE_MS)
            shot(page, '05-thruster')
            pause(page)
        page.wait_for_function(f'{P}.tests.includes({motor}) && !({P}.diagnostic > 0)', timeout=timeout(30000))
    page.wait_for_function(f'{P}.checked.includes("thrusters")')
    press(page)
    page.wait_for_function('window.__procedure().stage.lamps')
    page.wait_for_timeout(SETTLE_MS)
    shot(page, '06-lights')
    press(page)
    page.wait_for_function('window.__procedure().stage.feed')
    page.wait_for_timeout(SETTLE_MS)
    shot(page, '07-camera')
    press(page)
    page.wait_for_function(f'{P}.confirmed === true', timeout=timeout(30000))
    page.wait_for_timeout(1500)
    shot(page, '08-launch')


def missed_run(page):
    open_deck(page, 'shots-missed', 'line_fouled')
    walk(page, False, '09-missed')
    page.locator('.pp-link[data-focus=skip]').click()
    page.wait_for_function(f'{P}.confirmed === true', timeout=timeout(30000))
    press(page)
    page.wait_for_function('window.__intro().held === false', timeout=timeout(60000))
    page.evaluate('document.querySelector("#skipIntro").click()')
    page.wait_for_function('!window.__intro().playing', timeout=timeout(60000))
    press(page)
    page.wait_for_function(f'{P}.phase === "diving"')
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
    page.wait_for_function('window.__procedure().radio.speaker.startsWith("林岑")', timeout=timeout(30000))
    page.wait_for_timeout(800)
    shot(page, '10-fault')


def other_defects(page):
    """The two remaining defect kinds, as the walk-around sees them."""
    for name, kind in (('11-oring-debris', 'oring_debris'), ('12-connector-unlocked', 'connector_unlocked')):
        open_deck(page, f'shots-{kind}', kind)
        station = page.evaluate(f'{P}.defect.station')
        for index in range(station + 1):
            press(page)
            page.wait_for_function(f'{P}.seen.includes({index})')
        page.wait_for_timeout(SETTLE_MS)
        shot(page, name)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(90000))
        # The browser-check runner stops a script after 900 s: ROV_PREDIVE_SHOTS picks parts (found,missed,other).
        parts = (os.environ.get('ROV_PREDIVE_SHOTS') or 'found,missed').split(',')
        for name, part in (('found', found_run), ('missed', missed_run), ('other', other_defects)):
            if name in parts or 'all' in parts:
                part(page)
        browser.close()


if __name__ == '__main__':
    sys.exit(run())
