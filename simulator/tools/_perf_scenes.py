"""Shared helpers for the frame-cost profile in browser_gpu_bench.py (--profile, --check).

Opens one view of the game (menu stage, deploy intro on the deck, or a dive site in a camera view) with
tools/perf_probe.js injected, waits for it to settle, and returns what one frame asks of the GPU and the main
thread: draw calls, triangles, render passes with their sizes, uploads, shader compiles, texture memory,
JavaScript and layout time per frame (Chrome DevTools Protocol), and optionally where the JavaScript time
goes (sampling profiler, grouped by viewer module).
"""
from __future__ import annotations

import re
from pathlib import Path

from _browser import http_base, timeout, ws_base

PROBE = (Path(__file__).resolve().parent / 'perf_probe.js').read_text(encoding='utf-8')

# Module groups for the JavaScript attribution table (first match wins; paths are relative to viewer/).
GROUPS = (
    ('three.js (scene graph, render submission)', r'vendor/three|three\.module'),
    ('postprocessing / optics (fx)', r'/fx/|postprocessing'),
    ('fish', r'fish_|reef_life|pen_life|marine_registry'),
    ('environment / seabed / habitat', r'environment\.js|seabed\.js|kelp_flow|flow_field|aquaculture'),
    ('tether', r'cable\.js|/tether|tether_reel|spool_station'),
    ('state replay / interpolation', r'state_buffer|state_merge|camera_rig|fleet\.js'),
    ('HUD / DOM panels', r'/hud/|cockpit|mission_panel|procedure|pilot_guide|career|objective|/onboard/|'
                         r'attitude_indicator|video_link|/menu/|/story/|/sonar/|/vision/'),
    ('deploy intro / topside', r'deploy_intro|launch_rig|site_topside|wind_farm|surface_set|topside'),
    ('app.js frame loop', r'app\.js'),
)


def group_of(url):
    for name, pattern in GROUPS:
        if re.search(pattern, url or ''):
            return name
    if not url:
        return '(native / GC / idle)'
    return 'other viewer modules'


def new_page(browser, tier, size):
    width, height = size
    page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)[:300]))
    page.add_init_script(f"try{{localStorage.setItem('rov.quality','{tier}')}}catch(e){{}}")
    page.add_init_script(PROBE)
    return page, errors


def open_menu(browser, tier, size, room):
    page, errors = new_page(browser, tier, size)
    page.goto(f'{http_base()}/?ws={ws_base()}&room={room}&quality={tier}', wait_until='domcontentloaded',
              timeout=timeout(90000))
    page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
    return page, errors, 'window.__menu.renderer'


def open_intro(browser, site, tier, size, room):
    page, errors = new_page(browser, tier, size)
    url = (f'{http_base()}/?play=1&ws={ws_base()}&nopip&room={room}&scenario={site}&seed=1'
           f'&quality={tier}&cam=onboard')
    page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
    page.wait_for_function(f'window.__viewer?.W?.scenario?.key==="{site}" && window.__intro?.()',
                           timeout=timeout(120000))
    return page, errors, 'window.__viewer.renderer'


def open_dive(browser, site, tier, view, size, room):
    page, errors = new_page(browser, tier, size)
    cam = 'onboard' if view == 'onboard' else 'chase'
    third = '1' if view == 'third' else '0'
    url = (f'{http_base()}/?play=1&ws={ws_base()}&nointro&nopip&room={room}'
           f'&scenario={site}&seed=1&quality={tier}&cam={cam}&thirdPerson={third}')
    page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
    page.wait_for_function(
        f'window.__viewer?.W?.scenario?.key==="{site}" && !!window.__viewer?.renderer && !!window.__viewer?.S',
        timeout=timeout(120000))
    page.evaluate(f'window.__viewer.setCam("{cam}")')
    return page, errors, 'window.__viewer.renderer'


def _metrics(client):
    values = client.send('Performance.getMetrics')['metrics']
    return {item['name']: item['value'] for item in values}


def _attribute(profile):
    """Self time per module group, and per function, from a CDP CPU profile."""
    nodes = {node['id']: node for node in profile['nodes']}
    samples = profile.get('samples') or []
    deltas = profile.get('timeDeltas') or []
    totals = {}
    functions = {}
    for node_id, delta in zip(samples, deltas):
        frame = nodes[node_id]['callFrame']
        name = frame.get('functionName') or ''
        url = frame.get('url') or ''
        if name in ('(idle)', '(program)', '(garbage collector)') and not url:
            key = name
        else:
            key = group_of(url)
            label = f"{name or '(anonymous)'} {url.rsplit('/', 1)[-1].split('?')[0]}:{frame.get('lineNumber', 0) + 1}"
            functions[label] = functions.get(label, 0) + delta / 1000
        totals[key] = totals.get(key, 0) + delta / 1000
    return totals, functions


def sample(page, renderer_expr, seconds, warmup=2.5, attribute=False):
    """Warm up, then measure ``seconds`` of live frames. Returns a flat dict."""
    page.wait_for_timeout(int(warmup * 1000))
    client = page.context.new_cdp_session(page)
    client.send('Performance.enable')
    if attribute:
        client.send('Profiler.enable')
        client.send('Profiler.setSamplingInterval', {'interval': 500})
    page.evaluate('window.__perfProbe.reset()')
    before = _metrics(client)
    if attribute:
        client.send('Profiler.start')
    started = page.evaluate('performance.now()')
    page.wait_for_timeout(int(seconds * 1000))
    profile = client.send('Profiler.stop')['profile'] if attribute else None
    after = _metrics(client)
    elapsed = (page.evaluate('performance.now()') - started) / 1000
    snap = page.evaluate('window.__perfProbe.snapshot()')
    info = page.evaluate(f'''() => {{
      const r = {renderer_expr};
      const q = window.__viewer?.performance?.() || {{}};
      return {{programs: r.info.programs?.length ?? null, geometries: r.info.memory.geometries,
        textures: r.info.memory.textures, pixelRatio: r.getPixelRatio(),
        canvas: [r.domElement.width, r.domElement.height], mode: q.mode ?? null,
        effectsSuppressed: q.effectsSuppressed ?? null, shadows: r.shadowMap.enabled,
        heapMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null}};
    }}''')
    client.detach()
    frames = max(1, snap['frames'])
    per_frame = {
        'script_ms': (after['ScriptDuration'] - before['ScriptDuration']) * 1000 / frames,
        'layout_ms': (after['LayoutDuration'] - before['LayoutDuration']) * 1000 / frames,
        'style_ms': (after['RecalcStyleDuration'] - before['RecalcStyleDuration']) * 1000 / frames,
        'task_ms': (after['TaskDuration'] - before['TaskDuration']) * 1000 / frames,
    }
    row = {
        'fps': round(snap['frames'] / max(elapsed, 1e-3), 2),
        'frame_ms': round(elapsed * 1000 / frames, 1),
        **{key: round(value, 2) for key, value in per_frame.items()},
        **snap,
        **info,
    }
    if profile is not None:
        totals, functions = _attribute(profile)
        row['js_groups_ms_per_frame'] = {key: round(value / frames, 2) for key, value in
                                         sorted(totals.items(), key=lambda item: -item[1])}
        row['js_top_functions_ms_per_frame'] = {key: round(value / frames, 2) for key, value in
                                                sorted(functions.items(), key=lambda item: -item[1])[:15]}
    return row
