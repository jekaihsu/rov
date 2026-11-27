"""Photograph the unflown scenario start in the normal onboard viewer.

Run with the simulator's Python package on PYTHONPATH and a running viewer at
ROV_HTTP_PORT. ROV_LOOKS_TAG and ROV_LOOKS_OUT select the comparison revision.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from qysim.engine import Simulator
from qysim.server import _json_default

import browser_scene_looks as looks
from _browser import launch

SCENES = ('cold_open_jacket', 'harbor_inspection', 'hull_inspection', 'aquaculture_pen',
          'open_water', 'wreck_survey', 'tutorial_pool')


def spawn_clip(key):
    sim = Simulator(key, 42, model_id='falcon')
    state = sim.viewer_state()
    state['rc']['right_switch'] = 0
    frames = [dict(state, t=i * 0.5) for i in range(3)]
    clip = dict(key=key, title=key, world=sim.world_description(), frames=frames, script=[])
    return json.loads(json.dumps(dict(format=1, hz=2, clips=[clip]), default=_json_default))


def main():
    looks.OUT = Path(os.getenv('ROV_LOOKS_OUT') or Path(__file__).resolve().parents[2] / 'docs/design/scene-look-v1')
    looks.OUT.mkdir(exist_ok=True, parents=True)
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for key in SCENES:
            page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            ready = None
            if key == 'wreck_survey':
                ready = "window.__viewer.scene.getObjectByName('WreckChenjiaoLOD')?.levels.length === 3"
            result = looks.capture(page, looks.REAL, f'{key}-{looks.TAG}', spawn_clip(key), None, ready=ready)
            print(key, result, flush=True)
            assert not errors, errors
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
