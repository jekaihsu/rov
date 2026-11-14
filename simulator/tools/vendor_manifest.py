"""Resolve the viewer's literal ES module imports into one shared Three.js manifest."""
import argparse
import json
import re
import shutil
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "viewer"
MANIFEST = Path(__file__).with_name("vendor-manifest.json")
IMPORT = re.compile(r"(?:\b(?:import|export)\s+[^;]*?\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)['\"]([a-zA-Z0-9_./@-]+)['\"]")


def manifest():
    pending = [p for p in VIEWER.rglob("*.js") if "vendor" not in p.relative_to(VIEWER).parts]
    pending += list(VIEWER.glob("*.html"))
    visited = set()
    while pending:
        file = pending.pop().resolve()
        if file in visited:
            continue
        visited.add(file)
        source = re.sub(r"/\*.*?\*/|^[ \t]*//[^\n]*", "", file.read_text(), flags=re.S | re.M)
        for spec in IMPORT.findall(source):
            if spec == "three":
                target = VIEWER / "vendor/three/build/three.module.js"
            elif spec.startswith("three/addons/"):
                target = VIEWER / "vendor/three/examples/jsm" / spec.removeprefix("three/addons/")
            elif spec.startswith("."):
                target = file.parent / spec
            else:
                raise ValueError(f"Unresolved module {spec} in {file}")
            if not target.is_file():
                raise FileNotFoundError(target)
            pending.append(target)
    files = [p.relative_to(VIEWER / "vendor/three").as_posix()
             for p in visited if p.is_relative_to(VIEWER / "vendor/three")]
    return sorted(["LICENSE", *files])


def copy_vendor(destination):
    for name in json.loads(MANIFEST.read_text()):
        target = destination / "three" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(VIEWER / "vendor/three" / name, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    files = manifest()
    if args.check:
        assert json.loads(MANIFEST.read_text()) == files, "Regenerate vendor-manifest.json"
    else:
        MANIFEST.write_text(json.dumps(files, indent=2) + "\n")
    if args.prune:
        keep = set(files)
        for file in (VIEWER / "vendor/three").rglob("*"):
            if file.is_file() and file.relative_to(VIEWER / "vendor/three").as_posix() not in keep:
                file.unlink()
    print(f"Three.js manifest: {len(files)} files")
