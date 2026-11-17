"""Recompress viewer models: meshopt geometry, WebP textures, missing LODs.

From the simulator directory:

  python tools/compress_models.py

The Node step needs @gltf-transform, meshoptimizer and sharp. They are installed
into output/gltf-tools (gitignored) when that folder has no node_modules.
Already-meshopt files are not quantized again. JPEG images inside an
already-meshopt GLB are repacked to WebP in place, and the compressed geometry
bytes are copied through unchanged.

waternormals.jpg becomes WebP only when the WebP is smaller. The viewer already
decodes WebP. No Basis transcoder is added.
"""
import io
import json
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'viewer' / 'models'
TOOLS = Path(__file__).resolve().parent
PACKAGES = ROOT / 'output' / 'gltf-tools'
# Normals and roughness stay noisy at quality 95, and that WebP is larger than
# the JPEG. 80 is the lowest step that still beat every remaining JPEG.
WEBP_QUALITY = {'normal': 80, 'orm': 82, 'rough': 80, 'metal': 82}
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def install_packages():
    """ESM resolves packages from simulator/node_modules, which is gitignored."""
    modules = PACKAGES / 'node_modules'
    if not (modules / '@gltf-transform' / 'core').is_dir():
        PACKAGES.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            ['npm', 'install', '--silent', '--no-fund', '--no-audit',
             '@gltf-transform/core@4.5.1', '@gltf-transform/extensions@4.5.1',
             '@gltf-transform/functions@4.5.1', 'meshoptimizer@0.21.0', 'sharp@0.33.5'],
            cwd=PACKAGES,
        )
    link = ROOT / 'node_modules'
    if not link.exists():
        link.symlink_to(modules, target_is_directory=True)


def run_geometry():
    install_packages()
    subprocess.check_call(['node', str(TOOLS / 'compress_models.mjs')], cwd=ROOT)


def read_glb(data):
    magic, version, _total = struct.unpack_from('<III', data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError('not a GLB')
    json_length, json_type = struct.unpack_from('<II', data, 12)
    if json_type != JSON_CHUNK:
        raise ValueError('first GLB chunk is not JSON')
    document = json.loads(data[20:20 + json_length])
    bin_at = 20 + json_length
    bin_length, bin_type = struct.unpack_from('<II', data, bin_at)
    if bin_type != BIN_CHUNK:
        raise ValueError('second GLB chunk is not BIN')
    return document, bytearray(data[bin_at + 8:bin_at + 8 + bin_length])


def write_glb(path, document, binary):
    payload = json.dumps(document, separators=(',', ':')).encode('utf-8')
    payload += b' ' * ((4 - len(payload) % 4) % 4)
    blob = bytes(binary)
    blob += b'\x00' * ((4 - len(blob) % 4) % 4)
    total = 12 + 8 + len(payload) + 8 + len(blob)
    out = bytearray()
    out += struct.pack('<III', 0x46546C67, 2, total)
    out += struct.pack('<I', len(payload))
    out += struct.pack('<I', JSON_CHUNK)
    out += payload
    out += struct.pack('<I', len(blob))
    out += struct.pack('<I', BIN_CHUNK)
    out += blob
    path.write_bytes(out)


def to_webp(blob, quality):
    image = Image.open(io.BytesIO(blob))
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
    out = io.BytesIO()
    image.save(out, 'WEBP', quality=quality, method=6)
    return out.getvalue()


def quality_for(name):
    lower = name.lower()
    for key, quality in WEBP_QUALITY.items():
        if key in lower:
            return quality
    return 82


def physical_pieces(document, binary):
    images = {image['bufferView']: image for image in document.get('images') or []}
    pieces = []
    for index, view in enumerate(document['bufferViews']):
        ext = (view.get('extensions') or {}).get('EXT_meshopt_compression')
        if ext:
            off = ext.get('byteOffset', 0)
            length = ext['byteLength']
            pieces.append([off, 'meshopt', index, bytes(binary[off:off + length]), ext])
        else:
            off = view.get('byteOffset', 0)
            length = view['byteLength']
            kind = 'image' if index in images else 'raw'
            pieces.append([off, kind, index, bytes(binary[off:off + length]), images.get(index)])
    pieces.sort(key=lambda item: (item[0], item[2]))
    cursor = 0
    for off, _kind, _index, blob, _extra in pieces:
        if off < cursor:
            raise ValueError('physical buffer ranges overlap; refusing to repack')
        cursor = off + len(blob)
    return pieces


def add_extension(document, name):
    used = document.setdefault('extensionsUsed', [])
    required = document.setdefault('extensionsRequired', [])
    if name not in used:
        used.append(name)
    if name not in required:
        required.append(name)


def repack_webp(path):
    document, binary = read_glb(path.read_bytes())
    if 'EXT_meshopt_compression' not in document.get('extensionsRequired', []) and \
            'EXT_meshopt_compression' not in document.get('extensionsUsed', []):
        return
    images = document.get('images') or []
    if not images:
        return
    if all(image.get('mimeType') in ('image/webp', 'image/ktx2') for image in images):
        return
    pieces = physical_pieces(document, binary)
    changed = False
    packed = bytearray()
    cursor = 0
    for _off, kind, index, blob, extra in pieces:
        payload = blob
        if kind == 'image' and extra.get('mimeType') not in ('image/webp', 'image/ktx2'):
            name = extra.get('name') or f'image-{index}'
            converted = to_webp(blob, quality_for(name))
            if len(converted) < len(blob):
                payload = converted
                extra['mimeType'] = 'image/webp'
                changed = True
                print(f'  {path.name} {name}: {len(blob)} -> {len(converted)}')
        pad = (4 - cursor % 4) % 4
        packed.extend(b'\x00' * pad)
        cursor += pad
        if kind == 'meshopt':
            if payload != blob:
                raise ValueError('meshopt payload changed')
            extra['byteOffset'] = cursor
        else:
            view = document['bufferViews'][index]
            view['byteOffset'] = cursor
            view['byteLength'] = len(payload)
        packed.extend(payload)
        cursor += len(payload)
    if not changed:
        print(f'keep {path.name}: WebP was not smaller')
        return
    if any(image.get('mimeType') == 'image/webp' for image in images):
        add_extension(document, 'EXT_texture_webp')
    document['buffers'][0]['byteLength'] = len(packed)
    before = path.stat().st_size
    write_glb(path, document, packed)
    print(f'{path.name}: {before} -> {path.stat().st_size} bytes (geometry payloads unchanged)')


def convert_waternormals():
    source = MODELS / 'waternormals.jpg'
    if not source.is_file():
        return
    blob = to_webp(source.read_bytes(), 90)
    if len(blob) >= source.stat().st_size * 0.8:
        print(f'keep waternormals.jpg ({source.stat().st_size} vs webp {len(blob)})')
        return
    dest = MODELS / 'waternormals.webp'
    dest.write_bytes(blob)
    source.unlink()
    print(f'waternormals.jpg -> waternormals.webp ({dest.stat().st_size} bytes)')


def main():
    run_geometry()
    for path in sorted(MODELS.rglob('*.glb')):
        repack_webp(path)
    convert_waternormals()


if __name__ == '__main__':
    main()
