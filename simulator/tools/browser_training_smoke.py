"""Internal training mode: open the course map, fly B01, and export a local scorecard."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Error
from _browser import launch, http_base, ws_base, timeout
from _menu import open_main, set_intro, wait_screen, wait_title_card_gone
from _campaign_drive import hold_until_advanced, wait_left

OUT = Path(__file__).resolve().parents[1] / 'output' / 'training-validation'
OUT.mkdir(parents=True, exist_ok=True)


def run_once(page, label):
    errors = []
    page.on('pageerror', lambda error: (errors.append(str(error)), print('ERROR', error, flush=True)))
    room = f'train{time.time_ns()}'
    page.goto(
        f'{http_base(8093)}/?nointro&mission=campaign&chapter=course_b01&training=1'
        f'&trainingLesson=course_b01&fidelity=real&control=UAV_CHN'
        f'&room={room}&quality=performance&model=bluerov2_heavy&ws={ws_base(8793)}',
        wait_until='domcontentloaded',
    )
    page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
    open_main(page)
    page.click('#entry-team-training')
    wait_screen(page, 'training')
    page.wait_for_selector('[data-group="intro"] [data-lesson="course_b01"]')
    page.screenshot(path=str(OUT / f'{label}-map.png'))
    page.click('[data-lesson="course_b01"] button')
    page.click('#hangarNext')
    wait_screen(page, 'briefing')
    set_intro(page, False)
    page.click('#startDive')
    page.wait_for_function(
        'window.__viewer?.S?.campaign?.chapter === "course_b01"',
        timeout=timeout(90000),
    )
    wait_title_card_gone(page)
    page.wait_for_function('window.__training?.active === true', timeout=timeout(30000))
    page.screenshot(path=str(OUT / f'{label}-dive.png'))

    inputs = {
        'unlock': 'Space', 'move_前': 'w', 'move_後': 's', 'move_右': 'd',
        'move_左': 'a', 'move_下': 'ArrowDown', 'move_上': 'ArrowUp',
        'depth': 'h', 'light': 'l', 'photo': 'p',
    }
    visited = []
    for _ in range(40):
        campaign = page.evaluate('window.__viewer.S.campaign')
        if campaign['status'] == 'completed':
            break
        node = campaign.get('node') or {}
        if campaign.get('chapter') != 'course_b01' or 'type' not in node:
            raise AssertionError(f'{label}: left training course unexpectedly: {campaign}')
        visited.append(node['id'])
        print(label, node['id'], flush=True)
        if node['type'] == 'dialogue':
            page.locator('.story-radio button').evaluate(
                'button => { button.click(); button.click(); }')
            wait_left(page, node['id'])
        else:
            hold_until_advanced(page, node['id'], inputs[node['id']], inputs['unlock'])
        # A failsafe unlock (Space) must not start the story chain after the course ends.
        if page.evaluate('window.__viewer.S.campaign.status') == 'completed':
            break
    page.wait_for_function('window.__viewer.S.campaign.status === "completed"')
    page.wait_for_function(
        'window.__viewer.S.campaign.chapter === "course_b01"',
        timeout=timeout(5000),
    )
    page.wait_for_function('window.__training?.scorecard', timeout=timeout(30000))
    scorecard = page.evaluate('window.__training.scorecard')
    assert scorecard['lessonId'] == 'course_b01', scorecard
    assert scorecard['localOnly'] is True, scorecard
    assert 'elapsedS' in scorecard and 'tetherContactEpisodes' in scorecard, scorecard
    assert 'maxTensionN' in scorecard and 'procedureInOrder' in scorecard, scorecard
    assert scorecard['fidelityPreset'] in ('real', 'assisted', 'custom'), scorecard

    with page.expect_download() as download_info:
        page.evaluate('window.__training.exportPdf()')
    download = download_info.value
    pdf_path = OUT / f'{label}-scorecard.html'
    download.save_as(pdf_path)
    html = pdf_path.read_text(encoding='utf-8')
    assert '學員成績單' in html or 'scorecard' in html.lower(), html[:200]
    assert 'A4' in html, html[:200]

    with page.expect_download() as csv_info:
        page.evaluate('window.__training.exportCsv()')
    csv_download = csv_info.value
    csv_path = OUT / f'{label}-records.csv'
    csv_download.save_as(csv_path)
    csv_text = csv_path.read_text(encoding='utf-8')
    assert 'lesson_id' in csv_text and 'course_b01' in csv_text, csv_text[:300]

    assert not errors, errors
    page.screenshot(path=str(OUT / f'{label}-done.png'))
    return dict(visited=visited, scorecard=scorecard, errors=errors)


def run():
    with sync_playwright() as playwright:
        browser = launch(
            playwright, headless=True,
            args=['--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'],
        )
        context = browser.new_context(viewport=dict(width=1600, height=900), accept_downloads=True)
        try:
            page = context.new_page()
        except Error:
            context.close()
            context = browser.new_context(viewport=dict(width=1600, height=900), accept_downloads=True)
            page = context.new_page()
        page.set_default_timeout(timeout(30000))
        first = run_once(page, 'pass1')
        page.close()
        page = context.new_page()
        page.set_default_timeout(timeout(30000))
        second = run_once(page, 'pass2')
        (OUT / 'results.json').write_text(
            json.dumps(dict(pass1=first, pass2=second), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        context.close()
        browser.close()
    print('Training browser smoke passed:', OUT)


if __name__ == '__main__':
    run()
