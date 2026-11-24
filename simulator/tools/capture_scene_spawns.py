"""Capture medium-quality, lights-off spawn poses for T1-owned outdoor scenes.

Uses the same replay-placement path as browser_scene_looks.py.

  cd simulator && ROV_BROWSER_TIMEOUT_SCALE=3 python3 tools/capture_scene_spawns.py
"""
from __future__ import annotations

import base64
import json
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout
from browser_underwater_shots import look_pose, quaternion
from qysim.engine import Simulator
from qysim.scene_landmarks import OWNED
from qysim.server import _json_default

OUT = Path(os.environ.get('ROV_SPAWN_OUT') or Path(__file__).resolve().parents[2] / 'docs/design/scene-density/spawns')
QUERY = 'quality=medium&fidelity=real&cam=onboard'
MAX_BYTES = 300_000
SKIP = {'random'}


def aim_target(world, start):
    finds = [e for e in world.get('habitat', {}).get('entities', []) if str(e.get('id', '')).startswith('inspection-')]
    if finds:
        return min(finds, key=lambda e: math.dist(e['pos'][:2], start[:2]))['pos']
    objectives = [o['point'] for o in world.get('scenario', {}).get('objectives', []) if o.get('point')]
    if objectives:
        return objectives[0]
    return [start[0] + 8, start[1], start[2] + 2]


def build_replay(key):
    sim = Simulator(key, seed=42)
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    eye = list(sim.scenario.start_pos)
    target = aim_target(world, eye)
    heading, pitch = look_pose(eye, target)
    sim.vehicle.s.pos[:] = eye
    sim.vehicle.s.q[:] = quaternion(heading, pitch)
    sim.sensors.reset(sim)
    state = json.loads(json.dumps(sim.viewer_state(), default=_json_default))
    state['rc']['right_switch'] = 0
    state['rc']['rc_lock'] = 0
    state['locked'] = False
    state['tether'].update({'broken': False, 'break_reason': None, 'snagged_on': [], 'warn': False})
    back = [-math.cos(math.radians(heading)), -math.sin(math.radians(heading))]
    state['tether']['nodes'] = [[eye[0] + back[0] * (1 + i), eye[1] + back[1] * (1 + i), eye[2] * (1 - i / 8)]
                                for i in range(9)]
    frames = [{**state, 't': i * 0.5} for i in range(3)]
    clip = {'key': key, 'title': key, 'world': world, 'frames': frames, 'script': []}
    return {'format': 1, 'hz': 2, 'clips': [clip]}


def capture(page, key, replay):
    page.route('**/__spawn_replay.json', lambda route: route.fulfill(
        body=json.dumps(replay), content_type='application/json'))
    page.goto(f'{http_base(8092)}/?replay=__spawn_replay.json&nointro&capture&{QUERY}',
              wait_until='domcontentloaded', timeout=timeout(120_000))
    page.wait_for_function('typeof window.__advance === "function" && window.__viewer?.S',
                           timeout=timeout(120_000))
    page.add_style_tag(content='#replayBar,#rpSub,#hud{display:none!important}')
    page.wait_for_timeout(timeout(1200))
    for _ in range(12):
        page.evaluate('window.__advance(1/15)')
    path = OUT / f'{key}.jpg'
    quality = 82
    while True:
        page.screenshot(path=str(path), type='jpeg', quality=quality, timeout=timeout(240_000))
        if path.stat().st_size <= MAX_BYTES or quality <= 40:
            break
        quality -= 8
    print(f'{key}: {path.stat().st_size} bytes q={quality}')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenes = sorted(OWNED - SKIP)
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        try:
            for key in scenes:
                page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                capture(page, key, build_replay(key))
                assert not errors, errors
                page.close()
        finally:
            browser.close()


if __name__ == '__main__':
    main()
EOF
# Fix http_base usage - check signature
rg -n 'def http_base|def launch' simulator/tools/_browser.py | head -20
sed -n '1,80p' simulator/tools/_browser.py
