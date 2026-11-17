"""Vendor the species the viewer uses from the CC0 Fish Kit into viewer/models/fish/ and bake their far cards.

Source: https://cda-social.github.io/fish/kit/fish-kit.zip (CC0 1.0; see viewer/models/CREDITS.md). Pass the
kit's `fish/` folder. Nothing from the kit is executed: the GLB files are read as data.

For each species id in SPECIES:
  <id>.glb       the kit's full model (about 5,000 triangles), copied byte for byte;
  <id>_lo.glb    the kit's distance model (about 700 triangles) without its embedded texture, which is the same
                 atlas as in <id>.glb (checked byte for byte; the viewer takes the texture from <id>.glb);
  <id>_card.webp side view (top 80 rows) and top view (bottom 48 rows) of the full model, rendered orthographically
                 from the model's own texture with no lighting, for the two crossed cards that draw far fish
                 (viewer/fish_kit.js cardGeometry). The cards span the model's POSITION bounds.

  python simulator/tools/build_fish_kit.py --source <fish-kit>/fish
  python simulator/tools/build_fish_kit.py --source <fish-kit>/fish --check   # compare with the committed files
"""
import argparse
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[1] / 'viewer/models/fish'
# Species the viewer draws (viewer/fish_kit.js SITE_SPECIES and the farmed species of the pen).
SPECIES = ('aji', 'saba', 'buri', 'kurodai', 'mebaru', 'madai', 'isaki', 'isaki_young', 'shibudai', 'onagagure',
           'kuchibuto')
CARD_WIDTH = 256
SIDE_ROWS = 80
TOP_ROWS = 48
SUPERSAMPLE = 3
ALPHA_CUT = 0.5
MAX_FILE_BYTES = 2 * 1024 * 1024
GLB_MAGIC = 0x46546C67
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
DTYPES = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}


def read_glb(data):
    """(json document, binary chunk) of a GLB file."""
    magic, version, _ = struct.unpack_from('<III', data, 0)
    if magic != GLB_MAGIC or version != 2:
        raise ValueError('not a glTF 2.0 binary')
    json_length, json_type = struct.unpack_from('<II', data, 12)
    if json_type != JSON_CHUNK:
        raise ValueError('first GLB chunk is not JSON')
    document = json.loads(data[20:20 + json_length])
    offset = 20 + json_length
    bin_length, bin_type = struct.unpack_from('<II', data, offset)
    if bin_type != BIN_CHUNK:
        raise ValueError('second GLB chunk is not BIN')
    return document, data[offset + 8:offset + 8 + bin_length]


def write_glb(document, binary):
    """GLB bytes for a document and its binary chunk, both padded to 4 bytes."""
    text = json.dumps(document, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    binary = bytes(binary) + b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(text) + 8 + len(binary)
    header = struct.pack('<III', GLB_MAGIC, 2, total)
    return header + struct.pack('<II', len(text), JSON_CHUNK) + text + struct.pack('<II', len(binary), BIN_CHUNK) + binary


def accessor(document, binary, index):
    """Numpy array (count x components) of one accessor; only the tightly packed layouts the kit uses."""
    item = document['accessors'][index]
    view = document['bufferViews'][item['bufferView']]
    components = COMPONENTS[item['type']]
    dtype = DTYPES[item['componentType']]
    if view.get('byteStride') and view['byteStride'] != components * np.dtype(dtype).itemsize:
        raise ValueError('interleaved accessors are not supported')
    start = view.get('byteOffset', 0) + item.get('byteOffset', 0)
    array = np.frombuffer(binary, dtype=dtype, count=item['count'] * components, offset=start)
    return array.reshape(item['count'], components)


def image_bytes(document, binary):
    """Bytes of the single embedded image."""
    images = document.get('images', [])
    if len(images) != 1:
        raise ValueError(f'expected one embedded image, found {len(images)}')
    view = document['bufferViews'][images[0]['bufferView']]
    start = view.get('byteOffset', 0)
    return binary[start:start + view['byteLength']]


def strip_texture(document, binary):
    """The same model without its image, texture, sampler and the material's base colour texture."""
    document = json.loads(json.dumps(document))
    dropped = {image['bufferView'] for image in document.get('images', [])}
    kept = [index for index in range(len(document['bufferViews'])) if index not in dropped]
    remap = {old: new for new, old in enumerate(kept)}
    output = bytearray()
    views = []
    for old in kept:
        view = dict(document['bufferViews'][old])
        start = view.get('byteOffset', 0)
        output += b'\0' * (-len(output) % 4)
        chunk = binary[start:start + view['byteLength']]
        view['byteOffset'] = len(output)
        output += chunk
        views.append(view)
    document['bufferViews'] = views
    for item in document['accessors']:
        item['bufferView'] = remap[item['bufferView']]
    for key in ('images', 'textures', 'samplers'):
        document.pop(key, None)
    for material in document.get('materials', []):
        material.get('pbrMetallicRoughness', {}).pop('baseColorTexture', None)
    for key in ('extensionsUsed', 'extensionsRequired'):
        names = [name for name in document.get(key, []) if name != 'EXT_texture_webp']
        if names:
            document[key] = names
        else:
            document.pop(key, None)
    document['buffers'] = [{'byteLength': len(output)}]
    return document, bytes(output)


def mesh_arrays(document, binary):
    """Positions, texture coordinates and triangle indices of the model's one primitive."""
    meshes = document['meshes']
    if len(meshes) != 1 or len(meshes[0]['primitives']) != 1:
        raise ValueError('expected one mesh with one primitive')
    primitive = meshes[0]['primitives'][0]
    positions = accessor(document, binary, primitive['attributes']['POSITION']).astype(np.float64)
    uvs = accessor(document, binary, primitive['attributes']['TEXCOORD_0']).astype(np.float64)
    indices = accessor(document, binary, primitive['indices']).reshape(-1, 3).astype(np.int64)
    return positions, uvs, indices


def rasterise(points, depth, uvs, indices, atlas, size):
    """Orthographic, unlit render of the textured triangles: nearest surface (largest depth) wins, alpha cut."""
    width, height = size
    colour = np.zeros((height, width, 4), np.float64)
    zbuffer = np.full((height, width), -np.inf)
    texels = np.asarray(atlas, np.float64) / 255.0
    atlas_height, atlas_width = texels.shape[:2]
    for a, b, c in indices:
        corners = points[[a, b, c]]
        x0, y0 = np.floor(corners.min(axis=0)).astype(int)
        x1, y1 = np.ceil(corners.max(axis=0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, width - 1), min(y1, height - 1)
        if x1 < x0 or y1 < y0:
            continue
        (ax, ay), (bx, by), (cx, cy) = corners
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(area) < 1e-12:
            continue
        grid_y, grid_x = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        w0 = ((bx - grid_x) * (cy - grid_y) - (cx - grid_x) * (by - grid_y)) / area
        w1 = ((cx - grid_x) * (ay - grid_y) - (ax - grid_x) * (cy - grid_y)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not inside.any():
            continue
        z = w0 * depth[a] + w1 * depth[b] + w2 * depth[c]
        u = w0 * uvs[a, 0] + w1 * uvs[b, 0] + w2 * uvs[c, 0]
        v = w0 * uvs[a, 1] + w1 * uvs[b, 1] + w2 * uvs[c, 1]
        tx = np.clip((u * atlas_width).astype(int), 0, atlas_width - 1)
        ty = np.clip((v * atlas_height).astype(int), 0, atlas_height - 1)
        sample = texels[ty, tx]
        window = zbuffer[y0:y1 + 1, x0:x1 + 1]
        take = inside & (sample[..., 3] >= ALPHA_CUT) & (z > window)
        window[take] = z[take]
        colour[y0:y1 + 1, x0:x1 + 1][take] = sample[take]
    return colour


def downsample(colour, factor):
    """Box filter by `factor`; colour averaged over covered samples only (no dark fringe), alpha is coverage."""
    height, width = colour.shape[0] // factor, colour.shape[1] // factor
    blocks = colour.reshape(height, factor, width, factor, 4)
    alpha = blocks[..., 3].mean(axis=(1, 3))
    weight = blocks[..., 3:4]
    rgb = (blocks[..., :3] * weight).sum(axis=(1, 3)) / np.maximum(weight.sum(axis=(1, 3)), 1e-9)
    return np.concatenate([rgb, alpha[..., None]], axis=-1)


def bleed(colour, steps=8):
    """Spread colour into transparent texels so mip levels of the cut-out card do not fringe."""
    rgb = colour[..., :3].copy()
    known = colour[..., 3] > 0
    for _ in range(steps):
        total = np.zeros_like(rgb)
        count = np.zeros(known.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(np.roll(known, dy, axis=0), dx, axis=1)
            total += np.roll(np.roll(rgb * known[..., None], dy, axis=0), dx, axis=1)
            count += shifted
        grow = (~known) & (count > 0)
        rgb[grow] = total[grow] / count[grow][:, None]
        known = known | grow
    return np.concatenate([rgb, colour[..., 3:4]], axis=-1)


def bake_card(positions, uvs, indices, atlas):
    """Side view over the top rows and top view over the bottom rows (RGBA, 8 bit)."""
    low = positions.min(axis=0)
    high = positions.max(axis=0)
    span = np.maximum(high - low, 1e-9)
    width = CARD_WIDTH * SUPERSAMPLE
    # Model axes: x along the body (snout +x), y up, z to the side. Image u runs from the tail (min x) to the snout.
    side_points = np.stack([(positions[:, 0] - low[0]) / span[0] * width,
                            (high[1] - positions[:, 1]) / span[1] * SIDE_ROWS * SUPERSAMPLE], axis=1)
    side = rasterise(side_points, positions[:, 2], uvs, indices, atlas, (width, SIDE_ROWS * SUPERSAMPLE))
    top_points = np.stack([(positions[:, 0] - low[0]) / span[0] * width,
                           (positions[:, 2] - low[2]) / span[2] * TOP_ROWS * SUPERSAMPLE], axis=1)
    top = rasterise(top_points, positions[:, 1], uvs, indices, atlas, (width, TOP_ROWS * SUPERSAMPLE))
    card = np.concatenate([downsample(side, SUPERSAMPLE), downsample(top, SUPERSAMPLE)], axis=0)
    card = bleed(card)
    return Image.fromarray(np.clip(np.round(card * 255), 0, 255).astype(np.uint8), 'RGBA')


def vendor_species(source, species):
    """{file name: bytes} for one species."""
    hi_bytes = (source / f'{species}.glb').read_bytes()
    lo_bytes = (source / f'{species}_lo.glb').read_bytes()
    hi_document, hi_binary = read_glb(hi_bytes)
    lo_document, lo_binary = read_glb(lo_bytes)
    atlas_bytes = image_bytes(hi_document, hi_binary)
    if image_bytes(lo_document, lo_binary) != atlas_bytes:
        raise ValueError(f'{species}: the distance model does not share the full model texture')
    if 'swim' not in (hi_document['nodes'][0].get('extras') or {}):
        raise ValueError(f'{species}: no swim parameters in the node extras')
    lo_document, lo_binary = strip_texture(lo_document, lo_binary)
    atlas = Image.open(io.BytesIO(atlas_bytes)).convert('RGBA')
    positions, uvs, indices = mesh_arrays(hi_document, hi_binary)
    card = bake_card(positions, uvs, indices, atlas)
    buffer = io.BytesIO()
    card.save(buffer, 'WEBP', lossless=False, quality=88, alpha_quality=100, method=6, exact=True)
    return {f'{species}.glb': hi_bytes, f'{species}_lo.glb': write_glb(lo_document, lo_binary),
            f'{species}_card.webp': buffer.getvalue()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('--source', type=Path, required=True, help="the kit's fish/ folder")
    parser.add_argument('--check', action='store_true', help='compare with the committed files, write nothing')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    stale = []
    for species in SPECIES:
        for name, data in vendor_species(args.source, species).items():
            if len(data) > MAX_FILE_BYTES:
                raise ValueError(f'{name} is over 2 MB')
            total += len(data)
            target = OUT / name
            if args.check:
                if not target.is_file() or target.read_bytes() != data:
                    stale.append(name)
                continue
            target.write_bytes(data)
            print(f'{name:24} {len(data) / 1024:7.1f} KiB')
    print(f'total {total / 1024 / 1024:.2f} MiB for {len(SPECIES)} species')
    if stale:
        print('out of date:', ', '.join(stale))
        sys.exit(1)


if __name__ == '__main__':
    main()
