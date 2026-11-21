"""Long-running stability soak: drive the viewer for N minutes and report leaks / errors.

Starts the simulator itself (so it can kill and relaunch the process once mid-run),
launches Chromium through ``_browser.launch``, and cycles scenes, menus, pause, photo,
language, fake gamepad disconnect/reconnect and one server restart.

Usage:
  python simulator/tools/soak_test.py --minutes 30
  python simulator/tools/soak_test.py --minutes 1
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from _browser import launch, timeout
from _menu import open_main, set_intro, soft_click, to_briefing, wait_ready

OUT = ROOT / 'output' / 'soak'
OUT.mkdir(parents=True, exist_ok=True)

SCENES = ['coral_reef', 'seagrass_meadow', 'open_water', 'harbor_inspection', 'jacket_inspection']
LANGUAGES = ['zh-Hant', 'en', 'zh-Hans', 'ja']
FAKE_PAD = """
window.__soakPads = [{
  id: 'soak-pad', index: 0, connected: true, mapping: 'standard',
  axes: [0,0,0,0],
  buttons: Array.from({length: 17}, () => ({value: 0, pressed: false, touched: false})),
  timestamp: 0, hapticActuators: [], vibrationActuator: null,
}];
Object.defineProperty(navigator, 'getGamepads', {
  configurable: true,
  value: () => window.__soakPads,
});
"""


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def start_server(log_path, ports=None):
    ports = ports or {'http': free_port(), 'ws': free_port(), 'rpc': free_port()}
    command = [sys.executable, '-m', 'qysim.server',
               '--http-port', str(ports['http']),
               '--ws-port', str(ports['ws']),
               '--rpc-port', str(ports['rpc'])]
    log = open(log_path, 'w', encoding='utf-8')
    process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{ports['http']}/", timeout=2).close()
            return process, log, ports
        except OSError:
            time.sleep(0.5)
    stop_server(process, log)
    raise RuntimeError(f'server failed to start; see {log_path}')


def stop_server(process, log):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    if log:
        log.close()


def dive_url(ports, scene, room):
    # play=1 reads `scenario` (app.js launchScene); the menu path also accepts `scene`.
    return (
        f"http://127.0.0.1:{ports['http']}/?play=1&nointro&quality=performance"
        f"&mission=free_explore&scenario={scene}&scene={scene}&model=x1"
        f"&ws=ws://127.0.0.1:{ports['ws']}&room={room}"
    )


def menu_url(ports, room):
    return (
        f"http://127.0.0.1:{ports['http']}/?nointro&quality=performance"
        f"&ws=ws://127.0.0.1:{ports['ws']}&room={room}"
    )


def wait_dive(page, scene):
    page.wait_for_function(
        'key => window.__viewer?.W?.scenario?.key === key && window.__modelLoaded',
        arg=scene,
        timeout=timeout(90000),
    )


def sample_metrics(page):
    return page.evaluate("""() => {
      const perf = performance.memory || {};
      const gl = document.querySelector('canvas')?.getContext?.('webgl2')
        || document.querySelector('canvas')?.getContext?.('webgl');
      let gpu = null;
      if (gl) {
        const ext = gl.getExtension('WEBGL_debug_renderer_info');
        gpu = {
          renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null,
          maxTextureUnits: gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS),
        };
      }
      const info = window.__viewer?.renderer?.info;
      const programs = info?.programs;
      return {
        t: Date.now(),
        heap: perf.usedJSHeapSize || null,
        heapTotal: perf.totalJSHeapSize || null,
        programs: Array.isArray(programs) ? programs.length : null,
        geometries: info?.memory?.geometries ?? null,
        textures: info?.memory?.textures ?? null,
        calls: info?.render?.calls ?? null,
        triangles: info?.render?.triangles ?? null,
        paused: !!window.__viewer?.S?.paused,
        scene: window.__viewer?.W?.scenario?.key || window.__menu?.scene || null,
        screen: window.__menu?.screen || (window.__viewer ? 'game' : null),
        gpu,
      };
    }""")


def enter_scene(page, ports, scene, cycle, errors):
    """Load a scene via direct dive URL (reliable) or the launch menu (every 5th cycle)."""
    room = f'soak{cycle}'
    if cycle % 5 == 0:
        try:
            page.goto(menu_url(ports, room), wait_until='domcontentloaded')
            wait_ready(page, timeout=90000)
            open_main(page)
            to_briefing(page, mode='free_explore', site=scene)
            set_intro(page, False)
            soft_click(page, '#startDive')
            wait_dive(page, scene)
            return
        except Exception as exc:
            errors.append(f'cycle {cycle}: menu launch fallback after: {exc}')
    page.goto(dive_url(ports, scene, room), wait_until='domcontentloaded')
    wait_dive(page, scene)


def fly_and_pause(page, cycle, errors):
    try:
        page.keyboard.down('w')
        page.wait_for_timeout(350)
        page.keyboard.up('w')
        page.keyboard.press('Space')
        page.wait_for_timeout(150)
        page.keyboard.press('p')
        page.wait_for_timeout(250)
        page.keyboard.press('Escape')
        page.wait_for_selector('#pauseMenu:not([hidden])', timeout=timeout(20000))
        page.wait_for_timeout(150)
        page.keyboard.press('Escape')
        page.wait_for_selector('#pauseMenu', state='hidden', timeout=timeout(20000))
    except Exception as exc:
        errors.append(f'cycle {cycle}: flight/pause: {exc}')


def toggle_language(page, cycle, errors):
    try:
        lang = LANGUAGES[cycle % len(LANGUAGES)]
        page.evaluate("""(lang) => {
          const raw = JSON.parse(localStorage.getItem('rov.display.v1') || '{}');
          raw.language = lang;
          raw.version = 1;
          localStorage.setItem('rov.display.v1', JSON.stringify(raw));
        }""", lang)
    except Exception as exc:
        errors.append(f'cycle {cycle}: language: {exc}')


def yank_gamepad(page, cycle, errors):
    try:
        page.evaluate("""() => {
          window.__soakPads = [];
          window.dispatchEvent(new Event('gamepaddisconnected'));
        }""")
        page.wait_for_timeout(150)
        page.evaluate("""() => {
          window.__soakPads = [{
            id: 'soak-pad', index: 0, connected: true, mapping: 'standard',
            axes: [0,0,0,0],
            buttons: Array.from({length: 17}, () => ({value: 0, pressed: false, touched: false})),
            timestamp: performance.now(),
          }];
          window.dispatchEvent(new Event('gamepadconnected'));
        }""")
    except Exception as exc:
        errors.append(f'cycle {cycle}: gamepad: {exc}')


def return_to_menu(page, ports, cycle, errors):
    try:
        page.goto(menu_url(ports, f'soakMenu{cycle}'), wait_until='domcontentloaded')
        wait_ready(page, timeout=90000)
    except Exception as exc:
        errors.append(f'cycle {cycle}: return menu: {exc}')


def rising_trend(series, key, min_points=8):
    values = [row[key] for row in series if isinstance(row.get(key), (int, float))]
    if len(values) < min_points:
        return False, values
    mid = len(values) // 2
    first = sum(values[:mid]) / mid
    second = sum(values[mid:]) / (len(values) - mid)
    if first <= 0:
        return second > first + 5, values
    return second > first * 1.4 and values[-1] > values[0] * 1.3, values


def write_report(report):
    OUT.mkdir(parents=True, exist_ok=True)
    slim_samples = []
    for row in report.get('samples') or []:
        slim_samples.append({k: row.get(k) for k in (
            't', 'heap', 'heapTotal', 'programs', 'geometries', 'textures',
            'calls', 'triangles', 'paused', 'scene', 'screen')})
    payload = dict(report)
    payload['samples'] = slim_samples
    (OUT / 'report.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '# Soak test report',
        '',
        f"- minutes: {report['minutes']}",
        f"- cycles: {report['cycles']}",
        f"- errors: {len(report['errors'])}",
        f"- stuck cycles: {report['stuck']}",
        f"- server restarts: {report['server_restarts']}",
        f"- heap rising: {report['leaks']['heap']}",
        f"- geometries rising: {report['leaks']['geometries']}",
        f"- textures rising: {report['leaks']['textures']}",
        f"- programs rising: {report['leaks']['programs']}",
        '',
        '## Errors',
    ]
    if report['errors']:
        lines.extend(f'- {item}' for item in report['errors'][:80])
    else:
        lines.append('- none')
    final = report.get('final') or {}
    lines.extend([
        '',
        '## Final metrics',
        f"- scene: {final.get('scene')}",
        f"- heap: {final.get('heap')}",
        f"- programs/geometries/textures: {final.get('programs')}/"
        f"{final.get('geometries')}/{final.get('textures')}",
        '',
    ])
    text = '\n'.join(lines)
    (OUT / 'report.md').write_text(text + '\n', encoding='utf-8')
    print(text, flush=True)


def run(minutes: float):
    errors = []
    stuck = []
    samples = []
    server_restarts = 0
    process, log, ports = start_server(OUT / 'server.log')
    os.environ['ROV_HTTP_PORT'] = str(ports['http'])
    os.environ['ROV_WS_PORT'] = str(ports['ws'])
    started = time.monotonic()
    deadline = started + minutes * 60
    restarted = False
    cycles = 0

    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True, args=['--enable-unsafe-swiftshader'])
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        page.set_default_timeout(timeout(60000))
        page.add_init_script(FAKE_PAD)
        page.on('pageerror', lambda exc: errors.append(f'pageerror: {exc}'))

        def on_console(msg):
            if msg.type != 'error':
                return
            text = msg.text or ''
            if any(token in text for token in ('WebGL', 'webkit-masked-url', 'Failed to load resource')):
                return
            errors.append(f'console.error: {text}')

        page.on('console', on_console)

        # Start already diving so the first cycles exercise the in-game path.
        page.goto(dive_url(ports, SCENES[0], 'soak0'), wait_until='domcontentloaded')
        wait_dive(page, SCENES[0])

        while time.monotonic() < deadline:
            cycles += 1
            cycle = cycles
            scene = SCENES[cycle % len(SCENES)]
            try:
                alive = page.evaluate('!!(window.__viewer?.S || window.__menu?.ready)')
            except Exception as exc:
                errors.append(f'cycle {cycle}: page unresponsive: {exc}')
                stuck.append(cycle)
                break
            if not alive:
                stuck.append(cycle)
                errors.append(f'cycle {cycle}: menu/viewer not ready')
                break

            try:
                # Switch scenes regularly; also open the menu path occasionally.
                if cycle == 1 or cycle % 2 == 0:
                    enter_scene(page, ports, scene, cycle, errors)
                fly_and_pause(page, cycle, errors)
                if cycle % 3 == 0:
                    toggle_language(page, cycle, errors)
                yank_gamepad(page, cycle, errors)
                if cycle % 6 == 5:
                    return_to_menu(page, ports, cycle, errors)
            except Exception as exc:
                errors.append(f'cycle {cycle}: unexpected: {exc}')

            try:
                samples.append(sample_metrics(page))
            except Exception as exc:
                errors.append(f'sample {cycle}: {exc}')

            elapsed = time.monotonic() - started
            if not restarted and cycles >= 2 and elapsed >= minutes * 60 * 0.4:
                restarted = True
                server_restarts += 1
                print('soak: restarting server', flush=True)
                stop_server(process, log)
                process, log, ports = start_server(OUT / 'server-restart.log', ports)
                os.environ['ROV_HTTP_PORT'] = str(ports['http'])
                os.environ['ROV_WS_PORT'] = str(ports['ws'])
                try:
                    page.goto(dive_url(ports, SCENES[0], f'soakR{int(time.time())}'),
                              wait_until='domcontentloaded')
                    wait_dive(page, SCENES[0])
                except Exception as exc:
                    errors.append(f'server restart recovery: {exc}')
                    break
            page.wait_for_timeout(300)

        final = samples[-1] if samples else None
        browser.close()

    stop_server(process, log)
    heap_leak, heap_values = rising_trend(samples, 'heap')
    geo_leak, geo_values = rising_trend(samples, 'geometries')
    tex_leak, tex_values = rising_trend(samples, 'textures')
    prog_leak, prog_values = rising_trend(samples, 'programs')
    report = {
        'minutes': minutes,
        'cycles': cycles,
        'errors': errors,
        'stuck': stuck,
        'server_restarts': server_restarts,
        'samples': samples,
        'final': final,
        'leaks': {
            'heap': heap_leak,
            'geometries': geo_leak,
            'textures': tex_leak,
            'programs': prog_leak,
            'heap_first_last': [heap_values[0], heap_values[-1]] if heap_values else None,
            'geometries_first_last': [geo_values[0], geo_values[-1]] if geo_values else None,
            'textures_first_last': [tex_values[0], tex_values[-1]] if tex_values else None,
            'programs_first_last': [prog_values[0], prog_values[-1]] if prog_values else None,
        },
        'ok': not errors and not stuck and not heap_leak and not geo_leak and not tex_leak and not prog_leak,
    }
    write_report(report)
    return report


def main():
    parser = argparse.ArgumentParser(description='ROV viewer soak test')
    parser.add_argument('--minutes', type=float, default=30.0)
    args = parser.parse_args()
    report = run(args.minutes)
    # Hard-fail on stuck pages or pageerrors; soft-report transient action errors / leak flags.
    hard = [e for e in report['errors'] if e.startswith('pageerror:') or 'unresponsive' in e]
    if hard or report['stuck']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
