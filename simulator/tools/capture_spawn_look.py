"""Capture medium-quality, lights-off spawn views for the two inspection scenes."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch
from browser_underwater_shots import capture
from browser_scene_looks import build_replay
from qysim.engine import Simulator

OUT = Path(__file__).resolve().parents[2] / 'docs/design/hull-pen-r6/spawn'
# quality=medium, fidelity=real, lights off (lamp level 0), onboard camera.
QUERY = 'quality=medium&fidelity=real&cam=onboard'


def spawn_look(site):
    import math
    sim = Simulator(site, 71, model_id='falcon')
    eye = tuple(sim.scenario.start_pos)
    heading = float(sim.scenario.start_heading_deg)
    # Level pitch like the live spawn (start_heading only); keep the aim at the same depth.
    aim = (eye[0] + 4.5 * math.cos(math.radians(heading)),
           eye[1] + 4.5 * math.sin(math.radians(heading)),
           eye[2])
    return eye, aim


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for site in ('aquaculture_pen', 'hull_inspection'):
            eye, aim = spawn_look(site)
            page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda msg: errors.append(msg.text) if 'Shader Error' in msg.text else None)
            replay, _ = build_replay(f'{site}-spawn', (site, 71), eye, aim, 0)
            capture(page, http_base(8092), QUERY, f'{site}-spawn', replay, OUT, 8)
            assert not errors, errors
            page.close()
        browser.close()
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
