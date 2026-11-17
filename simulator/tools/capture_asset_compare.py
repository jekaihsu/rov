"""Cold-cache load timings and fixed-camera GLB shots for the asset-slimming comparison.

From the simulator directory:

  python tools/capture_asset_compare.py shots --out /tmp/q1-shots/before
  python tools/capture_asset_compare.py shots --out /tmp/q1-shots/after --cameras /tmp/q1-shots/before/cameras.json
  python tools/capture_asset_compare.py timings --out /tmp/q1-shots/before/timings.json
  python tools/capture_asset_compare.py diff --before /tmp/q1-shots/before --after /tmp/q1-shots/after

Shots use software GL (see tools/_browser.py). Timings are a fresh browser context per quality,
so the HTTP cache starts empty. Software-GL frame times are not Steam hardware numbers.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from _browser import launch  # noqa: E402

SHOTS = (
    ('falcon-close', 'models/falcon.glb', 1, '', ''),
    ('falcon-far', 'models/falcon.glb', 18, '', ''),
    ('heavy-close', 'models/bluerov2_heavy.glb', 1, '', ''),
    ('heavy-far', 'models/bluerov2_heavy.glb', 12, '', ''),
    ('observation-close', 'models/observation_rov.glb', 1, '', ''),
    ('observation-far', 'models/observation_rov.glb', 12, '', ''),
    ('castle-close', 'models/korean_castle.glb', 1, '', ''),
    ('castle-far', 'models/korean_castle.glb', 40, '', ''),
    ('workboat-close', 'models/workboat.glb', 1, 'LOD0', ''),
    ('workboat-far', 'models/workboat.glb', 40, 'LOD1', ''),
    ('worker-close', 'models/worker.glb', 1, '', 'Man_Idle'),
    ('worker-far', 'models/worker.glb', 10, '', 'Man_Idle'),
    ('rov-close', 'models/rov.glb', 1, '', ''),
    ('rov-far', 'models/rov.glb', 15, '', ''),
    ('falcon-far-lod', 'models/falcon_lod2.glb', 18, '', ''),
    ('heavy-far-lod', 'models/bluerov2_heavy_lod2.glb', 12, '', ''),
    ('worker-far-lod', 'models/worker_lod2.glb', 10, '', ''),
)
QUALITIES = ('performance', 'medium', 'high', 'ultra')


def free_port():
    import socket
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def start_static():
    port = free_port()
    (ROOT / 'output').mkdir(exist_ok=True)
    log = open(ROOT / 'output' / 'asset-shot-http.log', 'w', encoding='utf-8')
    process = subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/tools/asset_shot.html', timeout=2).close()
            return process, log, port
        except OSError:
            time.sleep(0.2)
    process.kill()
    raise RuntimeError('static server did not start')


def stop(process, log):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    log.close()


def shot_url(port, name, file, gap, isolate, clip, cameras):
    query = f'file={file}&gap={gap}'
    if isolate:
        query += f'&isolate={isolate}'
    if clip:
        query += f'&clip={clip}'
    saved = (cameras or {}).get(name)
    if saved:
        cam = ','.join(str(value) for value in saved['cam'])
        target = ','.join(str(value) for value in saved['target'])
        query += f'&cam={cam}&target={target}'
        if saved.get('fov') is not None:
            query += f'&fov={saved["fov"]}'
    return f'http://127.0.0.1:{port}/tools/asset_shot.html?{query}'


def capture_shots(out, cameras_path):
    out.mkdir(parents=True, exist_ok=True)
    cameras = {}
    if cameras_path:
        cameras = json.loads(Path(cameras_path).read_text(encoding='utf-8'))
    process, log, port = start_static()
    recorded = {}
    try:
        with sync_playwright() as playwright:
            browser = launch(playwright)
            page = browser.new_page(viewport={'width': 960, 'height': 540})
            for name, file, gap, isolate, clip in SHOTS:
                target = ROOT / 'viewer' / file
                if not target.is_file():
                    print(f'skip {name}: {file} is absent')
                    continue
                page.goto(shot_url(port, name, file, gap, isolate, clip, cameras), wait_until='load')
                page.wait_for_function('window.__shot && window.__shot.ready', timeout=120000)
                info = page.evaluate('window.__shot')
                if info.get('error'):
                    raise RuntimeError(f'{name}: {info["error"]}')
                page.locator('canvas').screenshot(path=str(out / f'{name}.png'))
                recorded[name] = {
                    'file': file, 'gap': gap, 'isolate': isolate, 'clip': clip,
                    'cam': info['cam'], 'target': info['target'], 'fov': info['fov'],
                    'triangles': info['triangles'],
                }
                print(f'{name}: {info["triangles"]:.0f} tris')
            browser.close()
    finally:
        stop(process, log)
    (out / 'cameras.json').write_text(json.dumps(recorded, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {out}')


def start_sim():
    port = free_port()
    ws = free_port()
    rpc = free_port()
    log_path = ROOT / 'output' / 'asset-timing-server.log'
    log = open(log_path, 'w', encoding='utf-8')
    process = subprocess.Popen(
        [sys.executable, '-m', 'qysim.server', '--http-port', str(port), '--ws-port', str(ws), '--rpc-port', str(rpc)],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2).close()
            return process, log, port, ws
        except OSError:
            time.sleep(0.4)
    stop(process, log)
    raise RuntimeError(f'simulator did not start; see {log_path}')


def capture_timings(out):
    out.parent.mkdir(parents=True, exist_ok=True)
    process, log, port, ws = start_sim()
    rows = []
    try:
        with sync_playwright() as playwright:
            browser = launch(playwright)
            for quality in QUALITIES:
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                page = context.new_page()
                url = f'http://127.0.0.1:{port}/?play=1&quality={quality}&ws=ws://127.0.0.1:{ws}'
                started = time.perf_counter()
                errors = []
                page.on('pageerror', lambda err: errors.append(str(err)))
                try:
                    page.goto(url, wait_until='domcontentloaded')
                    page.wait_for_function(
                        'window.__modelLoaded === true && window.__viewer && window.__viewer.W',
                        timeout=45000,
                    )
                except Exception as error:
                    elapsed = time.perf_counter() - started
                    row = {'quality': quality, 'seconds': round(elapsed, 3), 'error': str(error).splitlines()[0],
                           'page_errors': errors[:3]}
                    rows.append(row)
                    print(f'{quality}: failed after {elapsed:.1f}s ({row["error"]})')
                    context.close()
                    continue
                # The vehicle resolves before the intro, fish and scans finish.
                # worker_lod2 is requested only after worker.glb has parsed, so the
                # quiet window has to outlast that parse or the byte count drops it.
                page.wait_for_function(
                    """() => {
                      const names = performance.getEntriesByType('resource').map((entry) => entry.name);
                      const models = names.filter((name) => name.includes('/models/'));
                      const count = models.length;
                      const now = performance.now();
                      if (window.__modelQuiet !== count) {
                        window.__modelQuiet = count;
                        window.__modelQuietAt = now;
                      }
                      const worker = models.some((name) => name.endsWith('/worker.glb'));
                      const workerLod = models.some((name) => name.endsWith('/worker_lod2.glb'));
                      // The far crew file is fetched only after worker.glb finishes parsing.
                      if (worker && !workerLod) return false;
                      return now - window.__modelQuietAt > 1500;
                    }""",
                    timeout=60000,
                )
                elapsed = time.perf_counter() - started
                if errors:
                    print(f'{quality} page errors: {errors[:3]}')
                stats = page.evaluate(
                    """() => {
                      const rows = performance.getEntriesByType('resource')
                        .filter((entry) => entry.name.includes('/models/'));
                      const bytes = rows.reduce((sum, entry) => sum + (entry.encodedBodySize || 0), 0);
                      return {count: rows.length, bytes, names: rows.map((entry) => entry.name.split('/models/')[1])};
                    }"""
                )
                row = {'quality': quality, 'seconds': round(elapsed, 3), **stats}
                rows.append(row)
                print(f'{quality}: {elapsed:.2f}s  models {stats["bytes"]/1e6:.2f} MB  files {stats["count"]}')
                context.close()
            browser.close()
    finally:
        stop(process, log)
    out.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {out}')


def diff_shots(before, after, out):
    import numpy as np
    from PIL import Image
    rows = []
    for name, *_rest in SHOTS:
        left = before / f'{name}.png'
        right = after / f'{name}.png'
        if not left.is_file() or not right.is_file():
            continue
        a = np.asarray(Image.open(left).convert('RGB'), dtype=np.float32)
        b = np.asarray(Image.open(right).convert('RGB'), dtype=np.float32)
        if a.shape != b.shape:
            rows.append({'name': name, 'error': f'shape {a.shape} vs {b.shape}'})
            continue
        delta = np.abs(a - b)
        mean = float(delta.mean())
        peak = float(delta.max())
        changed = float((delta.max(axis=2) > 2).mean())
        rows.append({'name': name, 'mean_abs': round(mean, 3), 'peak': peak, 'fraction_over_2': round(changed, 5)})
        print(f'{name}: mean {mean:.2f}  peak {peak:.0f}  changed {changed:.3%}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('shots', 'timings', 'diff'))
    parser.add_argument('--out', type=Path)
    parser.add_argument('--cameras', type=Path)
    parser.add_argument('--before', type=Path)
    parser.add_argument('--after', type=Path)
    args = parser.parse_args()
    if args.command == 'shots':
        capture_shots(args.out, args.cameras)
    elif args.command == 'timings':
        capture_timings(args.out)
    else:
        diff_shots(args.before, args.after, args.out)


if __name__ == '__main__':
    main()
