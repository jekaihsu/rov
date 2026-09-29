"""Build the simulator assets for the Korean Castle wreck from the Blender export.

    python tools/build_wreck.py EXPORT_DIR

EXPORT_DIR is the output of tools/wreck_blender_export.py. Writes
    qysim/assets/korean_castle_field.npz   unsigned distance field of the collision meshes
    qysim/assets/korean_castle.json        route waypoints, inspection grid, source metadata
The field is sampled on a 0.3 m grid in the wreck's own frame (X bow->stern, Y transverse,
Z up, origin at the bow on the seabed) and stored as uint8 in 5 cm steps (clamped at 12.75 m),
so a vehicle sphere or tether node only needs a trilinear lookup at run time.
Needs scipy (build time only).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
H = 0.3            # grid spacing, m
PAD = 4.0          # grid margin around the collision meshes, m
QUANT = 0.05       # m per uint8 step
SAMPLE = 0.05      # surface sampling pitch, m


def surface_samples(tris: np.ndarray, pitch: float) -> np.ndarray:
    """Points covering every triangle at roughly ``pitch`` spacing (vertices and edges included)."""
    out = [tris.reshape(-1, 3)]
    for t in tris:
        a, b, c = t
        n = int(np.ceil(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / pitch)) + 1
        u, v = np.meshgrid(np.linspace(0, 1, n + 1), np.linspace(0, 1, n + 1))
        m = (u + v) <= 1.0 + 1e-9
        u, v = u[m], v[m]
        out.append(a + np.outer(u, b - a) + np.outer(v, c - a))
    return np.concatenate(out)


def route_waypoints(V: np.ndarray) -> list[list[float]]:
    """The preview path is a tube: cluster its vertices into the waypoint centres, in path order."""
    pts: list = []
    for v in V:
        for p in pts:
            if np.linalg.norm(p[0] / p[1] - v) < 0.6:
                p[0] += v; p[1] += 1
                break
        else:
            pts.append([v.copy(), 1])
    return [[round(float(x), 2) for x in p[0] / p[1]] for p in pts]


def main() -> None:
    src = Path(sys.argv[1])
    tris = np.load(src / "collision_tris.npy").astype(np.float64)
    lo = tris.reshape(-1, 3).min(0) - PAD
    hi = tris.reshape(-1, 3).max(0) + PAD
    lo[2] = max(lo[2], -1.0)                       # nothing below the seabed
    shape = np.ceil((hi - lo) / H).astype(int) + 1
    print("grid", shape, "cells", int(np.prod(shape)))
    pts = surface_samples(tris, SAMPLE)
    print("surface samples", len(pts))
    tree = cKDTree(pts)
    gx, gy, gz = (lo[i] + H * np.arange(shape[i]) for i in range(3))
    field = np.empty(shape, np.uint8)
    for i, x in enumerate(gx):                     # slab by slab keeps memory small
        Y, Z = np.meshgrid(gy, gz, indexing="ij")
        q = np.stack([np.full(Y.size, x), Y.ravel(), Z.ravel()], 1)
        d, _ = tree.query(q, workers=-1, distance_upper_bound=255 * QUANT)
        d = np.minimum(np.nan_to_num(d, posinf=255 * QUANT), 255 * QUANT)
        field[i] = np.round(d / QUANT).reshape(Y.shape).astype(np.uint8)
    out = ROOT / "qysim" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "korean_castle_field.npz", field=field, origin=lo, spacing=H, quant=QUANT)
    meta = {
        "name": "Korean Castle",
        "status": "ILLUSTRATIVE_NOT_FOR_NAVIGATION (poster reconstruction, not surveyed)",
        "loa_m": 149.9, "beam_m": 22.7, "moulded_depth_m": 12.75,
        "frame": "X bow->stern, Y transverse, Z up; origin at the bow on the seabed",
        "route": route_waypoints(np.load(src / "route_verts.npy")),
        "grid": {"columns": 15, "column_m": 10.0, "rows": 4, "row_y": [-20, -10, 0, 10, 20],
                 "sections": {"BOW": [1, 5], "MID": [6, 10], "STERN": [11, 15]}},
        "collision_bounds": [lo.round(2).tolist(), hi.round(2).tolist()],
    }
    (out / "korean_castle.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out / "korean_castle_field.npz", (out / "korean_castle_field.npz").stat().st_size / 1e6, "MB")


if __name__ == "__main__":
    main()
