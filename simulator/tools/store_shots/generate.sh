#!/usr/bin/env bash
# Regenerate the reviewable Steam images from the checked-out viewer and simulator.
set -euo pipefail
cd "$(dirname "$0")/../../.."
boards=simulator/tools/store_shots
out=docs/store/steam/assets
python simulator/tools/trailer/run.py --storyboard "$boards/dive.json" --hero-only \
  --out output/store --hero-dir "$out/shots"
python simulator/tools/trailer/run.py --storyboard "$boards/wide.json" --hero-only \
  --out output/store --hero-dir output/store/proofs
python "$boards/ui.py"
python "$boards/art.py"
