"""Pack Chenjiao using the established glTF-Transform dedup/prune/meshopt workflow and WebP."""

import io
import json
import struct
import shutil
from pathlib import Path

from PIL import Image
from pack_observation_rov import read_json_chunk, run

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "simulator/output/chenjiao"
MODELS = ROOT / "simulator/viewer/models"
REPORT = ROOT / "docs/design/scenes/chenjiao"


def main():
    cli = ["npx", "--yes", "@gltf-transform/cli@4.5.1"]
    report = []
    for lod, budget in enumerate((150000, 50000, 10000)):
        current = RAW / f"packed{lod}.glb"
        shutil.copyfile(RAW / f"lod{lod}.glb", current)
        run(cli, "dedup", current, current)
        run(cli, "weld", current, current)
        if lod:
            run(cli, "simplify", current, current, "--ratio", 0.45 if lod == 1 else 0.14, "--error", 0.003)
        run(cli, "webp", current, current)
        run(cli, "prune", current, current)
        target = MODELS / ("wreck_chenjiao" + (f"_lod{lod}" if lod else "") + ".glb")
        run(cli, "meshopt", current, target, "--level", "medium")
        gltf, data = read_json_chunk(target)
        tris = sum(
            gltf["accessors"][p["indices"]]["count"] // 3
            for n in gltf["nodes"]
            if "mesh" in n
            for p in gltf["meshes"][n["mesh"]]["primitives"]
        )
        draws = sum(len(gltf["meshes"][n["mesh"]]["primitives"]) for n in gltf["nodes"] if "mesh" in n)
        binary = data[28 + struct.unpack("<I", data[12:16])[0] :]
        memory = 0
        for image in gltf.get("images", []):
            view = gltf["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            im = Image.open(io.BytesIO(binary[start : start + view["byteLength"]]))
            memory += im.width * im.height * 4 * 4 // 3
        assert tris <= budget, (lod, tris, budget)
        assert memory <= 32 * 1024**2
        report.append(
            dict(
                lod=lod,
                triangles=tris,
                draw_calls=draws,
                texture_bytes_with_mips=memory,
                bytes=target.stat().st_size,
                extensions=gltf.get("extensionsUsed"),
            )
        )
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "asset-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
