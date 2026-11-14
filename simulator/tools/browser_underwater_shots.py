"""Capture fixed underwater camera positions in the real viewer for visual review (not a pass/fail check).

Each shot builds a one-frame replay from the real simulator: the scenario's world description and a viewer
state with the vehicle placed at a fixed pose. The page is opened in replay + capture mode, so no server
state, teleport command or physics is involved, and the onboard camera, lamps, materials, fog and
post-processing are exactly the ones a pilot sees. Frames are advanced with window.__advance so camera
smoothing and video delay settle; the first metered frame sets the exposure directly, later frames adapt.

Usage (from the simulator directory, against any running server that serves the viewer):
  python tools/run_browser_checks.py browser_underwater_shots      # writes output/underwater-shots/
  python tools/browser_underwater_shots.py --out DIR --query "quality=medium&beautify=1" [--only wreck-lit]
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch, timeout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qysim.engine import Simulator  # noqa: E402
from qysim.server import _json_default  # noqa: E402

# name, scenario, subject the vehicle looks at, lamp level 0/1/2
SHOTS = (
    ('reef', 'coral_reef', 'coral', 0),
    ('seagrass', 'seagrass_meadow', 'seagrass', 0),
    ('harbour', 'harbor_inspection', 'pile', 1),
    ('wreck-lit-1', 'korean_castle', 'wreck', 1),
    ('wreck-lit-2', 'korean_castle', 'wreck', 2),
    ('wreck-dark', 'korean_castle', 'wreck', 0),
    ('silt-lamps-full', 'incident_silt', 'silt', 2),
    ('silt-lamps-off', 'incident_silt', 'silt', 0),
)
# incident_silt: from the start pose 0.45 m over the fluff bed, full ascent thrust for 0.8 s, then 6 s of drift
# (the sequence of docs/design/silt/after_*); the vehicle is then shown back at the start pose, inside the
# cloud it raised (about 30 mg/L, 0.27 m visibility at the camera). Server puffs and turbidity are kept.
SILT_THRUST_S = 0.8
SILT_DRIFT_S = 6.0


WRECK_EYE_NED = (16.0, 0.0, 25.0)


def look_pose(eye, target):
    """Heading and pitch (deg) that point the vehicle nose from eye to target, both NED."""
    d = [target[i] - eye[i] for i in range(3)]
    heading = math.degrees(math.atan2(d[1], d[0]))
    pitch = -math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return heading, pitch


def quaternion(heading_deg, pitch_deg):
    """Body->NED quaternion [w, x, y, z] for yaw then pitch (no roll)."""
    hy = math.radians(heading_deg) / 2
    hp = math.radians(pitch_deg) / 2
    cy, sy, cp, sp = math.cos(hy), math.sin(hy), math.cos(hp), math.sin(hp)
    return [cy * cp, -sy * sp, cy * sp, sy * cp]


def subject_pose(sim, world, subject):
    """Pick the vehicle pose for one shot from the scenario geometry."""
    if subject in ('coral', 'seagrass'):
        entities = [e for e in world['habitat']['entities'] if e['kind'] == subject]
        target = min(entities, key=lambda e: math.hypot(e['pos'][0] - 12, e['pos'][1] + 6))['pos']
        eye = [target[0] - 3.2, target[1] - 0.6, target[2] - 1.3]
        heading, _ = look_pose(eye, target)
        return eye, heading, -12.0
    if subject == 'pile':
        target = [21.0, -10.0, 8.5]
        # 2 m from the pile surface (radius 0.65 m), inside the lamps' useful range in 7 m visibility.
        eye = [21.0 - 2.65, -10.4, 8.0]
        heading, pitch = look_pose(eye, target)
        return eye, heading, pitch
    # Port side of the bow section near the first inspection target: the hull plating is about 2.2 m ahead
    # (checked against the server's distance field), inside the lamps' useful range.
    return list(WRECK_EYE_NED), 0.0, -6.0


def stir_silt(sim):
    """Fly the incident_silt take-off: full ascent stick, then hands off while the cloud spreads."""
    sim.rc_physical.rc_lock = 0
    sim.rc_physical.left_wave = 1900
    for _ in range(int(SILT_THRUST_S / 0.01)):
        sim.step(0.01)
    sim.rc_physical.left_wave = 1500
    for _ in range(int(SILT_DRIFT_S / 0.01)):
        sim.step(0.01)


def build_replay(name, scenario, subject, lamp):
    sim = Simulator(scenario, seed=42)
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    if subject == 'silt':
        stir_silt(sim)
        sim.vehicle.s.pos[:] = sim.scenario.start_pos
        eye = [float(v) for v in sim.vehicle.s.pos]
        heading = math.degrees(float(sim.vehicle.euler[2]))
        pitch = math.degrees(float(sim.vehicle.euler[1]))
    else:
        eye, heading, pitch = subject_pose(sim, world, subject)
        sim.vehicle.s.pos[:] = eye
        sim.vehicle.s.q[:] = quaternion(heading, pitch)
    state = json.loads(json.dumps(sim.viewer_state(), default=_json_default))
    state['rc']['right_switch'] = lamp
    state['rc']['rc_lock'] = 0
    state['locked'] = False
    if subject != 'silt':
        # A tether leaving backwards and up, out of the onboard camera's view.
        back = [-math.cos(math.radians(heading)), -math.sin(math.radians(heading))]
        state['tether']['nodes'] = [[eye[0] + back[0] * (0.5 + i), eye[1] + back[1] * (0.5 + i), eye[2] * (1 - i / 8)]
                                    for i in range(9)]
    frames = []
    for i in range(3):
        frame = dict(state)
        frame['t'] = round(i * 0.5, 2)
        frames.append(frame)
    clip = {'key': name, 'title': name, 'world': world, 'frames': frames, 'script': []}
    meta = {'scenario': scenario, 'eye_ned': [round(v, 2) for v in eye], 'heading_deg': round(heading, 1),
            'pitch_deg': round(pitch, 1), 'lamp_level': lamp, 'visibility_m': world['scenario']['visibility_m']}
    return {'format': 1, 'hz': 2, 'clips': [clip]}, meta


def capture(page, base, query, name, replay, out, frames):
    page.route('**/__shot_replay.json', lambda route: route.fulfill(
        body=json.dumps(replay), content_type='application/json'))
    url = f'{base}/?replay=__shot_replay.json&nointro&capture&{query}'
    page.goto(url)
    page.wait_for_function('typeof window.__advance === "function" && window.__viewer?.S', timeout=timeout(90000))
    page.add_style_tag(content='#replayBar,#rpSub{display:none!important}')
    # Models (the wreck) load asynchronously; let them arrive before the frames are advanced.
    page.wait_for_load_state('networkidle', timeout=timeout(90000))
    page.wait_for_timeout(1500)
    started = time.monotonic()
    for _ in range(frames):
        page.evaluate('window.__advance(1/30)')
    seconds = time.monotonic() - started
    path = out / f'{name}.jpg'
    page.screenshot(path=str(path), type='jpeg', quality=82, timeout=timeout(240000))
    info = page.evaluate('window.__viewer.performance?.() || null')
    exposure = page.evaluate('globalThis.__underwaterOptics?.exposure?.() || null')
    return {'seconds_per_frame': round(seconds / frames, 3), 'quality': info and info.get('mode'),
            'exposure': exposure, 'bytes': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'output' / 'underwater-shots')
    parser.add_argument('--query', default='quality=medium')
    parser.add_argument('--only', default='')
    parser.add_argument('--frames', type=int, default=6, help='frames advanced before the screenshot')
    parser.add_argument('--url', default=http_base(8092))
    parser.add_argument('--size', default='1600x900', help='viewport, e.g. 800x450 for quick iteration')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        width, height = (int(v) for v in args.size.split('x'))
        page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda m: errors.append(m.text) if 'Shader Error' in m.text else None)
        for name, scenario, subject, lamp in SHOTS:
            if args.only and name not in args.only.split(','):
                continue
            replay, meta = build_replay(name, scenario, subject, lamp)
            meta.update(capture(page, args.url.rstrip('/'), args.query, name, replay, args.out, args.frames))
            report[name] = meta
            print(name, json.dumps(meta), flush=True)
        browser.close()
    (args.out / 'shots.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert not errors, errors
    print('Saved', len(report), 'shots to', args.out)


if __name__ == '__main__':
    main()
