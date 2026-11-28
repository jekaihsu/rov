"""S1 small-fix checks: Esc opens pause during the deck checklist; first-dive guide is not duplicated.

Browser and server addresses come from _browser.py.
"""
import time

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base


def run():
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.set_default_timeout(timeout(60000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        # Fresh profile: onboarding owns the first-dive checklist; the objective card must not mirror it.
        page.add_init_script("""() => {
          localStorage.clear();
          localStorage.setItem('rov.onboarding.v1', JSON.stringify({enabled: true}));
        }""")
        page.goto(f'{http_base()}/?play=1&fidelity=assisted&procedure=quick&nointro&quality=performance'
                  f'&room=s1{time.time_ns()}&ws={ws_base()}')
        page.wait_for_function('window.__viewer?.S?.pos', timeout=timeout(90000))
        page.wait_for_timeout(1500)
        assert page.locator('#objectiveCard .objective-guide').count() == 0, \
            'objective card must not duplicate the first-dive checklist'

        # Full deck procedure: Esc during the checklist opens the pause menu.
        page.goto(f'{http_base()}/?play=1&fidelity=real&procedure=full&quality=performance'
                  f'&room=s1deck{time.time_ns()}&ws={ws_base()}')
        page.wait_for_selector('#procedurePanel:not([hidden])', timeout=timeout(90000))
        page.wait_for_function('window.__intro?.()?.held === true', timeout=timeout(90000))
        page.keyboard.press('Escape')
        page.wait_for_selector('#pauseMenu:not([hidden])', timeout=timeout(15000))
        assert page.evaluate('!document.getElementById("procedurePanel").hidden'), \
            'checklist stays visible under the pause menu'
        page.keyboard.press('Escape')
        page.wait_for_selector('#pauseMenu', state='hidden', timeout=timeout(15000))

        assert not errors, errors
        browser.close()
    print('S1 smoke passed: Esc opens pause on deck; first-dive guide is not duplicated.')


if __name__ == '__main__':
    run()
