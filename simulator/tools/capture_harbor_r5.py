"""Photograph the running harbor site from twelve fixed NED poses."""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch
from browser_underwater_shots import build_replay, capture, look_pose
from browser_daylight_shots import PLACE, open_page

ROOT = Path(__file__).resolve().parents[2] / "docs/design/harbor-r5"
VIEWS = {
    "01-approach": ((19, -8, 1.2), (24, -10, .6)),
    "02-pile": ((19, -11, 6), (21, -10, 6.3)),
    "03-soffit": ((24, 9, 1.8), (26, 10, -1)),
    "04-toe": ((26, -7, 15.8), (24, -6, 17.8)),
    "05-wall": ((39, 4, 1.4), (42, 5, .3)),
    "06-tyre": ((37.1, 5.4, 16.8), (38.8, 6.5, 17.9)),
    "07-berth": ((6, -17, -5), (42, 0, -3)),
    "08-deck": ((20, -12, -4.7), (44, -9, -3)),
    "09-apron": ((38, 13, -6), (52, 0, -3)),
    "10-quayside": ((36, -20, -3), (43, 5, -2)),
    "11-yard": ((25, 0, -7), (64, 8, -7)),
    "12-overview": ((8, 24, -12), (43, 0, -2)),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["before", "after"])
    parser.add_argument("--layer", choices=["both", "wet", "dry"], default="both")
    parser.add_argument("--only", nargs="+", choices=VIEWS)
    args = parser.parse_args()
    folder = ROOT / args.stage
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = launch(playwright)
        for name, pose in VIEWS.items():
            if args.only and name not in args.only:
                continue
            if pose[0][2] > 0:
                if args.layer == "dry":
                    continue
                eye, target = pose
                replay, _ = build_replay(name, "harbor_inspection", "pile", 2, (eye, *look_pose(eye, target)))
                onboard = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1)
                capture(onboard, http_base(), "quality=medium&cam=onboard", name, replay, folder, 8)
                onboard.close()
                continue
            if args.layer == "wet":
                continue
            page, errors = open_page(browser, name, "harbor_inspection", False)
            page.evaluate(PLACE, [pose, .4, 30])
            page.add_style_tag(content="body * {visibility:hidden!important} canvas.gl {visibility:visible!important}")
            page.screenshot(path=str(folder / f"{name}.jpg"), type="jpeg", quality=84)
            page.close()
            if errors:
                raise RuntimeError(errors)
        browser.close()


if __name__ == "__main__":
    main()
