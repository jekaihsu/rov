#!/usr/bin/env python3
"""Bake, capture, encode, and extract hero frames for a trailer storyboard.

Examples (from the repository root, with a simulator already running on free ports
or let this script start one):

  python simulator/tools/trailer/run.py --storyboard simulator/tools/trailer/storyboards/test_5s.json
  python simulator/tools/trailer/run.py --storyboard …/store_80s.json --shots 01-harbor-fpv
  python simulator/tools/trailer/run.py --storyboard …/test_5s.json --bake-only
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SIM = TOOLS.parents[1]
ROOT = SIM.parent
sys.path.insert(0, str(TOOLS.parent))
sys.path.insert(0, str(SIM))

from trailer.bake import write_clip  # noqa: E402
from trailer.capture import capture_clip  # noqa: E402
from trailer.encode import encode_sequence  # noqa: E402
from trailer.hero import write_hero_jpeg  # noqa: E402
from trailer.storyboard import load_storyboard  # noqa: E402

OUT = SIM / 'output' / 'trailer'
HERO_DIR = ROOT / 'docs' / 'design' / 'trailer'


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def start_server(log_path: Path):
    ports = {'http': free_port(), 'ws': free_port(), 'rpc': free_port()}
    command = [sys.executable, '-m', 'qysim.server',
               '--http-port', str(ports['http']),
               '--ws-port', str(ports['ws']),
               '--rpc-port', str(ports['rpc'])]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, 'w', encoding='utf-8')
    process = subprocess.Popen(command, cwd=str(SIM), stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{ports['http']}/", timeout=2).close()
            return process, log, ports
        except OSError:
            time.sleep(0.4)
    stop_server(process, log)
    raise RuntimeError(f'simulator did not start; see {log_path}')


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


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--storyboard', type=Path, required=True, help='storyboard JSON path')
    parser.add_argument('--out', type=Path, default=OUT, help='output root (default simulator/output/trailer)')
    parser.add_argument('--hero-dir', type=Path, default=HERO_DIR, help='docs/design/trailer for review stills')
    parser.add_argument('--shots', default='', help='comma-separated shot ids (default: all)')
    parser.add_argument('--bake-only', action='store_true', help='only bake replay clips')
    parser.add_argument('--hero-only', action='store_true',
                        help='bake + one review still per shot (no full PNG sequence / video)')
    parser.add_argument('--skip-encode', action='store_true', help='keep PNG sequence, skip ffmpeg')
    parser.add_argument('--lossless', action='store_true', help='encode near-lossless H.264')
    parser.add_argument('--ffmpeg', default=None, help='ffmpeg binary')
    parser.add_argument('--http-port', type=int, default=None)
    parser.add_argument('--ws-port', type=int, default=None)
    parser.add_argument('--keep-frames', action='store_true', help='keep PNG sequence after encode')
    return parser.parse_args()


def main():
    args = parse_args()
    board = load_storyboard(args.storyboard)
    wanted = {part.strip() for part in args.shots.split(',') if part.strip()}
    shots = [shot for shot in board['shots'] if not wanted or shot['id'] in wanted]
    if not shots:
        raise SystemExit('no shots selected')

    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)
    summary = []

    process = log = ports = None
    try:
        if not args.bake_only:
            if args.http_port and args.ws_port:
                ports = {'http': args.http_port, 'ws': args.ws_port}
            else:
                process, log, ports = start_server(out_root / 'server.log')
                os.environ['ROV_HTTP_PORT'] = str(ports['http'])
                os.environ['ROV_WS_PORT'] = str(ports['ws'])

        for shot in shots:
            print(f'=== {shot["id"]} ({shot["duration"]} s) ===', flush=True)
            shot_dir = out_root / shot['id']
            clip_path = shot_dir / 'clip.json'
            frames_dir = shot_dir / 'frames'
            video_path = shot_dir / f'{shot["id"]}.mp4'
            hero_png = shot_dir / 'hero.png'
            hero_jpg = args.hero_dir / f'{shot["id"]}.jpg'

            print('  baking…', flush=True)
            write_clip(shot, clip_path, fps=board['fps'])
            size_mb = clip_path.stat().st_size / 1e6
            print(f'  wrote {clip_path} ({size_mb:.2f} MB)', flush=True)
            if args.bake_only:
                summary.append({'id': shot['id'], 'clip': str(clip_path), 'bake_mb': round(size_mb, 2)})
                continue

            print('  capturing…', flush=True)
            result = capture_clip(
                clip_path,
                None if args.hero_only else frames_dir,
                width=board['width'],
                height=board['height'],
                fps=board['fps'],
                http_port=ports['http'],
                ws_port=ports['ws'],
                hero_at=shot['hero_at'],
                hero_path=hero_png,
                hero_only=args.hero_only,
            )
            write_hero_jpeg(hero_png, hero_jpg)
            hero_kb = hero_jpg.stat().st_size // 1024
            print(f'  hero {hero_jpg.name} {hero_kb} KB', flush=True)

            if not args.hero_only and not args.skip_encode:
                print('  encoding…', flush=True)
                encode_sequence(frames_dir, video_path, fps=board['fps'], lossless=args.lossless,
                                ffmpeg=args.ffmpeg)
                print(f'  wrote {video_path}', flush=True)
                if not args.keep_frames:
                    for path in frames_dir.glob('frame_*.png'):
                        path.unlink()
                    try:
                        frames_dir.rmdir()
                    except OSError:
                        pass

            summary.append({
                'id': shot['id'],
                'frames': result['frames'],
                'video': None if args.hero_only or args.skip_encode else str(video_path),
                'hero': str(hero_jpg),
                'hero_kb': hero_kb,
            })

        manifest = out_root / 'manifest.json'
        manifest.write_text(json.dumps({'storyboard': str(args.storyboard), 'shots': summary},
                                       ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'wrote {manifest}', flush=True)
    finally:
        stop_server(process, log)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
