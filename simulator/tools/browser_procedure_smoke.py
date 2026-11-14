"""Exercise full T23 checklist, water confirmation, recovery and log export."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'output' / 'procedure-validation'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=which('chromium'), headless=True,
                                args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1600, 'height': 900}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8094/?play=1&procedure=full&room=t23&model=bluerov2_heavy'
              '&quality=performance&ws=ws://127.0.0.1:8794')
    panel = page.locator('#procedurePanel')
    panel.wait_for(state='visible', timeout=90000)
    page.wait_for_function('window.__modelLoaded', timeout=90000)
    page.screenshot(path=str(out / 'checks.png'))
    print('Checklist opened', flush=True)
    for i in range(10):
        if i == 7:
            for j in range(8):
                panel.get_by_role('button', name=f'短測推進器 {j + 1}', exact=True).click()
                page.wait_for_function(f'window.__viewer.S.procedure.tests.includes({j})')
                print('Motor tested', j + 1, flush=True)
        panel.locator('button').filter(has_not_text='跳過').last.click()
        page.wait_for_function(f'window.__viewer.S.procedure.checked.length === {i + 1}')
        print('Confirmed check', i + 1, flush=True)
    panel.get_by_role('button', name='與纜線手確認就緒').click()
    panel.get_by_role('button', name='選上游點，以纜線緩放入水').click()
    panel.get_by_role('button', name='影像、配平與功能正常；人員已離開').click()
    page.wait_for_function('window.__viewer.S.procedure.phase === "diving"')
    page.screenshot(path=str(out / 'water.png'))
    panel.get_by_role('button', name='水面上鎖後收纜回收').click()
    panel.get_by_role('button', name='已以淡水沖洗').click(timeout=90000)
    panel.get_by_role('button', name='潛後檢查完成').click()
    panel.get_by_role('textbox', name='潛水註記').fill('T23 browser full procedure')
    panel.get_by_role('button', name='儲存日誌').click()
    with page.expect_download() as download:
        panel.get_by_role('button', name='匯出日誌').click()
    download.value.save_as(out / 'dive-log.json')
    page.screenshot(path=str(out / 'complete.png'))
    assert not errors, errors
    assert page.evaluate('window.__viewer.S.procedure.notes') == 'T23 browser full procedure'
    browser.close()
print('Full checklist, 8 motor pulses, water gate, recovery, rinse, inspection and log export passed.')
