"""Capture reproducible pen review views and renderer budgets in the running simulator."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, timeout
from browser_reservoir_onboard import replay
from browser_underwater_shots import capture
from browser_scene_review import open_site, CAPTURE, save_jpeg

OUT = Path(__file__).resolve().parents[2] / 'docs/design/scenes/reservoir'
# Sum all renderer passes; the default autoReset would report only the final fullscreen triangle.
CAPTURE = CAPTURE.replace('const t0 = performance.now();',
                          'renderer.info.autoReset = false; renderer.info.reset(); const t0 = performance.now();')
CAPTURE = CAPTURE.replace('  const image = quality ?',
                          '  renderer.info.autoReset = true;\n  const image = quality ?')
CAPTURE = CAPTURE.replace('  const vis =',
    "  scene.background.setHex(0xa6b7b4); scene.fog.color.setHex(0xa6b7b4);\n  const vis =")
CAPTURE = CAPTURE.replace('const settle = quality ? 12 : 1;', 'const settle = quality ? 2 : 1;')
CAPTURE = CAPTURE.replace('scene.fog.far = real ? vis * 1.35 : 70;', 'scene.fog.far = 900;')
VIEWS = {
    'embankment-overlook': ((-16., -18., -12.), (18., 0., -1.)),
    'dock-equipment': ((1., -5., -2.3), (5., -2., -.6)),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    setup = OUT.parents[3] / "simulator/output/reservoir-review"
    setup.mkdir(parents=True, exist_ok=True)
    clip = replay('surface', (3., 0., 1.5), (10., 0., 1.5))
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for tier in ('medium', 'performance', 'high'):
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script(f"localStorage.setItem('rov.quality', '{tier}')")
            capture(page, http_base(8092), 'fidelity=real&cam=onboard',
                    'surface-setup', clip, setup, 1)
            print('loaded', tier, flush=True)
            page.wait_for_function("window.__viewer.scene.getObjectByName('structures')?.children.length > 0")
            report[f'{tier}-assets'] = page.evaluate("""() => {
                const textures = new Set();
                let triangles = 0;
                let meshes = 0;
                let visibleTriangles = 0;
                window.__viewer.scene.traverse(o => {
                    if (!o.isMesh) return;
                    const count = o.geometry.index?.count ?? o.geometry.attributes.position?.count ?? 0;
                    triangles += count / 3 * (o.isInstancedMesh ? o.count : 1);
                    meshes += 1;
                    let visible = true;
                    for (let parent = o; parent; parent = parent.parent) visible &&= parent.visible;
                    if (visible) visibleTriangles += count / 3 * (o.isInstancedMesh ? o.count : 1);
                    for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
                        for (const v of Object.values(m)) if (v?.isTexture) textures.add(v);
                    }
                });
                let bytes = 0;
                for (const t of textures) {
                    const image = t.image;
                    if (image?.width && image?.height) bytes += image.width * image.height * 4 * 4 / 3;
                }
                return {residentTrianglesIncludingHidden: triangles, visibleTriangles,
                    residentMeshesIncludingHidden: meshes, textureRGBAWithMipBytes: Math.ceil(bytes)};
            }""")
            views = VIEWS if tier == 'medium' else {'embankment-overlook': VIEWS['embankment-overlook']}
            for name, view in views.items():
                real = False
                page.evaluate("async real => (await import('./fidelity.js')).getFidelity()"
                              ".setPreset('real')", real)
                overview = tier == 'medium' and True
                width, height = (1600, 900) if overview else (800, 450)
                print('capture', tier, name, flush=True)
                shot = page.evaluate(CAPTURE, [view, real, width, height, .85 if overview else 0, 1])
                report[f'{tier}-{name}'] = shot['info']
                if shot['image']:
                    save_jpeg(shot['image'], OUT / f'{name}.jpg')
            assert not errors, errors
            page.close()
        browser.close()
    for name, measurement in report.items():
        if name.endswith('-assets'):
            assert measurement['visibleTriangles'] <= 200_000, (name, measurement)
            assert measurement['textureRGBAWithMipBytes'] + 4 * 256 * 256 * 4 * 4 / 3 <= 32 * 1024 ** 2
    (OUT / 'render-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
