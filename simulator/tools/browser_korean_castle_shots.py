"""Capture real-mode onboard lighting comparison for the Korean Castle wreck.

Acceptance poses: onboard at ~1 m and ~3 m from the port plating, lamps level 2
and lamps off. Writes docs/design/wreck/{tag}-onboard-{1m|3m}-{lit|dark}.jpg.
"""

import json
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch
import browser_underwater_shots as shots

OUT = Path(__file__).resolve().parents[2] / "docs/design/wreck"
TAG = os.environ.get("ROV_WRECK_TAG", "after")

# Local wreck-frame stand-offs (metres off the port plating at mid-height).
POSES = (
    ("1m", 1.0),
    ("3m", 3.0),
)


class PoseSimulator(shots.Simulator):
    def viewer_state(self):
        self.sensors.reset(self)
        return super().viewer_state()


def make_pose(stand_off_m):
    def pose(sim, world, subject):
        wreck = sim.scenario.obstacles[0]
        target = wreck.world_point((50.0, -11.2, 4.8)).tolist()
        eye = wreck.world_point((50.0, -11.2 - stand_off_m, 5.0)).tolist()
        heading, pitch = shots.look_pose(eye, target)
        return eye, heading, pitch

    return pose


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shots.Simulator = PoseSimulator
    report = {}
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for label, stand_off in POSES:
            shots.subject_pose = make_pose(stand_off)
            for lamp_name, lamp in (("dark", 0), ("lit", 2)):
                name = f"onboard-{label}-{lamp_name}"
                replay, meta = shots.build_replay(name, "korean_castle", "wreck", lamp)
                meta.update(
                    shots.capture(
                        page,
                        http_base(),
                        "fidelity=real&quality=high&nointro",
                        name,
                        replay,
                        OUT,
                        10,
                    )
                )
                meta["stand_off_m"] = stand_off
                meta["lamps"] = lamp
                tagged = OUT / f"{TAG}-{name}.jpg"
                produced = OUT / f"{name}.jpg"
                if produced.exists():
                    shutil.copyfile(produced, tagged)
                report[f"{TAG}-{name}"] = meta
        browser.close()
    (OUT / f"onboard-report-{TAG}.json").write_text(json.dumps(report, indent=2) + "\n")
    assert not errors, errors


if __name__ == "__main__":
    main()
