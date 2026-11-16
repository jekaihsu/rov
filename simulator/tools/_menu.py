"""Shared launch-menu walk for the browser checks: real clicks through title, main menu, mode, hangar, dive site and
briefing (simulator/viewer/menu/). Scripts that only need to get into the water call launch_from_menu(); scripts
that check the menu itself use the smaller steps.
"""
from _browser import timeout as scaled

READY = 'window.__menu?.ready'


def wait_ready(page, timeout=90000):
    page.wait_for_function(READY, timeout=scaled(timeout))


def wait_screen(page, name, timeout=30000):
    page.wait_for_function('name => window.__menu?.screen === name', arg=name, timeout=scaled(timeout))


def dismiss_new_game(page, preset='real'):
    """Confirm the first-run difficulty screen when it appears (fresh localStorage)."""
    if page.evaluate('window.__menu?.screen') != 'new_game':
        return
    page.click(f'#newGame-{preset}')
    page.locator('#newGameConfirm').click(timeout=scaled(30000))
    page.wait_for_function('window.__menu?.screen !== "new_game"', timeout=scaled(30000))


def open_main(page):
    """From the title screen (or any screen reached from it) to the main menu."""
    wait_ready(page)
    if page.evaluate('window.__menu.screen') == 'title':
        page.click('#titleStart')
        dismiss_new_game(page)
    elif page.evaluate('window.__menu.screen') == 'new_game':
        dismiss_new_game(page)
    else:
        page.evaluate('window.__menu.go("main")')
    wait_screen(page, 'main')


def set_intro(page, enabled):
    page.locator('#menuIntro').evaluate(
        '(el, value) => { el.checked = value; el.dispatchEvent(new Event("change", {bubbles: true})); }', enabled)


def to_briefing(page, mode='free_explore', site='coral_reef', model=None, sticker=None):
    """Main menu → 開始潛航 → mode → hangar → site → briefing. scenario_training picks the site from the list."""
    open_main(page)
    page.click('#entry-dive')
    wait_screen(page, 'modes')
    page.click(f'[data-mode="{mode}"]')
    if mode == 'scenario_training':
        wait_screen(page, 'training')
        page.click(f'[data-scenario="{site}"]')
    wait_screen(page, 'hangar')
    if model:
        page.click(f'[data-vehicle="{model}"]')
        page.wait_for_function('id => window.__menu.ready && window.__menu.model === id', arg=model,
                               timeout=scaled(90000))
    if sticker:
        page.click(f'[data-sticker="{sticker}"]')
    page.click('#hangarNext')
    if mode != 'scenario_training':
        wait_screen(page, 'sites')
        page.click(f'[data-site="{site}"]')
    wait_screen(page, 'briefing')


def open_settings_tab(page, tab):
    open_main(page)
    page.click('#entry-settings')
    wait_screen(page, 'settings')
    page.click(f'#menuSettings-tab-{tab}')


def launch_from_menu(page, intro=False, **choice):
    to_briefing(page, **choice)
    set_intro(page, intro)
    page.click('#startDive')
