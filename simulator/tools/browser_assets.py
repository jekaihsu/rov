"""Verify opt-in asset loading, inspector controls, packaging and comparable review captures."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / 'docs/assets/T11a'
BASE = 'http://127.0.0.1:8092'


def run():
    errors = []
    result = {}
    with sync_playwright() as p:
        chrome = os.environ.get('CHROME_PATH')
        browser = p.chromium.launch(executable_path=chrome, channel=None if chrome else 'chrome',
                                    args=['--enable-unsafe-swiftshader'])
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        poses = []
        for variant in ['training', 'generic']:
            asset_query = '&assets=generic' if variant == 'generic' else ''
            page.goto(f'{BASE}/model-preview.html?model=x1{asset_query}')
            page.wait_for_function('window.__modelPreview?.model && !window.__modelPreview.model.loadError')
            page.wait_for_timeout(800)
            expected = 'models/rov.glb' if variant == 'training' else 'models/observation-lod0.glb'
            assert page.evaluate('window.__modelPreview.model.definition.model') == expected
            poses.append(page.evaluate('''() => {
                const {camera} = window.__modelPreview;
                return {position:camera.position.toArray(), quaternion:camera.quaternion.toArray()};
            }'''))
            page.screenshot(path=str(OUT / f'observation-{variant}.png'))
            if variant == 'generic':
                for lod in range(3):
                    page.locator('aside select').first.select_option(str(lod))
                    page.wait_for_function('''lod => window.__modelPreview.model.definition.model.endsWith(
                        `lod${lod}.glb`) && !window.__modelPreview.model.loadError''', arg=lod)
                    assert page.evaluate('window.__modelPreview.model.rotors.length') == 6
                page.locator('aside select').first.select_option('0')
                page.wait_for_function('window.__modelPreview.model.definition.model.endsWith("lod0.glb")')
                page.get_by_text('Wireframe', exact=True).click()
                assert page.evaluate('''() => {
                    let valid = true;
                    window.__modelPreview.model.model.traverse(o => {
                        if (o.isMesh && !o.material.wireframe) valid = false;
                    });
                    return valid;
                }''')
                page.screenshot(path=str(OUT / 'observation-wire.png'))
                page.get_by_text('Wireframe', exact=True).click()
                for channel in range(1, 6):
                    page.locator('aside select').nth(1).select_option(str(channel))
                page.locator('aside select').nth(1).select_option('0')
                page.get_by_text('Collision proxy', exact=True).click()
                page.wait_for_function('window.__modelPreview.model.root.getObjectByName("collision")')
                result['lod_wireframe_channels_collision'] = 'passed'
        assert poses[0] == poses[1], poses
        for variant in ['training', 'generic']:
            page.goto(f'{BASE}/?ws=ws://127.0.0.1:8792&play=1&nointro&model=x1'
                      f'&assets={variant}&room=asset-{variant}&seed=42')
            page.wait_for_function('window.__viewer?.S?.vehicle_id && window.__modelLoaded', timeout=60000)
            page.wait_for_function('window.__viewer.rotors.length === 6', timeout=60000)
            assert page.evaluate('''() => !window.__viewer.rovG.children.some(
                o => o.userData.assetLoadError)''')
            page.evaluate('window.__viewer.setCam("orbit")')
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / f'game-{variant}.png'))
            result[f'game_{variant}_six_rotors_no_fallback'] = 'passed'
        assert not errors, errors
        browser.close()
    print(json.dumps({'status': 'passed', **result, 'page_errors': errors}, indent=2))


if __name__ == '__main__':
    run()
