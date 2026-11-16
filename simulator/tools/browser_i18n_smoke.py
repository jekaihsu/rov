"""Four-language title-to-briefing, HUD and real prologue results checks at both supported sizes."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, set_intro, wait_ready, wait_screen, wait_title_card_gone
from browser_results_smoke import play_prologue

OUT = Path(__file__).resolve().parents[2] / 'docs/i18n/screenshots'
OUT.mkdir(parents=True, exist_ok=True)


def capture(page, language, screen):
    for width, height in [(1280, 720), (1600, 900)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(300)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (language, screen, width)
        issues = page.locator('#launchMenu button:visible, #resultsScreen button:visible').evaluate_all('''nodes =>
            nodes.filter(node => {
                const r = node.getBoundingClientRect();
                return r.left < -1 || r.right > innerWidth + 1 || r.top < -1 || r.bottom > innerHeight + 1
                    || node.scrollWidth > node.clientWidth + 2;
            }).map(node => ({id:node.id, text:node.textContent}))''')
        assert not issues, (language, screen, width, issues)
        if screen == 'results':
            assert page.locator('.results-actions').evaluate('''node =>
                node.getBoundingClientRect().bottom <
                document.querySelector('.results-footer').getBoundingClientRect().top'''), (language, width)

        page.screenshot(path=str(OUT / f'{language}-{screen}-{width}.jpg'), type='jpeg', quality=75)


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        for language in ['zh-Hant', 'en', 'zh-Hans', 'ja']:
            page = browser.new_page(viewport={'width': 1600, 'height': 900}, locale='zh-TW')
            errors = []
            def page_error(error):
                errors.append(str(error))

            page.on('pageerror', page_error)
            page.goto(f'{http_base()}/?lang={language}&nointro&mission=campaign&control=UAV_CHN'
                      f'&quality=performance&model=bluerov2_heavy&room=i18n{time.time_ns()}&ws={ws_base()}')
            wait_ready(page)
            assert page.locator('html').get_attribute('lang') == language
            capture(page, language, 'title')
            open_main(page)
            capture(page, language, 'menu')
            page.click('#entry-story')
            page.click('[data-chapter="prologue"]')
            page.click('#hangarNext')
            wait_screen(page, 'briefing')
            expected = {'zh-Hant': '下水', 'en': 'Deploy', 'zh-Hans': '下水', 'ja': '着水'}
            assert page.locator('#startDive > span').last.inner_text() == expected[language]
            capture(page, language, 'briefing')
            set_intro(page, False)
            page.click('#startDive')
            page.wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=timeout(90000))
            # The chapter title card (brand/chapter_card.js) covers the HUD and takes the first key press.
            wait_title_card_gone(page)
            page.wait_for_timeout(1500)
            capture(page, language, 'hud')
            play_prologue(page)
            page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(15000))
            capture(page, language, 'results')
            assert not errors, errors
            page.close()
        browser.close()
    print('Four-language title, briefing, HUD and results checks passed:', OUT)


if __name__ == '__main__':
    run()
