"""Exercise the full T23 checklist, water confirmation, recovery and dive-log export in a real browser.

The real fidelity preset selects the full procedure. Buttons are clicked with the pointer (no gamepad). The panel
must sit on the --z-controls layer. Screenshots go to output/procedure-validation/.
Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'procedure-validation'
CHECKS = 10
THRUSTER_CHECK = 7


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={'width': 1600, 'height': 900}, accept_downloads=True)
        page.set_default_timeout(timeout(60000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'{http_base()}/?play=1&fidelity=real&room=t23&model=bluerov2_heavy&quality=performance'
                  f'&ws={ws_base()}')
        panel = page.locator('#procedurePanel')
        panel.wait_for(state='visible', timeout=timeout(90000))
        page.wait_for_function('window.__intro?.() == null || !window.__intro().playing')
        z_index = panel.evaluate('(el) => getComputedStyle(el).zIndex')
        controls = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--z-controls").trim()')
        assert z_index == controls, (z_index, controls)
        page.screenshot(path=str(OUT / 'checks.png'))
        print('Checklist opened', flush=True)
        thrusters = page.evaluate('window.__viewer.S.procedure.thrusters')
        for index in range(CHECKS):
            if index == THRUSTER_CHECK:
                for motor in range(thrusters):
                    panel.get_by_role('button', name=f'短測推進器 {motor + 1}', exact=True).click()
                    page.wait_for_function(f'window.__viewer.S.procedure.tests.includes({motor})')
                    print('Motor tested', motor + 1, flush=True)
            panel.locator('button').filter(has_not_text='跳過').last.click()
            page.wait_for_function(f'window.__viewer.S.procedure.checked.length === {index + 1}')
            print('Confirmed check', index + 1, flush=True)
        panel.get_by_role('button', name='與纜線手確認就緒').click()
        panel.get_by_role('button', name='選上游點，以纜線緩放入水').click()
        panel.get_by_role('button', name='影像、配平與功能正常；人員已離開').click()
        page.wait_for_function('window.__viewer.S.procedure.phase === "diving"')
        page.screenshot(path=str(OUT / 'water.png'))
        panel.get_by_role('button', name='水面上鎖後收纜回收').click()
        panel.get_by_role('button', name='已以淡水沖洗').click(timeout=timeout(120000))
        panel.get_by_role('button', name='潛後檢查完成').click()
        panel.get_by_role('textbox', name='潛水註記').fill('T23 browser full procedure')
        panel.get_by_role('button', name='儲存日誌').click()
        with page.expect_download() as download:
            panel.get_by_role('button', name='匯出日誌').click()
        download.value.save_as(OUT / 'dive-log.json')
        page.screenshot(path=str(OUT / 'complete.png'))
        assert page.evaluate('window.__viewer.S.procedure.notes') == 'T23 browser full procedure'
        assert not errors, errors
        browser.close()
    print('Full checklist, motor pulses, water gate, recovery, rinse, inspection and log export passed.')


if __name__ == '__main__':
    sys.exit(run())
