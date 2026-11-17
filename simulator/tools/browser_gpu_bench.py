"""Real-GPU (or software-GL) frame-time bench for Steam quality defaults.

Measures stable requestAnimationFrame intervals, draw calls, triangles and a coarse
GPU/JS memory estimate across quality tiers, dive sites and camera views. Works
without a discrete GPU (SwiftShader / software GL); those numbers are not Steam
certification data — re-run on a physical GPU with ROV_BROWSER_GL=gpu.

Usage (from the simulator directory, server already running or via run_browser_checks):

  # Smoke (optional check; short samples, exits 0 on software GL too):
  ROV_GPU_BENCH_SMOKE=1 python tools/run_browser_checks.py browser_gpu_bench

  # Full Steam matrix on a GPU machine:
  export ROV_CHROMIUM=/usr/bin/google-chrome
  export ROV_BROWSER_GL=gpu
  export ROV_BROWSER_EXTRA_ARGS='--no-sandbox --disable-dev-shm-usage'   # containers only
  python tools/browser_gpu_bench.py --full --machine my-pc --duration 30

  # Electron comparison (same matrix subset; needs npm deps under desktop/):
  python tools/browser_gpu_bench.py --desktop --smoke --machine my-pc

Output: simulator/output/gpu-bench/<machine>/results.json and a Markdown report path
printed at the end. Does not modify renderer code.

Frame-cost profile and budgets (tools/_perf_profile.py, tools/perf_probe.js, tools/perf_budgets.json):

  # Draw calls, triangles, passes, uploads, texture memory and main-thread ms per scene (menu, intro, dives):
  python tools/run_browser_checks.py browser_gpu_bench   # with ROV_GPU_BENCH_ARGS='--profile --sites open_water'
  python tools/browser_gpu_bench.py --profile --sites jacket_inspection --tiers medium --attribute

  # Regression check against the stored budgets (counts, so valid on software GL); exits 1 on a violation:
  python tools/browser_gpu_bench.py --check
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import gl_mode, http_base, launch, timeout, ws_base

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / 'output' / 'gpu-bench'
BUDGETS = Path(__file__).resolve().parent / 'perf_budgets.json'
TOOLS = Path(__file__).resolve().parent

# browser_scene_review's sites plus the fish pen and the new-game cold open's jacket (its start pose is the cold
# open's). Each page starts at the scenario's seed=1 start pose and only switches the camera mode (onboard /
# chase); free-camera poses would fight camera_rig every frame.
SITES = (
    'jacket_inspection', 'monopile_current', 'tether_untangle', 'hull_inspection', 'wreck_survey',
    'korean_castle', 'harbor_inspection', 'tutorial_pool', 'coral_reef', 'seagrass_meadow', 'open_water',
    'aquaculture_pen', 'cold_open_jacket',
)
TIERS = ('performance', 'medium', 'high', 'ultra')
VIEWS = ('onboard', 'third')
HEAVY = (
    ('silt-lamps-full', 'incident_silt', 'silt', 2),
    ('wreck-lit-2', 'korean_castle', 'wreck', 2),
)

# Samples the live viewer rAF cadence (what pilots feel under vsync). Pose is the seed=1 start /
# replay pose with setCam; free-camera overrides would fight camera_rig every frame.
SAMPLE_JS = '''([durationMs, view]) => new Promise((resolve) => {
  const v = window.__viewer;
  const renderer = v.renderer;
  const scene = v.scene;
  const camera = v.camera;
  if (typeof v.setCam === 'function') v.setCam(view === 'onboard' ? 'onboard' : 'chase');
  const dt = [];
  let last = null;
  let start = null;
  function mem() {
    const info = renderer.info;
    const heap = performance.memory ? performance.memory.usedJSHeapSize : null;
    return {
      geometries: info.memory.geometries,
      textures: info.memory.textures,
      jsHeapMB: heap == null ? null : Math.round(heap / 1048576 * 10) / 10,
      gpuMemMB: null,
      estimateMB: Math.round(((info.memory.textures || 0) * 4 + (info.memory.geometries || 0) * 0.25
        + (heap || 0) / 1048576) * 10) / 10,
    };
  }
  function countsAfterFrame() {
    // EffectComposer runs several renderer.render passes; disable autoReset so they add up.
    const previous = renderer.info.autoReset;
    window.__skipRender = true;
    renderer.info.autoReset = false;
    renderer.info.reset();
    const gl = renderer.getContext();
    const pixel = new Uint8Array(4);
    renderer.render(scene, camera);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    const calls = renderer.info.render.calls;
    const triangles = renderer.info.render.triangles;
    renderer.info.autoReset = previous;
    window.__skipRender = false;
    return {calls, triangles};
  }
  function step(t) {
    if (start === null) start = t;
    if (last !== null) dt.push(t - last);
    last = t;
    if (t - start >= durationMs) {
      const info = window.__viewer.performance?.() || {};
      const counted = countsAfterFrame();
      info.drawCalls = counted.calls;
      info.triangles = counted.triangles;
      resolve({dt, info, memory: mem(), canvas: {
        width: renderer.domElement.width, height: renderer.domElement.height,
        cssWidth: renderer.domElement.clientWidth, cssHeight: renderer.domElement.clientHeight,
        pixelRatio: renderer.getPixelRatio(),
      }});
      return;
    }
    requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
})'''


def percentile(sorted_values, fraction):
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * fraction))))
    return sorted_values[index]


def summarise_intervals(dt):
    if len(dt) < 2:
        return {'frames': len(dt), 'mean_ms': None, 'p95_ms': None, 'p99_ms': None, 'min_ms': None, 'max_ms': None}
    ordered = sorted(dt)
    return {
        'frames': len(dt),
        'mean_ms': round(statistics.mean(dt), 3),
        'p95_ms': round(percentile(ordered, 0.95), 3),
        'p99_ms': round(percentile(ordered, 0.99), 3),
        'min_ms': round(ordered[0], 3),
        'max_ms': round(ordered[-1], 3),
    }


def run_cmd(command):
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def collect_host_specs():
    """Record host identity for the report; values are best-effort on containers."""
    cpu = ''
    try:
        for line in Path('/proc/cpuinfo').read_text(encoding='utf-8', errors='replace').splitlines():
            if line.lower().startswith('model name'):
                cpu = line.split(':', 1)[1].strip()
                break
    except OSError:
        cpu = platform.processor() or platform.machine()
    mem_kb = None
    try:
        for line in Path('/proc/meminfo').read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('MemTotal:'):
                mem_kb = int(line.split()[1])
                break
    except (OSError, ValueError):
        mem_kb = None
    display = run_cmd(['xrandr'])
    resolution, refresh = None, None
    if display:
        match = re.search(r'current\s+(\d+)\s*x\s*(\d+)', display)
        if match:
            resolution = f'{match.group(1)}x{match.group(2)}'
        star = re.search(r'(\d+)x(\d+)\s+([\d.]+)\*', display)
        if star:
            resolution = resolution or f'{star.group(1)}x{star.group(2)}'
            refresh = float(star.group(3))
    lspci = run_cmd(['lspci'])
    gpu_lines = [line for line in lspci.splitlines() if re.search(r'VGA|3D|Display', line, re.I)]
    return {
        'hostname': platform.node(),
        'os': f'{platform.system()} {platform.release()} ({platform.platform()})',
        'cpu': cpu,
        'logical_cpus': os.cpu_count(),
        'ram_gb': None if mem_kb is None else round(mem_kb / 1024 / 1024, 1),
        'display_resolution': resolution,
        'display_refresh_hz': refresh,
        'lspci_gpu': gpu_lines,
        'gl_mode_requested': gl_mode(),
        'chrome_path': os.environ.get('ROV_CHROMIUM') or '',
    }


def read_chrome_gpu(page):
    """Best-effort chrome://gpu feature summary (may be empty in some headless builds)."""
    try:
        page.goto('chrome://gpu', timeout=timeout(30000))
        page.wait_for_timeout(800)
        text = page.evaluate(
            '() => (document.body && (document.body.innerText || document.body.textContent) || "").slice(0, 8000)')
    except Exception as error:  # noqa: BLE001 — probe only
        return {'ok': False, 'error': str(error).splitlines()[0]}
    hardware = bool(re.search(r'Hardware accelerated|Hardware Acceleration', text, re.I))
    software = bool(re.search(r'SwiftShader|Software only|Disabled', text, re.I))
    return {'ok': True, 'hardware_accelerated_mentioned': hardware, 'software_mentioned': software,
            'excerpt': text[:2000]}


def read_webgl_renderer(page):
    return page.evaluate('''() => {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
      if (!gl) return {renderer: '', vendor: ''};
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      return {
        renderer: gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || '',
        vendor: gl.getParameter(ext ? ext.UNMASKED_VENDOR_WEBGL : gl.VENDOR) || '',
      };
    }''')


def open_site(browser, site, tier, view, size):
    width, height = size
    page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)[:300]))
    page.add_init_script(f"try{{localStorage.setItem('rov.quality','{tier}')}}catch(e){{}}")
    room = f'gb{abs(hash((site, tier, view))) % 10**8}'
    cam = 'onboard' if view == 'onboard' else 'chase'
    third = '1' if view == 'third' else '0'
    url = (f'{http_base()}/?play=1&ws={ws_base()}&nointro&nopip&room={room}'
           f'&scenario={site}&seed=1&quality={tier}&cam={cam}&thirdPerson={third}')
    page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
    page.wait_for_function(
        f'window.__viewer?.W?.scenario?.key==="{site}" && !!window.__viewer?.renderer && !!window.__viewer?.S',
        timeout=timeout(90000))
    page.wait_for_timeout(timeout(2500))
    page.evaluate(f'window.__viewer.setCam("{cam}")')
    return page, errors


def measure_page(page, duration_s, view):
    raw = page.evaluate(SAMPLE_JS, [int(duration_s * 1000), view])
    stats = summarise_intervals(raw['dt'])
    info = raw.get('info') or {}
    return {
        **stats,
        'draw_calls': info.get('drawCalls'),
        'triangles': info.get('triangles'),
        'quality_mode': info.get('mode'),
        'effects_suppressed': info.get('effectsSuppressed'),
        'scale_percent': info.get('scale'),
        'hardware_label': info.get('hardwareLabel'),
        'hardware_renderer': info.get('hardwareRenderer'),
        'hardware_tier': info.get('hardwareTier'),
        'memory': raw.get('memory'),
        'canvas': raw.get('canvas'),
        'over_16_7_ms': (stats['mean_ms'] is not None and stats['mean_ms'] > 16.7),
    }


def capture_heavy(browser, name, scenario, subject, lamp, tier, duration_s, size, out_dir):
    """Reuse the fixed-pose replay builder from underwater shots for the two heaviest frames."""
    sys.path.insert(0, str(TOOLS))
    from browser_underwater_shots import build_replay  # noqa: WPS433

    width, height = size
    page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)[:300]))
    page.add_init_script(f"try{{localStorage.setItem('rov.quality','{tier}')}}catch(e){{}}")
    replay, meta = build_replay(name, scenario, subject, lamp)
    page.route('**/__gpu_heavy.json', lambda route: route.fulfill(
        body=json.dumps(replay), content_type='application/json'))
    # No &capture so requestAnimationFrame keeps running (vsync cadence).
    url = f'{http_base()}/?replay=__gpu_heavy.json&nointro&quality={tier}&beautify=0&cam=onboard'
    page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
    page.wait_for_function('window.__viewer?.S && window.__viewer?.renderer', timeout=timeout(90000))
    page.wait_for_load_state('networkidle', timeout=timeout(90000))
    page.wait_for_timeout(timeout(2000))
    # Freeze on the first replay frame so the silt / lamp pose stays fixed while we sample.
    page.evaluate('''() => {
      const bar = window.__replay?.();
      const play = document.getElementById('rpPlay');
      if (play && play.textContent.includes('❚')) play.click();
      void bar;
    }''')
    page.evaluate('window.__viewer.setCam("onboard")')
    sample = measure_page(page, duration_s, 'onboard')
    shot = out_dir / f'heavy-{name}-{tier}.jpg'
    page.screenshot(path=str(shot), type='jpeg', quality=80, timeout=timeout(120000))
    sample['screenshot'] = str(shot.relative_to(ROOT)) if shot.exists() else None
    sample['meta'] = meta
    sample['errors'] = errors
    page.close()
    return sample


def ensure_machine_id(value):
    if value:
        return re.sub(r'[^a-zA-Z0-9._-]+', '-', value).strip('-') or 'unknown'
    host = platform.node().split('.')[0] or 'host'
    mode = 'gpu' if gl_mode() == 'gpu' else 'sw'
    return re.sub(r'[^a-zA-Z0-9._-]+', '-', f'{host}-{mode}').strip('-')


def write_markdown(report, path):
    webgl = (report.get('webgl') or {}).get('renderer', '')
    software = bool(re.search(r'swiftshader|llvmpipe|softpipe|software', webgl, re.I))
    lines = [
        f"# GPU 效能量測：`{report['machine']}`",
        '',
    ]
    if software or report.get('host', {}).get('gl_mode_requested') != 'gpu':
        lines += [
            '> **警告：本輪 WebGL 為軟體算圖或未開 `ROV_BROWSER_GL=gpu`。數字不可作為 Steam 預設／最低需求。**',
            '> 實體 GPU：`ROV_CHROMIUM=… ROV_BROWSER_GL=gpu python tools/browser_gpu_bench.py '
            '--full --machine <代號> --duration 30 --desktop`',
            '',
        ]
    lines += [
        f"- 量測時間（UTC）：{report['collected_at_utc']}",
        f"- GL 模式：`{report['host']['gl_mode_requested']}`（實際 WebGL：{webgl or '?'}）",
        f"- 取樣：穩定 {report['duration_s']} s 的 rAF 間隔；`?nointro`；seed=1 起始姿態或重負載回放",
        f"- 視埠：{report['viewport'][0]}×{report['viewport'][1]}，deviceScaleFactor=1",
        '',
        '## 機器規格',
        '',
        f"| 項目 | 值 |",
        f"|---|---|",
        f"| CPU | {report['host'].get('cpu')} |",
        f"| 邏輯核心 | {report['host'].get('logical_cpus')} |",
        f"| RAM | {report['host'].get('ram_gb')} GB |",
        f"| OS | {report['host'].get('os')} |",
        f"| 螢幕 | {report['host'].get('display_resolution')} @ {report['host'].get('display_refresh_hz')} Hz |",
        f"| lspci GPU | {'; '.join(report['host'].get('lspci_gpu') or []) or '（無）'} |",
        f"| Chrome | {report['host'].get('chrome_path') or 'Playwright / 系統預設'} |",
        f"| chrome://gpu | {json.dumps(report.get('chrome_gpu', {}), ensure_ascii=False)[:240]} |",
        '',
        '## 結果表（瀏覽器）',
        '',
        '| 場址 | 畫質 | 視角 | mean ms | p95 | p99 | draw calls | tris | mem估MB | >16.7ms |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|:---:|',
    ]
    for row in report.get('browser_rows', []):
        lines.append(
            f"| {row['site']} | {row['tier']} | {row['view']} | {row.get('mean_ms')} | {row.get('p95_ms')} | "
            f"{row.get('p99_ms')} | {row.get('draw_calls')} | {row.get('triangles')} | "
            f"{(row.get('memory') or {}).get('estimateMB')} | {'是' if row.get('over_16_7_ms') else '否'} |"
        )
    lines += ['', '## 最重畫面', '']
    for key, sample in (report.get('heavy') or {}).items():
        lines.append(
            f"- `{key}` mean={sample.get('mean_ms')} ms p95={sample.get('p95_ms')} "
            f"draw={sample.get('draw_calls')} tris={sample.get('triangles')} "
            f"shot=`{sample.get('screenshot')}`"
        )
    if report.get('desktop_rows'):
        lines += ['', '## Electron 桌面版', '',
                  '| 場址 | 畫質 | 視角 | mean ms | p95 | p99 | draw calls | tris |',
                  '|---|---|---|---:|---:|---:|---:|---:|']
        for row in report['desktop_rows']:
            lines.append(
                f"| {row['site']} | {row['tier']} | {row['view']} | {row.get('mean_ms')} | {row.get('p95_ms')} | "
                f"{row.get('p99_ms')} | {row.get('draw_calls')} | {row.get('triangles')} |"
            )
    lines += [
        '',
        '## 建議（依本機數字；軟體算圖時僅作流程驗證）',
        '',
        report.get('recommendations_md', ''),
        '',
        '## 超過 16.7 ms（60 fps）的組合',
        '',
    ]
    slow = [r for r in report.get('browser_rows', []) if r.get('over_16_7_ms')]
    if not slow:
        lines.append('無（在本輪取樣下 mean ≤ 16.7 ms）。')
    else:
        for row in slow:
            lines.append(
                f"- {row['site']} / {row['tier']} / {row['view']}: mean {row.get('mean_ms')} ms "
                f"(p95 {row.get('p95_ms')}); draw {row.get('draw_calls')}, tris {row.get('triangles')}"
            )
        lines.append('')
        lines.append(
            '原因分析：軟體算圖或無硬體加速時幾乎所有光學檔都會超過 16.7 ms；'
            '在真實 GPU 上請用瀏覽器 Performance 面板或 Spector.js 截一幀，對照 draw calls／後製 pass。'
            '本輪若有重負載截圖見上方「最重畫面」。'
        )
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def recommendations(report):
    """Draft Steam auto/quality thresholds from the measured means (honest about software GL)."""
    webgl = (report.get('webgl') or {}).get('renderer', '')
    software = bool(re.search(r'swiftshader|llvmpipe|softpipe|software', webgl, re.I))
    rows = report.get('browser_rows') or []
    by_tier = {}
    for row in rows:
        by_tier.setdefault(row['tier'], []).append(row.get('mean_ms') or 1e9)
    tier_ok = {tier: (max(values) <= 16.7) for tier, values in by_tier.items() if values}
    lines = []
    if software:
        lines.append(
            '**本機 WebGL 為軟體算圖，數字不可用於 Steam 預設畫質或最低需求。**'
            '請在實體 GPU 上以 `ROV_BROWSER_GL=gpu` 重跑後再定案。'
        )
    lines.append('')
    lines.append('| 畫質層 | 本輪最差 mean ms | 建議目標硬體（草稿） |')
    lines.append('|---|---:|---|')
    hints = {
        'performance': '整合式 GPU 入門筆電；Steam Deck 預設可落在此層',
        'medium': '中階整合式或入門獨顯（如 MX／入門 RTX）',
        'high': '主流獨顯，1080p／1440p 目標 60 fps',
        'ultra': '高階獨顯或降低解析度後的主流卡',
    }
    for tier in TIERS:
        if tier not in by_tier:
            continue
        worst = max(by_tier[tier])
        status = '達 60 fps' if tier_ok.get(tier) else '未達 60 fps'
        lines.append(f'| {tier} | {worst:.1f}（{status}） | {hints.get(tier, "")} |')
    lines.append('')
    lines.append('### auto 模式判斷門檻（建議寫回 `render_quality.js` 前先在 GPU 複測）')
    lines.append('')
    lines.append('- 維持現況：連續樣本 < 50 fps → 先關光學再降 pixel ratio；> 58 fps 且穩定 8 s 再緩升。')
    lines.append('- 軟體算圖：維持 `effectsSuppressed` 起始為真，且初始 ratio ≤ 0.6。')
    lines.append('- 獨顯：可從 ratio 1.0／medium 光學起步；入門 MX 從 0.85。')
    lines.append('- 若 GPU 複測後 medium 在整合式上仍常 > 16.7 ms，auto 的非軟體起始應改為 performance。')
    return '\n'.join(lines)


def run_browser_matrix(browser, sites, tiers, views, duration_s, size, out_dir, heavy=True):
    rows = []
    for site in sites:
        for tier in tiers:
            for view in views:
                page, errors = open_site(browser, site, tier, view, size)
                try:
                    sample = measure_page(page, duration_s, view)
                finally:
                    page.close()
                row = {'site': site, 'tier': tier, 'view': view, 'errors': errors, **sample}
                rows.append(row)
                print(json.dumps({'browser': row}, ensure_ascii=False), flush=True)
    heavy_out = {}
    if heavy:
        for name, scenario, subject, lamp in HEAVY:
            for tier in tiers:
                key = f'{name}:{tier}'
                sample = capture_heavy(browser, name, scenario, subject, lamp, tier, duration_s, size, out_dir)
                heavy_out[key] = sample
                print(json.dumps({'heavy': key, **{k: sample.get(k) for k in
                      ('mean_ms', 'p95_ms', 'draw_calls', 'triangles', 'screenshot')}},
                                 ensure_ascii=False), flush=True)
    return rows, heavy_out


def launch_electron(debug_port, env_extra):
    desktop = ROOT / 'desktop'
    electron = desktop / 'node_modules' / '.bin' / 'electron'
    if not electron.exists():
        raise RuntimeError('desktop/node_modules/.bin/electron missing; run npm ci in simulator/desktop')
    env = dict(os.environ)
    env.update(env_extra)
    env.setdefault('ELECTRON_ENABLE_LOGGING', '1')
    # Unpackaged start uses system python for the backend.
    env.setdefault('ROV_PYTHON', sys.executable)
    # Allow Playwright CDP evaluate during benches (see desktop/main.cjs).
    env['ROV_DESKTOP_BENCH'] = '1'
    command = [str(electron), str(desktop), f'--remote-debugging-port={debug_port}']
    if gl_mode() == 'gpu':
        command.extend(['--enable-gpu', '--ignore-gpu-blocklist'])
    else:
        # Headless / cloud agents blacklist WebGL without a software ANGLE path.
        command.extend(['--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=swiftshader'])
    return subprocess.Popen(command, cwd=str(desktop), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def run_desktop_matrix(playwright, sites, tiers, views, duration_s, size):
    """Connect to Electron over CDP and sample the same viewer hooks."""
    import socket
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    proc = launch_electron(port, {})
    rows = []
    try:
        deadline = time.monotonic() + 90
        browser = None
        while time.monotonic() < deadline:
            try:
                browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        if browser is None:
            raise RuntimeError('could not connect to Electron CDP')
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        # Wait for the live viewer (after menu start) or drive the menu.
        page = None
        for _ in range(60):
            for candidate in context.pages:
                if '127.0.0.1' in candidate.url and 'ws=' in candidate.url:
                    page = candidate
                    break
            if page:
                break
            time.sleep(1)
        if page is None:
            # Still on the boot/menu page: start a dive with nointro already in the URL from main.cjs.
            page = context.pages[0]
            page.wait_for_function('window.__menu?.ready', timeout=timeout(90000))
            page.evaluate('''() => {
              const intro = document.getElementById('menuIntro');
              if (intro) intro.checked = false;
              document.getElementById('launchForm')?.requestSubmit();
            }''')
            page.wait_for_function('window.__viewer?.S && window.__viewer?.renderer', timeout=timeout(120000))
        width, height = size
        page.set_viewport_size({'width': width, 'height': height})
        for site in sites:
            for tier in tiers:
                for view in views:
                    cam = 'onboard' if view == 'onboard' else 'chase'
                    page.evaluate(f'''async () => {{
                      try {{ localStorage.setItem('rov.quality', '{tier}'); }} catch (e) {{}}
                      const params = new URLSearchParams(location.search);
                      params.set('scenario', '{site}');
                      params.set('quality', '{tier}');
                      params.set('cam', '{cam}');
                      params.set('thirdPerson', '{1 if view == 'third' else 0}');
                      params.set('nointro', '1');
                      params.set('seed', '1');
                      location.search = params.toString();
                    }}''')
                    page.wait_for_function(
                        f'window.__viewer?.W?.scenario?.key==="{site}" && !!window.__viewer?.S',
                        timeout=timeout(120000))
                    page.wait_for_timeout(timeout(2000))
                    page.evaluate(f'window.__viewer.setCam("{cam}")')
                    sample = measure_page(page, duration_s, view)
                    row = {'site': site, 'tier': tier, 'view': view, **sample}
                    rows.append(row)
                    print(json.dumps({'desktop': row}, ensure_ascii=False), flush=True)
        browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    return rows


def parse_args(argv=None):
    env_smoke = os.environ.get('ROV_GPU_BENCH_SMOKE', '').lower() in ('1', 'true', 'yes')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--full', action='store_true',
                        help='all sites × tiers × views at --duration (default 30 s); for Steam GPU runs')
    parser.add_argument('--smoke', action='store_true', default=env_smoke,
                        help='short subset (default when --full is omitted; also ROV_GPU_BENCH_SMOKE=1)')
    parser.add_argument('--desktop', action='store_true', help='also sample the Electron shell')
    parser.add_argument('--duration', type=float, default=None, help='seconds of rAF sampling (default 30, smoke 2)')
    parser.add_argument('--machine', default=os.environ.get('ROV_GPU_MACHINE', ''), help='machine id for report path')
    parser.add_argument('--size', default='1280x720', help='viewport WxH')
    parser.add_argument('--sites', default='', help='comma-separated site keys')
    parser.add_argument('--tiers', default='', help='comma-separated quality tiers')
    parser.add_argument('--views', default='', help='onboard,third')
    parser.add_argument('--no-heavy', action='store_true', help='skip silt / wreck lamp-2 shots')
    parser.add_argument('--no-docs', action='store_true',
                        help='do not write docs/perf/gpu-<machine>.md (smoke defaults to this)')
    parser.add_argument('--profile', action='store_true',
                        help='frame-cost profile (draw calls, passes, memory, JS ms) instead of the frame-time matrix')
    parser.add_argument('--check', action='store_true', help='compare the scenes in --budgets against their budgets')
    parser.add_argument('--budgets', default=str(BUDGETS), help='budget JSON for --check')
    parser.add_argument('--attribute', action='store_true', help='--profile: CPU profiler time per viewer module')
    extra = (os.environ.get('ROV_GPU_BENCH_ARGS') or '').split()
    return parser.parse_args((argv if argv is not None else sys.argv[1:]) + extra)


def run_profile(args, machine):
    """--profile / --check: count what each scene asks of the GPU and the main thread."""
    import _perf_profile
    width, height = (int(part) for part in args.size.split('x'))
    out_dir = OUT_ROOT / machine
    out_dir.mkdir(parents=True, exist_ok=True)
    budgets = {}
    if args.check:
        stored = json.loads(Path(args.budgets).read_text(encoding='utf-8'))
        budgets = stored['scenes']
        width, height = stored.get('viewport', [width, height])
        keys = list(budgets)
    else:
        sites = [s for s in args.sites.split(',') if s in SITES] if args.sites else list(SITES)
        tiers = [t for t in args.tiers.split(',') if t] if args.tiers else ['performance', 'medium', 'high']
        views = [v for v in args.views.split(',') if v in VIEWS] if args.views else list(VIEWS)
        keys = _perf_profile.profile_keys(sites, tiers, views, intro=[(sites[0], tier) for tier in tiers[:2]])
    extra_args = ['--disable-dev-shm-usage']
    if 'no-sandbox' not in (os.environ.get('ROV_BROWSER_EXTRA_ARGS') or ''):
        extra_args.append('--no-sandbox')
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True, args=extra_args)
        rows = _perf_profile.measure(browser, keys, (width, height), seconds=args.duration or 4.0,
                                     attribute=args.attribute, log=lambda line: print(line, flush=True))
        browser.close()
    name = 'check' if args.check else 'profile'
    (out_dir / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (out_dir / f'{name}.md').write_text(_perf_profile.markdown(rows), encoding='utf-8')
    print('Wrote', out_dir / f'{name}.json', flush=True)
    print(_perf_profile.markdown(rows), flush=True)
    if not args.check:
        return 0 if all('error' not in row for row in rows.values()) else 1
    failures = _perf_profile.check(rows, budgets)
    for failure in failures:
        print('BUDGET', failure, flush=True)
    print('budget check:', 'FAIL' if failures else 'PASS', flush=True)
    return 1 if failures else 0


def main(argv=None):
    args = parse_args(argv)
    machine = ensure_machine_id(args.machine)
    if args.profile or args.check:
        return run_profile(args, machine)
    # Default is smoke so `run_browser_checks.py browser_gpu_bench` stays optional and fast.
    # Explicit --sites/--tiers/--views select a custom matrix (not the short smoke list).
    custom_matrix = bool(args.sites or args.tiers or args.views)
    use_smoke = (not args.full) and (not custom_matrix)
    if args.smoke and not args.full and not custom_matrix:
        use_smoke = True
    duration = args.duration
    if duration is None:
        duration = 2.0 if use_smoke else 30.0
    if use_smoke:
        sites = [s for s in ('open_water', 'tutorial_pool') if s in SITES]
        tiers = ['performance', 'medium']
        views = ['onboard', 'third']
    else:
        sites = list(SITES)
        tiers = list(TIERS)
        views = list(VIEWS)
    if args.sites:
        sites = [s for s in args.sites.split(',') if s in SITES]
    if args.tiers:
        tiers = [t for t in args.tiers.split(',') if t in TIERS]
    if args.views:
        views = [v for v in args.views.split(',') if v in VIEWS]
    width, height = (int(part) for part in args.size.split('x'))
    out_dir = OUT_ROOT / machine
    out_dir.mkdir(parents=True, exist_ok=True)
    host = collect_host_specs()
    report = {
        'machine': machine,
        'collected_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'duration_s': duration,
        'viewport': [width, height],
        'host': host,
        'smoke': use_smoke,
    }
    # Container Chrome often needs these; set ROV_BROWSER_EXTRA_ARGS on locked-down hosts.
    extra_args = ['--disable-dev-shm-usage']
    if 'no-sandbox' not in (os.environ.get('ROV_BROWSER_EXTRA_ARGS') or ''):
        extra_args.append('--no-sandbox')
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True, args=extra_args)
        probe = browser.new_page()
        report['chrome_gpu'] = read_chrome_gpu(probe)
        report['webgl'] = read_webgl_renderer(probe)
        probe.close()
        rows, heavy = run_browser_matrix(
            browser, sites, tiers, views, duration, (width, height), out_dir,
            heavy=(not args.no_heavy) and (not use_smoke))
        if use_smoke and not args.no_heavy:
            name, scenario, subject, lamp = HEAVY[0]
            heavy = {
                f'{name}:performance': capture_heavy(
                    browser, name, scenario, subject, lamp, 'performance', duration,
                    (width, height), out_dir),
            }
        report['browser_rows'] = rows
        report['heavy'] = heavy
        if args.desktop:
            try:
                report['desktop_rows'] = run_desktop_matrix(
                    playwright, sites[:1], tiers[:1], views[:1], min(duration, 5.0), (width, height))
            except Exception as error:  # noqa: BLE001 — desktop is best-effort on non-Windows hosts
                report['desktop_error'] = str(error).splitlines()[0]
                report['desktop_rows'] = []
                print('desktop bench skipped:', report['desktop_error'], flush=True)
        browser.close()
    report['recommendations_md'] = recommendations(report)
    (out_dir / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    md_out = out_dir / f'gpu-{machine}.md'
    write_markdown(report, md_out)
    # Smoke checks must not clobber a real GPU report under docs/perf/.
    write_docs = (not args.no_docs) and (not use_smoke)
    if write_docs:
        docs = ROOT.parent / 'docs' / 'perf'
        docs.mkdir(parents=True, exist_ok=True)
        target = docs / f'gpu-{machine}.md'
        target.write_text(md_out.read_text(encoding='utf-8'), encoding='utf-8')
        print('Wrote', target, flush=True)
    print('Wrote', out_dir / 'results.json', flush=True)
    # Pass/fail for run_browser_checks: the harness must complete and produce rows.
    if not report['browser_rows']:
        print('No browser samples collected', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
