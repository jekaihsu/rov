"""Actual onboard renderer with lamps at reproducible inspection poses (fixed replay, not flown)."""
import json
import math
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch
from browser_underwater_shots import capture, look_pose, quaternion
from qysim.engine import Simulator
from qysim.server import _json_default

OUT = Path(__file__).resolve().parents[2] / 'docs/design/scenes/aquaculture'
SHOTS = {
    'onboard-real': ((3., 0., 7.), (8., 0., 7.)),
    'net-close-real': ((4.5, 4., 5.), (7., 4., 5.)),
    'mort-hole-real': ((11.5, 2., 14.), (8., 0., 15.3)),
}


def replay(name, eye, target):
    sim = Simulator('aquaculture_pen', 71, model_id='falcon')
    heading, pitch = look_pose(eye, target)
    sim.vehicle.s.pos[:] = eye
    sim.vehicle.s.q[:] = quaternion(heading, pitch)
    sim.sensors.reset(sim)
    state = json.loads(json.dumps(sim.viewer_state(), default=_json_default))
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    state['rc']['right_switch'] = 2
    state['rc']['rc_lock'] = 0
    state['locked'] = False
    back = [-math.cos(math.radians(heading)), -math.sin(math.radians(heading))]
    state['tether']['nodes'] = [[eye[0] + back[0] * (1 + i), eye[1] + back[1] * (1 + i),
                                 eye[2] * (1 - i / 8)] for i in range(9)]
    frames = [{**state, 't': i * .5} for i in range(3)]
    return {'format': 1, 'hz': 2, 'clips': [dict(key=name, title=name, world=world, frames=frames, script=[])]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for name, (eye, target) in SHOTS.items():
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            report[name] = capture(page, http_base(8092), 'quality=medium&fidelity=real&cam=onboard',
                                   name, replay(name, eye, target), OUT, 8)
            report[name].update(eye_ned=eye, target_ned=target, lamp_level=2, fidelity='real')
            models = page.evaluate("""() => {
                const mort = [], farm = [];
                window.__viewer.scene.traverse(mesh => {
                    if (mesh.userData.mort) mort.push(mesh.userData.mortSpecies);
                    if (mesh.userData.fishLevel && mesh.name.startsWith('fish-pen-school-')) {
                        farm.push(Boolean(mesh.material.map?.image));
                    }
                });
                return {mort, farm};
            }""")
            assert models["mort"] == ["madai"] * 4, models
            assert models["farm"] and all(models["farm"]), models
            assert not errors, errors
            page.close()
        browser.close()
    (OUT / 'onboard-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
