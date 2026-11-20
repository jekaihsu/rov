"""Capture the identity screenshots in docs/design/key-art/in-game/ (not a pass/fail check).

  python tools/run_browser_checks.py browser_brand_shots        # through the runner (free ports)

Writes 1600x900 JPEGs (each at most 300 KB): the title, the loading screen, the hangar for the three models, three
chapter title cards and two licence grades. The chapter cards and licences come from brand/demo.html, which
draws the same components the game uses; the title, loading screen and hangar are the live launch menu.
"""
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout
from _menu import open_internal, wait_ready, wait_screen

OUT = Path(__file__).resolve().parents[2] / 'docs' / 'design' / 'key-art' / 'in-game'
VIEWPORT = {'width': 1600, 'height': 900}
LIMIT = 300 * 1024
MODELS = ('x1', 'bluerov2_heavy', 'falcon')
LETTERS = {'x1': 'r', 'bluerov2_heavy': 'o', 'falcon': 'v'}
CARDS = ('prologue', 'harbor', 'offshore')
LICENCES = ('trainee', 'senior')


def save(page, name):
    """Save the page as a JPEG no larger than LIMIT, lowering quality until it fits."""
    image = Image.open(io.BytesIO(page.screenshot(timeout=timeout(120000)))).convert('RGB')
    for quality in (86, 80, 74, 68, 60, 52):
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=quality, optimize=True, progressive=True)
        if buffer.tell() <= LIMIT:
            break
    (OUT / name).write_bytes(buffer.getvalue())
    print('wrote', name, buffer.tell(), flush=True)


def demo(page, query, name):
    page.goto(f'{http_base(8092)}/brand/demo.html?{query}')
    page.wait_for_selector('html[data-ready]', state='attached', timeout=timeout(30000))
    page.wait_for_function('[...document.images].every(image => image.complete)', timeout=timeout(30000))
    page.wait_for_timeout(300)
    save(page, name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport=VIEWPORT)
        page.set_default_timeout(timeout(30000))
        # Loading: hold the catalogue request so the static loading block stays on screen.
        page.route('**/menu_catalogue.json', lambda route: None)
        page.goto(f'{http_base(8092)}/')
        page.wait_for_selector('#brandLoadingMark svg', timeout=timeout(30000))
        page.wait_for_timeout(600)
        save(page, 'loading.jpg')
        page.unroute('**/menu_catalogue.json')
        page.goto(f'{http_base(8092)}/?quality=medium')
        wait_ready(page, 180000)
        page.wait_for_timeout(2500)
        save(page, 'title.jpg')
        open_internal(page)
        page.click('#entry-dive')
        wait_screen(page, 'modes')
        page.click('[data-mode="free_explore"]')
        wait_screen(page, 'hangar')
        for model in MODELS:
            page.click(f'[data-vehicle="{model}"]')
            page.wait_for_function('id => window.__menu.ready && window.__menu.model === id', arg=model,
                                   timeout=timeout(120000))
            page.wait_for_timeout(2500)
            save(page, f'hangar-model-{LETTERS[model]}.jpg')
        for card in CARDS:
            demo(page, f'card={card}', f'chapter-card-{card}.jpg')
        for grade in LICENCES:
            demo(page, f'licence={grade}', f'licence-{grade}.jpg')
        browser.close()


if __name__ == '__main__':
    main()
