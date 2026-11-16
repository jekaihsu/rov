"""Capture real-mode onboard lighting comparison for the Korean Castle wreck.

Acceptance poses: onboard at ~1 m and ~3 m from the port plating, lamps level 2
and lamps off. Writes docs/design/wreck/{tag}-onboard-{1m|3m}-{lit|dark}.jpg.

Stand-off is the wreck distance-field value at the eye (unsigned SDF), not a
guessed offset from a local y that is not on the plating. At midships x=50,
z≈5 the 1 m / 3 m eyes sit near local y ≈ −10.3 / −12.3.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from playwright.sync_api import sync_playwright
from _browser import http_base, launch
import browser_underwater_shots as shots

OUT = Path(__file__).resolve().parents[2] / "docs/design/wreck"
TAG = os.environ.get("ROV_WRECK_TAG", "after")

# Look toward the port plating; the target is inside the hull, not a distance reference.
# Eyes at y −10.3 / −12.3 keep FieldMesh.sdf ≈ 1 m / 3 m (review stand-offs).
HULL_TARGET = (50.0, -7.7, 5.0)
POSES = (
    ("1m", 1.0),
    ("3m", 3.0),
)
DIST_TOL_M = 0.005
POSE_REPORT = {}


class PoseSimulator(shots.Simulator):
    def viewer_state(self):
        self.sensors.reset(self)
        return super().viewer_state()


def make_pose(stand_off_m: float):
    def pose(sim, world, subject):
        wreck = sim.scenario.obstacles[0]
        target = wreck.world_point(HULL_TARGET).tolist()
        # Solve the server FieldMesh SDF, keeping x=50 and z=5 fixed.
        lo, hi = -16.0, -9.0
        for _ in range(40):
            y = (lo + hi) / 2
            distance, _ = wreck.sdf(wreck.world_point((50.0, y, 5.0)))
            if distance > stand_off_m:
                lo = y
            else:
                hi = y
        local = (50.0, (lo + hi) / 2, 5.0)
        camera_eye = wreck.world_point(local)
        distance, _ = wreck.sdf(camera_eye)
        assert abs(float(distance) - stand_off_m) < DIST_TOL_M
        heading, pitch = shots.look_pose(camera_eye, target)
        # subject_pose returns the vehicle origin; compensate the real camera mount.
        from qysim.engine import q_rot
        offset = q_rot(np.asarray(shots.quaternion(heading, pitch)),
                       np.asarray(sim.vehicle.definition.camera_body))
        eye = (camera_eye - offset).tolist()
        POSE_REPORT.update(eye_local=list(local), camera_eye_ned=camera_eye.tolist(),
                           measured_distance_m=float(distance))
        return eye, heading, pitch

    return pose


def _cleanup_untagged_jpegs() -> None:
    """Remove leftover onboard-*.jpg copies the capture helper may leave behind."""
    for path in OUT.glob("onboard-*.jpg"):
        path.unlink(missing_ok=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    _cleanup_untagged_jpegs()
    shots.Simulator = PoseSimulator
    report = {}
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        if TAG == "before":
            baseline = subprocess.check_output(
                ["git", "show", "origin/main:simulator/viewer/models/korean_castle.glb"])
            page.route("**/models/korean_castle.glb", lambda route: route.fulfill(
                body=baseline, content_type="model/gltf-binary"))
        model_bytes = baseline if TAG == "before" else (
            OUT.parents[2] / "simulator/viewer/models/korean_castle.glb").read_bytes()
        model_hash = hashlib.sha256(model_bytes).hexdigest()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for label, stand_off in POSES:
            shots.subject_pose = make_pose(stand_off)
            for lamp_name, lamp in (("dark", 0), ("lit", 2)):
                name = f"onboard-{label}-{lamp_name}"
                replay, meta = shots.build_replay(name, "korean_castle", "wreck", lamp)
                # Calibrate the mounted camera from the rendered pose (including async model
                # initialization), then recapture. Temporary shots never enter the docs folder.
                with tempfile.TemporaryDirectory() as tmp:
                    for attempt in range(2):
                        print(f"Capturing {TAG}-{name}, attempt {attempt + 1}", flush=True)
                        capture_meta = shots.capture(
                            page, http_base(), "fidelity=real&quality=high&nointro",
                            name, replay, Path(tmp), 1 if attempt == 0 else 10,
                        )
                        camera = page.evaluate("window.__viewer.camera.position.toArray()")
                        actual = np.asarray([camera[2], -camera[0], -camera[1]])
                        correction = np.asarray(POSE_REPORT["camera_eye_ned"]) - actual
                        if attempt == 1:
                            assert np.linalg.norm(correction) < DIST_TOL_M, (actual, correction)
                            break
                        for frame in replay["clips"][0]["frames"]:
                            frame["pos"] = (np.asarray(frame["pos"]) + correction).tolist()
                    meta.update(capture_meta)
                    if lamp:
                        exposure = meta["exposure"]
                        assert abs(np.log(exposure["exposure"] / exposure["target"])) < 0.05, exposure
                    (Path(tmp) / f"{name}.jpg").replace(OUT / f"{TAG}-{name}.jpg")
                camera = page.evaluate("window.__viewer.camera.position.toArray()")
                actual_ned = [camera[2], -camera[0], -camera[1]]
                sim = PoseSimulator("korean_castle", seed=42)
                measured, _ = sim.scenario.obstacles[0].sdf(np.asarray(actual_ned))
                assert abs(float(measured) - stand_off) < DIST_TOL_M, (actual_ned, measured)
                assert "碧海號" in page.locator("body").inner_text()
                meta["model_sha256"] = model_hash
                meta["rendered_eye_ned"] = actual_ned
                meta["rendered_distance_m"] = float(measured)
                meta["stand_off_m"] = stand_off
                meta.update(POSE_REPORT)
                meta["hull_target_local"] = list(HULL_TARGET)
                meta["lamps"] = lamp
                report[f"{TAG}-{name}"] = meta
                print(f"{TAG}-{name}: SDF={float(measured):.6f} m", flush=True)
        browser.close()
    _cleanup_untagged_jpegs()
    (OUT / f"onboard-report-{TAG}.json").write_text(json.dumps(report, indent=2) + "\n")
    assert not errors, errors


if __name__ == "__main__":
    main()
