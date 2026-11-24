"""Capture medium-quality, lights-off spawn poses for T1-owned outdoor scenes.

Uses the same replay-placement path as browser_scene_looks.py.

  cd simulator && ROV_BROWSER_TIMEOUT_SCALE=3 ROV_HTTP_PORT=8092 python3 tools/capture_scene_spawns.py
"""
from __future__ import annotations

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
HTTP_PORT = int(os.environ.get('ROV_HTTP_PORT') or 8092)


def aim_target(world, start):
    # Prefer a mid-water subject near the eye depth so the first frame is not a seabed dive.
    finds = [e for e in world.get('habitat', {}).get('entities', []) if str(e.get('id', '')).startswith('inspection-')]
    if finds:
        def score(entity):
            pos = entity['pos']
            horizontal = math.dist(pos[:2], start[:2])
            depth_gap = abs(pos[2] - start[2])
            return horizontal + 2.5 * depth_gap
        return min(finds, key=score)['pos']
    objectives = [o['point'] for o in world.get('scenario', {}).get('objectives', []) if o.get('point')]
    if objectives:
        point = objectives[0]
        return [point[0], point[1], start[2] + 0.4 * (point[2] - start[2])]
    return [start[0] + 8, start[1], start[2] + 1]


def build_replay(key, eye=None, target=None):
    sim = Simulator(key, seed=42)
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    eye = list(eye if eye is not None else sim.scenario.start_pos)
    target = list(target if target is not None else aim_target(world, eye))
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


def capture(page, name, replay, hide_vehicle=False):
    page.route('**/__spawn_replay.json', lambda route: route.fulfill(
        body=json.dumps(replay), content_type='application/json'))
    page.goto(f'{http_base(HTTP_PORT)}/?replay=__spawn_replay.json&nointro&capture&{QUERY}',
              wait_until='domcontentloaded', timeout=timeout(120_000))
    page.wait_for_function('typeof window.__advance === "function" && window.__viewer?.S',
                           timeout=timeout(120_000))
    page.add_style_tag(content='#replayBar,#rpSub,#hud{display:none!important}')
    page.wait_for_timeout(timeout(1200))
    for _ in range(12):
        page.evaluate('window.__advance(1/15)')
    if hide_vehicle:
        # Hull meshes sit inside the near clip at 0.1 m and paint white/blue near-plane slabs;
        # hide them so the proof shot shows the water path, not the vehicle.
        page.evaluate('''() => {
          const v = window.__viewer;
          v.scene.traverse((o) => {
            if (!o.isMesh || !o.visible) return;
            const p = o.getWorldPosition(new v.THREE.Vector3());
            if (p.distanceTo(v.camera.position) < 1.2) o.visible = false;
          });
          window.__skipRender = true;
          for (let i = 0; i < 8; i++) v.renderer.render(v.scene, v.camera);
          window.__skipRender = false;
        }''')
    path = OUT / f'{name}.jpg'
    quality = 82
    while True:
        page.screenshot(path=str(path), type='jpeg', quality=quality, timeout=timeout(240_000))
        if path.stat().st_size <= MAX_BYTES or quality <= 40:
            break
        quality -= 8
    print(f'{name}: {path.stat().st_size} bytes q={quality}')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenes = sorted(OWNED - SKIP)
    only = os.environ.get('ROV_SPAWN_ONLY')
    if only:
        scenes = [key for key in scenes if key in only.split(',')]
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
            if not only or 'open_water' in (only or ''):
                # Proof shot for the near-surface water plate. Hide the vehicle so hull near-clip
                # does not mask the water/fog (the plate bug was the 800 m optics surface).
                page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                capture(page, 'open_water_depth01',
                        build_replay('open_water', eye=(0, 0, .1), target=(6.0, 0.0, 1.2)),
                        hide_vehicle=True)
                assert not errors, errors
                page.close()
        finally:
            browser.close()


if __name__ == '__main__':
    main()
