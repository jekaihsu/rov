"""Capture the lamp and exposure review shots of docs/design/lamp-exposure/ in the real viewer (not a pass/fail check).

Every shot is a one-frame replay of the real simulator (see browser_scene_looks.py): the vehicle is placed at a fixed
pose with the onboard camera in `fidelity=real`, with the lamps off, at level 1 and at level 2. The same poses on two
servers give before / after pairs. Each report entry adds the range from the camera to the first surface on the
optical axis (`centre_range_m`, a raycast in the page), so "1 m" and "3 m" shots are checked, not assumed.

  ROV_LOOKS_TAG=before ROV_HTTP_PORT=8101 python tools/browser_lamp_exposure.py
  ROV_LOOKS_TAG=after ROV_LOOKS_ONLY=wreck1m-2,wreck3m-2 python tools/browser_lamp_exposure.py
"""
import json
import math
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

import browser_scene_looks as looks
import browser_underwater_look as fish_looks
from _browser import launch

OUT = Path(os.environ.get('ROV_LOOKS_OUT') or Path(__file__).resolve().parents[2] / 'docs/design/lamp-exposure')
TAG = os.environ.get('ROV_LOOKS_TAG', 'after')
LAMP_LEVELS = (0, 1, 2)
WRECK = ('wreck_survey', 42)
# The onboard camera sits this far ahead of the vehicle position the replay places (raycasts from both agree), so
# ranges are set from the camera, not from the vehicle centre.
CAMERA_AHEAD_M = 0.49
# Wreck hull side, 12 m aft of the model origin: the eye looks square at the side plating across the hull (heading
# 35 deg + 90 deg). The plating there is 5.8 m from the origin line at 28.0-28.6 m (seabed 30 m), found by raycasts;
# centre_range_m checks it on every run.
WRECK_HEADING = math.radians(35.0)
WRECK_STATION = (25.0 - 12.0 * math.cos(WRECK_HEADING), 5.0 - 12.0 * math.sin(WRECK_HEADING))
WRECK_ACROSS = (-math.sin(WRECK_HEADING), math.cos(WRECK_HEADING))
WRECK_SIDE_M = 5.8
WRECK_DEPTH = 28.2


def school(key):
    """Eye and target of a close fish-school shot of browser_underwater_look.py."""
    site = next(item for item in fish_looks.SITES if item[0] == key)
    return (site[1], site[2]), fish_looks.school_view(site[1], site[2], site[3], site[4])


def wreck_view(range_m):
    """Eye `range_m` from the hull side plating (along the beam line), looking square at it."""
    side = WRECK_SIDE_M + range_m + CAMERA_AHEAD_M
    eye = [WRECK_STATION[0] + WRECK_ACROSS[0] * side, WRECK_STATION[1] + WRECK_ACROSS[1] * side, WRECK_DEPTH]
    target = [WRECK_STATION[0], WRECK_STATION[1], WRECK_DEPTH]
    return eye, target


def shots():
    """name -> ((scenario, seed), eye NED, target NED)."""
    items = {}
    for key in ('reefclose', 'penclose', 'harbourclose'):
        site, (eye, target) = school(key)
        items[key] = (site, eye, target)
    harbour = ('harbor_inspection', 42)
    items['harbourpiles'] = (harbour, [19.2, -6.9, 6.0], [21.0, -10.0, 6.1])
    # Pile A (radius 0.65 m at x 21): the camera 1 m from its face.
    items['harbourpile1m'] = (harbour, [21.0 - 0.65 - 1.0 - CAMERA_AHEAD_M, -10.0, 6.0], [21.0, -10.0, 6.05])
    items['wreck1m'] = (WRECK, *wreck_view(1.0))
    items['wreck3m'] = (WRECK, *wreck_view(3.0))
    # Leg A anode at 6 m (radius 0.13 m): the camera 1 m from its outer face, looking along the leg's diagonal.
    anode = [25.736, 5.736, 5.96]
    out = (0.13 + 1.0 + CAMERA_AHEAD_M) / math.sqrt(2.0)
    items['jacketanode'] = (('jacket_inspection', 42), [anode[0] + out, anode[1] + out, 5.9], anode)
    items['seabed'] = (('open_water', 42), [0.0, 0.0, 23.4], [2.2, 0.0, 25.0])
    return items


# Range along the optical axis to the first drawn surface (structures, seabed); fish and helpers are skipped.
CENTRE_RANGE = '''() => {
  const v = window.__viewer;
  const T = v.THREE;
  const ray = new T.Raycaster();
  ray.setFromCamera(new T.Vector2(0, 0), v.camera);
  const hits = ray.intersectObjects(v.scene.children, true).filter((hit) => {
    for (let o = hit.object; o; o = o.parent) if (!o.visible) return false;
    const m = hit.object.material;
    const helper = hit.object.userData.fish || hit.object.userData.observationIgnore;
    return hit.object.isMesh && !helper && m && !m.transparent && m.isMeshStandardMaterial;
  });
  const first = hits[0];
  return first ? {range: +first.distance.toFixed(2), object: first.object.name || first.object.parent?.name} : null;
}'''


def main():
    looks.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    only = [name for name in os.environ.get('ROV_LOOKS_ONLY', '').split(',') if name]
    width, height = (int(v) for v in os.environ.get('ROV_LOOKS_SIZE', '1600x900').split('x'))
    report_path = OUT / f'report-{TAG}.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for key, (site, eye, target) in shots().items():
            for lamp in LAMP_LEVELS:
                name = f'{key}-{lamp}'
                if only and name not in only:
                    continue
                page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                replay, meta = looks.build_replay(name, site, eye, target, lamp)
                meta.update(looks.capture(page, looks.REAL, f'{name}-{TAG}', replay, None))
                meta['centre_range_m'] = page.evaluate(CENTRE_RANGE)
                meta['query'] = looks.REAL
                report[name] = meta
                print(name, json.dumps(meta), flush=True)
                page.close()
                assert not errors, errors
                report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        browser.close()


if __name__ == '__main__':
    main()
