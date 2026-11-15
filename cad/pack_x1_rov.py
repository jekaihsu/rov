"""Compress the X1 training ROV into three LODs (merge-by-material + simplify).

Usage (repository root):
  python cad/pack_x1_rov.py

Installs @gltf-transform + meshoptimizer into simulator/output/x1-lod/node_modules
(build-time only; not shipped) and runs cad/pack_x1_rov.mjs.

Outputs:
  simulator/viewer/models/rov.glb          LOD0 (appearance bar; joined draw calls)
  simulator/viewer/models/rov_lod1.glb     ~80k triangles
  simulator/viewer/models/rov_lod2.glb     ~20k triangles
  docs/design/vehicle/x1-lod-report.json
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'simulator' / 'output' / 'x1-lod'
SCRIPT = ROOT / 'cad' / 'pack_x1_rov.mjs'
LINK = ROOT / 'cad' / 'node_modules'
PACKAGES = (
    '@gltf-transform/core@4.5.1',
    '@gltf-transform/extensions@4.5.1',
    '@gltf-transform/functions@4.5.1',
    'meshoptimizer@0.22.0',
    'gl-matrix@3.4.3',
)


def ensure_modules(skip_install: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'node_modules'
    if not skip_install or not target.exists():
        subprocess.run(
            ['npm', 'install', '--prefix', str(OUT), '--no-save', '--no-package-lock', *PACKAGES],
            check=True,
        )
    if LINK.exists() or LINK.is_symlink():
        LINK.unlink()
    LINK.symlink_to(target, target_is_directory=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--skip-install', action='store_true',
                        help='reuse simulator/output/x1-lod/node_modules')
    args = parser.parse_args()
    ensure_modules(args.skip_install)
    env = os.environ.copy()
    result = subprocess.run(['node', str(SCRIPT)], cwd=str(ROOT), env=env)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
