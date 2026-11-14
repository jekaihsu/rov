"""Build the deck support assets (work boat, deck crew) and compress them into simulator/viewer/models/.

Usage (from the repository root or anywhere):
  python simulator/tools/build_support_assets.py [vessel] [crew] [--work DIR]
  python simulator/tools/build_support_assets.py --report       # texture memory of the committed GLBs only

Steps per asset: run the Blender generator in cad/ (needs `import bpy`, e.g. `pip install bpy`, or Blender's
own Python), then compress with gltf-transform via npx (MIT): dedup, prune, per-variant texture downscaling
(resize), WebP textures (EXT_texture_webp) and meshopt geometry (EXT_meshopt_compression, decoded by the
vendored three.js MeshoptDecoder). Each asset can have several texture variants: the work boat ships a
standard file (default and lower quality modes) and a "_high" file with the 2048 hull maps that
render_quality.js selects only for the "high" quality mode. Prints triangles, textures, file sizes and the
GPU memory estimate (WebP decodes to RGBA8 on the GPU: width x height x 4 bytes x 4/3 for mipmaps) and fails
if a budget is exceeded.
"""
import argparse
import io
import json
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / 'simulator' / 'viewer' / 'models'
GLTF_TRANSFORM = '@gltf-transform/cli@4.5.1'
MIB = 1024 * 1024

# Maximum texture edge per texture-name pattern. Detail that is invisible at intro / review distances
# (transom, deck, worn paint, brushed metal, canopy fabric, lettering, deck monitor) is downscaled in every variant.
STANDARD_TEXTURES = (
    ('hull_*', 1024),
    ('transom_*', 512),
    ('deck_*', 512),
    ('paint_*', 512),
    ('metal_*', 512),
    ('fabric_*', 256),
    ('registration', 512),
    ('screen', 256),
)
HIGH_TEXTURES = (
    ('deck_*', 1024),
    ('transom_*', 512),
    ('paint_*', 512),
    ('metal_*', 512),
    ('fabric_*', 256),
    ('registration', 512),
    ('screen', 256),
)
ASSETS = {
    'vessel': {
        'script': 'cad/build_support_vessel.py',
        'max_tris': 120_000,
        'variants': (
            {'out': 'workboat.glb', 'textures': STANDARD_TEXTURES, 'max_gpu_mib': 32},
            {'out': 'workboat_high.glb', 'textures': HIGH_TEXTURES, 'max_gpu_mib': 64},
        ),
    },
    'crew': {
        'script': 'cad/build_deck_crew.py',
        'max_tris': 40_000,
        'variants': ({'out': 'worker.glb', 'textures': (), 'max_gpu_mib': 8},),
    },
}
MAX_BYTES = 8 * 1024 * 1024
WEBP_QUALITY = '88'


def npx(*args):
    command = ['npx', '--yes', GLTF_TRANSFORM, *args]
    subprocess.run(command, check=True, cwd=ROOT)


def compress(raw, out, textures):
    staged = raw.with_name(out.stem + '.stage.glb')
    npx('dedup', str(raw), str(staged))
    npx('prune', str(staged), str(staged), '--keep-leaves', 'true')
    for pattern, edge in textures:
        npx('resize', str(staged), str(staged), '--pattern', pattern, '--width', str(edge), '--height', str(edge))
    npx('webp', str(staged), str(staged), '--quality', WEBP_QUALITY)
    npx('meshopt', str(staged), str(out), '--level', 'medium')
    staged.unlink()


def read_glb(path):
    data = path.read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + length])
    offset = 20 + length
    bin_length = struct.unpack_from('<I', data, offset)[0] if offset < len(data) else 0
    return doc, data[offset + 8:offset + 8 + bin_length]


def glb_report(path):
    """Triangles (from index/position counts), texture list with GPU memory estimate and file size of a GLB."""
    doc, binary = read_glb(path)
    tris = 0
    for mesh in doc.get('meshes', []):
        for prim in mesh['primitives']:
            if 'indices' in prim:
                tris += doc['accessors'][prim['indices']]['count'] // 3
            else:
                tris += doc['accessors'][prim['attributes']['POSITION']]['count'] // 3
    images = []
    gpu = 0.0
    for image in doc.get('images', []):
        view = doc['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        width, height = Image.open(io.BytesIO(binary[start:start + view['byteLength']])).size
        memory = width * height * 4 * 4 / 3
        gpu += memory
        images.append((image.get('name', '?'), image.get('mimeType'), view['byteLength'], width, height, memory))
    return {'triangles': tris, 'images': images, 'bytes': path.stat().st_size, 'gpu_bytes': gpu,
            'materials': len(doc.get('materials', [])), 'meshes': len(doc.get('meshes', []))}


def print_report(out, report):
    print(f"{out.name}: {report['triangles']} triangles (all LODs), {report['meshes']} meshes, "
          f"{report['materials']} materials, {report['bytes'] / 1e6:.2f} MB file, "
          f"GPU textures ~{report['gpu_bytes'] / MIB:.1f} MiB")
    for image_name, mime, size, width, height, memory in report['images']:
        print(f'  {image_name:24s} {mime:12s} {size / 1024:8.1f} KB  {width:5d}x{height:<5d} {memory / MIB:6.2f} MiB')


def build(name, work):
    spec = ASSETS[name]
    raw = work / f'{name}_raw.glb'
    subprocess.run([sys.executable, str(ROOT / spec['script']), str(raw), '--textures', str(work / f'{name}_tex')],
                   check=True, cwd=ROOT)
    for variant in spec['variants']:
        out = MODELS / variant['out']
        compress(raw, out, variant['textures'])
        report = glb_report(out)
        print_report(out, report)
        if report['triangles'] > spec['max_tris'] or report['bytes'] > MAX_BYTES:
            raise SystemExit(f"{variant['out']} exceeds its budget ({spec['max_tris']} triangles, 8 MB)")
        if report['gpu_bytes'] > variant['max_gpu_mib'] * MIB:
            raise SystemExit(f"{variant['out']} textures exceed {variant['max_gpu_mib']} MiB of GPU memory")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('assets', nargs='*', default=list(ASSETS), choices=list(ASSETS))
    parser.add_argument('--work', type=Path, default=ROOT / 'simulator' / 'output' / 'support-assets')
    parser.add_argument('--report', action='store_true', help='only report the committed GLBs')
    args = parser.parse_args()
    if args.report:
        for name in args.assets:
            for variant in ASSETS[name]['variants']:
                path = MODELS / variant['out']
                if path.exists():
                    print_report(path, glb_report(path))
        return
    args.work.mkdir(parents=True, exist_ok=True)
    for name in args.assets:
        build(name, args.work.resolve())


if __name__ == '__main__':
    main()
