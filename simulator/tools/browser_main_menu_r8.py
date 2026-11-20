"""Walk the first-level menu in both desktop editions and check the corresponding player surfaces."""
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen


def walk(browser, edition):
    page = browser.new_page(viewport={'width': 1366, 'height': 768})
    page.add_init_script(f"window.rovDesktop = {{edition: '{edition}', rememberModel() {{}}}}")
    page.goto(f'{http_base()}/?ws={ws_base()}&quality=performance&menu=main')
    open_main(page)
    assert page.locator('.field-actions button').evaluate_all('els => els.map(el => el.id)') == [
        'entry-resume', 'entry-story', 'entry-training', 'entry-settings', 'entry-exit']
    retail = edition == 'steam'
    page.click('#entry-resume')
    wait_screen(page, 'contract')
    page.keyboard.press('Escape')
    page.click('#entry-story')
    page.wait_for_selector('#journalReplay')
    assert page.locator('.field-order[aria-disabled=true]').count()
    page.keyboard.press('Escape')
    page.click('#entry-training')
    assert page.locator('#training-tab-internal').count() == int(not retail)
    assert page.locator('#training-tab-story').count() == int(not retail)
    for selector in ['#entry-dive', '#entry-multiplayer', '#shop-tab-cosmetic', '[data-sticker]']:
        assert bool(page.locator(selector).count()) != retail, selector
    page.keyboard.press('Escape')
    page.click('#entry-settings')
    assert bool(page.locator('[data-fidelity-item="aiOverlay"]').count()) != retail
    page.keyboard.press('Escape')
    page.evaluate('window.close = () => {window.exitRequested = true}')
    page.click('#entry-exit')
    assert page.evaluate('window.exitRequested')
    page.goto(f'{http_base()}/instructor/instructor.html')
    if retail:
        wait_screen(page, 'main', timeout=90000)
    else:
        assert page.title() == '教官台'
    page.goto(f'{http_base()}/?play=1&ws={ws_base()}&room=r8{edition}&quality=performance&nointro')
    page.wait_for_function('window.__viewer?.S && document.querySelector("#engineering")',
                           timeout=timeout(90000))
    assert page.locator('#flightDrawer').is_visible() != retail
    page.keyboard.press('Tab')
    assert page.locator('#engineering').is_visible() != retail
    if retail:
        page.goto(f'{http_base()}/?menu=main&quality=performance')
        wait_screen(page, 'main', timeout=90000)
        page.evaluate('''() => {
          const save = window.__menu.career;
          save.contracts.c2_net_inspection = {completed: 1, medal: 'gold', best: 95};
          localStorage.setItem('rov.career.v1', JSON.stringify(save));
        }''')
        page.reload()
        wait_screen(page, 'main', timeout=90000)
        assert page.evaluate('window.__menu.scene') == 'aquaculture_pen'
        frames = page.evaluate('window.__menu.renderer.info.render.frame')
        page.wait_for_timeout(500)
        assert page.evaluate('window.__menu.renderer.info.render.frame') == frames
        page.click('#entry-story')
        page.click('#journal-tab-ch2')
        assert page.locator('[data-order="c2_net_inspection"]').get_attribute('data-medal') == 'gold'
    page.close()


if __name__ == '__main__':
    with sync_playwright() as pw:
        browser = launch(pw)
        for edition in ('steam', 'internal'):
            walk(browser, edition)
        browser.close()
    print('Steam and internal menu walks passed')
