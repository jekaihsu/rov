"""Capture deterministic frames inside the running simulator; no photographic inputs.
Run from repo root: python simulator/tools/render_swim_platform.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, timeout
from render_support_assets import start_simulator, shrink

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/design/support-assets/swim-platform'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    process, http, ws = start_simulator(ROOT / 'simulator')
    try:
        with sync_playwright() as p:
            browser = launch(p)
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{http}/?ws=ws://127.0.0.1:{ws}&play=1&model=x1'
                      '&quality=high&room=m3review&launchMode=swim-platform&introReview=1')
            page.wait_for_function('window.__seekIntro?.(0)', timeout=timeout(240000))
            for label, at in [('overhead', 0), ('lift', 2.3), ('lower', 5.2), ('float', 7.3), ('cable', 8.2)]:
                assert page.evaluate('(t) => window.__seekIntro(t)', at)
                page.wait_for_timeout(800)
                path = OUT / f'ingame-{label}.png'
                page.screenshot(path=str(path))
                shrink(path)
                print(path, flush=True)
            assert not errors, errors
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=20)


if __name__ == '__main__':
    main()
