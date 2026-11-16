"""Capture deterministic frames inside the running simulator; no photographic inputs.
Run from repo root: python simulator/tools/render_swim_platform.py
"""
from pathlib import Path
import sys
import os
from playwright.sync_api import sync_playwright
from _browser import launch, timeout
from render_support_assets import start_simulator, shrink

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/design/support-assets/swim-platform'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Screenshots do not use SDK RPC; let the OS assign it so concurrent reviews cannot collide.
    os.environ.setdefault('QYSIM_RPC_PORT', '0')
    process, http, ws = start_simulator(ROOT / 'simulator')
    try:
        with sync_playwright() as p:
            browser = launch(p)
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: (errors.append(str(e)), print('PAGE ERROR', e, flush=True)))
            if '--menu-only' not in sys.argv:
                page.goto(f'http://127.0.0.1:{http}/?ws=ws://127.0.0.1:{ws}&play=1&model=x1'
                          '&quality=high&room=m3review&launchMode=swim-platform&introReview=1')
                page.wait_for_function('window.__seekIntro?.(0)', timeout=timeout(240000))
                page.add_style_tag(content='body > :not(canvas):not(script) { visibility: hidden !important; } canvas { visibility: visible !important; }')
                for label, at in [('overhead', 0), ('lift', 2.3), ('lower', 5.2), ('float', 7.3), ('cable', 8.2)]:
                    if '--contact-only' in sys.argv and label not in ('lift', 'lower'):
                        continue
                    if '--lower-only' in sys.argv and label != 'lower':
                        continue
                    assert page.evaluate('(t) => window.__seekIntro(t)', at)
                    page.wait_for_timeout(800)
                    path = OUT / f'ingame-{label}.png'
                    page.screenshot(path=str(path))
                    shrink(path)
                    print(path, flush=True)
            if not {'--lower-only', '--contact-only'}.intersection(sys.argv):
                page.goto(f'http://127.0.0.1:{http}/?menuStage=boat&boatReview=1&quality=high')
                page.wait_for_function('window.__boatStage?.state.modelReady && window.__boatStage?.state.sceneReady',
                                       timeout=timeout(240000))
                page.add_style_tag(content='body * { visibility: hidden !important; } canvas { visibility: visible !important; } .menu-shade { display: none !important; }')
                page.evaluate('''() => {
                    const stage = window.__boatStage;
                    const required = ['screen_main', 'screen_log', 'frame_licence'];
                    for (let i = 0; i < 6; i++) required.push('photo_wall_' + i, 'gear_slot_' + i);
                    for (let i = 0; i < 2; i++) required.push('rov_slot_' + i);
                    for (const name of required) {
                        const node = stage.scene.getObjectByName(name);
                        if (!node) throw Error('Missing loaded node: ' + name);
                        if (/screen_|photo_wall_|frame_licence/.test(name)) {
                            const uv = node.geometry.attributes.uv;
                            if (!uv) throw Error('UV missing: ' + name);
                            for (let i = 0; i < uv.count; i++) {
                                if (uv.getX(i) < 0 || uv.getX(i) > 1 || uv.getY(i) < 0 || uv.getY(i) > 1) {
                                    throw Error('UV range: ' + name);
                                }
                            }
                        }
                    }
                    if (stage.scene.getObjectByName('WindFarmSilhouettes')) throw Error('Duplicate horizon');
                }''')
                for anchor in ['cockpit', 'platform', 'logbook', 'horizon']:
                    page.evaluate('(name) => window.__boatStage.goTo("anchor_" + name, {immediate:true})', anchor)
                    page.wait_for_timeout(1500)
                    path = OUT / f'anchor-{anchor}.png'
                    page.screenshot(path=str(path))
                    shrink(path)
                    print(path, flush=True)
                page.goto(f'http://127.0.0.1:{http}/?menuStage=boat&boatReview=1&quality=high&sky=clear')
                page.wait_for_function('window.__boatStage?.state.modelReady', timeout=timeout(240000))
                page.add_style_tag(content='body * { visibility: hidden !important; } canvas { visibility: visible !important; }')
                page.evaluate('window.__boatStage.goTo("anchor_horizon", {immediate:true})')
                page.wait_for_timeout(1500)
                path = OUT / 'anchor-horizon-day.png'
                page.screenshot(path=str(path))
                shrink(path)
            assert not errors, errors
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=20)


if __name__ == '__main__':
    main()
