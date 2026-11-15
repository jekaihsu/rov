"""Capture real-mode onboard lighting comparison for the Korean Castle wreck."""

import json
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch
import browser_underwater_shots as shots

OUT = Path(__file__).resolve().parents[2] / "docs/design/wreck"
TAG = os.environ.get("ROV_WRECK_TAG", "after")


class PoseSimulator(shots.Simulator):
    def viewer_state(self):
        self.sensors.reset(self)
        return super().viewer_state()


def pose(sim, world, subject):
    # Stand ~3.5 m off the port plating so lamps resolve rust and fouling under real optics.
    wreck = sim.scenario.obstacles[0]
    target = wreck.world_point((50.0, -11.2, 4.8)).tolist()
    eye = wreck.world_point((50.0, -14.7, 5.0)).tolist()
    heading, pitch = shots.look_pose(eye, target)
    return eye, heading, pitch


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shots.subject_pose = pose
    shots.Simulator = PoseSimulator
    report = {}
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for name, lamp in (("onboard-dark", 0), ("onboard-lit", 2)):
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
