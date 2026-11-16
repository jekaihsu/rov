"""Exercise the full T23 checklist, water confirmation, recovery and dive-log export in a real browser.

The real fidelity preset selects the full procedure. The first two checks are confirmed with Space and Enter, the
rest with the pointer (no gamepad). The column
must sit on the --z-controls layer, keep clear of the middle third and stay off screen during the dive, where
recovery is reached through the pause menu. Screenshots go to output/procedure-validation/.
Browser and server addresses come from _browser.py (ROV_CHROMIUM, ROV_HOST, ROV_HTTP_PORT, ROV_WS_PORT).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'procedure-validation'
CHECKS = 10
THRUSTER_CHECK = 7
KEYBOARD_CONFIRM = ('Space', 'Enter')
CHECK_TITLES = ['外觀、密封與穿艙件已檢查', '纜線接頭與固定環已確認', '配重與配平已確認', '岸上供電與載具上電已確認',
                '通訊已確認', '相機影像已確認', '燈光已確認', '逐顆推進器短測完成', '深度零點與羅盤已確認',
                '入水、人員離開後才解鎖，已確認']


def assert_title(panel, text, wait=None):
    """The current step is the column's large title."""
    panel.locator('.pp-title', has_text=text).wait_for(state='visible', timeout=wait)


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
        # The vehicle is on the aft deck during the checklist: the launch intro opens there and holds its first frame.
        page.wait_for_function('window.__intro?.()?.held === true', timeout=timeout(90000))
        assert page.evaluate('window.__intro().t') == 0, 'the held deck frame must not advance'
        assert page.evaluate('window.__viewer.S.pos[2]') < 0, 'the full procedure starts on deck, above the water'
        z_index = panel.evaluate('(el) => getComputedStyle(el).zIndex')
        controls = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--z-controls").trim()')
        assert z_index == controls, (z_index, controls)
        page.screenshot(path=str(OUT / 'checks.png'))
        box = panel.bounding_box()
        assert box['x'] + box['width'] <= 1600 / 3, ('the checklist keeps clear of the middle third', box)
        print('Checklist opened', flush=True)
        thrusters = page.evaluate('window.__viewer.S.procedure.thrusters')
        primary = panel.locator('#procedurePrimary')
        for index in range(CHECKS):
            assert_title(panel, CHECK_TITLES[index])
            count = panel.locator('.pp-count').text_content()
            assert count == f'{index} / {CHECKS}', ('finished checks collapse into a count', count)
            if index == THRUSTER_CHECK:
                assert primary.is_disabled(), 'the thruster check waits for every motor pulse'
                for motor in range(thrusters):
                    panel.get_by_role('button', name=f'短測推進器 {motor + 1}', exact=True).click()
                    page.wait_for_function(f'window.__viewer.S.procedure.tests.includes({motor})')
                    print('Motor tested', motor + 1, flush=True)
            # The first two checks go by keyboard (Space, then Enter): the primary action holds focus between steps.
            if index < len(KEYBOARD_CONFIRM):
                page.keyboard.press(KEYBOARD_CONFIRM[index])
            else:
                primary.click()
            page.wait_for_function(f'window.__viewer.S.procedure.checked.length === {index + 1}')
            print('Confirmed check', index + 1, flush=True)
        assert_title(panel, '與纜線手確認就緒')
        primary.click()
        page.wait_for_function('window.__viewer.S.procedure.confirmed === true')
        held = page.evaluate('window.__intro()')
        assert held['held'] and held['t'] == 0, 'the launch intro must wait on deck for the lowering step'
        assert_title(panel, '選上游點，以纜線緩放入水')
        primary.click()
        # Procedure first, then the A-frame launch cinematic at the lowering step; skip it to keep the check short.
        page.wait_for_function('window.__intro?.()?.starts > 0 && window.__intro().held === false',
                               timeout=timeout(90000))
        page.evaluate('document.querySelector("#skipIntro").click()')
        page.wait_for_function('!window.__intro().playing', timeout=timeout(60000))
        assert_title(panel, '入水確認')
        primary.click()
        page.wait_for_function('window.__viewer.S.procedure.phase === "diving"')
        # Nothing stays on screen during the dive; recovery is an entry of the pause menu.
        panel.wait_for(state='hidden')
        page.screenshot(path=str(OUT / 'water.png'))
        page.keyboard.press('Escape')
        recover = page.locator('#pauseMenu [data-action="procedure-recover"]')
        recover.wait_for(state='visible')
        assert recover.text_content() == '收纜回收', recover.text_content()
        recover.click()
        page.wait_for_function('window.__viewer.S.procedure.phase !== "diving"')
        assert_title(panel, '已以淡水沖洗', timeout(120000))
        primary.click()
        page.wait_for_function('window.__viewer.S.procedure.phase === "inspect"')
        assert_title(panel, '潛後檢查完成')
        primary.click()
        page.wait_for_function('window.__viewer.S.procedure.phase === "log"')
        panel.get_by_role('textbox', name='潛水註記').fill('T23 browser full procedure')
        panel.get_by_role('button', name='儲存日誌').click()
        page.wait_for_function('window.__viewer.S.procedure.phase === "complete"')
        with page.expect_download() as download:
            panel.get_by_role('button', name='匯出日誌').click()
        download.value.save_as(OUT / 'dive-log.json')
        exported = json.loads((OUT / 'dive-log.json').read_text(encoding='utf-8'))
        assert exported.get('pilot_log'), 'dive-log export must carry the pilot log lines'
        page.screenshot(path=str(OUT / 'complete.png'))
        assert page.evaluate('window.__viewer.S.procedure.notes') == 'T23 browser full procedure'
        assert not errors, errors
        browser.close()
    print('Full checklist, motor pulses, water gate, recovery, rinse, inspection and log export passed.')


if __name__ == '__main__':
    sys.exit(run())
