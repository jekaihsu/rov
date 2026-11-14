"""Verify the legacy quick-launch animation and nointro bypass remain available."""
from shutil import which
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=which('chromium'), headless=True,
                                args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    base = ('http://127.0.0.1:8092/?play=1&procedure=quick&quality=performance'
            '&model=bluerov2_heavy&ws=ws://127.0.0.1:8792')
    page.goto(base + '&room=t23-animation')
    page.wait_for_function('window.__intro?.()?.starts > 0', timeout=90000)
    assert not page.evaluate('window.__viewer.S.procedure.active')
    page.evaluate('document.querySelector("#skipIntro").click()')
    page.wait_for_function('!window.__intro().playing')
    page.goto(base + '&room=t23-nointro&nointro')
    page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=90000)
    assert page.evaluate('window.__intro()') is None
    assert not page.evaluate('window.__viewer.S.procedure.active')
    assert not errors, errors
    browser.close()
print('Quick-launch animation, skip and ?nointro compatibility passed.')
