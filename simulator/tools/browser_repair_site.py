"""Capture the cable repair site's real onboard renderer from repeatable survey poses."""
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch
from browser_underwater_shots import build_replay, capture, look_pose
from qysim.cable_repair import RepairBed, repair_site

OUT = Path(__file__).resolve().parents[2] / 'docs/design/chapter4-k4'


def main():
    bed = RepairBed()
    site = repair_site()
    poses = {
        'deployment': (site.start_pos, site.start_heading_deg, 0),
        'fracture': (bed.point(-1.2, -.35, .53), *look_pose(bed.point(-1.2, -.35, .53), bed.point(0, -.72, .29))),
        'housing': ((.25, 2, 12.42), *look_pose((.25, 2, 12.42), bed.point(1.3, 2.1, .20))),
        'recovery': ((-1, 2, 7), *look_pose((-1, 2, 7), (4, 5, 3.2))),
    }
    errors = []
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for name, pose in poses.items():
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            replay, _ = build_replay(name, site.key, None, 0 if name == 'deployment' else 1, pose)
            capture(page, http_base(), 'quality=medium&fidelity=real&cam=onboard', name, replay, OUT, 12)
            page.close()
        browser.close()
    assert not errors, errors


if __name__ == '__main__':
    main()
