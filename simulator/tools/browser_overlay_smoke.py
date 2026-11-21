"""Check that overlays neither cover instruments nor intercept controls, in replay, campaign and menu.

Every check is geometric: controls must be the element returned by document.elementFromPoint at their
own centre, and read-outs must not share pixels with the overlays listed next to them. Layer order is
compared with the stacking scale in viewer/hud/tokens.css.

Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT;
defaults http://127.0.0.1:8092 and ws://127.0.0.1:8792).
"""
import sys
import time

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_internal, to_briefing, wait_screen, wait_title_card_gone

BASE_URL = http_base()
WS_URL = ws_base()
SIZES = [(1280, 720), (390, 844)]
LONG_LINE = '測試用的長對話，確認無線電對話框再長也不會蓋住深度、航向、速度與小地圖。' * 4

HELPERS = """
window.__overlay = {
  element(selector) {
    return document.querySelector(selector);
  },
  visible(selector) {
    const el = this.element(selector);
    if (!el || !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return false;
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  },
  // The control is what a pointer at its centre would actually hit.
  reachable(selector) {
    const el = this.element(selector);
    if (!this.visible(selector)) return 'not visible';
    const box = el.getBoundingClientRect();
    const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
    if (hit && el.contains(hit)) return '';
    return 'covered by ' + (hit ? hit.id || hit.className || hit.tagName : 'nothing');
  },
  // Shared area in CSS pixels; zero when either element is not shown.
  overlap(first, second) {
    if (!this.visible(first) || !this.visible(second)) return 0;
    const a = this.element(first).getBoundingClientRect();
    const b = this.element(second).getBoundingClientRect();
    const width = Math.min(a.right, b.right) - Math.max(a.x, b.x);
    const height = Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y);
    return width > 0 && height > 0 ? Math.round(width * height) : 0;
  },
  layer(selector) {
    return Number(getComputedStyle(this.element(selector)).zIndex);
  },
  token(name) {
    return Number(getComputedStyle(document.documentElement).getPropertyValue(name));
  },
};
"""

failures = []
checks = 0


def check(condition, message):
    """Record one assertion; all failures are reported together at the end."""
    global checks
    checks += 1
    if not condition:
        failures.append(message)
        print('FAIL', message, flush=True)


def reachable(page, label, selectors):
    for selector in selectors:
        reason = page.evaluate('s => window.__overlay.reachable(s)', selector)
        check(reason == '', f'{label}: {selector} is {reason}')


def disjoint(page, label, pairs):
    for first, second in pairs:
        area = page.evaluate('([a, b]) => window.__overlay.overlap(a, b)', [first, second])
        check(area == 0, f'{label}: {first} overlaps {second} by {area} px²')


def layers(page, label, expected):
    """Each element must sit on the layer the stacking scale assigns to it."""
    for selector, token in expected:
        actual = page.evaluate('s => window.__overlay.layer(s)', selector)
        wanted = page.evaluate('t => window.__overlay.token(t)', token)
        check(actual == wanted, f'{label}: {selector} has z-index {actual}, scale says {token} = {wanted}')


def new_page(browser, size):
    context = browser.new_context(viewport={'width': size[0], 'height': size[1]})
    page = context.new_page()
    page.add_init_script(HELPERS)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    return page, errors


def replay(browser, size):
    label = f'replay {size[0]}x{size[1]}'
    page, errors = new_page(browser, size)
    page.goto(f'{BASE_URL}/?replay=demo_recording.json&nointro&quality=performance')
    page.wait_for_function('window.__replay?.() && document.querySelector("#flightCable")', timeout=timeout(120000))
    # Pause with a real, hit-tested click so the bar stays awake and the subtitle stays put.
    button = page.locator('#rpPlay').bounding_box()
    page.mouse.click(button['x'] + button['width'] / 2, button['y'] + button['height'] / 2)
    page.wait_for_function('document.querySelector("#rpPlay").textContent === "▶"', timeout=timeout(30000))
    line = page.evaluate('''async () => {
      const clip = (await (await fetch('demo_recording.json')).json()).clips[0];
      const longest = [...clip.script].sort((a, b) => b.text.length - a.text.length)[0];
      const start = clip.frames[0].t;
      return {fraction: (longest.t - start + 1) / (clip.frames.at(-1).t - start)};
    }''')
    page.evaluate('''fraction => {
      const seek = document.querySelector('#rpSeek');
      seek.value = Math.round(fraction * 1000);
      seek.dispatchEvent(new Event('input'));
    }''', line['fraction'])
    page.wait_for_function('!document.querySelector("#rpSub").hidden', timeout=timeout(60000))
    page.mouse.move(size[0] / 2, size[1] / 3)
    page.wait_for_timeout(500)
    reachable(page, label, ['#rpPlay', '#rpSeek', '#rpSpeed', '#camBtn', '#flightMapMode',
                            '#flightDrawer', '#flightDensity', '#flightHide'])
    disjoint(page, label, [
        ('#rpSub', '.readout'), ('#rpSub', '.rp-row'), ('#rpSub', '#rpClips'), ('#rpSub', '#flightTools'),
        ('#rpSub', '#flightMapBox'), ('#rpSub', '#flightDepth'), ('#rpSub', '.hud.tl'), ('#rpSub', '#tape'),
        ('.readout', '#replayBar'), ('.readout', '#flightMapBox'), ('.readout', '#flightTools'),
        ('#flightTools', '#replayBar'), ('#flightMapBox', '#replayBar'),
    ])
    layers(page, label, [('#rpSub', '--z-subtitle'), ('#replayBar', '--z-controls'), ('.hud.bc', '--z-hud'),
                         ('#flightTools', '--z-drawer-toggle'), ('#flightMapBox', '--z-hud')])
    # While the bar has faded out, the subtitle must not take the click meant to wake the play button.
    page.evaluate('document.querySelector("#replayBar").classList.add("idle")')
    hit = page.evaluate('''() => {
      const box = document.querySelector('#rpPlay').getBoundingClientRect();
      const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
      return hit ? hit.id : '';
    }''')
    check(hit != 'rpSub', f'{label}: the subtitle intercepts the play button while the bar is idle')
    check(page.evaluate('getComputedStyle(document.querySelector("#rpSub")).pointerEvents') == 'none',
          f'{label}: the subtitle accepts pointer events')
    check(not errors, f'{label}: page errors {errors}')
    page.context.close()


def campaign(browser, size):
    label = f'campaign {size[0]}x{size[1]}'
    page, errors = new_page(browser, size)
    # Exercise the node-based radio and engineering drawer from a returning player's checkpoint.
    page.add_init_script('''localStorage.setItem("rov.campaign.v1", JSON.stringify({
      completed: [], checkpoint: {chapter:"prologue", index:0}
    }))''')
    page.goto(f'{BASE_URL}/?play=1&nointro&mission=campaign&quality=performance'
              f'&ws={WS_URL}&room=overlay{time.time_ns()}')
    page.wait_for_function('window.__viewer?.S?.campaign && document.querySelector("#flightCable")',
                           timeout=timeout(120000))
    page.wait_for_function('''(() => {
      const radio = document.querySelector('.story-radio');
      return radio && !radio.hidden && window.__viewer.S.campaign.node?.type === 'dialogue';
    })()''', timeout=timeout(120000))
    wait_title_card_gone(page)
    # Let the typewriter finish, then stretch the line far beyond anything the chapters contain.
    page.wait_for_function('''(() => {
      const text = document.querySelector('.story-radio p').textContent;
      return text.length > 0 && text === window.__viewer.S.campaign.node.text;
    })()''', timeout=timeout(60000))
    page.evaluate('text => { document.querySelector(".story-radio p").textContent = text; }', LONG_LINE)
    page.wait_for_timeout(300)
    disjoint(page, label, [
        ('.story-radio', '#flightDepth'), ('.story-radio', '.readout'), ('.story-radio', '#tape'),
        ('.story-radio', '#flightMapBox'), ('.story-radio', '#flightTools'), ('.story-radio', '.hud.tl'),
        ('.story-radio', '#flightAttitude'), ('.story-radio', '#flightMission'),
    ])
    reachable(page, label, ['#camBtn', '#flightMapMode', '#flightDrawer', '#flightDensity', '#flightHide'])
    box = page.locator('.story-radio').bounding_box()
    check(box['x'] >= 0 and box['y'] >= 0 and box['x'] + box['width'] <= size[0]
          and box['y'] + box['height'] <= size[1], f'{label}: the radio leaves the viewport {box}')
    layers(page, label, [('.story-radio', '--z-story'), ('#flightPeek', '--z-notice'),
                         ('#flightWarning', '--z-notice'), ('#flightDepth', '--z-hud')])
    # The engineering drawer is opened on purpose and must cover the radio, not the other way round.
    drawer = page.locator('#flightDrawer').bounding_box()
    page.mouse.click(drawer['x'] + drawer['width'] / 2, drawer['y'] + drawer['height'] / 2)
    page.wait_for_selector('#engineering', state='visible', timeout=timeout(30000))
    reachable(page, label + ' drawer', ['#engineering > button'])
    layers(page, label + ' drawer', [('#engineering', '--z-drawer')])
    covered = page.evaluate('''() => {
      const radio = document.querySelector('.story-radio').getBoundingClientRect();
      const panel = document.querySelector('#engineering').getBoundingClientRect();
      const x = (Math.max(radio.x, panel.x) + Math.min(radio.right, panel.right)) / 2;
      const y = (Math.max(radio.y, panel.y) + Math.min(radio.bottom, panel.bottom)) / 2;
      if (Math.max(radio.x, panel.x) >= Math.min(radio.right, panel.right)) return true;
      if (Math.max(radio.y, panel.y) >= Math.min(radio.bottom, panel.bottom)) return true;
      const hit = document.elementFromPoint(x, y);
      return !!hit && document.querySelector('#engineering').contains(hit);
    }''')
    check(covered, f'{label}: the radio shows through the engineering drawer')
    page.locator('#engineering > button').click()
    check(not errors, f'{label}: page errors {errors}')
    page.context.close()


def centred(page, selector):
    """Scroll the control to the middle of its screen and wait out the screen's fade-in."""
    page.evaluate('s => document.querySelector(s).scrollIntoView({block: "center"})', selector)
    page.wait_for_function('s => window.__overlay.visible(s)', arg=selector, timeout=timeout(10000))


def menu(browser, size):
    """Every step of the launch flow keeps its controls reachable above the 3D stage and the footer."""
    label = f'menu {size[0]}x{size[1]}'
    page, errors = new_page(browser, size)
    page.goto(f'{BASE_URL}/?ws={WS_URL}&quality=performance')
    page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    layers(page, label, [('#launchMenu', '--z-menu')])
    centred(page, '#titleStart')
    reachable(page, label + ' title', ['#titleStart'])
    page.click('#titleStart')
    wait_screen(page, 'main')
    centred(page, '#entry-resume')
    first_level = ['#entry-resume', '#entry-story', '#entry-training', '#entry-settings', '#entry-exit']
    reachable(page, label + ' main', first_level)
    open_internal(page)
    for selector in ['#entry-dive', '#internal-settings', '#menuCollection']:
        centred(page, selector)
        reachable(page, label + ' main', [selector])
    page.locator('#menuCollection').click()
    page.wait_for_selector('dialog.collection-panel[open]', timeout=timeout(30000))
    reachable(page, label + ' collection', ['.collection-close'])
    page.locator('.collection-close').click()
    to_briefing(page, mode='free_explore', site='coral_reef')
    centred(page, '#startDive')
    reachable(page, label + ' briefing', ['#startDive'])
    check(not errors, f'{label}: page errors {errors}')
    page.context.close()


def scale_order(browser):
    """The scale itself must stay ordered the way its comment documents."""
    page, _ = new_page(browser, SIZES[0])
    page.goto(f'{BASE_URL}/?ws={WS_URL}&quality=performance', wait_until='domcontentloaded')
    names = ['--z-scene-mark', '--z-hud', '--z-hud-alert', '--z-pip', '--z-subtitle', '--z-story', '--z-notice',
             '--z-controls', '--z-banner', '--z-drawer', '--z-blocker', '--z-menu', '--z-toast']
    values = [page.evaluate('t => window.__overlay.token(t)', name) for name in names]
    check(all(a < b for a, b in zip(values, values[1:])), f'stacking scale is not ascending: {values}')
    page.context.close()


def run():
    with sync_playwright() as playwright:
        browser = launch(playwright)
        scale_order(browser)
        for size in SIZES:
            replay(browser, size)
            campaign(browser, size)
            menu(browser, size)
        browser.close()
    if failures:
        print(f'Overlay smoke FAILED: {len(failures)} of {checks} checks')
        for failure in failures:
            print(' -', failure)
        sys.exit(1)
    print(f'Overlay smoke passed: {checks} checks at {", ".join(f"{w}x{h}" for w, h in SIZES)} '
          '(replay, campaign, engineering drawer, menu, collection panel).')


if __name__ == '__main__':
    run()
