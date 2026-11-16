"""Inspect delivered GLB bytes independently of the Blender authoring scene (standard library only)."""
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LENGTHS = dict(salmon=.6, saithe=.45, fusilier=.25, damselfish=.09, butterflyfish=.13, surgeonfish=.2)


def validate(path, length):
    data = path.read_bytes()
    magic, version, size = struct.unpack_from('<3I', data)
    assert (magic, version, size) == (0x46546C67, 2, len(data))
    assert size <= 300000
    json_size, kind = struct.unpack_from('<2I', data, 12)
    assert kind == 0x4E4F534A
    doc = json.loads(data[20:20 + json_size])
    binary = data[28 + json_size:]
    assert len(doc['meshes']) == len(doc['nodes']) == 3
    assert len(doc['images']) == 2
    assert len(doc['materials']) == 1
    mat = doc['materials'][0]
    assert mat['doubleSided']
    assert mat['pbrMetallicRoughness']['baseColorTexture']['index'] == 0
    assert mat['pbrMetallicRoughness']['metallicRoughnessTexture']['index'] == 1
    assert mat['occlusionTexture']['index'] == 1
    for image in doc['images']:
        view = doc['bufferViews'][image['bufferView']]
        png = binary[view['byteOffset']:view['byteOffset'] + view['byteLength']]
        suffix = 'basecolor' if image is doc['images'][0] else 'orm'
        assert png == path.with_name(f'{path.stem}_{suffix}.png').read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack_from('>2I', png, 16) == (512, 256)

    def values(index):
        acc = doc['accessors'][index]
        view = doc['bufferViews'][acc['bufferView']]
        width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[acc['type']]
        code = 'f' if acc['componentType'] == 5126 else 'H'
        start = view['byteOffset']
        raw = binary[start:start + view['byteLength']]
        result = list(struct.iter_unpack('<' + code * width, raw))
        assert len(result) == acc['count']
        assert all(math.isfinite(x) for row in result for x in row)
        return result

    counts = []
    for lod, mesh in enumerate(doc['meshes']):
        assert mesh['name'] == f'{path.stem}_lod{lod}'
        assert len(mesh['primitives']) == 1
        primitive = mesh['primitives'][0]
        attrs = primitive['attributes']
        pos = values(attrs['POSITION'])
        normals = values(attrs['NORMAL'])
        uv0 = values(attrs['TEXCOORD_0'])
        uv1 = values(attrs['TEXCOORD_1'])
        assert len(pos) == len(normals) == len(uv0) == len(uv1)
        indices = [row[0] for row in values(primitive['indices'])]
        count = len(indices) // 3
        assert len(indices) % 3 == 0
        assert count <= [2500, 800, 250][lod]
        assert max(indices) < len(pos)
        assert abs(max(p[2] for p in pos) - length / 2) < 1e-7
        assert abs(min(p[2] for p in pos) + length / 2) < 1e-7
        for p, uv, n in zip(pos, uv1, normals):
            assert abs(uv[0] - (.5 - p[2] / length)) < 1e-6
            assert 0 <= uv[0] <= 1
            assert abs(sum(x * x for x in n) - 1) < 1e-4
        for offset in range(0, len(indices), 3):
            a, b, c = [pos[i] for i in indices[offset:offset + 3]]
            ab = [b[i] - a[i] for i in range(3)]
            ac = [c[i] - a[i] for i in range(3)]
            cross = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
                     ab[0] * ac[1] - ab[1] * ac[0]]
            assert sum(v * v for v in cross) > 1e-22
        counts.append(count)
    print(f'{path.stem}: {counts} triangles, {size} bytes; dimensions, UVs, normals, images OK')


def validate_renders():
    directory = ROOT / 'docs/design/fish-models'
    paths = [directory / f'{name}_{view}.jpg' for name in LENGTHS for view in ('side', 'top', 'front34')]
    paths.append(directory / 'overview.jpg')
    for path in paths:
        data = path.read_bytes()
        assert len(data) <= 300000
        assert data[:2] == b'\xff\xd8'
        offset = 2
        found = False
        while offset < len(data):
            assert data[offset] == 255
            marker = data[offset + 1]
            size = struct.unpack_from('>H', data, offset + 2)[0]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack_from('>HH', data, offset + 5)
                assert (width, height) == (1600, 900)
                found = True
                break
            offset += 2 + size
        assert found
    print('19 JPEG renders: 1600x900 and <=300000 bytes each')


if __name__ == '__main__':
    for name, length in LENGTHS.items():
        validate(ROOT / 'simulator/viewer/models/fish' / f'{name}.glb', length)
    validate_renders()
