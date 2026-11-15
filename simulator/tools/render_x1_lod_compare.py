"""Render baseline vs packed X1 LOD0 under the same studio rig and write difference images.

Usage (repository root):
  python simulator/tools/render_x1_lod_compare.py

Reads simulator/output/x1-lod/baseline/rov.glb (pre-I1 copy) and the packed
simulator/viewer/models/rov.glb. Writes PNGs into docs/design/vehicle/x1-lod/.
During each pass the LOD1/LOD2 sidecars are moved aside so createVehicleModel
loads a single LOD0 file (baseline or packed) for an apples-to-apples shot.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

from render_vehicle_compare import VIEWS, render

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / 'simulator' / 'viewer' / 'models'
BASELINE = ROOT / 'simulator' / 'output' / 'x1-lod' / 'baseline' / 'rov.glb'
OUT = ROOT / 'docs' / 'design' / 'vehicle' / 'x1-lod'
CURRENT = MODELS / 'rov.glb'
SIDECARS = (MODELS / 'rov_lod1.glb', MODELS / 'rov_lod2.glb')


def render_variant(label: str, glb: Path) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stash = {}
        for path in (CURRENT, *SIDECARS):
            if path.exists():
                backup = tmp / path.name
                shutil.copy2(path, backup)
                stash[path] = backup
                if path in SIDECARS:
                    path.unlink()
        try:
            shutil.copy2(glb, CURRENT)
            report = render(OUT, ['x1-training'])
            for view in VIEWS:
                src = OUT / f'compare-{view}-x1-training.png'
                dest = OUT / f'{label}-{view}.png'
                shutil.move(str(src), str(dest))
            return report
        finally:
            for path, backup in stash.items():
                shutil.copy2(backup, path)


def difference(before: Path, after: Path, dest: Path) -> float:
    a = Image.open(before).convert('RGB')
    b = Image.open(after).convert('RGB')
    diff = ImageChops.difference(a, b)
    ImageEnhance.Brightness(diff).enhance(8).save(dest)
    pixels = list(diff.getdata())
    return sum(sum(pixel) for pixel in pixels) / (len(pixels) * 3 * 255)


def main():
    if not BASELINE.is_file():
        raise SystemExit(f'missing baseline GLB at {BASELINE}; run cad/pack_x1_rov.py once first')
    # Keep a stable copy of the packed LOD0 across the baseline pass.
    packed = Path(tempfile.mkdtemp()) / 'rov-packed.glb'
    shutil.copy2(CURRENT, packed)
    before = render_variant('before', BASELINE)
    after = render_variant('after', packed)
    scores = {}
    for view in VIEWS:
        scores[view] = difference(
            OUT / f'before-{view}.png',
            OUT / f'after-{view}.png',
            OUT / f'diff-{view}.png',
        )
    summary = {'before': before, 'after': after, 'mean_channel_delta': scores}
    (OUT / 'compare-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'draws_before': {k: v.get('calls') for k, v in before.items()},
                      'draws_after': {k: v.get('calls') for k, v in after.items()},
                      'mean_channel_delta': scores}, indent=2))
    # Same size and centre as the baseline: overview views stay under 0.5 %; the thruster close-up allows 1 %
    # (rotor rest phase and normal quantisation). A rescaled or shifted LOD0 scores several percent.
    limits = {'front34': 0.005, 'side': 0.005, 'top': 0.005, 'thruster': 0.01}
    bad = [view for view, score in scores.items() if score > limits.get(view, 0.005)]
    if bad:
        raise SystemExit(f'LOD0 differs too much from baseline in: {", ".join(bad)} ({scores})')


if __name__ == '__main__':
    main()
