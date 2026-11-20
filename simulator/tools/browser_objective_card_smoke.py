"""Contracts and the first-dive checklist are reachable without the engineering drawer.

Main menu YX 委託看板 → 海洋探索委託 → expedition sea → dive; the in-flight objective card lists the contracts on offer and the
first-dive checklist, accepting a contract from the card starts it, and the drawer is never opened.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base
from _menu import open_internal, set_intro, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'objective-card-validation'
OUT.mkdir(parents=True, exist_ok=True)


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        # Clicks and waits follow ROV_BROWSER_TIMEOUT_SCALE; the default scale leaves CI timing unchanged.
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=card{time.time_ns()}&quality=performance'
                  '&fidelity=assisted')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        open_internal(page)
        page.click('#entry-contracts')
        wait_screen(page, 'board')
        page.click('#board-tab-other')
        page.click('#boardExpedition')
        wait_screen(page, 'hangar')
        assert page.evaluate('window.__menu.mission') == 'expedition'
        page.click('#hangarNext')
        wait_screen(page, 'sites')
        page.click('[data-site="coral_reef"]')
        wait_screen(page, 'briefing')
        set_intro(page, False)
        page.click('#startDive')
        page.wait_for_function('window.__viewer?.S?.mission?.mode === "expedition"', timeout=timeout(90000))
        page.wait_for_selector('#objectiveCard:not([hidden]) [data-contract="inspect"]', timeout=timeout(30000))
        assert page.locator('#objectiveCard .objective-guide li').count() == 4, 'first-dive checklist'
        assert page.locator('#engineering').is_hidden(), 'the drawer stays closed'
        page.click('#objectiveCard [data-contract="inspect"]')
        page.wait_for_function('window.__viewer.S.expedition.active?.kind === "inspect"', timeout=timeout(30000))
        page.wait_for_function('document.querySelector("#objectiveCard .objective-active")', timeout=timeout(5000))
        page.screenshot(path=str(OUT / 'contract-active.jpg'), type='jpeg', quality=80)
        page.click('#objectiveToggle')
        assert page.locator('#objectiveCard .objective-body').is_hidden(), 'the card collapses'
        assert not errors, errors
        browser.close()
    print('Objective card smoke passed:', OUT)


if __name__ == '__main__':
    run()
