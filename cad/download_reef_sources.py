"""Download N3 CC0 sources into the scratch layout expected by cad/build_reef_life.py.

Scratch layout (never committed):
  <out>/ffish/<id>/src/scene.gltf     Sketchfab glTF export (unzipped)
  <out>/smithsonian/<id>_raw.glb      Smithsonian mesh (meshopt decoded)

Requires SKETCHFAB_API_TOKEN for ffishAsia models (Sketchfab → Settings → Password & API).
Smithsonian corals can come from Sketchfab or the CC0 Hugging Face mirror of the same
NMNH packages (--corals-from hf|sketchfab|auto).

Usage:
  export SKETCHFAB_API_TOKEN=...
  python cad/download_reef_sources.py --out /tmp/reef_sources
  blender -b -P cad/build_reef_life.py -- --source /tmp/reef_sources
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# ids match ASSETS in cad/build_reef_life.py
MODELS = [
    ("urchin", "4cbc27daa0404b628e3b2f05b59d4f49", None),
    ("starfish", "14319712a5f445fe8a1eb461eadf6527", None),
    ("crab", "4915ee5a2d9f46af9a24d3b8da505d00", None),
    ("cucumber", "c8fcb7b084df432c9d5765eee264ee02", None),
    ("mussel", "0920004b72a54a099155abbad85de99d", None),
    ("barnacle", "7e2bbead73344312aad9ba99240be7ab", None),
    ("butterflyfish", "27f435f82a0443ef8980b42e4bd9105e", None),
    ("angelfish", "a5c0bb6877184e698c1992e5ce1a69d0", None),
    ("stripey", "32e3ef9d5ea24bd3a05a282416f9baac", None),
    ("wrasse", "a1fa2be4f363454baadf35fafa403e6b", None),
    ("acropora_palmata", "8cb986313c824ac38c373c0fabd0805f",
     "engine/acropora-palmata-6fd30c79/acropora-palmata-6fd30c79.glb"),
    ("acropora_hyacinthus", "5e8f3939400d4753bcb8e4a43819473c",
     "engine/madrepora-hyacinthus-1a0a3b2d/madrepora-hyacinthus-1a0a3b2d.glb"),
    ("diploria", "cbbf64f211f84a7cb62887fec11f54fe",
     "engine/diploria-labyrinthiformis-87738412/diploria-labyrinthiformis-87738412.glb"),
    ("pocillopora", "925b1db06f1d407f8bbca23d91031049",
     "engine/pocillopora-damicornis-1951c814/pocillopora-damicornis-1951c814.glb"),
    ("porites", "68c44f2315374bb0a4f088c9a1ab174e",
     "engine/porites-monticulosa-32cb1ed0/porites-monticulosa-32cb1ed0.glb"),
]

GLTF_TRANSFORM = ["npx", "--yes", "@gltf-transform/cli@4.5.1"]


def api_get(url: str, token: str | None = None) -> dict:
    headers = {"User-Agent": "rov-n3-reef-life/1.0"}
    if token:
        headers["Authorization"] = f"Token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def verify_cc0(uid: str) -> dict:
    meta = api_get(f"https://api.sketchfab.com/v3/models/{uid}")
    license_slug = ((meta.get("license") or {}).get("slug") or "").lower()
    if license_slug != "cc0":
        raise RuntimeError(f"{uid} license is {license_slug!r}, not cc0 — skip")
    return meta


def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "rov-n3-reef-life/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)


def download_sketchfab(uid: str, dest_zip: Path, token: str):
    verify_cc0(uid)
    url = f"https://api.sketchfab.com/v3/models/{uid}/download"
    for attempt in range(12):
        headers = {"Authorization": f"Token {token}", "User-Agent": "rov-n3-reef-life/1.0"}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in {202, 429}:
                time.sleep(2 + attempt)
                continue
            raise
        download_url = (payload.get("gltf") or {}).get("url")
        if not download_url:
            time.sleep(2 + attempt)
            continue
        download(download_url, dest_zip)
        return payload
    raise RuntimeError(f"timed out waiting for Sketchfab archive {uid}")


def download_hf(path: str, dest: Path):
    url = f"https://huggingface.co/datasets/codepawl/smithsonian-3d-glb/resolve/main/{path}"
    download(url, dest)


def extract_sketchfab_gltf(zip_path: Path, model_id: str, out_root: Path) -> Path:
    """Unzip into <out>/ffish/<id>/… and ensure scene.gltf is at …/src/scene.gltf."""
    staging = out_root / "ffish" / model_id / "_zip"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(staging)
    gltfs = sorted(staging.rglob("*.gltf"))
    if not gltfs:
        raise FileNotFoundError(f"no .gltf in {zip_path}")
    # Prefer scene.gltf from Sketchfab exports.
    gltfs.sort(key=lambda p: (0 if p.name.lower() == "scene.gltf" else 1, len(p.parts)))
    chosen = gltfs[0]
    src_dir = out_root / "ffish" / model_id / "src"
    if src_dir.exists():
        shutil.rmtree(src_dir)
    # Keep sibling buffers/textures next to the glTF.
    shutil.copytree(chosen.parent, src_dir)
    scene = src_dir / "scene.gltf"
    if not scene.exists():
        # Rename the chosen file to scene.gltf if needed.
        target = src_dir / chosen.name
        if target.exists() and target.name != "scene.gltf":
            target.rename(scene)
    shutil.rmtree(staging)
    if not scene.exists():
        raise FileNotFoundError(f"expected {scene}")
    return scene


def decode_coral_glb(src: Path, dest: Path):
    """Copy/decode to a Blender-importable GLB (strip meshopt if present)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(GLTF_TRANSFORM + ["copy", str(src), str(dest)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--corals-from", choices=("sketchfab", "hf", "auto"), default="auto")
    args = parser.parse_args()
    token = os.environ.get("SKETCHFAB_API_TOKEN", "").strip()
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    for model_id, uid, hf_path in MODELS:
        if args.only and model_id not in args.only:
            continue
        try:
            meta = verify_cc0(uid)
        except Exception as exc:
            report.append({"id": model_id, "status": "skipped", "reason": str(exc)})
            print("SKIP", model_id, exc)
            continue
        print("CC0 OK", model_id, meta.get("name"))
        is_coral = hf_path is not None
        use_hf = is_coral and args.corals_from in {"hf", "auto"} and (
            args.corals_from == "hf" or not token
        )
        if use_hf:
            raw = args.out / "_hf" / f"{model_id}.glb"
            download_hf(hf_path, raw)
            dest = args.out / "smithsonian" / f"{model_id}_raw.glb"
            decode_coral_glb(raw, dest)
            report.append({"id": model_id, "status": "hf", "path": str(dest), "bytes": dest.stat().st_size})
            continue
        if not token:
            report.append({"id": model_id, "status": "need_token"})
            print("NEED TOKEN", model_id)
            continue
        zip_path = args.out / "_zips" / f"{model_id}.zip"
        download_sketchfab(uid, zip_path, token)
        if is_coral:
            # Sketchfab coral zip → decode to smithsonian/<id>_raw.glb
            extract_dir = args.out / "_zips" / model_id
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
            glbs = list(extract_dir.rglob("*.glb")) + list(extract_dir.rglob("*.gltf"))
            if not glbs:
                raise FileNotFoundError(f"no mesh in {zip_path}")
            glbs.sort(key=lambda p: (0 if p.suffix.lower() == ".glb" else 1, p.stat().st_size), reverse=True)
            dest = args.out / "smithsonian" / f"{model_id}_raw.glb"
            decode_coral_glb(glbs[0], dest)
            report.append({"id": model_id, "status": "sketchfab", "path": str(dest), "bytes": dest.stat().st_size})
        else:
            scene = extract_sketchfab_gltf(zip_path, model_id, args.out)
            report.append({"id": model_id, "status": "sketchfab", "path": str(scene), "bytes": scene.stat().st_size})
    (args.out / "download_report.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = {
        "downloaded": [r for r in report if r["status"] in {"hf", "sketchfab"}],
        "need_token": [r["id"] for r in report if r["status"] == "need_token"],
        "skipped": [r for r in report if r["status"] == "skipped"],
    }
    print(json.dumps(summary, indent=2))
    if summary["need_token"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
