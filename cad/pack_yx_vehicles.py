"""Meshopt-compress the YX fleet GLBs and copy them into the viewer.

The Blender export already embeds the foam-pore normal as WebP. This step adds
EXT_meshopt_compression and writes a triangle / size report.

Usage (repository root):
  python cad/pack_yx_vehicles.py

Build-time packages (not shipped): @gltf-transform 4.5.1 (MIT), meshoptimizer
(MIT). They are installed under simulator/output/yx-vehicles/node_modules.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'simulator' / 'output' / 'yx-vehicles' / 'raw'
PACK = ROOT / 'simulator' / 'output' / 'yx-vehicles'
MODELS = ROOT / 'simulator' / 'viewer' / 'models'
REPORT = ROOT / 'docs' / 'design' / 'vehicle-models' / 'report.json'
NODE_MODULES = Path('/tmp/yx-pack/node_modules')
BUDGETS = (40000, 12000, 3000)
BYTE_BUDGET = int(1.5 * 1024 * 1024)
FILES = {
    'x1': 'rov',
    'bluerov2_heavy': 'bluerov2_heavy',
    'falcon': 'falcon',
}
PACK_JS = r"""
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from '@gltf-transform/extensions';
import { MeshoptEncoder } from 'meshoptimizer';

const input = process.argv[2];
const output = process.argv[3];
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'meshopt.encoder': MeshoptEncoder,
});
const document = await io.read(input);
// Compress buffers only. The meshopt() helper also quantizes positions and bakes
// the undo into the node, which moves rotor pivots off the physics points.
document.createExtension(EXTMeshoptCompression)
  .setRequired(true)
  .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
await io.write(output, document);
"""


def names_for(stem):
    return (f'{stem}.glb', f'{stem}_lod1.glb', f'{stem}_lod2.glb')


def read_doc(path):
    raw = path.read_bytes()
    length = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20 + length]), raw


def drawn_triangles(doc):
    accessors = doc['accessors']
    total = 0
    for node in doc['nodes']:
        if 'mesh' not in node:
            continue
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            if 'indices' in primitive:
                total += accessors[primitive['indices']]['count'] // 3
            else:
                total += accessors[primitive['attributes']['POSITION']]['count'] // 3
    return total


def describe(path):
    doc, raw = read_doc(path)
    return {
        'file': path.name,
        'bytes': len(raw),
        'triangles': drawn_triangles(doc),
        'meshes': len(doc.get('meshes', [])),
        'nodes': len(doc['nodes']),
        'extensions': doc.get('extensionsUsed', []),
    }


def pack_one(source, target):
    # The script has to sit next to node_modules; Node ESM does not honour NODE_PATH.
    script = NODE_MODULES.parent / 'pack_one.mjs'
    script.write_text(PACK_JS, encoding='utf8')
    subprocess.run(['node', str(script), str(source), str(target)], check=True, cwd=str(script.parent))


def main():
    if not NODE_MODULES.is_dir():
        raise SystemExit(f'missing {NODE_MODULES}; install gltf-transform and meshoptimizer there')
    report = {'source': 'cad/build_yx_vehicles.py', 'vehicles': {}}
    for model_id, stem in FILES.items():
        levels = []
        for index, name in enumerate(names_for(stem)):
            source = RAW / name
            if not source.is_file():
                raise SystemExit(f'missing {source}; run cad/build_yx_vehicles.py first')
            target = MODELS / name
            pack_one(source, target)
            info = describe(target)
            info['lod'] = index
            info['triangle_budget'] = BUDGETS[index]
            info['byte_budget'] = BYTE_BUDGET
            if info['triangles'] > BUDGETS[index]:
                raise SystemExit(f"{name} has {info['triangles']} triangles")
            if info['bytes'] > BYTE_BUDGET:
                raise SystemExit(f"{name} is {info['bytes']} bytes")
            if 'EXT_meshopt_compression' not in info['extensions']:
                raise SystemExit(f'{name} is missing meshopt')
            if 'EXT_texture_webp' not in info['extensions']:
                raise SystemExit(f'{name} is missing webp')
            levels.append(info)
            print(f"{name:28} {info['bytes']/1e6:6.2f} MB  {info['triangles']:6d} tris")
        report['vehicles'][model_id] = levels
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print('wrote', REPORT)


if __name__ == '__main__':
    sys.exit(main() or 0)
