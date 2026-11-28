"""Local instructor course files and their host-authoritative target progression."""

import json
import math
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path

from .. import scenarios
from . import SCHEMA, validate


def enabled():
    viewer = Path(__file__).resolve().parents[2] / "viewer"
    return os.getenv("ROV_BUILD_EDITION") != "steam" and (viewer / "mission-editor/index.html").is_file()


def folder():
    return Path(os.getenv("ROV_MISSION_DIR", Path.home() / ".rov" / "missions"))


def check(script):
    json.dumps(script, allow_nan=False)
    error = next(SCHEMA.iter_errors(script), None)
    if error:
        raise ValueError(f"{error.json_path}: {error.message}")
    if not re.fullmatch(r"custom_[a-z0-9_-]{1,56}", script["id"]):
        raise ValueError("$.id: custom_[a-z0-9_-]{1,56}")
    if script["scenario"] not in scenarios.LIBRARY:
        raise ValueError("$.scenario")
    for key, expected in [("category", "course"), ("mode", "scenario_training"), ("nodes", [])]:
        if script[key] != expected:
            raise ValueError(f"$.{key}")
    if not script["title"].strip():
        raise ValueError("$.title")
    supported = {"id", "title", "scenario", "mode", "order", "category", "nodes", "strings", "beats", "instructor"}
    for key in script.keys() - supported:
        raise ValueError(f"$.{key}")
    if "instructor" not in script:
        raise ValueError("$.instructor")
    cfg = script["instructor"]
    beats = script.get("beats", [])
    if len(beats) != len(cfg["targets"]):
        raise ValueError("$.beats")
    depth = scenarios.build(script["scenario"]).seabed_depth
    for path, point in [("start_pos", cfg["start_pos"]), ("spool_pos", cfg["spool_pos"])] + [
        (f"targets[{i}].point", t["point"]) for i, t in enumerate(cfg["targets"])
    ]:
        if not 0 <= point[2] <= depth:
            raise ValueError(f"$.instructor.{path}[2]: 0..{depth}")
    if math.dist(cfg["start_pos"], cfg["spool_pos"]) > cfg["tether_length"]:
        raise ValueError("$.instructor.tether_length")
    ids = set()
    for i, b in enumerate(beats):
        if not b["id"] or b["id"] in ids or b["id"] == "done":
            raise ValueError(f"$.beats[{i}].id")
        ids.add(b["id"])
        for key in b.keys() - {"id", "next", "limit", "idle", "radio", "hint", "reminder", "hud"}:
            raise ValueError(f"$.beats[{i}].{key}")
        for key in ("limit", "idle"):
            if b.get(key, 0) > 86400:
                raise ValueError(f"$.beats[{i}].{key}: <=86400")
        expected = beats[i + 1]["id"] if i + 1 < len(beats) else "done"
        if b["next"] != expected:
            raise ValueError(f"$.beats[{i}].next")
        for field in ("radio", "hint", "reminder"):
            if field in b and b[field] not in script["strings"]["zh-TW"]:
                raise ValueError(f"$.beats[{i}].{field}")
    for lang, lines in script["strings"].items():
        if not isinstance(lines, dict) or any(not isinstance(v, str) for v in lines.values()):
            raise ValueError(f"$.strings.{lang}")
    validate(deepcopy(script))
    return script


def load(key):
    if not enabled() or not re.fullmatch(r"custom_[a-z0-9_-]{1,56}", key):
        return None
    path = folder() / (key + ".json")
    try:
        if path.stat().st_size > 262144:
            return None
        script = check(json.loads(path.read_text(encoding="utf-8")))
        return script if script["id"] == key else None
    except (ValueError, OSError, RecursionError):
        return None


def courses():
    if enabled():
        for path in sorted(folder().glob("custom_*.json")):
            script = load(path.stem)
            if script:
                yield script


def save(script):
    check(script)
    directory = folder()
    directory.mkdir(parents=True, exist_ok=True)
    data = json.dumps(script, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    if len(data) > 262144:
        raise ValueError("$: <=262144 bytes")
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as out:
        tmp = Path(out.name)
        try:
            out.write(data)
        except OSError:
            out.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        tmp.replace(directory / (script["id"] + ".json"))
    finally:
        tmp.unlink(missing_ok=True)


def configure(site, cfg):
    for key in ("start_pos", "spool_pos", "visibility_m", "tether_length"):
        setattr(site, key, cfg[key])
    for layer in ("surface", "mid", "bottom"):
        setattr(site.current, layer + "_kn", cfg["current_kn"])
        setattr(site.current, layer + "_dir", cfg["current_deg"])
    site.objectives = []


class CourseRun:
    def __init__(self, script):
        self.script = script
        self.index = 0
        self.started = 0
        self.files = 0
        self.done = 0
        self.earned = 0
        self.idle = 0

    def step(self, sim, dt):
        cfg = self.script["instructor"]
        target = cfg["targets"][self.index]
        beat = self.script["beats"][self.index]
        point = target["point"]
        passed = math.dist(point, sim.vehicle.s.pos) <= target["radius"]
        if target["kind"] == "photo":
            passed = False
            for photo in sim.camera.files[self.files :]:
                pose = photo["pose"]
                delta = [x - pose[k] for x, k in zip(point, ("n", "e", "depth"))]
                yaw = math.degrees(math.atan2(delta[1], delta[0]))
                passed |= (
                    photo["name"].endswith(".JPG")
                    and math.hypot(*delta) <= target["radius"]
                    and abs((yaw - pose["yaw"] + 180) % 360 - 180) <= 20
                    and abs(delta[2]) <= 0.3 * math.hypot(*delta[:2])
                )
        self.files = len(sim.camera.files)
        moving = any(abs(getattr(sim.rc, k) - 1500) >= 40 for k in ("left_ud", "left_lr", "right_ud", "right_lr"))
        self.idle = 0 if moving else self.idle + dt
        if passed or sim.t - self.started >= beat["limit"]:
            self.done += int(passed)
            self.earned += target["points"] if passed else 0
            self.index += 1
            self.started = sim.t
            self.idle = 0
        return self.index == len(cfg["targets"])

    def state(self):
        cfg = self.script["instructor"]
        score = round(100 * self.earned / sum(t["points"] for t in cfg["targets"]), 2)
        data = dict(
            score=score,
            passed=score >= cfg["pass_score"],
            title=self.script["title"],
            done=self.done,
            total=len(cfg["targets"]),
        )
        if self.index < len(cfg["targets"]):
            beat = self.script["beats"][self.index]
            fields = ["radio", "hint"]
            if beat.get("idle") and self.idle >= beat["idle"]:
                fields.append("reminder")
            data["lines"] = {
                lang: [lines.get(beat.get(f), "") for f in fields] for lang, lines in self.script["strings"].items()
            }
            data["target"] = cfg["targets"][self.index]
        return data
