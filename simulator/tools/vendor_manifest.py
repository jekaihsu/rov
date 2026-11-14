"""Resolve imports and preserve manually listed runtime decoder/worker assets.

vendor-manifest.json: modules is generated; runtime is maintained by hand for
path-loaded assets (e.g. Basis/Draco WASM) invisible to the ES module graph.
--check never writes files. Generation restores missing files from pinned npm Three.js.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "viewer"
MANIFEST = Path(__file__).with_name("vendor-manifest.json")
NPM_THREE = VIEWER.parent / "desktop/node_modules/three"
THREE_VERSION = "0.160.0"
REGENERATE = (
    "Run from the repository root: (cd simulator/desktop && npm ci) && "
    "python simulator/tools/vendor_manifest.py --prune; commit the manifest and vendor files."
)
IMPORT = re.compile(
    r"(?:\b(?:import|export)\s+[^;]*?\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)"
    r"['\"]([a-zA-Z0-9_./@-]+)['\"]"
)


def vendor_file(name, check=False):
    root = (VIEWER / "vendor/three").resolve()
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Vendor path escapes three/: {name}")
    if target.is_file():
        return target
    if check:
        raise ValueError(f"Missing vendor file: {name}. {REGENERATE}")
    package = NPM_THREE / "package.json"
    if not package.is_file() or json.loads(package.read_text(encoding="utf-8"))["version"] != THREE_VERSION:
        raise ValueError(f"Install three@{THREE_VERSION} before restoring {name}. {REGENERATE}")
    source = NPM_THREE / name
    if not source.is_file():
        raise ValueError(f"Not present in three@{THREE_VERSION}: {name}. {REGENERATE}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def vendor_files(data):
    return sorted(set(data["modules"] + data["runtime"]))


def manifest(check=False):
    pending = [p for p in VIEWER.rglob("*.js") if "vendor" not in p.relative_to(VIEWER).parts]
    pending += list(VIEWER.glob("*.html"))
    vendor_root = (VIEWER / "vendor/three").resolve()
    visited = set()
    while pending:
        file = pending.pop().resolve()
        if file in visited:
            continue
        visited.add(file)
        source = re.sub(r"/\*.*?\*/|^[ \t]*//[^\n]*", "", file.read_text(encoding="utf-8"), flags=re.S | re.M)
        for spec in IMPORT.findall(source):
            if spec == "three":
                target = VIEWER / "vendor/three/build/three.module.js"
            elif spec.startswith("three/addons/"):
                target = VIEWER / "vendor/three/examples/jsm" / spec.removeprefix("three/addons/")
            elif spec.startswith("."):
                target = file.parent / spec
            else:
                raise ValueError(f"Unresolved module {spec} in {file}")
            target = target.resolve()
            if target.is_relative_to(vendor_root):
                target = vendor_file(target.relative_to(vendor_root).as_posix(), check)
            elif not target.is_file():
                raise FileNotFoundError(f"Missing viewer import: {target}")
            pending.append(target)
    files = [p.relative_to(VIEWER / "vendor/three").as_posix()
             for p in visited if p.is_relative_to(VIEWER / "vendor/three")]
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = sorted(["LICENSE", *files])
    for name in set(modules + data["runtime"]):
        vendor_file(name, check)
    return {**data, "modules": modules}


def prune_vendor(data):
    keep = set(vendor_files(data))
    for file in (VIEWER / "vendor/three").rglob("*"):
        if file.is_file() and file.relative_to(VIEWER / "vendor/three").as_posix() not in keep:
            file.unlink()


def copy_vendor(destination):
    for name in vendor_files(json.loads(MANIFEST.read_text(encoding="utf-8"))):
        target = destination / "three" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(VIEWER / "vendor/three" / name, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    try:
        data = manifest(check=args.check)
        if args.check:
            if json.loads(MANIFEST.read_text(encoding="utf-8")) != data:
                raise ValueError(f"Vendor manifest is stale. {REGENERATE}")
        else:
            MANIFEST.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        files = vendor_files(data)
        if args.prune:
            if args.check:
                parser.error("--check cannot be combined with --prune")
            prune_vendor(data)
        print(f"Three.js manifest: {len(files)} files")
    except (ValueError, FileNotFoundError) as error:
        parser.exit(1, f"{error}\n")
