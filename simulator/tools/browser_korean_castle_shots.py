"""Capture real-mode onboard lighting comparison for the Korean Castle wreck.

Acceptance poses: onboard at ~1 m and ~3 m from the port plating, lamps level 2
and lamps off. Writes docs/design/wreck/{tag}-onboard-{1m|3m}-{lit|dark}.jpg.

Stand-off is the wreck distance-field value at the eye (unsigned SDF), not a
guessed offset from a local y that is not on the plating. At midships x=50,
z≈5 the 1 m / 3 m eyes sit near local y ≈ −10.3 / −12.3.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import http_base, launch
import browser_underwater_shots as shots

OUT = Path(__file__).resolve().parents[2] / "docs/design/wreck"
TAG = os.environ.get("ROV_WRECK_TAG", "after")

# Look-at on the port plating near the surface (sdf≈0 at ≈ y −7.65, z≈5).
# Eyes at y −10.3 / −12.3 keep FieldMesh.sdf ≈ 1 m / 3 m (review stand-offs).
HULL_TARGET = (50.0, -7.7, 5.0)
POSES = (
    ("1m", 1.0, (50.0, -10.3, 5.0)),
    ("3m", 3.0, (50.0, -12.3, 5.0)),
)
DIST_TOL_M = 0.25


class PoseSimulator(shots.Simulator):
    def viewer_state(self):
        self.sensors.reset(self)
        return super().viewer_state()


def make_pose(stand_off_m: float, eye_local: tuple[float, float, float]):
    def pose(sim, world, subject):
        wreck = sim.scenario.obstacles[0]
        target = wreck.world_point(HULL_TARGET).tolist()
        eye = wreck.world_point(eye_local).tolist()
        d_eye, _ = wreck.sdf(wreck.world_point(eye_local))
        if abs(float(d_eye) - stand_off_m) > DIST_TOL_M:
            raise AssertionError(
                f"eye stand-off {float(d_eye):.3f} m != requested {stand_off_m} m "
                f"(local eye {eye_local}, tol {DIST_TOL_M})"
            )
        heading, pitch = shots.look_pose(eye, target)
        return eye, heading, pitch

    return pose


def _cleanup_untagged_jpegs() -> None:
    """Remove leftover onboard-*.jpg copies the capture helper may leave behind."""
    for path in OUT.glob("onboard-*.jpg"):
        path.unlink(missing_ok=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shots.Simulator = PoseSimulator
    report = {}
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for label, stand_off, eye_local in POSES:
            shots.subject_pose = make_pose(stand_off, eye_local)
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
                meta["eye_local"] = list(eye_local)
                meta["hull_target_local"] = list(HULL_TARGET)
                meta["lamps"] = lamp
                tagged = OUT / f"{TAG}-{name}.jpg"
                produced = OUT / f"{name}.jpg"
                if produced.exists():
                    shutil.copyfile(produced, tagged)
                    produced.unlink()
                report[f"{TAG}-{name}"] = meta
        browser.close()
    _cleanup_untagged_jpegs()
    (OUT / f"onboard-report-{TAG}.json").write_text(json.dumps(report, indent=2) + "\n")
    assert not errors, errors


if __name__ == "__main__":
    main()
