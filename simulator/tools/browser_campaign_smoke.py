"""Capture the campaign radio and drive onboarding through physical browser inputs."""
import json
import os
import time
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base
from _menu import open_main, set_intro, wait_screen

OUT = Path(__file__).resolve().parents[1] / 'output' / 'campaign-validation'
OUT.mkdir(parents=True, exist_ok=True)


def _playwright_ffmpeg_available():
    """Playwright records WebM only when its bundled ffmpeg (or PATH ffmpeg) is present."""
    if which('ffmpeg'):
        return True, 'PATH ffmpeg'
    cache = Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or (Path.home() / '.cache' / 'ms-playwright'))
    matches = sorted(cache.glob('ffmpeg-*/ffmpeg-linux')) + sorted(cache.glob('ffmpeg-*/ffmpeg-*'))
    if matches:
        return True, str(matches[0])
    return False, None


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True,
                                    args=['--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'])
        record_video, ffmpeg_note = _playwright_ffmpeg_available()
        context_opts = dict(viewport=dict(width=1600, height=900))
        if record_video:
            context_opts.update(record_video_dir=str(OUT), record_video_size=dict(width=800, height=450))
        else:
            print('Skipping campaign video capture: ffmpeg not available '
                  f'(looked on PATH and under {Path.home() / ".cache" / "ms-playwright"}). '
                  'Other campaign steps still run.', flush=True)
        context = browser.new_context(**context_opts)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: (errors.append(str(error)), print('ERROR', error, flush=True)))
        page.goto(f'{http_base(8092)}/?nointro&mission=campaign&control=UAV_CHN'
                  f'&room=campaign{time.time_ns()}&quality=performance&model=bluerov2_heavy&ws={ws_base(8792)}')
        page.wait_for_function('window.__menu?.ready', timeout=90000)
        open_main(page)
        page.click('#entry-story')
        page.click('[data-chapter="prologue"]')
        page.click('#hangarNext')
        wait_screen(page, 'briefing')
        set_intro(page, False)
        page.click('#startDive')
        page.wait_for_function('window.__viewer?.S?.campaign?.chapter === "prologue"', timeout=90000)
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
            else:
                key = inputs[node['id']]
                page.keyboard.down(key)
                try:
                    page.wait_for_function('id => window.__viewer.S.campaign.node?.id !== id',
                                           arg=node['id'], timeout=45000)
                except Exception:
                    diagnostic = page.evaluate('''({mode:window.__viewer.S.operation_mode,
                        locked:window.__viewer.S.locked, rc:window.__viewer.S.rc,
                        pos:window.__viewer.S.pos, vel:window.__viewer.S.vel})''')
                    print(diagnostic, flush=True)
                    raise
                page.keyboard.up(key)
            page.wait_for_function('id => window.__viewer.S.campaign.node?.id !== id',
                                   arg=node['id'], timeout=45000)
        page.wait_for_function('window.__viewer.S.campaign.status === "completed"')
        result = page.evaluate('window.__viewer.S.campaign')
        assert 'prologue' in result['completed'], result
        assert not errors, errors
        page.screenshot(path=str(OUT / 'prologue-completed.png'))
        payload = dict(visited=visited, state=result, errors=errors, video_recorded=bool(record_video),
                       ffmpeg=ffmpeg_note)
        (OUT / 'results.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        video = page.video if record_video else None
        context.close()
        if video is not None:
            Path(video.path()).replace(OUT / 'prologue.webm')
        browser.close()
    print('Campaign browser input proof passed:', OUT)


if __name__ == '__main__':
    run()
