"""Record inspection approaches from the real spawn and replay their onboard camera at five-second intervals.

Run "record" with PYTHONPATH pointing at the baseline simulator, then "before" / "after" with PYTHONPATH
and ROV_HTTP_PORT pointing at the corresponding checkout. Vehicle state, inputs, silt and the tether
come from the same fixed-step recording on both passes. Fish follow each version's own school layout.
The cache holds the baseline replays outside version control. The "after" pass writes paired sheets;
use "sheets" to rebuild them from the saved images.
"""
import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout
from qysim.aquaculture import CENTER, RADIUS, layout
from qysim.ecology import step_schools
from qysim.engine import Simulator
from qysim.scenarios import catalogue
from qysim.server import _json_default

ROOT = Path(__file__).resolve().parents[2]
SITES = [entry['key'] for entry in catalogue() if entry['key'] != 'tutorial_pool']
TIMES = range(5, 61, 5)
SEED = 42


def route(scenario):
    """Follow the ordered work points. When orbiting external gear, keep the camera trained on it."""
    steps = []
    if scenario.key in ('aquaculture_pen', 'aquaculture_pen_slack'):
        for degrees in range(185, 545, 10):
            angle = math.radians(degrees)
            direction = np.array([math.cos(angle), math.sin(angle)])
            position = np.array([*CENTER, 7.0])
            position[:2] += (RADIUS + 3) * direction
            face = position.copy()
            face[:2] -= 4 * direction
            steps.append((position, face, 0))
        return steps
    if scenario.key == 'jacket_inspection':
        # Fly outside the four faces. In the east-going tide an inside turn between B and C
        # sweeps the vehicle into a brace. Approach the outside stand-offs from up-current.
        positions = [(5, 6.5, 4), (23, 8.5, 6), (28.8, 7.8, 6), (29, -7.9, 12),
                     (26, -9.4, 14), (13, -9.4, 16), (10.5, -7.9, 16), (10.5, 7.9, 10)]
        for i, objective in enumerate(scenario.objectives[:4]):
            face = np.array(objective.face_point)
            stand = np.array(objective.point)
            start = 2 * i
            for point in positions[start:start + 2]:
                steps.append((np.array(point), face, 0))
            if stand[1] < 0:
                stand[1] -= 1
            steps.append((stand, face, objective.hold_s + 3))
        return steps
    if scenario.key == 'aquaculture_pen_inside':
        # Inspect the mortality figures from a stand-off. Parking directly over the first fish
        # puts it underneath the vehicle instead of in the forward-facing camera.
        for fish in layout()[1]['dead_fish']:
            face = np.array(fish['pos'])
            steps.append((face + [2.1, 0, -1.6], face, 3.5))
        return steps
    if scenario.key == 'hull_inspection':
        # Approach on the starboard quarter to inspect the propeller before crossing below the keel.
        # The direct line from the launch to the first station would drive into the trailing rudder.
        steps.append((np.array([11., 3.6, 8.3]), np.array([14.4, 0., 5.6]), 2.5))
    if scenario.prewrap:
        start = np.array(scenario.start_pos, dtype=float)
        pile = next(ob for ob in scenario.obstacles if ob.name == scenario.prewrap['pile'])
        center = np.array([*pile.p0[:2], start[2]])
        radius = np.linalg.norm(start[:2] - center[:2])
        initial = math.atan2(start[1] - center[1], start[0] - center[0])
        for i in range(1, 19):
            angle = initial - i * math.pi / 6
            position = center + [radius * math.cos(angle), radius * math.sin(angle), 0]
            steps.append((position, center, 1))
    if scenario.key == 'sonar_search':
        # Final visual ID of the near face of the acoustic target. The pilot approaches and then holds
        # a stand-off within the scored checkpoint radius and the scenario's 0.8 m optical range.
        target = np.array(scenario.obstacles[0].center, dtype=float)
        # The onboard lens projects ~0.4 m beyond the CG. Leave room to read the whole cabinet.
        return [(target - [2.04, 0, 0], target, 60)]
    for objective in scenario.objectives:
        if objective.point is None:
            continue
        face = np.array(objective.face_point) if objective.face_point is not None else None
        steps.append((np.array(objective.point), face, min(15., getattr(objective, 'hold_s', 0) or 0)))
    return steps


def pwm(axis):
    return int(round(1500 + 500 * np.clip(axis, -.76, .76)))


def pilot(sim, point, face):
    state = sim.vehicle.s
    north, east, down = point - state.pos
    yaw = sim.yaw
    look = (point if face is None or math.hypot(north, east) > 7 else face) - state.pos
    turn = math.atan2(look[1], look[0]) - yaw
    rc = sim.rc_physical
    # A checkpoint has no subject to face. On arrival keep the last approach heading instead of
    # chasing a bearing to a point only a few centimetres away.
    holding_heading = face is None and math.hypot(north, east) <= 1.5
    rc.left_lr = 1500 if holding_heading else pwm(math.atan2(math.sin(turn), math.cos(turn)) * 1.4)
    rc.right_ud = pwm((math.cos(yaw) * north + math.sin(yaw) * east) * .36 - .55 * state.vel[0])
    rc.right_wave = pwm((-math.sin(yaw) * north + math.cos(yaw) * east) * .36 - .55 * state.vel[1])
    rc.left_wave = pwm(-.50 * down + .6 * state.vel[2])
    if sim.scenario.key in ('hull_inspection', 'aquaculture_pen_inside'):
        # Use the physical ROV_USA pitch stick and leave vertical station keeping to the depth controller.
        hull = sim.scenario.key == 'hull_inspection'
        rc.keep_depth = 1
        setpoint = sim.controller.depth_hold if sim.controller.depth_hold is not None else state.pos[2]
        stand_off = .7 if hull and state.pos[0] > 14 else 0
        rc.left_wave = pwm(setpoint - point[2] - stand_off)
        # At inspection speed the depth loop has enough heave authority to counter the pitched surge thrust.
        rc.right_ud = int(np.clip(rc.right_ud, 1240, 1760))
        if hull:
            target_pitch = math.radians(np.clip(7 * (state.pos[2] - 5), -10, 28))
        else:
            to_fish = face - state.pos
            target_pitch = max(math.radians(-40), -math.atan2(to_fish[2], np.linalg.norm(to_fish[:2])))
        rc.left_ud = pwm(2.2 * (sim.vehicle.euler[1] - target_pitch) + .36 * state.omega[1])
    return np.linalg.norm(point - state.pos)


def record(site, cache):
    sim = Simulator(site, seed=SEED)
    sim.rc_physical.rc_lock = 0
    sim.rc_physical.right_switch = 1
    waypoints = route(sim.scenario)
    frames = []
    index = 0
    held = 0
    for tick in range(6001):
        if tick % 100 == 0:
            frames.append(json.loads(json.dumps(sim.viewer_state(), default=_json_default)))
        if tick % 10 == 0:
            point, face, dwell = waypoints[index]
            distance = pilot(sim, point, face)
            held = held + .1 if distance <= 1.5 else 0
            if held > dwell and index < len(waypoints) - 1:
                index += 1
                held = 0
        if tick < 6000:
            sim.step(.01)
    with gzip.open(cache / f'{site}.json.gz', 'wt', encoding='utf-8') as file:
        json.dump(frames, file, separators=(',', ':'))
    print(site, 'recorded', frames[0]['pos'], 'to', frames[-1]['pos'], flush=True)


def replay(site, cache):
    sim = Simulator(site, seed=SEED)
    with gzip.open(cache / f'{site}.json.gz', 'rt', encoding='utf-8') as file:
        frames = json.load(file)
    world = sim.world_description()
    # Evolve each version's schools around the recorded vehicle. Keep the recorded optical conditions.
    for i, frame in enumerate(frames):
        if i:
            previous = np.array(frames[i - 1]['pos'])
            delta = np.array(frame['pos']) - previous
            for sample in range(1, 11):
                sim.world.time += .1
                step_schools(sim.world, .1, [{'pos': previous + delta * sample / 10, 'light': 1}])
        frame['environment']['fish_schools'] = sim.world.environment_state()['fish_schools']
    clip = dict(key=site, title=site, world=world, frames=frames, script=[])
    return json.dumps(dict(format=1, hz=1, clips=[clip]), default=_json_default)


def capture(browser, site, cache, directory):
    payload = replay(site, cache)
    directory.mkdir(parents=True, exist_ok=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    page.route('**/density-replay.json', lambda req: req.fulfill(body=payload, content_type='application/json'))
    query = 'replay=density-replay.json&nointro&nopip&capture&quality=performance&fidelity=real&cam=onboard'
    page.goto(f'{http_base()}/?{query}')
    page.wait_for_function('window.__viewer?.S && !!window.__advance', timeout=timeout(90000))
    page.wait_for_load_state('networkidle', timeout=timeout(90000))
    # Capture the optical feed edge-to-edge, keeping the exact onboard lens, fog, lights and materials.
    page.add_style_tag(content='#vp {position:fixed!important;inset:0!important;width:100vw!important;'
                               'height:100vh!important;z-index:9999!important} #vp > :not(canvas){visibility:hidden}')
    page.evaluate("""() => {
      window.dispatchEvent(new Event('resize'));
      const v = window.__viewer;
      v.rep.playing = false;
      v.setCam('onboard');
    }""")
    samples = []
    for second in TIMES:
        actual = page.evaluate("""t => {
          const v = window.__viewer;
          window.__skipRender = true;
          for (let i = 1; i <= 20; i++) {
            v.rep.t = t - 5 + i * .25;
            window.__advance(.25);
          }
          window.__skipRender = false;
          window.__advance(0);
          return {time: v.rep.t, video_time: v.S.t, ned: v.S.pos, attitude: v.S.euler};
        }""", second)
        if actual['time'] != second or abs(actual['video_time'] - second) > .25:
            raise RuntimeError(f'{site}: expected {second}, saw {actual}')
        samples.append(actual)
        path = directory / f'{second:02d}s.jpg'
        page.screenshot(path=str(path), type='jpeg', quality=81, timeout=timeout(120000))
    log = directory.parent.parent / 'routes' / f'{site}.json'
    log.parent.mkdir(exist_ok=True)
    if directory.parent.name == 'before':
        log.write_text(json.dumps(samples, separators=(',', ':')) + '\n', encoding='utf-8')
    elif json.loads(log.read_text(encoding='utf-8')) != samples:
        raise RuntimeError(f'{site}: replay trajectory differs from baseline')
    page.close()
    if errors:
        raise RuntimeError(errors)
    print(site, 'captured', flush=True)


def sheet(site, output, tags, dest):
    width, height = 240, 135
    image = Image.new('RGB', (width * 4, (height + 18) * 3 * len(tags)), '#182029')
    draw = ImageDraw.Draw(image)
    for index, second in enumerate(TIMES):
        x = index % 4 * width
        for row, tag in enumerate(tags):
            y = (index // 4 * len(tags) + row) * (height + 18)
            with Image.open(output / tag / site / f'{second:02d}s.jpg') as tile:
                assert tile.size == (1600, 900)
                image.paste(tile.resize((width, height), Image.Resampling.LANCZOS), (x, y + 18))
            draw.text((x + 4, y + 2), f'{tag}   {second:02d} s', fill='white')
    dest.mkdir(parents=True, exist_ok=True)
    image.save(dest / f'{site}.jpg', quality=88)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['record', 'before', 'after', 'sheets'])
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/design/scene-density')
    parser.add_argument('--sites', nargs='+', choices=SITES, default=SITES)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.mode == 'record':
        for site in args.sites:
            record(site, args.cache)
    elif args.mode == 'sheets':
        for site in args.sites:
            sheet(site, args.output, ['before', 'after'], args.output / 'contacts')
    else:
        with sync_playwright() as pw:
            browser = launch(pw)
            for site in args.sites:
                capture(browser, site, args.cache, args.output / args.mode / site)
                if args.mode == 'before':
                    sheet(site, args.output, ['before'], args.cache / 'before-sheets')
                else:
                    sheet(site, args.output, ['before', 'after'], args.output / 'contacts')
            browser.close()


if __name__ == '__main__':
    main()
