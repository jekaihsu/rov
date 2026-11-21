"""Verify the YX identity in the game: marks on the title and loading block, fleet symbols in the hangar and
briefing, the chapter title card (appears when the prologue starts, leaves on a key press and on its own), and the
?brandDemo component sheet with the licence certificate.
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_ready, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'brand-validation'
MODELS = {'x1': 'R', 'bluerov2_heavy': 'O', 'falcon': 'V'}
ACCENT = 'rgb(255, 122, 47)'
CARD = '.brand-card-overlay'
# How long the card stays without input: 3.5 s plus the 0.4 s fade (brand/chapter_card.js).
CARD_TOTAL_MS = 3900
# Everything the check needs from the card, read in one call because the card only stays a few seconds.
CARD_FACTS = '''() => {
  const card = document.querySelector('.brand-card-overlay');
  if (!card) return null;
  return {
    chapter: window.__brandCard.last,
    title: card.querySelector('.brand-card-title').textContent,
    number: card.querySelector('.brand-card-number').textContent,
    symbols: card.querySelectorAll('svg[data-symbol="pool"]').length,
    inGame: document.documentElement.classList.contains('in-game'),
    covers: card.getBoundingClientRect().width === innerWidth
      && card.getBoundingClientRect().height === innerHeight,
  };
}'''
CARD_DONE = 'window.__brandCard?.dismissed && !document.querySelector(".brand-card-overlay")'


def check_menu(page, base):
    page.goto(f'{base}/?ws={ws_base(8792)}&room=brand{time.time_ns()}')
    assert page.locator('#brandLoadingMark svg.yx-mark').count() == 1, 'loading block carries the mark'
    wait_ready(page)
    assert page.evaluate('window.__menu.screen') == 'title'
    mark = page.locator('.menu-title-block .brand-lockup svg.yx-mark-tether')
    assert mark.is_visible(), 'title shows the YX mark'
    assert mark.bounding_box()['height'] >= 60, mark.bounding_box()
    assert page.locator('.menu-title').text_content() == 'ROV Solution'
    # One orange primary action on the title; the mark's accent is a stroke, not a filled control.
    filled = page.evaluate('''accent => [...document.querySelectorAll('.menu-screen[data-screen=title] button')]
      .filter(button => getComputedStyle(button).backgroundColor === accent).map(button => button.id)''', ACCENT)
    assert filled == ['titleStart'], filled
    page.screenshot(path=str(OUT / 'title.png'))
    open_main(page)
    assert page.locator('.menu-brand svg.yx-mark-compact').is_visible(), 'header shows the compact mark'
    page.click('#entry-dive')
    wait_screen(page, 'modes')
    page.click('[data-mode="free_explore"]')
    wait_screen(page, 'hangar')
    for model, letter in MODELS.items():
        chip = page.locator(f'[data-vehicle="{model}"]')
        assert chip.locator(f'svg[data-symbol="{letter}"]').count() == 1, f'chip symbol for {model}'
        chip.click()
        page.wait_for_selector(f'.menu-vehicle-title .brand-fleet-symbol[data-model="{model}"] '
                               f'svg[data-symbol="{letter}"]', timeout=timeout(30000))
        assert page.locator('.menu-vehicle-title .brand-fleet-symbol').count() == 1
        name = page.locator('.menu-vehicle-name').text_content()
        assert name == f'YX Model {letter} · Block 1', name
    page.screenshot(path=str(OUT / 'hangar.png'))
    page.click('#hangarNext')
    wait_screen(page, 'sites')
    page.click('[data-site="coral_reef"]')
    wait_screen(page, 'briefing')
    kicker = page.locator('.menu-briefing-main .menu-kicker')
    assert kicker.locator('svg[data-symbol="V"]').count() == 1, 'briefing kicker carries the symbol'
    assert 'YX Model V · Block 1' in kicker.text_content(), kicker.text_content()
    page.screenshot(path=str(OUT / 'briefing.png'))


def start_prologue(page, base):
    # A node-format save still opens with the chapter card. New games have the directed pool shot.
    page.add_init_script('''localStorage.setItem("rov.campaign.v1", JSON.stringify({
      completed: [], checkpoint: {chapter:"prologue", index:0}
    }))''')
    page.goto(f'{base}/?play=1&nointro&mission=campaign&chapter=prologue&quality=performance'
              f'&room=brand{time.time_ns()}&ws={ws_base(8792)}')
    facts = page.wait_for_function(CARD_FACTS, timeout=timeout(120000)).json_value()
    assert facts == {'chapter': 'prologue', 'title': '見習之前', 'number': '序章 / 00', 'symbols': 2,
                     'inGame': True, 'covers': True}, facts


def check_chapter_card(page, base):
    # Real preset (the default): the card appears as the dive page starts, before the pilot has flown.
    start_prologue(page, base)
    page.keyboard.press('KeyK')
    page.wait_for_function(CARD_DONE, timeout=timeout(10000))
    report = page.evaluate('window.__brandCard')
    assert report['dismissed'] == 'key' and report['shown'] == 1, report
    # Without input it leaves by itself after its duration and does not come back.
    start_prologue(page, base)
    page.wait_for_function(CARD_DONE, timeout=timeout(20000))
    report = page.evaluate('window.__brandCard')
    assert report['dismissed'] == 'timeout' and report['shown'] == 1, report
    # The page is still building the scene while the card is up; a busy main thread can only delay the timer.
    assert CARD_TOTAL_MS - 100 <= report['visibleMs'] <= CARD_TOTAL_MS + timeout(4000), report
    page.wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=timeout(60000))
    page.wait_for_timeout(1500)
    assert page.locator(CARD).count() == 0
    assert page.evaluate('window.__brandCard.shown') == 1
    return report['visibleMs']


def check_demo(page, base):
    page.goto(f'{base}/?brandDemo')
    page.wait_for_selector('#brandDemo .brand-licence', timeout=timeout(90000))
    grades = page.evaluate('[...document.querySelectorAll("#brandDemo .brand-licence")].map(el => el.dataset.grade)')
    assert grades == ['trainee', 'grade2', 'grade1', 'senior', 'supervisor'], grades
    titles = page.locator('#brandDemo .brand-licence-grade').all_text_contents()
    assert titles == ['見習駕駛員', '二級駕駛員', '一級駕駛員', '資深駕駛員', '主管'], titles
    assert page.locator('#brandDemo .brand-licence .yx-mark').count() == 5
    assert page.locator('#brandDemo .brand-demo-card .brand-card').count() == 3
    page.locator('#brandDemo .brand-licence').first.scroll_into_view_if_needed()
    page.screenshot(path=str(OUT / 'demo-licence.png'))
    page.click('.brand-demo-close')
    assert page.locator('#brandDemo').count() == 0


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    base = http_base(8092)
    with sync_playwright() as p:
        browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        check_menu(page, base)
        elapsed = check_chapter_card(page, base)
        check_demo(page, base)
        assert not errors, errors
        (OUT / 'results.json').write_text(json.dumps({
            'title_mark': True, 'hangar_symbols': list(MODELS), 'briefing_symbol': True,
            'chapter_card_key_dismiss': True, 'chapter_card_timeout_ms': round(elapsed),
            'brand_demo_licences': 5, 'page_errors': 0,
        }, indent=2), encoding='utf8')
        browser.close()
    print('browser_brand_smoke ok')


if __name__ == '__main__':
    run()
