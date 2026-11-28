"""Exercise graphics recovery, launcher bind races and interrupted gameplay over a real socket."""
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout, ws_base

ROOT = Path(__file__).resolve().parents[1]


def graphics(browser):
    page = browser.new_page(viewport={'width': 850, 'height': 600})
    page.add_init_script("""if (!sessionStorage.glRestored) {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type, ...args) {
        return type.includes('webgl') ? null : original.call(this, type, ...args);
      };
    }""")
    page.goto(http_base() + '/?lang=en&play=1')
    panel = page.locator('#recoveryPanel')
    panel.wait_for(timeout=timeout(60000))
    assert 'Graphics unavailable' in panel.inner_text()
    page.evaluate("sessionStorage.glRestored = '1'")
    panel.get_by_role('button', name='Retry', exact=True).click()
    page.wait_for_function("window.__viewer?.performance?.()?.mode === 'low'", timeout=timeout(90000))
    assert page.evaluate('window.__viewer.performance().effectsSuppressed')
    page.close()

    page = browser.new_page()
    page.goto(http_base() + '/?lang=en')
    page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
    page.evaluate("window.__menu.renderer.getContext().getExtension('WEBGL_lose_context').loseContext()")
    page.wait_for_function("window.__menu?.screen === 'title' && !!document.querySelector('#safeNotice')",
                           timeout=timeout(60000))
    assert 'lost' in page.locator('#safeNotice').inner_text()
    page.close()


def backend(browser):
    fixture = ROOT / 'tools' / 'robustness_backend.cjs'
    with subprocess.Popen(['node', fixture, sys.executable, ROOT], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True) as process:
        try:
            lines = []
            for line in process.stdout:
                if line.startswith('{'):
                    result = json.loads(line)
                    break
                lines.append(line.strip())
            assert 'port' in lines and result['attempts'] == 2, lines
            base = http_base(result['http'], env='ROV_FIXTURE_HTTP')
            ws = ws_base(result['ws'], env='ROV_FIXTURE_WS')
            page = browser.new_page()
            page.goto(f'{base}/?play=1&safe=1&nointro&ws={ws}')
            page.wait_for_function('!!window.__viewer?.S', timeout=timeout(90000))
            process.stdin.write('stop\n')
            process.stdin.flush()
            assert process.stdout.readline().strip() == 'stopped'
            notice = page.locator('#offline')
            notice.wait_for(timeout=timeout(45000))
            assert notice.locator('.offline-menu').is_visible()
            process.stdin.write('start\n')
            process.stdin.flush()
            assert json.loads(process.stdout.readline())['http'] == result['http']
            notice.wait_for(state='hidden', timeout=timeout(60000))
            page.close()
        finally:
            process.stdin.close()


with sync_playwright() as playwright:
    chromium = launch(playwright)
    graphics(chromium)
    backend(chromium)
    chromium.close()
print('Passed WebGL creation, context loss, port collision and live reconnection.')
