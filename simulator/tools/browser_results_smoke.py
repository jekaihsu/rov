"""Results screen: the story prologue ends on the results card, and 下一章 starts chapter one.

Launches the prologue from the menu, drives it with physical key presses (as browser_campaign_smoke.py does),
then checks the results card: outcome, medal, score rows, rewards earned, the local best-score record and
gamepad/keyboard focus on the actions. Pressing the primary action must start the next story chapter. Finally
the story cards in the menu must show the chapter's medal and best score, and chapter one unlocked.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, set_intro, wait_screen, wait_title_card_gone
from browser_prologue_smoke import play_prologue

OUT = Path(__file__).resolve().parents[1] / 'output' / 'results-validation'
OUT.mkdir(parents=True, exist_ok=True)


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        # Clicks and waits follow ROV_BROWSER_TIMEOUT_SCALE; the default scale leaves CI timing unchanged.
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base(8092)}/?nointro&mission=campaign&control=UAV_CHN&room=results{time.time_ns()}'
                  f'&quality=performance&model=bluerov2_heavy&ws={ws_base(8792)}')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        open_main(page)
        page.click('#entry-story')
        page.click('[data-chapter="prologue"]')
        page.click('#hangarNext')
        wait_screen(page, 'briefing')
        set_intro(page, False)
        page.click('#startDive')
        page.wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=timeout(90000))
        wait_title_card_gone(page)
        assert page.locator('#resultsScreen').is_hidden(), 'no results card while flying'
        play_prologue(page)
        page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(15000))
        outcome = page.evaluate('window.__results.outcome')
        assert outcome['kind'] == 'chapter' and outcome['id'] == 'prologue', outcome
        assert outcome['success'] and outcome['medal'] in ('gold', 'silver', 'bronze'), outcome
        assert outcome['next']['id'] == 'harbor', outcome
        assert any('首次下潛' in text for text in outcome['rewards']), outcome['rewards']
        assert page.locator('#resultsHeading').inner_text() == '任務完成'
        for row in ['objectives', 'time', 'tether', 'contacts']:
            assert page.locator(f'.results-rows tr[data-row="{row}"]').count() == 1, row
        assert page.locator('.results-rewards li').count() >= 1
        for button in ['resultsNext', 'resultsRetry', 'resultsDebrief', 'resultsMenu']:
            assert page.locator('#' + button).is_visible(), button
        assert not page.locator('#resultsDebrief').is_disabled(), 'the flight was recorded for the debrief'
        record = page.evaluate('JSON.parse(localStorage.getItem("rov.results.v1"))["chapter:prologue"]')
        assert record['best'] == outcome['score'], record
        page.wait_for_function('document.activeElement?.id === "resultsNext"', timeout=timeout(5000))
        page.screenshot(path=str(OUT / 'prologue-results.jpg'), type='jpeg', quality=80)
        # Flight input is blocked while the card is up; the arrow keys move focus instead.
        page.keyboard.press('ArrowRight')
        page.wait_for_function('document.activeElement?.id === "resultsRetry"', timeout=timeout(5000))
        page.keyboard.press('ArrowLeft')
        page.keyboard.press('Enter')
        page.wait_for_selector('#resultsScreen', state='hidden', timeout=timeout(5000))
        page.wait_for_function('window.__viewer.S.campaign.chapter === "harbor" && '
                               'window.__viewer.S.campaign.status === "active"', timeout=timeout(30000))
        page.click('#flightDrawer')
        page.click('#returnMenu')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        open_main(page)
        page.click('#entry-story')
        wait_screen(page, 'training')
        card = page.locator('[data-chapter="prologue"]')
        assert card.get_attribute('data-medal') == outcome['medal'], card.get_attribute('data-medal')
        assert str(outcome['score']) in card.inner_text(), card.inner_text()
        assert page.locator('[data-chapter="harbor"]').is_enabled()
        page.screenshot(path=str(OUT / 'story-after.jpg'), type='jpeg', quality=80)
        assert not errors, errors
        browser.close()
    print('Results screen smoke passed:', OUT)


if __name__ == '__main__':
    run()
