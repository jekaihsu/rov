"""Budget and contract checks for the I4 Korean Castle wreck LODs."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "viewer" / "models"
LODS = (
    ("korean_castle.glb", 300_000),
    ("korean_castle_lod1.glb", 100_000),
    ("korean_castle_lod2.glb", 20_000),
)
TEX_BUDGET = 32 * 1024**2


def read_glb(path: Path):
    data = path.read_bytes()
    length = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20 : 20 + length]), data


def triangles(gltf) -> int:
    total = 0
    for node in gltf["nodes"]:
        if "mesh" not in node:
            continue
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            if "indices" in prim:
                total += gltf["accessors"][prim["indices"]]["count"] // 3
    return total


def texture_memory(gltf, data: bytes) -> int:
    from io import BytesIO

    from PIL import Image

    json_length = struct.unpack("<I", data[12:16])[0]
    binary = data[20 + json_length + 8 :]
    memory = 0
    for image in gltf.get("images", []):
        view = gltf["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        img = Image.open(BytesIO(binary[start : start + view["byteLength"]]))
        memory += img.width * img.height * 4 * 4 // 3
        assert img.width <= 1024 and img.height <= 1024
    return memory


class KoreanCastleAssetTests(unittest.TestCase):
    def test_lod_budgets(self):
        for name, budget in LODS:
            path = MODELS / name
            self.assertTrue(path.exists(), name)
            gltf, data = read_glb(path)
            tris = triangles(gltf)
            mem = texture_memory(gltf, data)
            self.assertLessEqual(tris, budget, name)
            self.assertLessEqual(mem, TEX_BUDGET, name)
            self.assertIn("EXT_meshopt_compression", gltf.get("extensionsUsed", []))
            self.assertIn("EXT_texture_webp", gltf.get("extensionsUsed", []))

    def test_lod0_not_above_previous_main(self):
        gltf, _ = read_glb(MODELS / "korean_castle.glb")
        self.assertLessEqual(triangles(gltf), 300_000)

    def test_asset_report_matches_files(self):
        report = json.loads((ROOT.parent / "docs/design/wreck/asset-report.json").read_text())
        self.assertEqual(len(report), 3)
        for entry, (name, budget) in zip(report, LODS):
            self.assertEqual(entry["file"], name)
            self.assertLessEqual(entry["triangles"], budget)
            self.assertLessEqual(entry["texture_bytes_with_mips"], TEX_BUDGET)


if __name__ == "__main__":
    unittest.main()
