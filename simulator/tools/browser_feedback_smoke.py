"""Verify the playtest feedback dialog: pause-menu entry, F8, category save, and a downloaded ZIP."""
import json
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import set_intro, to_briefing, wait_ready

OUT = Path(__file__).resolve().parents[1] / 'output' / 'feedback-smoke'
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&room=feedbackcheck&model=x1&nointro')
    wait_ready(page)
    to_briefing(page, mode='free_explore', site='seagrass_meadow', model='x1')
    set_intro(page, False)
    page.click('#startDive')
    page.wait_for_function(
        'window.__viewer?.S && document.documentElement.classList.contains("in-game")',
        timeout=timeout(90000),
    )
    page.wait_for_timeout(1200)

    # Pause menu exposes 回報問題.
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseMenu:not([hidden])')
    page.wait_for_selector('#pauseReport')
    page.screenshot(path=str(OUT / 'pause-with-report.png'))
    opened = page.evaluate('''() => {
      const button = document.getElementById('pauseReport');
      button?.click();
      const dialog = document.getElementById('feedbackDialog');
      const style = dialog ? getComputedStyle(dialog) : null;
      const box = dialog?.getBoundingClientRect();
      return {
        clicked: !!button,
        tag: dialog?.tagName || null,
        open: dialog?.open ?? null,
        modal: dialog?.matches?.(':modal') ?? null,
        display: style?.display || null,
        visibility: style?.visibility || null,
        width: box?.width || 0,
        height: box?.height || 0,
      };
    }''')
    (OUT / 'open-debug.json').write_text(json.dumps(opened, indent=2), encoding='utf8')
    assert opened['tag'] == 'DIALOG', opened
    assert opened['open'] is True and opened['modal'] is True, opened
    assert opened['display'] != 'none', opened
    assert opened['width'] > 0 and opened['height'] > 0, opened
    page.wait_for_function('document.getElementById("feedbackDialog")?.open === true')
    # Native modal dialog owns menu navigation while open.
    nav = page.evaluate('''() => {
      const dialog = document.getElementById('feedbackDialog');
      return dialog === document.querySelector('dialog[open]:modal');
    }''')
    assert nav is True, nav
    page.locator('#feedbackDescription').wait_for(state='attached')
    page.screenshot(path=str(OUT / 'feedback-dialog.png'), animations='disabled')
    page.locator('#feedbackCancel').evaluate('el => el.click()')
    page.wait_for_function('document.getElementById("feedbackDialog")?.open !== true')
    page.keyboard.press('Escape')
    page.wait_for_selector('#pauseMenu', state='hidden')

    # F8 opens the same dialog in flight.
    page.keyboard.press('F8')
    page.wait_for_function('document.getElementById("feedbackDialog")?.open === true',
                           timeout=timeout(30000))
    page.fill('#feedbackDescription', 'smoke: right stick felt sticky once')
    page.select_option('#feedbackCategory', 'feel')

    with page.expect_download(timeout=timeout(30000)) as download_info:
        page.locator('#feedbackSubmit').evaluate('el => el.click()')
    download = download_info.value
    target = OUT / (download.suggested_filename or 'rov-report.zip')
    download.save_as(target)
    page.wait_for_function('document.getElementById("feedbackDialog")?.open !== true',
                           timeout=timeout(10000))

    assert target.exists() and target.stat().st_size > 32, target
    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        assert 'report.json' in names, names
        assert 'screenshot.png' in names, names
        report = json.loads(archive.read('report.json'))
    assert report['category'] == 'feel', report
    assert 'sticky' in report['description'], report
    assert report['privacy'].startswith('local-only'), report
    assert 'fidelity' in report and 'device' in report and 'fps' in report, report.keys()
    blob = json.dumps(report)
    assert '@' not in blob or '[redacted-email]' in blob

    collisions = page.evaluate('''async () => {
      const mod = await import('/input/bindings.js');
      return mod.findCollisions();
    }''')
    assert collisions == [], collisions
    keys = page.evaluate('''async () => {
      const mod = await import('/input/bindings.js');
      return {
        report: mod.bindingRow('reportBug').keys,
        settings: mod.bindingRow('settings').keys,
      };
    }''')
    assert keys == {'report': ['F8'], 'settings': ['F9']}, keys

    assert not errors, errors
    (OUT / 'results.json').write_text(json.dumps({
        'pause_entry': True,
        'f8_opens': True,
        'modal_dialog': True,
        'zip_saved': True,
        'report_category': report['category'],
        'zip_bytes': target.stat().st_size,
        'errors': errors,
    }, indent=2), encoding='utf8')
    browser.close()

print('Feedback smoke passed:', OUT)
