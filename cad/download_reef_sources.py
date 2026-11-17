"""Download N3 CC0 Sketchfab sources into a scratch folder (not the repository).

Requires SKETCHFAB_API_TOKEN (Sketchfab → Settings → Password & API).
Smithsonian corals can also be fetched from the CC0 Hugging Face mirror of the
same NMNH packages when Sketchfab is unavailable (see --corals-from hf).

Usage:
  export SKETCHFAB_API_TOKEN=...
  python cad/download_reef_sources.py --out /tmp/reef_sources
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# (id, sketchfab_uid, optional HF engine path under codepawl/smithsonian-3d-glb)
MODELS = [
    ("urchin", "4cbc27daa0404b628e3b2f05b59d4f49", None),
    ("starfish", "14319712a5f445fe8a1eb461eadf6527", None),
    ("crab", "4915ee5a2d9f46af9a24d3b8da505d00", None),
    ("sea_cucumber", "c8fcb7b084df432c9d5765eee264ee02", None),
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
    ("brain_coral", "cbbf64f211f84a7cb62887fec11f54fe",
     "engine/diploria-labyrinthiformis-87738412/diploria-labyrinthiformis-87738412.glb"),
    ("pocillopora", "925b1db06f1d407f8bbca23d91031049",
     "engine/pocillopora-damicornis-1951c814/pocillopora-damicornis-1951c814.glb"),
    ("porites", "68c44f2315374bb0a4f088c9a1ab174e",
     "engine/porites-monticulosa-32cb1ed0/porites-monticulosa-32cb1ed0.glb"),
]


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
    # Download endpoint may return 202 while the archive is prepared.
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
        gltf = (payload.get("gltf") or {})
        download_url = gltf.get("url")
        if not download_url:
            # Some responses nest under "detail" while processing.
            time.sleep(2 + attempt)
            continue
        download(download_url, dest_zip)
        return payload
    raise RuntimeError(f"timed out waiting for Sketchfab archive {uid}")


def download_hf(path: str, dest: Path):
    url = f"https://huggingface.co/datasets/codepawl/smithsonian-3d-glb/resolve/main/{path}"
    download(url, dest)


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
        name = meta.get("name")
        print("CC0 OK", model_id, name)
        if hf_path and args.corals_from in {"hf", "auto"} and (
            args.corals_from == "hf" or not token
        ):
            dest = args.out / f"{model_id}.glb"
            download_hf(hf_path, dest)
            report.append({"id": model_id, "status": "hf", "path": str(dest), "bytes": dest.stat().st_size})
            continue
        if not token:
            report.append({"id": model_id, "status": "need_token"})
            print("NEED TOKEN", model_id)
            continue
        dest = args.out / f"{model_id}.zip"
        download_sketchfab(uid, dest, token)
        # Prefer extracting scene.gltf for Blender.
        extract_dir = args.out / model_id
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)
        extract_dir.mkdir()
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(extract_dir)
        report.append({"id": model_id, "status": "sketchfab", "path": str(dest), "bytes": dest.stat().st_size})
    (args.out / "download_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"downloaded": [r for r in report if r["status"] in {"hf", "sketchfab"}],
                      "need_token": [r["id"] for r in report if r["status"] == "need_token"],
                      "skipped": [r for r in report if r["status"] == "skipped"]}, indent=2))
    if any(r["status"] == "need_token" for r in report):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
