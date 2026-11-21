"""Walk the first-level menu in both desktop editions and check the corresponding player surfaces."""
import json

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, wait_screen
from browser_playstation_smoke import CIRCLE, CROSS, DOWN, FAKE_PAD, L1, PROFILES, R1, press, press_until, wait_focus


def choose_entry(page, entry):
    wait_focus(page, 'entry-resume')
    press_until(page, DOWN, 'entry-' + entry)
    press(page, CROSS)


def walk(browser, edition):
    page = browser.new_page(viewport={'width': 1366, 'height': 768})
    page.add_init_script(f"window.rovDesktop = {{edition: '{edition}', rememberModel() {{}}}}")
    page.add_init_script(FAKE_PAD + '\nwindow.__setPs(' + json.dumps(PROFILES['dualsense_standard']) + ');')
    page.goto(f'{http_base()}/?ws={ws_base()}&quality=performance&menu=main')
    open_main(page)
    assert page.locator('.field-actions button').evaluate_all('els => els.map(el => el.id)') == [
        'entry-resume', 'entry-story', 'entry-training', 'entry-settings', 'entry-exit']
    retail = edition == 'steam'
    choose_entry(page, 'resume')
    wait_screen(page, 'contract')
    press(page, CIRCLE)
    choose_entry(page, 'story')
    page.wait_for_selector('#journalReplay')
    press(page, R1)
    wait_focus(page, 'journal-tab-ch1')
    press(page, L1)
    wait_focus(page, 'journal-tab-prologue')
    assert page.locator('.field-order[aria-disabled=true]').count()
    press(page, CIRCLE)
    choose_entry(page, 'training')
    assert page.locator('#training-tab-internal').count() == int(not retail)
    assert page.locator('#training-tab-story').count() == int(not retail)
    for selector in ['#entry-dive', '#entry-multiplayer', '#shop-tab-cosmetic', '[data-sticker]']:
        assert bool(page.locator(selector).count()) != retail, selector
    press(page, CIRCLE)
    choose_entry(page, 'settings')
    assert bool(page.locator('[data-fidelity-item="aiOverlay"]').count()) != retail
    press(page, CIRCLE)
    page.evaluate('window.close = () => {window.exitRequested = true}')
    choose_entry(page, 'exit')
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
          // Finish prologue + chapter 1 and the first farm job so continue is another aquaculture pen dive.
          save.licence = 'grade2';
          save.owned = Array.from(new Set([...(save.owned || []), 'gripper', 'imaging_sonar', 'laser_scaler']));
          for (const id of ['p0_induction', 'p1_pool_checkout', 'p2_open_water',
                            'c1_pier_level1', 'c1_pier_level2', 'c1_hull_fouling', 'c1_dropped_object',
                            'c2_net_inspection']) {
            save.contracts[id] = {completed: 1, medal: id === 'c2_net_inspection' ? 'gold' : 'silver', best: 90};
          }
          localStorage.setItem('rov.career.v1', JSON.stringify(save));
        }''')
        page.reload()
        wait_screen(page, 'main', timeout=90000)
        assert page.evaluate('window.__menu.scene') == 'aquaculture_pen'
        assert '死魚' in page.locator('.field-title').inner_text()
        frames = page.evaluate('window.__menu.renderer.info.render.frame')
        page.wait_for_timeout(500)
        assert page.evaluate('window.__menu.renderer.info.render.frame') == frames
        choose_entry(page, 'story')
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
