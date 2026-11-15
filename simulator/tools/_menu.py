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


def soft_click(page, selector):
    """Activate a control without waiting on soft-GL paint frames (Playwright actionability stalls under load)."""
    page.locator(selector).click(force=True, no_wait_after=True)


def open_main(page):
    """From the title screen (or any screen reached from it) to the main menu."""
    wait_ready(page)
    if page.evaluate('window.__menu.screen') == 'title':
        soft_click(page, '#titleStart')
    else:
        page.evaluate('window.__menu.go("main")')
    wait_screen(page, 'main')


def set_intro(page, enabled):
    page.locator('#menuIntro').evaluate(
        '(el, value) => { el.checked = value; el.dispatchEvent(new Event("change", {bubbles: true})); }', enabled)


def to_briefing(page, mode='free_explore', site='coral_reef', model=None, sticker=None):
    """Main menu → 開始潛航 → mode → hangar → site → briefing. scenario_training picks the site from the list."""
    open_main(page)
    soft_click(page, '#entry-dive')
    wait_screen(page, 'modes')
    soft_click(page, f'[data-mode="{mode}"]')
    if mode == 'scenario_training':
        wait_screen(page, 'training')
        soft_click(page, f'[data-scenario="{site}"]')
    wait_screen(page, 'hangar')
    if model:
        soft_click(page, f'[data-vehicle="{model}"]')
        page.wait_for_function('id => window.__menu.ready && window.__menu.model === id', arg=model,
                               timeout=scaled(90000))
    if sticker:
        soft_click(page, f'[data-sticker="{sticker}"]')
    soft_click(page, '#hangarNext')
    if mode != 'scenario_training':
        wait_screen(page, 'sites')
        soft_click(page, f'[data-site="{site}"]')
    wait_screen(page, 'briefing')


def open_settings_tab(page, tab):
    open_main(page)
    soft_click(page, '#entry-settings')
    wait_screen(page, 'settings')
    soft_click(page, f'#menuSettings-tab-{tab}')


def launch_from_menu(page, intro=False, **choice):
    to_briefing(page, **choice)
    set_intro(page, intro)
    soft_click(page, '#startDive')
