"""Check that ?assets=generic draws the original observation ROV in game and that the default stays the X1.

Run against a simulator (see run_browser_checks.py, which sets ROV_HTTP_PORT / ROV_WS_PORT):
  python tools/run_browser_checks.py browser_vehicle_assets_smoke
With --docs the in-game screenshot is also written to docs/design/vehicle/in-game-generic.png (1600x900).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'vehicle-assets'
DOCS = ROOT.parent / 'docs' / 'design' / 'vehicle'
INSPECT = '''() => {
  const names = [];
  window.__viewer.scene.traverse((o) => names.push(o.name));
  const has = (name) => names.includes(name);
  return {model: window.__loadedModelId, loaded: window.__modelLoaded, rotors: window.__viewer.rotors.length,
    hull: has('observation_rov_hull'), gimbal: has('camera_gimbal'), lamps: has('lamp_pivot_0') && has('lamp_pivot_1'),
    mapped: window.__viewer.rotorOf.map((r) => r.thrusterIndex)};
}'''


def open_game(browser, query, requests):
    page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
    page.set_default_timeout(timeout(120000))
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url) if '/models/' in request.url else None)
    url = f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&model=x1&cam=chase&room=assetcheck{query}'
    page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
    page.wait_for_function('window.__modelLoaded === true && window.__loadedModelId === "x1"')
    return page, errors


def check_generic(browser, docs):
    requests = []
    page, errors = open_game(browser, '&assets=generic', requests)
    page.wait_for_timeout(timeout(4000))
    result = page.evaluate(INSPECT)
    assert result['hull'] and result['gimbal'] and result['lamps'], result
    assert result['rotors'] == 6 and sorted(result['mapped']) == list(range(6)), result
    assert any(url.endswith('/models/observation_rov.glb') for url in requests), requests
    assert not any(url.endswith('/models/rov.glb') for url in requests), requests
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / 'in-game-generic.png'), timeout=timeout(180000))
    if docs:
        DOCS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DOCS / 'in-game-generic.png'), timeout=timeout(180000))
    page.close()
    assert not errors, errors
    return result


def check_default(browser):
    requests = []
    page, errors = open_game(browser, '', requests)
    result = page.evaluate(INSPECT)
    assert not result['hull'], 'default asset set must keep the training X1'
    assert any(url.endswith('/models/rov.glb') for url in requests), requests
    assert not any('observation_rov' in url for url in requests), requests
    page.close()
    assert not errors, errors
    return result


def check_menu_label(browser):
    """The menu must present the swapped vehicle under its generic name, not the training model's."""
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    page.set_default_timeout(timeout(120000))
    page.goto(f'{http_base(8092)}/?assets=generic&model=x1', wait_until='domcontentloaded')
    page.wait_for_selector('[data-vehicle="x1"]')
    generic = page.locator('[data-vehicle="x1"]').inner_text()
    page.goto(f'{http_base(8092)}/?model=x1', wait_until='domcontentloaded')
    page.wait_for_selector('[data-vehicle="x1"]')
    training = page.locator('[data-vehicle="x1"]').inner_text()
    page.close()
    assert generic != training and 'X1' not in generic, (generic, training)
    return {'generic': generic, 'training': training}


def main():
    docs = '--docs' in sys.argv
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        generic = check_generic(browser, docs)
        default = check_default(browser)
        labels = check_menu_label(browser)
        browser.close()
    print(json.dumps({'generic': generic, 'default': default, 'menu': labels}, ensure_ascii=False))
    print('Vehicle asset selection passed:', OUT)


if __name__ == '__main__':
    main()
