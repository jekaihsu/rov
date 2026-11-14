"""Verify training GLBs, bound rotors and all arm sliders using the shared browser runner.

The hangar has no built-in rotor tick. This check drives its bound rotors for 0.5 s with
app.js's quaternion expression, without changing the preview page or the source assets.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout

OUT = Path(__file__).resolve().parents[2] / '.runtime/a3'
OUT.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as playwright:
    browser = launch(playwright)
    page = browser.new_page(viewport={'width': 960, 'height': 540}, device_scale_factor=1)
    page.set_default_timeout(timeout(90000))
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for model, count in [('falcon', 5), ('bluerov2_heavy', 8)]:
        print('Opening', model, flush=True)
        page.goto(f'{http_base(8080)}/model-preview.html?model={model}')
        page.wait_for_function('window.__modelPreview?.model && !window.__modelPreview.model.loadError')
        assert page.locator('#status').inner_text() == '模型已載入'
        loaded = page.evaluate('''() => {
            const {model} = window.__modelPreview;
            const mapped = [];
            model.root.traverse(object => {
                if (object.isMesh && object.material?.normalMap && object.material?.roughnessMap) {
                    mapped.push(object.name);
                }
            });
            return {indices: model.rotors.map(rotor => rotor.thrusterIndex).sort(), mapped: mapped.length};
        }''')
        print('Loaded', model, loaded, flush=True)
        assert loaded['indices'] == list(range(count)), loaded
        assert loaded['mapped'] > 50, loaded
        rotation = page.evaluate('''async () => {
            const rotors = window.__modelPreview.model.rotors;
            const before = rotors.map(rotor => rotor.o.quaternion.toArray());
            const pivots = rotors.map(rotor => rotor.o.position.toArray());
            const delta = rotors[0].base.clone();
            let start = null;
            let previous = null;
            await new Promise(resolve => {
                function step(now) {
                    if (start === null) start = previous = now;
                    const dt = (now - previous) / 1000;
                    previous = now;
                    for (const rotor of rotors) {
                        rotor.ang += .5 * 40 * dt;
                        rotor.o.quaternion.copy(rotor.base).multiply(delta.setFromAxisAngle(rotor.axis, rotor.ang));
                    }
                    if (now - start < 500) requestAnimationFrame(step);
                    else resolve();
                }
                requestAnimationFrame(step);
            });
            return rotors.map((rotor, index) => ({
                moved: rotor.o.quaternion.toArray().some((value, axis) => Math.abs(value - before[index][axis]) > .01),
                pivotFixed: rotor.o.position.toArray().every((value, axis) => value === pivots[index][axis]),
                blades: rotor.o.children.length,
            }));
        }''')
        assert all(item['moved'] and item['pivotFixed'] and item['blades'] >= 3 for item in rotation), rotation
        print('Rotors verified', model, flush=True)
        sliders = []
        if model == 'falcon':
            for index, value in enumerate([35, 25, 70, 30]):
                old = page.evaluate(f'window.__modelPreview.model.arm.joints[{index}].quaternion.toArray()')
                page.locator(f'#j{index}').evaluate(
                    '(element, value) => { element.value = value; element.dispatchEvent(new Event("input")); }',
                    str(value),
                )
                page.wait_for_function(
                    '''({index, old}) => window.__modelPreview.model.arm.joints[index].quaternion.toArray()
                        .some((value, axis) => Math.abs(value - old[axis]) > .01)''',
                    arg={'index': index, 'old': old},
                )
                sliders.append(f'j{index}')
                print('Slider verified', index, flush=True)
            old = page.evaluate('window.__modelPreview.model.arm.jaws.map(jaw => jaw.position.x)')
            page.locator('#grip').evaluate(
                '(element) => { element.value = 0.1; element.dispatchEvent(new Event("input")); }',
            )
            page.wait_for_function(
                '''old => window.__modelPreview.model.arm.jaws.every((jaw, index) =>
                    Math.abs(jaw.position.x - old[index]) > .005)''', arg=old,
            )
            sliders.append('grip')
        print('Validated', model, loaded, sliders, flush=True)
        page.screenshot(path=str(OUT / (model + '-preview.png')))
        results.append({'model': model, 'rotors': rotation, 'sliders': sliders, **loaded})
    assert not errors, errors
    browser.close()
(OUT / 'browser-check.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
