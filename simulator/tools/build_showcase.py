"""Build the static replay showcase (no simulator server needed).

    python tools/build_showcase.py                 # -> ../docs/showcase  (GitHub Pages)
    python tools/build_showcase.py --artifact DIR  # same, with .glb.json copies for hosts
                                                   #    that refuse to serve .glb files

The page is the normal cockpit with ``data-replay`` set, so it plays
viewer/demo_recording.json (tools/record_demo.py) with the deployment intro,
operator picture-in-picture and subtitles.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil

from vendor_manifest import copy_vendor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer"
# Every viewer source file ships, so new modules (hud/, input/, audio/ ...) are never forgotten.
# index.html is rewritten below; vendor/ and models/ are copied separately; dev-only pages are skipped.
SKIP_DIRS = {"vendor", "models", "node_modules", "output"}
SKIP_FILES = {"index.html", "anim_test.html", "controller-check.html", "controller-check.js"}
PAGE_SUFFIXES = {".js", ".css", ".json", ".html", ".svg", ".md", ".txt"}


def pages() -> list[Path]:
    """Viewer source files (relative paths) that the replay page may import or fetch."""
    found = []
    for path in sorted(VIEWER.rglob("*")):
        rel = path.relative_to(VIEWER)
        if not path.is_file() or rel.parts[0] in SKIP_DIRS or rel.as_posix() in SKIP_FILES:
            continue
        if path.suffix in PAGE_SUFFIXES:
            found.append(rel)
    return found


MODELS = ["rov.glb", "workboat.glb", "worker.glb", "korean_castle.glb", "waternormals.jpg", "CREDITS.md"]
MODELS += ["bluerov2_heavy.glb", "falcon.glb"]
MODELS += [f"observation-lod{lod}.glb" for lod in range(3)]
MODELS += ["observation-collision.json", "assets-report.json"]


def build(out: Path, glb_json: bool, overrides: dict | None = None) -> None:
    (out / "models").mkdir(parents=True, exist_ok=True)
    html = (VIEWER / "index.html").read_text(encoding="utf-8")
    html = html.replace("<html lang=", '<html data-replay="demo_recording.json" lang=', 1)
    assert 'data-replay=' in html, "index.html must start with <html lang=...>"
    html = html.replace("<head>", '<head>\n<script>window.QYSIM_REPLAY = "demo_recording.json";</script>', 1)
    if glb_json:
        # artifact hosts wrap the page in their own document: ship only the content
        html = re.sub(r"<!doctype html>\s*", "", html, flags=re.I)
        html = re.sub(r"</?(html|head|body)\b[^>]*>\s*", "", html, flags=re.I)
        html = html.replace("<title>X1 ROV 訓練駕駛台</title>", "<title>X1 ROV 訓練回放</title>")
    (out / "index.html").write_text(html, encoding="utf-8")
    for rel in pages():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(VIEWER / rel, out / rel)
    shutil.rmtree(out / "vendor", ignore_errors=True)
    copy_vendor(out / "vendor")
    for f in MODELS:
        src = VIEWER / "models" / f
        if overrides and f in overrides:
            src = overrides[f]
        if glb_json and f.endswith(".glb"):
            data = {"glb": base64.b64encode(src.read_bytes()).decode("ascii")}
            (out / "models" / (f + ".json")).write_text(json.dumps(data), encoding="ascii")
        else:
            shutil.copy2(src, out / "models" / f)
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"wrote {out} ({size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "docs" / "showcase"))
    ap.add_argument("--artifact", default=None, help="also write an artifact bundle (.glb as base64 JSON) here")
    ap.add_argument("--artifact-model", action="append", default=[], metavar="NAME=PATH",
                    help="replace models/NAME in the artifact bundle, e.g. rov.glb=rov_quantized.glb "
                         "(copies without meshopt in case the host blocks the WebAssembly decoder, "
                         "or a lighter wreck to stay under the host's file size limit)")
    args = ap.parse_args()
    build(Path(args.out), glb_json=False)
    if args.artifact:
        overrides = dict((k, Path(v)) for k, v in (a.split("=", 1) for a in args.artifact_model))
        build(Path(args.artifact), glb_json=True, overrides=overrides)


if __name__ == "__main__":
    main()
