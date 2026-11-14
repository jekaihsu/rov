"""Capture deterministic hangar and in-game comparisons for T11a review."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / 'docs/assets/T11a'
BASE = 'http://127.0.0.1:8092'
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME_PATH'), channel=None if os.environ.get('CHROME_PATH') else 'chrome', args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    for identifier in ['x1', 'falcon', 'bluerov2_heavy']:
        page.goto(f'{BASE}/model-preview.html?model={identifier}')
        page.wait_for_function('window.__modelPreview?.model && !window.__modelPreview.model.loadError')
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / f'{identifier}-turntable.png'))
        page.get_by_text('Wireframe', exact=True).click()
        page.screenshot(path=str(OUT / f'{identifier}-wire.png'))
    for variant in ['training', 'steam']:
        page.goto(f'{BASE}/?ws=ws://127.0.0.1:8792&play=1&nointro&model=falcon&assets={variant}')
        page.wait_for_function('window.__viewer?.S?.vehicle_id')
        page.evaluate('window.__viewer.setCam("orbit")')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / f'game-{variant}.png'))
    browser.close()
