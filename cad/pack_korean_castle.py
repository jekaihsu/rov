"""Pack Korean Castle I4 LODs with glTF-Transform (WebP + meshopt) and write the asset report."""

from __future__ import annotations

import io
import json
import shutil
import struct
from pathlib import Path

from PIL import Image
from pack_observation_rov import read_json_chunk, run

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "simulator/output/korean_castle_i4"
MODELS = ROOT / "simulator/viewer/models"
REPORT = ROOT / "docs/design/wreck"

BUDGETS = (
    ("korean_castle.glb", "lod0_raw.glb", 300_000, 32 * 1024**2),
    ("korean_castle_lod1.glb", "lod1_raw.glb", 100_000, 32 * 1024**2),
    ("korean_castle_lod2.glb", "lod2_raw.glb", 20_000, 32 * 1024**2),
)


def describe(path: Path) -> dict:
    gltf, data = read_json_chunk(path)
    accessors = gltf["accessors"]
    tris = 0
    draws = 0
    for node in gltf["nodes"]:
        if "mesh" not in node:
            continue
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            draws += 1
            if "indices" in prim:
                tris += accessors[prim["indices"]]["count"] // 3
            else:
                tris += accessors[prim["attributes"]["POSITION"]]["count"] // 3
    json_length = struct.unpack("<I", data[12:16])[0]
    binary = data[20 + json_length + 8 :]
    memory = 0
    images = []
    for image in gltf.get("images", []):
        view = gltf["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        blob = binary[start : start + view["byteLength"]]
        img = Image.open(io.BytesIO(blob))
        bytes_with_mips = img.width * img.height * 4 * 4 // 3
        memory += bytes_with_mips
        images.append(
            {
                "name": image.get("name"),
                "mime": image.get("mimeType"),
                "width": img.width,
                "height": img.height,
                "bytes": len(blob),
                "gpu_rgba8_mips": bytes_with_mips,
            }
        )
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "triangles": tris,
        "draw_calls": draws,
        "materials": len(gltf.get("materials", [])),
        "textures": images,
        "texture_bytes_with_mips": memory,
        "extensions": gltf.get("extensionsUsed", []),
    }


def main() -> None:
    cli = ["npx", "--yes", "@gltf-transform/cli@4.5.1"]
    report = []
    REPORT.mkdir(parents=True, exist_ok=True)
    for target_name, source_name, tri_budget, tex_budget in BUDGETS:
        source = RAW / source_name
        if not source.exists():
            raise SystemExit(f"missing {source}; run cad/build_korean_castle_i4.py first")
        current = RAW / f"packed_{target_name}"
        shutil.copyfile(source, current)
        run(cli, "dedup", current, current)
        run(cli, "weld", current, current)
        # Authoring already hit the LOD triangle targets; a light simplify only cleans seams.
        if "lod1" in target_name:
            run(cli, "simplify", current, current, "--ratio", "0.95", "--error", "0.002")
        elif "lod2" in target_name:
            run(cli, "simplify", current, current, "--ratio", "0.9", "--error", "0.004")
        # Quality 78: softer albedo edges than 70 (fewer WebP blocks) while staying small on disk.
        run(cli, "webp", current, current, "--quality", "78", "--effort", "90")
        run(cli, "prune", current, current)
        target = MODELS / target_name
        # LOD0 stays above the 2 MB new-asset soft limit (tris + 1K atlases); see PR description.
        level = "high" if source_name.startswith("lod0") else "medium"
        run(cli, "meshopt", current, target, "--level", level)
        info = describe(target)
        assert info["triangles"] <= tri_budget, (target_name, info["triangles"], tri_budget)
        assert info["texture_bytes_with_mips"] <= tex_budget, (
            target_name,
            info["texture_bytes_with_mips"],
            tex_budget,
        )
        info["triangle_budget"] = tri_budget
        info["texture_budget_bytes"] = tex_budget
        report.append(info)
        print(
            f"{target_name:28s} {info['bytes']/1e6:5.2f} MB  {info['triangles']:7d} tris  "
            f"{info['draw_calls']:3d} draws  {info['texture_bytes_with_mips']/1024**2:5.2f} MiB tex"
        )
    (REPORT / "asset-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
