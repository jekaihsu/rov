"""Rebuild viewer/models/aquaculture/net.webp: an original tileable knotless square-mesh net (CC0, Pillow only).

One 256 px tile holds 8 x 8 meshes and is drawn 0.32 m wide (40 mm bar length, about 3 mm twine); see
viewer/aquaculture.js. Alpha is a soft ramp across the twine (0.5 at the twine edge) instead of a hard mask, so
  - the shader can cut it at a threshold near the camera and move that threshold to thicken fouled twine;
  - the mip chain averages it to the net's solidity, which the shader uses as a haze at distance.
RGB carries only a grey fibre variation (also under the transparent texels, so mips do not fringe); the shader
supplies the twine and fouling colours.

  python simulator/tools/build_pen_net_texture.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / 'viewer/models/aquaculture/net.webp'
SIZE = 256
MESHES = 8
SEED = 71


def twine_distance(across, along, rng):
    """Distance in pixels to the nearest twine of one direction; twines wander and vary in width."""
    cell = SIZE / MESHES
    index = np.floor(across / cell + 0.5).astype(int) % MESHES
    phase = rng.uniform(0, 2 * np.pi, MESHES)[index]
    wander = 1.1 * np.sin(2 * np.pi * along / SIZE * 2 + phase) + 0.5 * np.sin(2 * np.pi * along / SIZE * 5 + phase * 3)
    centre = (across + wander) / cell
    distance = np.abs(centre - np.round(centre)) * cell
    width = rng.uniform(1.05, 1.6, MESHES)[index]
    return distance, width


def build():
    rng = np.random.default_rng(SEED)
    y, x = np.mgrid[:SIZE, :SIZE].astype(float)
    vertical, vertical_width = twine_distance(x, y, rng)
    horizontal, horizontal_width = twine_distance(y, x, rng)
    # Joints of a knotless net are slightly thicker than the bars.
    joint = np.exp(-(vertical ** 2 + horizontal ** 2) / 14.0)
    edge = np.minimum(vertical - vertical_width, horizontal - horizontal_width) - 1.3 * joint
    alpha = np.round(np.clip(0.5 - edge / 3.0, 0.0, 1.0) * 32) / 32
    # Coarse fibre variation (4 px blocks, 8 levels) keeps the lossless file small.
    blocks = np.round(rng.random((SIZE // 4, SIZE // 4)) * 7) / 7
    fibre = 0.78 + 0.22 * np.kron(blocks, np.ones((4, 4)))
    grey = np.clip(fibre * (0.9 + 0.1 * joint), 0.0, 1.0)
    rgba = np.stack([grey, grey, grey, alpha], axis=-1)
    return Image.fromarray(np.round(rgba * 255).astype(np.uint8), 'RGBA')


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    build().save(OUT, lossless=True, exact=True)
    print(OUT, OUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
