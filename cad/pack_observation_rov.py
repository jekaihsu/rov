"""Compress the baked observation ROV into three LODs and write an asset report.

Usage (repository root, after cad/build_observation_rov.py):
  python cad/pack_observation_rov.py [--gltf-transform PATH]

Steps per LOD use the glTF-Transform CLI (MIT; fetched by npx unless a path is given):
  LOD0  full geometry, 2048/1024 px textures                  -> models/observation_rov.glb
  LOD1  meshoptimizer simplify (error 0.3 % of radius), textures halved     -> models/observation_rov_lod1.glb
  LOD2  simplify (error 1.2 % of radius), textures quartered               -> models/observation_rov_lod2.glb
All LODs use EXT_meshopt_compression + KHR_mesh_quantization, which the viewer already decodes. Textures stay
JPEG because the viewer has no KTX2 transcoder (see docs/design/vehicle/README.md).
"""
import argparse
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'simulator' / 'output' / 'observation_rov' / 'observation_rov_raw.glb'
MODELS = ROOT / 'simulator' / 'viewer' / 'models'
REPORT = ROOT / 'docs' / 'design' / 'vehicle' / 'asset-report.json'
# (file, simplify ratio, simplify error as a fraction of mesh radius, texture size divisor)
LODS = (
    ('observation_rov.glb', None, None, 1),
    ('observation_rov_lod1.glb', 0.5, 0.003, 2),
    ('observation_rov_lod2.glb', 0.25, 0.012, 4),
)
TRIANGLE_BUDGET = 80_000
BYTE_BUDGET = 8 * 1024 * 1024


def run(cli, *args):
    command = list(cli) + [str(arg) for arg in args]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)


def read_json_chunk(path):
    data = path.read_bytes()
    length = struct.unpack('<I', data[12:16])[0]
    return json.loads(data[20:20 + length]), data


def jpeg_size(blob):
    """Width and height from a JPEG SOF marker."""
    i = 2
    while i < len(blob):
        marker = blob[i + 1]
        size = struct.unpack('>H', blob[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack('>HH', blob[i + 5:i + 9])
            return width, height
        i += 2 + size
    return None


def describe(path):
    """Triangles drawn (counting every node instance), textures and byte size of a packed GLB."""
    gltf, data = read_json_chunk(path)
    accessors = gltf['accessors']
    mesh_triangles = []
    for mesh in gltf['meshes']:
        count = 0
        for primitive in mesh['primitives']:
            if 'indices' in primitive:
                count += accessors[primitive['indices']]['count'] // 3
            else:
                count += accessors[primitive['attributes']['POSITION']]['count'] // 3
        mesh_triangles.append(count)
    drawn = sum(mesh_triangles[node['mesh']] for node in gltf['nodes'] if 'mesh' in node)
    json_length = struct.unpack('<I', data[12:16])[0]
    binary = data[20 + json_length + 8:]
    textures = []
    for image in gltf.get('images', []):
        view = gltf['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        blob = binary[start:start + view['byteLength']]
        width, height = jpeg_size(blob) if image.get('mimeType') == 'image/jpeg' else (None, None)
        textures.append({'name': image.get('name'), 'mime': image.get('mimeType'), 'bytes': view['byteLength'],
                         'width': width, 'height': height})
    gpu_bytes = sum(t['width'] * t['height'] * 4 * 4 // 3 for t in textures if t['width'])
    return {'file': path.name, 'bytes': path.stat().st_size, 'triangles_drawn': drawn,
            'unique_triangles': sum(mesh_triangles), 'materials': len(gltf.get('materials', [])),
            'nodes': len(gltf['nodes']), 'textures': textures,
            'texture_memory_rgba8_with_mips_bytes': gpu_bytes,
            'extensions': gltf.get('extensionsUsed', [])}


def pack(cli):
    if not RAW.exists():
        raise SystemExit(f'{RAW} missing; run cad/build_observation_rov.py first')
    report = {'source': 'cad/build_observation_rov.py', 'lods': []}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name, ratio, error, divisor in LODS:
            current = tmp / f'{name}.0.glb'
            shutil.copy(RAW, current)
            run(cli, 'dedup', current, current)
            if ratio:
                run(cli, 'simplify', current, current, '--ratio', ratio, '--error', error)
                width = max(256, 2048 // divisor)
                run(cli, 'resize', current, current, '--width', width, '--height', width)
            run(cli, 'prune', current, current, '--keep-leaves', 'true')
            target = MODELS / name
            run(cli, 'meshopt', current, target, '--level', 'medium')
            report['lods'].append(describe(target))
    lod0 = report['lods'][0]
    report['budget'] = {'triangles': TRIANGLE_BUDGET, 'bytes': BYTE_BUDGET,
                        'lod0_within_triangles': lod0['triangles_drawn'] <= TRIANGLE_BUDGET,
                        'lod0_within_bytes': lod0['bytes'] <= BYTE_BUDGET}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    for lod in report['lods']:
        print(f"{lod['file']:28s} {lod['bytes'] / 1e6:6.2f} MB  {lod['triangles_drawn']:6d} tris  "
              f"{len(lod['textures'])} textures  {lod['materials']} materials")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--gltf-transform', help='path to a gltf-transform executable (default: npx)')
    args = parser.parse_args()
    cli = [args.gltf_transform] if args.gltf_transform else ['npx', '--yes', '@gltf-transform/cli@4.5.1']
    report = pack(cli)
    if not all(value for key, value in report['budget'].items() if key.startswith('lod0_')):
        raise SystemExit('LOD0 exceeds the T11 budget')


if __name__ == '__main__':
    main()
