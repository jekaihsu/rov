"""Render fixed-camera review images of the deck support assets (work boat, deck crew, operator station).

Usage (from the simulator directory):
  python tools/render_support_assets.py OUT_DIR [--viewer DIR] [--prefix after]
  python tools/render_support_assets.py OUT_DIR --intro [--viewer DIR] [--prefix after] [--times label=sec ...]
  python tools/render_support_assets.py OUT_DIR --intro-frames [--viewer DIR] [--prefix after] [--times label=sec ...]

--viewer points at the viewer directory to review (default: this tree's viewer/). Pointing it at an older
checkout renders "before" images with exactly the same cameras and lights (tools/asset_review.html).
--intro captures the running game (timing drifts on slow machines); --intro-frames steps the intro on the review
page with a fixed time step, so frames land exactly on the requested intro times.
Images are 1600x900 PNG, palette-reduced when needed to stay under 1.1 MB.
"""
import argparse
import base64
import functools
import http.server
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from _browser import launch, timeout

ROOT = Path(__file__).resolve().parents[1]
REVIEW_PAGE = Path(__file__).resolve().with_name('asset_review.html')
SHOTS = (
    ('boat', 'quarter'), ('boat', 'side'), ('boat', 'deck'), ('boat', 'below'),
    ('crew', 'quarter'), ('crew', 'side'), ('crew', 'close'),
    ('station', 'shoulder'), ('station', 'front'),
)
INTRO_TIMES = (('establishing', 0.6), ('crew', 2.6), ('release', 5.4), ('underwater', 8.0))
MAX_BYTES = 1_100_000


class ReviewHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the viewer directory, with /review.html mapped to the review page in tools/."""

    def translate_path(self, path):
        if path.split('?')[0] == '/review.html':
            return str(REVIEW_PAGE)
        return super().translate_path(path)

    def log_message(self, *args):
        pass


def start_server(viewer):
    handler = functools.partial(ReviewHandler, directory=str(viewer))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def shrink(path):
    """Keep the PNG under MAX_BYTES; fall back to a dithered 256-colour palette."""
    if path.stat().st_size <= MAX_BYTES:
        return
    image = Image.open(path).convert('RGB')
    image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
        path, optimize=True)


def shoot(browser, base, query, path):
    """Render review.html?<query> and save the WebGL canvas to ``path``."""
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    page.on('pageerror', lambda error: print('PAGE ERROR', error, flush=True))
    page.goto(f'{base}/review.html?{query}')
    page.wait_for_function('window.__done || window.__error', timeout=timeout(240000))
    error = page.evaluate('window.__error')
    if error:
        raise RuntimeError(f'{query}: {error}')
    # read the WebGL canvas directly (preserveDrawingBuffer); compositor screenshots can stall here
    data_url = page.evaluate("[...document.querySelectorAll('canvas')].pop().toDataURL('image/png')")
    path.write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
    shrink(path)
    print(path, path.stat().st_size, flush=True)
    page.close()
    return path


def render(out, viewer, prefix, only=None, intro_times=None):
    """Asset review shots, or (``intro_times``) deterministic deploy-intro frames at those intro times."""
    server = start_server(viewer)
    base = f'http://127.0.0.1:{server.server_address[1]}'
    written = []
    with sync_playwright() as playwright:
        browser = launch(playwright)
        if intro_times:
            for label, at in intro_times:
                written.append(shoot(browser, base, f'asset=intro&t={at}', out / f'{prefix}-intro-{label}.png'))
        else:
            for asset, view in SHOTS:
                if only and asset not in only:
                    continue
                written.append(shoot(browser, base, f'asset={asset}&view={view}', out / f'{prefix}-{asset}-{view}.png'))
        browser.close()
    server.shutdown()
    return written


def start_simulator(simulator_dir):
    """Start `python -m qysim.server` from ``simulator_dir`` on free ports; returns (process, http, ws)."""
    ports = []
    for _ in range(2):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            ports.append(probe.getsockname()[1])
    command = [sys.executable, '-m', 'qysim.server', '--http-port', str(ports[0]), '--ws-port', str(ports[1])]
    process = subprocess.Popen(command, cwd=simulator_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{ports[0]}/', timeout=2).read()
            return process, ports[0], ports[1]
        except OSError:
            time.sleep(0.5)
    process.terminate()
    raise RuntimeError('simulator did not start')


def capture_intro(out, simulator_dir, prefix, times=INTRO_TIMES):
    """Screenshot the in-game deploy intro at fixed intro times (the intro plays on scene load)."""
    process, http_port, ws_port = start_simulator(simulator_dir)
    written = []
    try:
        with sync_playwright() as playwright:
            browser = launch(playwright)
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            page.on('pageerror', lambda error: print('PAGE ERROR', error, flush=True))
            url = f'http://127.0.0.1:{http_port}/?ws=ws://127.0.0.1:{ws_port}&play=1&model=x1&room=assetreview'
            page.goto(url, wait_until='domcontentloaded')
            page.wait_for_function('window.__intro && window.__intro()', timeout=timeout(240000))
            for label, at in times:
                page.wait_for_function(f'window.__intro().t >= {at}', timeout=timeout(240000))
                path = out / f'{prefix}-intro-{label}.png'
                page.screenshot(path=str(path))
                shrink(path)
                written.append(path)
                print(path, path.stat().st_size, flush=True)
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=20)
    return written


def parse_time(text):
    """``label=seconds`` -> (label, seconds)."""
    label, _, seconds = text.partition('=')
    return label, float(seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('out', type=Path)
    parser.add_argument('--viewer', type=Path, default=ROOT / 'viewer')
    parser.add_argument('--prefix', default='after')
    parser.add_argument('--only', nargs='*', choices=('boat', 'crew', 'station'), help='render only these assets')
    parser.add_argument('--intro', action='store_true',
                        help='capture the in-game deploy intro from the simulator that owns --viewer instead')
    parser.add_argument('--times', nargs='*', type=parse_time, default=list(INTRO_TIMES),
                        help='intro capture points as label=seconds (default: %(default)s)')
    parser.add_argument('--intro-frames', action='store_true',
                        help='render the intro deterministically on the review page at --times (no simulator)')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.intro_frames:
        render(args.out, args.viewer.resolve(), args.prefix, intro_times=args.times)
    elif args.intro:
        capture_intro(args.out, args.viewer.resolve().parent, args.prefix, args.times)
    else:
        render(args.out, args.viewer.resolve(), args.prefix, args.only)


if __name__ == '__main__':
    main()
