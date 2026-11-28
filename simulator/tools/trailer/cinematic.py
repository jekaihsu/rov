"""Render cinematic JSON through the viewer's frame painter at fixed timestamps."""
import argparse
import base64
import math
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _browser import launch
from trailer.encode import encode_sequence

ROOT = Path(__file__).resolve().parents[3]
PAINTER = """async id => {
  const {drawFrame} = await import('/story/cinematic/frame.js');
  const {CINEMATIC_TRACKS} = await import('/audio/music.js');
  const board = await (await fetch('/story/cinematic/' + id + '.json')).json();
  const canvas = document.createElement('canvas');
  canvas.width = 1600;
  canvas.height = 900;
  const ctx = canvas.getContext('2d');
  window.paint = (t, format) => {
    drawFrame(ctx, board, t);
    return canvas.toDataURL(format, 0.91).split(',')[1];
  };
  return board.shots.map(shot => ({
    duration: shot.duration, ambient: shot.ambient, track: CINEMATIC_TRACKS[shot.cue]?.[0]
  }));
}"""


def frame(page, t, dest):
    media = 'image/png' if dest.suffix == '.png' else 'image/jpeg'
    data = page.evaluate('args => paint(...args)', [t, media])
    dest.write_bytes(base64.b64decode(data))


def soundtrack(shots, picture, dest):
    """Mix the board's cue files and filtered sea noise against the frame timestamps."""
    command = ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(picture)]
    filters = []
    for i, shot in enumerate(shots):
        seconds = shot['duration']
        track = shot.get('track')
        if track:
            cue = ROOT / 'simulator/viewer/audio/music' / track['file']
            command.extend(['-stream_loop', '-1', '-t', str(seconds), '-i', str(cue)])
        else:
            command.extend(['-f', 'lavfi', '-t', str(seconds), '-i', 'anullsrc'])
        level = track['level'] * .325 if track else 0
        fade = min(seconds / 2, .6)
        filters.append(f'[{i + 1}:a]volume={level},afade=in:d={fade},'
                       f'afade=out:st={seconds - fade}:d={fade}[cue{i}]')
        if shot.get('ambient'):
            filters.append(f"anoisesrc=color=brown:seed=1:d={seconds}:a=0.015,lowpass=f={shot['ambient']}[sea{i}]")
            filters.append(f'[cue{i}][sea{i}]amix=normalize=0[a{i}]')
        else:
            filters.append(f'[cue{i}]anull[a{i}]')
    filters.append(''.join(f'[a{i}]' for i in range(len(shots))) + f'concat=n={len(shots)}:v=0:a=1[mix]')
    command.extend(['-filter_complex', ';'.join(filters), '-map', '0:v', '-map', '[mix]',
                    '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', str(dest)])
    subprocess.run(command, check=True)


def record(page, args):
    reviews = []
    for film in args.films:
        shots = page.evaluate(PAINTER, film)
        start = 0
        for shot in shots:
            duration = shot['duration']
            t = start + duration // 2
            dest = args.stills / f'{film}-{t:02}s.jpg'
            frame(page, t, dest)
            reviews.append(dest)
            start += duration
        if args.stills_only:
            continue
        with TemporaryDirectory() as directory:
            frames = Path(directory)
            for i in range(math.ceil(start * args.fps)):
                frame(page, i / args.fps, frames / f'frame_{i:06}.png')
            picture = encode_sequence(frames, frames / 'picture.mp4', fps=args.fps)
            args.out.mkdir(parents=True, exist_ok=True)
            soundtrack(shots, picture, args.out / f'{film}.mp4')
    sheet = Image.new('RGB', (800, 254 * math.ceil(len(reviews) / 2)), '#0c1b26')
    for i, dest in enumerate(reviews):
        x, y = i % 2 * 400, i // 2 * 254
        with Image.open(dest) as image:
            sheet.paste(image.resize((400, 225), Image.Resampling.LANCZOS), (x, y))
        ImageDraw.Draw(sheet).text((x + 12, y + 232), dest.stem, fill='#e3e6da')
    sheet.save(args.stills / 'contact-sheet.jpg', quality=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('films', nargs='*', default=['harbor', 'strait'])
    parser.add_argument('--fps', type=int, default=24, choices=range(1, 61), metavar='1..60')
    parser.add_argument('--out', type=Path, default=ROOT / 'output/trailer')
    parser.add_argument('--stills', type=Path, default=ROOT / 'docs/design/cinematics-k2')
    parser.add_argument('--stills-only', action='store_true')
    args = parser.parse_args()
    args.stills.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=ROOT / 'simulator/viewer')
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server, sync_playwright() as runner:
        Thread(target=server.serve_forever, daemon=True).start()
        browser = launch(runner)
        page = browser.new_page()
        page.goto(f'http://127.0.0.1:{server.server_port}/story/cinematic/harbor.json?lang=zh-Hant')
        record(page, args)
        browser.close()
        server.shutdown()


if __name__ == '__main__':
    main()
