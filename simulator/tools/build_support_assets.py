"""Build the deck support assets (work boat, deck crew) and compress them into simulator/viewer/models/.

Usage (from the repository root or anywhere):
  python simulator/tools/build_support_assets.py [vessel] [crew] [--work DIR]

Steps per asset: run the Blender generator in cad/ (needs `import bpy`, e.g. `pip install bpy`, or Blender's
own Python), then compress with gltf-transform via npx (MIT): dedup, prune, WebP textures (EXT_texture_webp)
and meshopt geometry (EXT_meshopt_compression, decoded by the vendored three.js MeshoptDecoder). Prints a
report of triangles, textures and file sizes and fails if a budget from docs/tasks/T11 is exceeded.
"""
import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / 'simulator' / 'viewer' / 'models'
GLTF_TRANSFORM = '@gltf-transform/cli@4.5.1'
ASSETS = {
    'vessel': {'script': 'cad/build_support_vessel.py', 'out': 'workboat.glb', 'max_tris': 120_000},
    'crew': {'script': 'cad/build_deck_crew.py', 'out': 'worker.glb', 'max_tris': 40_000},
}
MAX_BYTES = 8 * 1024 * 1024
WEBP_QUALITY = '88'


def npx(*args):
    command = ['npx', '--yes', GLTF_TRANSFORM, *args]
    subprocess.run(command, check=True, cwd=ROOT)


def compress(raw, out):
    staged = raw.with_name(raw.stem + '.stage.glb')
    npx('dedup', str(raw), str(staged))
    npx('prune', str(staged), str(staged), '--keep-leaves', 'true')
    npx('webp', str(staged), str(staged), '--quality', WEBP_QUALITY)
    npx('meshopt', str(staged), str(out), '--level', 'medium')
    staged.unlink()


def glb_report(path):
    """Triangles (from index/position counts), texture list and file size of a GLB."""
    data = path.read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + length])
    tris = 0
    for mesh in doc.get('meshes', []):
        for prim in mesh['primitives']:
            if 'indices' in prim:
                tris += doc['accessors'][prim['indices']]['count'] // 3
            else:
                tris += doc['accessors'][prim['attributes']['POSITION']]['count'] // 3
    images = []
    for image in doc.get('images', []):
        view = doc['bufferViews'][image['bufferView']]
        images.append((image.get('name', '?'), image.get('mimeType'), view['byteLength']))
    return {'triangles': tris, 'images': images, 'bytes': path.stat().st_size,
            'materials': len(doc.get('materials', [])), 'meshes': len(doc.get('meshes', []))}


def build(name, work):
    spec = ASSETS[name]
    raw = work / f'{name}_raw.glb'
    subprocess.run([sys.executable, str(ROOT / spec['script']), str(raw), '--textures', str(work / f'{name}_tex')],
                   check=True, cwd=ROOT)
    out = MODELS / spec['out']
    compress(raw, out)
    report = glb_report(out)
    print(f"{spec['out']}: {report['triangles']} triangles, {report['meshes']} meshes, "
          f"{report['materials']} materials, {report['bytes'] / 1e6:.2f} MB")
    for image_name, mime, size in report['images']:
        print(f'  {image_name:24s} {mime:12s} {size / 1024:8.1f} KB')
    if report['triangles'] > spec['max_tris'] or report['bytes'] > MAX_BYTES:
        raise SystemExit(f"{spec['out']} exceeds its budget ({spec['max_tris']} triangles, 8 MB)")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('assets', nargs='*', default=list(ASSETS), choices=list(ASSETS))
    parser.add_argument('--work', type=Path, default=ROOT / 'simulator' / 'output' / 'support-assets')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    for name in args.assets:
        build(name, args.work.resolve())


if __name__ == '__main__':
    main()
