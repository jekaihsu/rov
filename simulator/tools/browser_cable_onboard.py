"""Actual onboard renderer with lamps at reproducible inspection poses (fixed replay, not flown)."""
import argparse
import json
import math
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch
from browser_underwater_shots import capture, look_pose, quaternion
from qysim.engine import Simulator
from qysim.server import _json_default

OUT = Path(__file__).resolve().parents[2] / 'docs/design/scenes/cable_route'
from qysim.cable_route import layout, at
DATA = layout()[1]
SHOTS = {}
for name, chainage in [('buried', 18), ('partial', 56), ('exposed', 115),
                       ('free-span', 141), ('protected', 202), ('crossing', 244)]:
    target = at(DATA['centerline'], chainage)
    SHOTS[name] = (tuple(target + [-2.8, -.5, -1.7]), tuple(target))
for anomaly in DATA['anomalies']:
    target = at(DATA['centerline'], anomaly['chainage_m'])
    SHOTS[anomaly['id']] = (tuple(target + [-1.8, -.5, -.9]), tuple(target))
for name in ('free-span', 'excess_span'):
    target = at(DATA['centerline'], DATA['anomalies'][-1]['chainage_m'])
    SHOTS[name] = (tuple(target + [-.4, 2., -.35]), tuple(target))
SHOTS['lights-off'] = SHOTS['exposed']



SIM = None


def replay(name, eye, target):
    global SIM
    if SIM is None:
        SIM = Simulator('cable_survey', 51, model_id='falcon')
    sim = SIM
    heading, pitch = look_pose(eye, target)
    sim.vehicle.s.pos[:] = eye
    sim.vehicle.s.q[:] = quaternion(heading, pitch)
    sim.sensors.reset(sim)
    state = json.loads(json.dumps(sim.viewer_state(), default=_json_default))
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    state['rc']['right_switch'] = 0 if name == 'lights-off' else 1
    state['rc']['rc_lock'] = 0
    state['locked'] = False
    back = [-math.cos(math.radians(heading)), -math.sin(math.radians(heading))]
    state['tether']['nodes'] = [[eye[0] + back[0] * (1 + i), eye[1] + back[1] * (1 + i),
                                 eye[2] * (1 - i / 8)] for i in range(9)]
    frames = [{**state, 't': i * .5} for i in range(3)]
    clip = dict(key=name, title=name, world=world, frames=frames, script=[])
    return {'format': 1, 'hz': 2, 'clips': [clip]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default=os.environ.get('ROV_CABLE_SHOTS', ''), help='Comma-separated shot names')
    args = parser.parse_args()
    report_path = OUT / 'onboard-report.json'
    report = json.loads(report_path.read_text()) if args.only and report_path.exists() else {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for name, (eye, target) in SHOTS.items():
            if args.only and name not in args.only.split(','):
                continue
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            report[name] = capture(page, http_base(8092), 'quality=medium&fidelity=real&cam=onboard',
                                   name, replay(name, eye, target), OUT, 6)
            report[name].update(eye_ned=eye, target_ned=target,
                                lamp_level=0 if name == 'lights-off' else 1, fidelity='real')
            report[name]['render'] = page.evaluate("""() => {
                const renderer = window.__viewer.renderer;
                renderer.info.autoReset = false;
                renderer.info.reset();
                window.__advance(1 / 30);
                const info = {...renderer.info.render};
                renderer.info.autoReset = true;
                return info;
            }""")
            assert not errors, errors
            page.close()
        browser.close()
    (OUT / 'onboard-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
