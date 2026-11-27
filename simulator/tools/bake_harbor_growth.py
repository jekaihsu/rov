"""Bake the harbor pile unwrap in metres, using the credited CC0 concrete and shell scans."""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "viewer/models/scan"
WIDTH, HEIGHT = 512, 2048
RNG = np.random.default_rng(504)


def tiled_scan(name):
    scan = Image.open(ROOT / name).convert("L").resize((WIDTH, HEIGHT // 4))
    tile = np.asarray(scan, dtype=float)
    return np.tile(tile / tile.mean(), (4, 1))


def main():
    yy, xx = np.mgrid[:HEIGHT, :WIDTH]
    tide = (yy / HEIGHT * 20 - 2 + .32 * np.sin(xx / WIDTH * 4 * np.pi)
            + .16 * np.cos(xx / WIDTH * 8 * np.pi + yy / 60))
    mineral = tiled_scan("concrete_c.webp")
    shell = tiled_scan("shell_c.webp")
    noise = RNG.normal(0, 2.2, (HEIGHT, WIDTH))
    rgb = np.zeros((HEIGHT, WIDTH, 3))
    for start, tint in [(-10, [142, 134, 119]), (-.35, [80, 82, 48]), (2.1, [91, 85, 72]), (8.3, [110, 98, 80])]:
        mask = tide >= start
        rgb[mask] = np.asarray(tint) * (.44 + .56 * mineral[mask, None])
    relief = .002 * mineral + .001 * shell
    # Overlapping individuals grow in dense, uneven beds separated by exposed concrete.
    for _ in range(780):
        cx, cy = RNG.uniform([0, 150], [WIDTH, HEIGHT])
        direction = RNG.uniform(-1, 1)
        for _ in range(RNG.integers(9, 37)):
            x, y = RNG.normal([cx, cy], [14, 20])
            ix, iy = int(x) % WIDTH, int(y)
            if not 32 <= iy < HEIGHT - 32:
                continue
            zone = tide[iy, ix]
            if zone < -.25:
                continue
            sx, sy = (2.3, 13) if zone < 2.1 else (3.5, 7.4) if zone < 8.3 else (4.3, 4.3)
            scale = RNG.uniform(.6, 1.35)
            angle = direction + RNG.normal(0, .48)
            u, v = np.mgrid[-20:21, -20:21]
            row = iy + u
            col = (ix + v) % WIDTH
            a = (v * np.cos(angle) - u * np.sin(angle)) / (sx * scale)
            b = (v * np.sin(angle) + u * np.cos(angle)) / (sy * scale)
            if zone < 2.1:
                a += .56 * np.sin(b * 4)
                radius = np.hypot(a * (1 + .45 * b), b)
                height = .008 * np.maximum(0, 1 - radius)
                tone = np.array([72, 80, 36]) + RNG.uniform(-12, 16)
                light = .72 + .31 * np.cos(a * 3)
            elif zone < 8.3:
                radius = np.hypot(a * (1 + .46 * b), b)
                height = .03 * np.sqrt(np.maximum(0, 1 - radius ** 2))
                tone = np.array([56, 49, 62]) + RNG.uniform(-13, 17)
                light = .66 + .3 * (1 - a) + .11 * np.sin(22 * radius + 2 * b)
            else:
                radius = np.hypot(a, b)
                crown = np.clip((1 - radius) * 3.5, 0, 1)
                throat = np.clip((radius - .18) * 5, 0, 1)
                height = .031 * crown * throat
                tone = np.array([161, 145, 117]) + RNG.uniform(-19, 20)
                light = (.35 + .65 * throat) * (.86 + .11 * np.sin(9 * np.arctan2(b, a)))
            visible = (radius < 1) & (height + .004 > relief[row, col])
            rr, cc = row[visible], col[visible]
            relief[rr, cc] = height[visible] + .004
            rgb[rr, cc] = tone * (light[visible] * (.88 + .12 * shell[rr, cc]))[:, None]
    rgb += noise[:, :, None]
    dy, dx = np.gradient(relief)
    normal = np.stack((-dx * WIDTH / 3.77, dy * HEIGHT / 20, np.ones_like(dx)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    Image.fromarray(rgb.clip(0, 255).astype("uint8")).save(ROOT / "harbor_growth_c.webp", quality=91)
    # Colour preserves fine growth rings. The filtered surface slope needs fewer texels.
    filtered = normal.reshape(HEIGHT // 2, 2, WIDTH // 2, 2, 3).mean(axis=(1, 3))
    filtered /= np.linalg.norm(filtered, axis=-1, keepdims=True)
    Image.fromarray(((filtered + 1) * 127.5).astype("uint8")).save(ROOT / "harbor_growth_n.webp", quality=94)


if __name__ == "__main__":
    main()
