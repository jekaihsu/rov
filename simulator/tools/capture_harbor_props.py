"""Capture matched inspection views from the optical centre of the onboard camera."""
import argparse
import math
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch
from browser_underwater_shots import build_replay, capture, look_pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--only', nargs='+', help='capture only the named views')
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    views = [(f'pile-{distance}m', (20.4, -10, 2.6), distance, (1, 0, 0)) for distance in (1, 3, 6)]
    views += [('crab-pot', (24, -6, 17.8), 1, (.8, 0, .6)),
              ('shackle', (23.08, -10.15, 1.18), 1, (0, 1, 0)),
              ('tyre', (38.8, 6.5, 17.88), 1, (.6, 0, .8))]
    with sync_playwright() as pw:
        browser = launch(pw)
        for name, target, distance, forward in views:
            if args.only and name not in args.only:
                continue
            lens = [t - distance * f for t, f in zip(target, forward)]
            heading, pitch = look_pose(lens, target)
            yaw, tilt = map(math.radians, (heading, pitch))
            down = (math.sin(tilt)*math.cos(yaw), math.sin(tilt)*math.sin(yaw), math.cos(tilt))
            body = [c - .39*f + .03*d for c, f, d in zip(lens, forward, down)]
            replay, _ = build_replay(name, 'harbor_inspection', 'pile', 1, (body, heading, pitch))
            page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda msg: errors.append(msg.text) if 'Shader Error' in msg.text else None)
            print(name, capture(page, http_base(), 'quality=medium&cam=onboard&fidelity=real',
                                name, replay, args.folder, 6), flush=True)
            actual = page.evaluate("""() => {
              const p = window.__viewer.camera.position;
              return [p.z, -p.x, -p.y];
            }""")
            if math.dist(actual, lens) > .025 or errors:
                raise RuntimeError(f'{name}: expected lens {lens}, got {actual}, errors {errors}')
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
