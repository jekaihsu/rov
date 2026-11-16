"""Capture the pen and reef review shots of docs/design/scene-looks/ in the real viewer (not a pass/fail check).

Every shot is a one-frame replay built from the real simulator (see browser_underwater_shots.py): the vehicle is
placed at a fixed pose, the page runs the normal onboard or chase camera, optics, exposure and HUD. Real-mode
shots use `fidelity=real`; the third-person shots use `fidelity=assisted&cam=chase`.

  python tools/run_browser_checks.py browser_scene_looks
  ROV_LOOKS_TAG=before ROV_LOOKS_ONLY=pen-net-lamps ROV_LOOKS_SIZE=800x450 python tools/browser_scene_looks.py
"""
import base64
import json
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout
from browser_underwater_shots import look_pose, quaternion
from qysim.engine import Simulator
from qysim.server import _json_default

OUT = Path(os.environ.get('ROV_LOOKS_OUT') or Path(__file__).resolve().parents[2] / 'docs/design/scene-looks')
TAG = os.environ.get('ROV_LOOKS_TAG', 'after')
REAL = 'quality=medium&fidelity=real&cam=onboard'
THIRD = 'quality=medium&fidelity=assisted&cam=chase'
MAX_BYTES = 300_000
# In a placed (not flown) replay the chase camera stays half a metre from the vehicle, so the third-person
# shots put the viewer's own camera at a chase-like offset and render the canvas (no HUD) with the page's
# assisted presentation, optics and exposure.
EXTERNAL_VIEW = '''([view, quality]) => {
  const v = window.__viewer;
  const P = (p) => new v.THREE.Vector3(-p[1], -p[2], p[0]);
  window.__skipRender = true;
  const hidden = [];
  v.scene.traverse((o) => {
    if (o.visible && (o.isGridHelper || o.material?.wireframe)) hidden.push(o);
  });
  for (const o of hidden) o.visible = false;
  v.camera.fov = 55;
  v.camera.position.copy(P(view[0]));
  v.camera.up.set(0, 1, 0);
  v.camera.lookAt(P(view[1]));
  v.camera.updateProjectionMatrix();
  v.camera.updateMatrixWorld();
  for (let i = 0; i < 14; i++) v.renderer.render(v.scene, v.camera);
  const image = v.renderer.domElement.toDataURL('image/jpeg', quality);
  for (const o of hidden) o.visible = true;
  window.__skipRender = false;
  return image;
}'''
PEN = ('aquaculture_pen', 71)
REEF = ('coral_reef', 42)
# name, (scenario, seed), eye NED or None (nearest coral), target NED, lamp level, query,
# optional external camera (eye, target) for third-person shots
SHOTS = (
    ('pen-net-dark', PEN, (4.9, 3.6, 6.5), (6.5, 5.0, 6.8), 0, REAL),
    ('pen-net-lamps', PEN, (4.9, 3.6, 6.5), (6.5, 5.0, 6.8), 1, REAL),
    ('pen-inside-dark', PEN, (11.0, 4.0, 8.5), (24.0, -3.0, 10.0), 0, REAL),
    ('pen-inside-lamps', PEN, (11.0, 4.0, 8.5), (24.0, -3.0, 10.0), 2, REAL),
    ('pen-mort-dark', PEN, (8.25, 2.3, 14.9), (9.0, 1.0, 15.8), 0, REAL),
    ('pen-mort-lamps', PEN, (8.25, 2.3, 14.9), (9.0, 1.0, 15.8), 1, REAL),
    ('pen-third', PEN, (6.0, -7.0, 6.5), (8.4, -11.5, 6.6), 1, THIRD, ((5.2, -4.9, 6.0), (6.9, -8.8, 6.7))),
    ('reef-dark', REEF, None, 3.4, 0, REAL),
    ('reef-lamps', REEF, None, 3.4, 2, REAL),
    ('reef-close-lamps', REEF, None, 2.0, 1, REAL),
    ('reef-third', REEF, None, 4.5, 1, THIRD),
)


def coral_view(world, distance):
    """Eye and target for the coral nearest to a fixed point of the reef, seen from `distance` metres."""
    corals = [entity for entity in world['habitat']['entities'] if entity['kind'] == 'coral']
    target = min(corals, key=lambda entity: math.hypot(entity['pos'][0] - 12, entity['pos'][1] + 6))['pos']
    eye = [target[0] - distance * 0.92, target[1] - distance * 0.18, target[2] - 0.25 - distance * 0.28]
    return eye, target


def external_camera(replay):
    """Camera 3 m behind, 1.5 m to port and 1.1 m above the placed vehicle, looking 2 m ahead of it (NED)."""
    state = replay['clips'][0]['frames'][0]
    eye = state['pos']
    w, x, y, z = state['q']
    heading = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    ahead = [math.cos(heading), math.sin(heading)]
    camera = [eye[0] - 3.0 * ahead[0] + 1.5 * ahead[1], eye[1] - 3.0 * ahead[1] - 1.5 * ahead[0], eye[2] - 1.1]
    target = [eye[0] + 2.0 * ahead[0], eye[1] + 2.0 * ahead[1], eye[2] + 0.4]
    return [camera, target]


def build_replay(name, site, eye, target, lamp):
    sim = Simulator(site[0], site[1], model_id='falcon')
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    if eye is None:
        eye, target = coral_view(world, target)
    heading, pitch = look_pose(eye, target)
    sim.vehicle.s.pos[:] = eye
    sim.vehicle.s.q[:] = quaternion(heading, pitch)
    sim.sensors.reset(sim)
    state = json.loads(json.dumps(sim.viewer_state(), default=_json_default))
    state['rc']['right_switch'] = lamp
    state['rc']['rc_lock'] = 0
    state['locked'] = False
    state['tether'].update({'broken': False, 'break_reason': None, 'snagged_on': [], 'warn': False})
    back = [-math.cos(math.radians(heading)), -math.sin(math.radians(heading))]
    state['tether']['nodes'] = [[eye[0] + back[0] * (1 + i), eye[1] + back[1] * (1 + i), eye[2] * (1 - i / 8)]
                                for i in range(9)]
    frames = [{**state, 't': i * 0.5} for i in range(3)]
    clip = {'key': name, 'title': name, 'world': world, 'frames': frames, 'script': []}
    meta = {'scenario': site[0], 'seed': site[1], 'eye_ned': [round(v, 2) for v in eye],
            'target_ned': [round(v, 2) for v in target], 'lamp_level': lamp,
            'visibility_m': world['scenario']['visibility_m'], 'water_type': world['scenario'].get('water_type')}
    return {'format': 1, 'hz': 2, 'clips': [clip]}, meta


def capture(page, query, name, replay, view):
    """Open the replay in capture mode, let camera, exposure and white balance settle, save the JPEG."""
    page.route('**/__shot_replay.json', lambda route: route.fulfill(
        body=json.dumps(replay), content_type='application/json'))
    page.goto(f'{http_base(8092)}/?replay=__shot_replay.json&nointro&capture&{query}')
    page.wait_for_function('typeof window.__advance === "function" && window.__viewer?.S', timeout=timeout(90000))
    page.add_style_tag(content='#replayBar,#rpSub{display:none!important}')
    page.wait_for_load_state('networkidle', timeout=timeout(90000))
    page.wait_for_timeout(1500)
    if query == THIRD:
        # The vehicle model is hidden when it finishes loading in a replay; switching views shows it again.
        page.evaluate('window.__viewer.setCam("onboard")')
        page.evaluate('window.__advance(1/30)')
        page.evaluate('window.__viewer.setCam("chase")')
    for _ in range(10):
        page.evaluate('window.__advance(1/15)')
    path = OUT / f'{name}.jpg'
    quality = 82
    while True:
        if query == THIRD:
            data = page.evaluate(EXTERNAL_VIEW, [view, quality / 100])
            path.write_bytes(base64.b64decode(data.split(',', 1)[1]))
        else:
            page.screenshot(path=str(path), type='jpeg', quality=quality, timeout=timeout(240000))
        if path.stat().st_size <= MAX_BYTES or quality <= 40:
            break
        quality -= 8
    exposure = page.evaluate('globalThis.__underwaterOptics?.exposure?.() || null')
    return {'exposure': exposure, 'bytes': path.stat().st_size, 'jpeg_quality': quality}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = [name for name in os.environ.get('ROV_LOOKS_ONLY', '').split(',') if name]
    width, height = (int(v) for v in os.environ.get('ROV_LOOKS_SIZE', '1600x900').split('x'))
    report_path = OUT / f'report-{TAG}.json'
    # A partial run (ROV_LOOKS_ONLY) updates the entries it reshoots and keeps the rest.
    report = json.loads(report_path.read_text(encoding='utf-8')) if only and report_path.exists() else {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for name, site, eye, target, lamp, query, *external in SHOTS:
            if only and name not in only:
                continue
            page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            replay, meta = build_replay(name, site, eye, target, lamp)
            view = list(external[0]) if external else external_camera(replay)
            meta.update(capture(page, query, f'{name}-{TAG}', replay, view))
            if query == THIRD:
                meta['camera_ned'] = view
            meta['query'] = query
            report[name] = meta
            print(name, json.dumps(meta), flush=True)
            assert not errors, errors
            page.close()
        browser.close()
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
