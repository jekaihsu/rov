"""Render the dive-site card images of the launch menu from the menu's own live 3D stage.

Usage (from the simulator directory, with a server running or through run_browser_checks-style ports):
  python tools/capture_site_previews.py            # every dive site in scene_previews.json
  python tools/capture_site_previews.py coral_reef # only the named sites

Writes viewer/menu/previews/<key>.jpg (480x270, JPEG). The menu shows a plain gradient for a site that has no
image, so a missing file is never an error. Re-run after build_menu_previews.py changes a site.
"""
import io
import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'viewer' / 'menu' / 'previews'
SIZE = (480, 270)


def site_keys(names):
    scenes = json.loads((ROOT / 'viewer' / 'scene_previews.json').read_text(encoding='utf8'))
    keys = [scene['key'] for scene in scenes]
    return [key for key in keys if not names or key in names]


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport={'width': 960, 'height': 540})
        page.goto(f'{http_base()}/?quality=medium')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
        page.evaluate('window.__menu.go("sites")')
        page.evaluate('window.__menu.pose("preview")')
        page.add_style_tag(content='.menu-stack,.menu-header,.menu-footer,.menu-shade{display:none!important}')
        sites = page.evaluate('[...document.querySelectorAll("[data-site]")].map(card => card.dataset.site)')
        for key in site_keys(names):
            if key not in sites:
                continue
            page.evaluate('key => window.__menu.configure({scenario: key})', key)
            page.wait_for_function('key => window.__menu.ready && window.__menu.scene === key', arg=key,
                                   timeout=timeout(60000))
            page.wait_for_timeout(2500)
            image = Image.open(io.BytesIO(page.screenshot())).convert('RGB').resize(SIZE, Image.LANCZOS)
            image.save(OUT / f'{key}.jpg', quality=72, optimize=True, progressive=True)
            print('wrote', key)
        browser.close()


if __name__ == '__main__':
    main(sys.argv[1:])
