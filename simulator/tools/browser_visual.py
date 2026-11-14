"""Capture the real model viewer and desktop cockpit for visual review."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base

out = Path(__file__).resolve().parents[1] / 'output' / 'upgrade-validation'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1920,'height':1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'{http_base(8092)}/model-preview.html?model=falcon')
    page.wait_for_function('window.__modelPreview?.model && !window.__modelPreview.model.loadError')
    page.wait_for_timeout(1500)
    page.screenshot(path=str(out/'falcon-hangar.png'))
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&nointro&room=visual_review')
    page.wait_for_function('window.__viewer?.S?.vehicle_id')
    page.select_option('#vehicleSelect','falcon')
    page.click('#changeVehicle')
    page.wait_for_function('window.__viewer.S.model_id==="falcon"')
    page.wait_for_timeout(1500)
    page.evaluate('window.__viewer.setCam("orbit");window.scrollTo(0,0)')
    page.wait_for_timeout(1000)
    page.screenshot(path=str(out/'falcon-cockpit-1080.png'))
    assert not errors, errors
    browser.close()
print('Visual captures saved:', out)
