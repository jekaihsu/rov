"""Photograph both inspection routes from repeatable underwater stations in NED metres."""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch
from browser_underwater_shots import capture
from browser_scene_looks import REAL, build_replay

OUT = Path(__file__).resolve().parents[2] / 'docs/design/hull-pen-r6'
STATIONS = {
    'hull_inspection': {
        'stern': ((9.2, -2.6, 6.5), (13.6, 0, 5.6)),
        'screw': ((11.4, -2.8, 6.5), (14.4, 0, 5.6)),
        'bilge': ((45, -10.3, 8.8), (46.5, -8.75, 7.6)),
        'bottom': ((51, -.5, 9.25), (51.7, -.5, 8)),
        'intake': ((43, -12, 5.7), (43, -9, 5.7)),
        'draught': ((49.85, -10.65, 2), (50, -9, 1.95)),
    },
    'aquaculture_pen': {
        'collar': ((3.6, -2.8, 1.3), (5.6, .1, 0)),
        'bridle': ((.7, -22.5, .85), (0, -24, .25)),
        'mesh': ((4.8, 3, 5), (6.5, 3, 5)),
        'tear': ((3.8, 1.2, 7), (6.1, 1.2, 7)),
        'sinker': ((5, -3, 17.3), (8, 0, 16)),
        'school': ((31.4, -1.6, 6.3), (34, .4, 6)),
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['before', 'after'])
    names = sorted(name for stations in STATIONS.values() for name in stations)
    parser.add_argument('--station', nargs='+', choices=names, default=names)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    folder = args.out / args.stage
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for site, stations in STATIONS.items():
            for name, (eye, target) in stations.items():
                if name not in args.station:
                    continue
                page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda msg: errors.append(msg.text) if 'Shader Error' in msg.text else None)
                label = f'{site}-{name}'
                replay, _ = build_replay(label, (site, 1), eye, target, 2)
                capture(page, http_base(8092), REAL, label, replay, folder, 8)
                assert not errors, errors
                page.close()
        browser.close()


if __name__ == '__main__':
    main()
