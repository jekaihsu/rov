"""Debrief replay smoke: timeline markers, student/god viewpoints, HTML report export.

Uses the small fixture at viewer/debrief/fixtures/debrief_smoke.json so the check does not
depend on regenerating demo_recording.json. Screenshots land in output/debrief-validation/.
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'debrief-validation'
OUT.mkdir(parents=True, exist_ok=True)
FIXTURE = 'debrief/fixtures/debrief_smoke.json'


def run():
    errors = []
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        context.set_default_timeout(timeout(60000))
        page = context.new_page()
        page.on('pageerror', lambda error: (errors.append(str(error)), print('PAGE ERROR', error, flush=True)))
        url = f'{http_base()}?replay={FIXTURE}&nointro&ws={ws_base()}'
        page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
        page.wait_for_function(
            'window.__viewer?.debrief && document.body.classList.contains("debriefing")'
            ' && !document.querySelector("#replayBar").hidden',
            timeout=timeout(120000),
        )
        # Timeline markers from the fixture (inject, collision, tether, silt, dvl, comms, …).
        marker_count = page.locator('.debrief-marker').count()
        assert marker_count >= 5, marker_count
        page.locator('.debrief-marker').first.click(no_wait_after=True)
        page.wait_for_function('window.__replay?.() && window.__replay().t >= 0')
        # Student (onboard) view is the default; capture the timeline composition.
        page.evaluate('window.__viewer.setCam("onboard")')
        page.wait_for_timeout(timeout(800))
        page.screenshot(path=str(OUT / 'debrief-timeline-student.png'), full_page=False)
        # God view banner and sensor-error strip.
        page.locator('.debrief-view-btn', has_text='上帝視角').click(no_wait_after=True)
        page.wait_for_function('document.body.dataset.debriefView === "god"')
        page.wait_for_function('!document.querySelector(".debrief-banner")?.hidden')
        banner = page.locator('.debrief-banner').inner_text()
        assert '講評視角' in banner and '非學員' in banner, banner
        page.wait_for_timeout(timeout(800))
        page.screenshot(path=str(OUT / 'debrief-god-view.png'), full_page=False)
        # Back to student view for the second viewpoint shot.
        page.locator('.debrief-view-btn', has_text='學員機載畫面').click(no_wait_after=True)
        page.wait_for_function('document.body.dataset.debriefView === "student"')
        page.wait_for_timeout(timeout(600))
        page.screenshot(path=str(OUT / 'debrief-student-view.png'), full_page=False)
        # Notes live in a collapsed <details>; open it then fill.
        page.locator('.debrief-details summary').click(no_wait_after=True)
        page.fill('.debrief-notes', '煙霧測試：碰撞前討論纜線回彈')
        with page.expect_download(timeout=timeout(60000)) as download_info:
            page.locator('.debrief-export').click(no_wait_after=True)
        download = download_info.value
        report_path = OUT / 'debrief-report.html'
        download.save_as(str(report_path))
        html = report_path.read_text(encoding='utf8')
        assert '教官講評' in html or '講評報告' in html, html[:200]
        assert '煙霧測試：碰撞前討論纜線回彈' in html
        # Student-view export must not print the god-view banner.
        assert '講評視角，非學員畫面' not in html
        # Public demo replay keeps the plain bar (no debrief panel).
        demo = context.new_page()
        demo.on('pageerror', lambda error: (errors.append(str(error)), print('PAGE ERROR', error, flush=True)))
        demo.goto(f'{http_base()}?replay=demo_recording.json&nointro&ws={ws_base()}',
                  wait_until='domcontentloaded', timeout=timeout(90000))
        demo.wait_for_function(
            'window.__viewer?.rep && !document.querySelector("#replayBar").hidden',
            timeout=timeout(120000),
        )
        assert demo.evaluate('!document.body.classList.contains("debriefing")'
                             ' && !document.querySelector(".debrief-panel")')
        demo.close()
        # Replay must not open a live session / send RC.
        assert page.evaluate('!window.__viewer?.S?.vehicle_id || !!window.__replay?.()')
        live = page.evaluate('''() => {
          const rep = window.__viewer?.rep;
          return !!(rep && document.body.classList.contains("replaying"));
        }''')
        assert live
        (OUT / 'results.json').write_text(json.dumps({
            'markers': marker_count,
            'report_bytes': report_path.stat().st_size,
            'screenshots': [
                'debrief-timeline-student.png',
                'debrief-god-view.png',
                'debrief-student-view.png',
                'debrief-report.html',
            ],
            'errors': errors,
            'status': 'passed',
        }, ensure_ascii=False, indent=2), encoding='utf8')
        assert not errors, errors
        browser.close()
    print('Debrief smoke passed:', OUT)


if __name__ == '__main__':
    run()
