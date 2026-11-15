"""Verify the reservoir can be selected by the ordinary launch URL, with no replay fixture."""
from playwright.sync_api import sync_playwright
from _browser import launch
from browser_scene_review import open_site


def main():
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        page, errors = open_site(browser, 'reservoir_intake', 'performance')
        state = page.evaluate('({world:window.__viewer.W.scenario,state:window.__viewer.S})')
        assert state['world']['visibility_m'] == 3
        assert state['world']['water_type'] == 'fresh_green'
        assert state['world']['camera_anchors']['dock_equipment']
        assert not errors, errors
        browser.close()
    print('Reservoir live launch passed')


if __name__ == '__main__':
    main()
