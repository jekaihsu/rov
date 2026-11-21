"""Capture the campaign radio and drive onboarding through physical browser inputs."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Error
from _browser import launch, http_base, ws_base, timeout
from _menu import open_main, set_intro, wait_screen, wait_title_card_gone
from _campaign_drive import hold_until_advanced, wait_left

OUT = Path(__file__).resolve().parents[1] / 'output' / 'campaign-validation'
OUT.mkdir(parents=True, exist_ok=True)


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True,
                                    args=['--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'])
        context = browser.new_context(viewport=dict(width=1600, height=900), record_video_dir=str(OUT),
                                      record_video_size=dict(width=800, height=450))
        try:
            page = context.new_page()
        except Error as error:
            if 'ffmpeg' not in str(error).lower() or "Executable doesn't exist" not in str(error):
                raise
            print('SKIP video recording: Playwright ffmpeg executable is missing; all campaign checks still run.',
                  flush=True)
            context.close()
            context = browser.new_context(viewport=dict(width=1600, height=900))
            page = context.new_page()
        # Clicks and waits follow ROV_BROWSER_TIMEOUT_SCALE; the default scale leaves CI timing unchanged.
        page.set_default_timeout(timeout(30000))
        errors = []
        page.on('pageerror', lambda error: (errors.append(str(error)), print('ERROR', error, flush=True)))
        page.goto(f'{http_base(8092)}/?nointro&mission=campaign&control=UAV_CHN'
                  f'&room=campaign{time.time_ns()}&quality=performance&model=bluerov2_heavy&ws={ws_base(8792)}')
        page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
        page.evaluate('''localStorage.setItem("rov.campaign.v1", JSON.stringify({
          completed: [], checkpoint: {chapter:"prologue", index:0}
        }))''')
        open_main(page)
        page.click('#entry-training')
        page.click('#training-tab-story')
        page.click('[data-chapter="prologue"]')
        page.click('#hangarNext')
        wait_screen(page, 'briefing')
        set_intro(page, False)
        page.click('#startDive')
        page.wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=timeout(90000))
        wait_title_card_gone(page)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / 'prologue.png'))

        for width, height in [(1280, 720), (1920, 1080)]:
            page.set_viewport_size(dict(width=width, height=height))
            radio = page.locator('.story-radio').bounding_box()
            assert radio['width'] <= width * .45, radio
            assert radio['x'] + radio['width'] < width * .5, radio
            page.screenshot(path=str(OUT / f'dialogue-{width}x{height}.png'))
        visited = []
        inputs = {'unlock': 'Space', 'move_前': 'w', 'move_後': 's', 'move_右': 'd',
                  'move_左': 'a', 'move_下': 'ArrowDown', 'move_上': 'ArrowUp',
                  'depth': 'h', 'light': 'l', 'photo': 'p'}
        for _ in range(40):
            campaign = page.evaluate('window.__viewer.S.campaign')
            if campaign['status'] == 'completed':
                break
            node = campaign['node']
            visited.append(node['id'])
            print(node['id'], flush=True)
            if node['type'] == 'dialogue':
                page.locator('.story-radio button').evaluate('button => { button.click(); button.click(); }')
                wait_left(page, node['id'])
            else:
                hold_until_advanced(page, node['id'], inputs[node['id']], inputs['unlock'])
        page.wait_for_function('window.__viewer.S.campaign.status === "completed"')
        result = page.evaluate('window.__viewer.S.campaign')
        assert 'prologue' in result['completed'], result
        assert not errors, errors
        page.screenshot(path=str(OUT / 'prologue-completed.png'))
        (OUT / 'results.json').write_text(json.dumps(dict(visited=visited, state=result, errors=errors),
                                                    ensure_ascii=False, indent=2))
        video = page.video
        context.close()
        if video is not None:
            Path(video.path()).replace(OUT / 'prologue.webm')
        browser.close()
    print('Campaign browser input proof passed:', OUT)


if __name__ == '__main__':
    run()
