"""Capture the underwater-look review shots of docs/design/underwater-look/ (fish and water colour per water type).

Not a pass/fail check. Every shot is a one-frame replay of the real simulator (see browser_scene_looks.py): the
vehicle is placed a few metres from the fish school nearest to the start, facing it, and the page runs the normal
onboard camera, optics, exposure and white balance (`fidelity=real`) with the lamps off and on, plus one
third-person view (`fidelity=assisted&cam=chase`) per site. The same poses on two servers give before / after pairs.

  ROV_LOOKS_TAG=before ROV_HTTP_PORT=8101 python tools/browser_underwater_look.py
  ROV_LOOKS_TAG=after ROV_LOOKS_ONLY=pen-school-lamps python tools/browser_underwater_look.py
"""
import json
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser_scene_looks as looks
from _browser import launch
from qysim.engine import Simulator

OUT = Path(os.environ.get('ROV_LOOKS_OUT') or Path(__file__).resolve().parents[2] / 'docs/design/underwater-look')
TAG = os.environ.get('ROV_LOOKS_TAG', 'after')
# scenario, seed, distance from the school centre (m), height above it (m)
SITES = (
    ('pen', 'aquaculture_pen', 71, 3.0, 0.3),
    ('penclose', 'aquaculture_pen', 71, 1.4, 0.1),
    ('reef', 'coral_reef', 42, 3.2, 0.4),
    ('harbour', 'harbor_inspection', 42, 2.8, 0.3),
    ('seagrass', 'seagrass_meadow', 42, 3.0, 0.3),
    ('wreck', 'wreck_survey', 42, 2.6, 0.3),
    ('jacket', 'jacket_inspection', 42, 3.0, 0.3),
    ('pool', 'tutorial_pool', 42, 3.0, 0.3),
    # Close-ups 1.1 m from the school centre: the nearest fish are 0.5-1.5 m from the camera.
    ('reefclose', 'coral_reef', 42, 1.1, 0.1),
    ('harbourclose', 'harbor_inspection', 42, 1.1, 0.1),
    ('seagrassclose', 'seagrass_meadow', 42, 1.1, 0.1),
    ('wreckclose', 'wreck_survey', 42, 1.1, 0.1),
    ('jacketclose', 'jacket_inspection', 42, 1.1, 0.1),
)
VIEWS = (('dark', 0, looks.REAL), ('lamps', 2, looks.REAL), ('third', 1, looks.THIRD))


def school_view(scenario, seed, distance, rise):
    """Eye and target (NED) for the school nearest the start: `distance` m from its centre on the start side."""
    sim = Simulator(scenario, seed)
    start = [float(v) for v in sim.scenario.start_pos]
    schools = sim.world.fish_schools
    school = min(schools, key=lambda s: math.dist(s['pos'][:2], start[:2]))
    centre = [float(v) for v in school['pos']]
    if school.get('pen'):
        # Pen schools sweep a 10 m circle round the pen centre; stand inside the band, looking along it.
        pen = [24.0, 0.0]
        radial = [centre[0] - pen[0], centre[1] - pen[1]]
        length = math.hypot(*radial)
        inward = [-radial[0] / length, -radial[1] / length]
        eye = [centre[0] + inward[0] * distance, centre[1] + inward[1] * distance, centre[2] - rise]
        return eye, centre
    away = [start[0] - centre[0], start[1] - centre[1]]
    length = math.hypot(*away) or 1.0
    eye = [centre[0] + away[0] / length * distance, centre[1] + away[1] / length * distance, centre[2] - rise]
    return eye, centre


def main():
    looks.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    only = [name for name in os.environ.get('ROV_LOOKS_ONLY', '').split(',') if name]
    width, height = (int(v) for v in os.environ.get('ROV_LOOKS_SIZE', '1600x900').split('x'))
    report_path = OUT / f'report-{TAG}.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for key, scenario, seed, distance, rise in SITES:
            eye, target = school_view(scenario, seed, distance, rise)
            for view_name, lamp, query in VIEWS:
                name = f'{key}-{view_name}'
                if only and name not in only:
                    continue
                page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                replay, meta = looks.build_replay(name, (scenario, seed), eye, target, lamp)
                view = looks.external_camera(replay)
                meta.update(looks.capture(page, query, f'{name}-{TAG}', replay, view))
                meta['query'] = query
                report[name] = meta
                print(name, json.dumps(meta), flush=True)
                page.close()
                assert not errors, errors
                report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        browser.close()


if __name__ == '__main__':
    main()
