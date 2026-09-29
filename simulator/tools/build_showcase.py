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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer"
PAGES = [
    "app.js", "style.css", "deploy_intro.js", "pilot_pip.js", "humanoid.js", "figures.js", "glb.js", "cable.js", "environment.js",
    "demo_recording.json",
]
MODELS = ["rov.glb", "workboat.glb", "worker.glb", "korean_castle.glb", "waternormals.jpg", "CREDITS.md"]


def build(out: Path, glb_json: bool, overrides: dict | None = None) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / "models").mkdir(parents=True)
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
    for f in PAGES:
        shutil.copy2(VIEWER / f, out / f)
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
