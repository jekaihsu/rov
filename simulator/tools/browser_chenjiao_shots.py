"""Capture real-mode onboard lighting comparison from authored wreck poses via the existing replay harness."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch
import browser_underwater_shots as shots

OUT = Path(__file__).resolve().parents[2] / "docs/design/scenes/chenjiao"


class PoseSimulator(shots.Simulator):
    """Initialize instruments at the captured pose instead of retaining launch-depth readings."""

    def viewer_state(self):
        self.sensors.reset(self)
        return super().viewer_state()


def pose(sim, world, subject):
    wreck = sim.scenario.obstacles[0]
    eye = wreck.world_point((-9, -7, 4.1)).tolist()
    target = wreck.world_point((-8, -3.5, 3.8)).tolist()
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
            replay, meta = shots.build_replay(name, "wreck_survey", "wreck", lamp)
            meta.update(shots.capture(page, http_base(), "fidelity=real&quality=high", name, replay, OUT, 8))
            report[name] = meta
        browser.close()
    (OUT / "onboard-report.json").write_text(json.dumps(report, indent=2) + "\n")
    assert not errors, errors


if __name__ == "__main__":
    main()
