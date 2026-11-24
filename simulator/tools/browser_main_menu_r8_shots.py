"""Retake R8 main-menu after shots at the same angles (1600x900 / 1366x768) plus four languages.

Not a pass/fail check. Writes JPEGs under docs/design/main-menu-r8/after/ and a languages contact sheet.
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import open_main, set_intro, wait_screen, wait_title_card_gone
from browser_prologue_smoke import play_prologue

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs' / 'design' / 'main-menu-r8' / 'after'
SIZES = [(1600, 900), (1366, 768)]
LANGS = [('zh-Hant', 'main-zh-Hant'), ('en', 'main-en'), ('zh-Hans', 'main-zh-Hans'), ('ja', 'main-ja')]


def jpeg(page, path, quality=82):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = page.screenshot(type='jpeg', quality=quality, timeout=timeout(120000))
    Image.open(io.BytesIO(data)).convert('RGB').save(path, quality=quality, optimize=True)
    print(path.name, path.stat().st_size // 1024, 'KB', flush=True)


def main_page(browser, width, height, query=''):
    page = browser.new_page(viewport={'width': width, 'height': height})
    page.set_default_timeout(timeout(90000))
    page.goto(f'{http_base()}/?ws={ws_base()}&quality=medium&menu=main{query}')
    open_main(page)
    page.wait_for_function('window.__menu?.ready && window.__menu?.scene', timeout=timeout(120000))
    page.wait_for_timeout(2000)
    return page


def capture_pair(browser, name, open_screen):
    for width, height in SIZES:
        page = main_page(browser, width, height)
        open_screen(page)
        page.mouse.move(4, 4)
        page.wait_for_timeout(1400)
        jpeg(page, OUT / f'after-{name}-{width}.jpg')
        page.close()


def languages_sheet(paths):
    tiles = [Image.open(path).convert('RGB') for path in paths]
    width = 800
    height = round(tiles[0].height * width / tiles[0].width)
    sheet = Image.new('RGB', (width * 2, height * 2), (8, 12, 14))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (tile, path) in enumerate(zip(tiles, paths)):
        resized = tile.resize((width, height))
        x = (index % 2) * width
        y = (index // 2) * height
        sheet.paste(resized, (x, y))
        draw.text((x + 12, y + 10), path.stem.replace('main-', ''), fill=(255, 255, 255), font=font)
    target = OUT.parent / 'languages.jpg'
    sheet.save(target, quality=80, optimize=True)
    print('languages.jpg', target.stat().st_size // 1024, 'KB', flush=True)


def comparison(before_name, after_name, out_name, size):
    before = ROOT / 'docs' / 'design' / 'main-menu-r8' / 'before' / f'{before_name}-{size}.jpg'
    after = OUT / f'{after_name}-{size}.jpg'
    if not before.exists() or not after.exists():
        return
    left = Image.open(before).convert('RGB')
    right = Image.open(after).convert('RGB')
    height = max(left.height, right.height)
    sheet = Image.new('RGB', (left.width + right.width + 8, height), (0, 0, 0))
    sheet.paste(left, (0, 0))
    sheet.paste(right, (left.width + 8, 0))
    target = OUT.parent / out_name
    sheet.save(target, quality=80, optimize=True)
    print(out_name, target.stat().st_size // 1024, 'KB', flush=True)


def capture_pause_results(browser):
    for width, height in SIZES:
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.set_default_timeout(timeout(90000))
        page.goto(f'{http_base()}/?ws={ws_base()}&quality=performance&play=1&nointro&room=r8shot{width}')
        page.wait_for_function('window.__viewer?.S', timeout=timeout(120000))
        page.wait_for_timeout(2500)
        # Unlock like a pilot if the dive starts latched; do not hang the shot on lock state.
        page.keyboard.press('Space')
        page.wait_for_timeout(800)
        page.keyboard.press('Escape')
        page.wait_for_timeout(1000)
        jpeg(page, OUT / f'after-pause-{width}.jpg')
        page.close()


def capture_results(browser):
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    page.set_default_timeout(timeout(90000))
    page.goto(
        f'{http_base()}/?nointro&mission=campaign&control=UAV_CHN'
        f'&quality=performance&model=bluerov2_heavy&room=r8results&ws={ws_base()}')
    open_main(page)
    page.click('#entry-training')
    page.click('#training-tab-story')
    page.click('[data-chapter="prologue"]')
    page.click('#hangarNext')
    wait_screen(page, 'briefing')
    set_intro(page, False)
    page.click('#startDive')
    page.wait_for_function(
        'window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=timeout(120000))
    wait_title_card_gone(page)
    play_prologue(page)
    page.wait_for_selector('#resultsScreen:not([hidden])', timeout=timeout(30000))
    page.mouse.move(4, 4)
    page.wait_for_timeout(600)
    jpeg(page, OUT / 'after-results-1600.jpg')
    page.set_viewport_size({'width': 1366, 'height': 768})
    page.wait_for_timeout(500)
    jpeg(page, OUT / 'after-results-1366.jpg')
    page.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        capture_pair(browser, 'main', lambda page: None)
        capture_pair(browser, 'story', lambda page: (page.click('#entry-story'), wait_screen(page, 'story')))
        capture_pair(browser, 'training', lambda page: (page.click('#entry-training'), wait_screen(page, 'training')))
        capture_pair(browser, 'settings', lambda page: (page.click('#entry-settings'), wait_screen(page, 'settings')))
        capture_pause_results(browser)
        capture_results(browser)

        lang_paths = []
        for lang, name in LANGS:
            page = main_page(browser, 1600, 900, f'&lang={lang}')
            path = OUT / f'{name}.jpg'
            jpeg(page, path)
            lang_paths.append(path)
            page.close()
        languages_sheet(lang_paths)
        comparison('before-main', 'after-main', 'comparison-1600.jpg', 1600)
        comparison('before-main', 'after-main', 'comparison-1366.jpg', 1366)
        browser.close()
    print('R8 after shots written to', OUT)


if __name__ == '__main__':
    run()
