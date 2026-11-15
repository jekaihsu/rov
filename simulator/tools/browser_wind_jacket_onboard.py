"""Actual onboard renderer with lamps at reproducible inspection poses (fixed replay, not flown)."""
import json
import math
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import http_base, launch
from browser_underwater_shots import capture, look_pose, quaternion
from qysim.engine import Simulator
from qysim.server import _json_default

OUT = Path(__file__).resolve().parents[2] / 'docs/design/scenes/wind-jacket'
SHOTS = {
    'onboard-lit': ((27.6, 7.6, 6.), (25.3, 5.3, 6.3)),
    'onboard-dark': ((27.6, 7.6, 6.), (25.3, 5.3, 6.3)),
}


def replay(name, eye, target):
    sim = Simulator('jacket_inspection', 71, model_id='falcon')
    heading, pitch = look_pose(eye, target)
    sim.vehicle.s.pos[:] = eye
    sim.vehicle.s.q[:] = quaternion(heading, pitch)
    sim.sensors.reset(sim)
    state = json.loads(json.dumps(sim.viewer_state(), default=_json_default))
    world = json.loads(json.dumps(sim.world_description(), default=_json_default))
    state['rc']['right_switch'] = 0 if name.endswith('dark') else 1
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
            page.add_init_script("localStorage.setItem('rov.quality', 'high')")
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda msg: errors.append(msg.text[:500]) if msg.type == 'error' else None)
            report[name] = capture(page, http_base(8092), 'quality=medium&fidelity=real&cam=onboard',
                                   name, replay(name, eye, target), OUT, 8)
            # Keep the actual onboard renderer and optics; omit only diagnostic target wireframes.
            page.evaluate("""() => {
                window.__viewer.scene.traverse(o => {
                    if (o.material?.wireframe) o.visible = false;
                });
                window.__advance(0);
            }""")
            page.screenshot(path=str(OUT / f'{name}.jpg'), type='jpeg', quality=82)
            report[name].update(eye_ned=eye, target_ned=target,
                                lamp_level=0 if name.endswith('dark') else 1, fidelity='real',
                                diagnostic_wireframes=False, bytes=(OUT / f'{name}.jpg').stat().st_size)
            assert not errors, errors
            page.close()
        browser.close()
    (OUT / 'onboard-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
