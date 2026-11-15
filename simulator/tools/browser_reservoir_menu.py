"""Capture the reservoir card and both named surface cameras in the simulator's native menu stage."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, timeout
from capture_site_previews import main as capture_cards

OUT = Path(__file__).resolve().parents[2] / 'docs/design/scenes/reservoir'


def main():
    capture_cards(['reservoir_intake'])
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base()}/?quality=medium')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
        page.evaluate("window.__menu.go('sites')")
        page.evaluate("window.__menu.pose('preview')")
        page.evaluate("window.__menu.configure({scenario:'reservoir_intake'})")
        page.wait_for_function("window.__menu.ready && window.__menu.scene === 'reservoir_intake'",
                               timeout=timeout(60000))
        page.add_style_tag(content='.menu-stack,.menu-header,.menu-footer,.menu-shade{display:none!important}')
        for name in ('embankment_overlook', 'dock_equipment'):
            page.evaluate('name => window.__menu.pose(name)', name)
            page.wait_for_timeout(3000)
            page.screenshot(path=str(OUT / (name.replace('_', '-') + '.jpg')), type='jpeg', quality=85)
        assert not errors, errors
        browser.close()
    print('Both named reservoir menu cameras captured at 1600x900')


if __name__ == '__main__':
    main()
