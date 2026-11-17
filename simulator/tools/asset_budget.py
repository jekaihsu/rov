"""Report every viewer GLB and check it against docs/design/asset-budget.json.

From the repository root or the simulator directory:

  python simulator/tools/asset_budget.py
  python simulator/tools/asset_budget.py --json
  python simulator/tools/asset_budget.py --check

Each GLB line is the file size, triangle count, embedded texture count and
resolution, estimated GPU memory, and the scenarios that load it.

GPU memory is the decoded mesh (accessor count times component size, which is
what the loader uploads) plus RGBA8 textures with mipmaps (width * height * 4
* 4/3). WebP and JPEG do not stay compressed on the GPU. KTX2 would; this
project does not ship a Basis transcoder, so textures are WebP.

A file counts as loaded when viewer or qysim source names it, when fish_kit.js
builds it from a KIT_SPECIES id, when a scan id in the viewer names it, or when
scene_models.js builds it as the _lod1/_lod2 sibling of a loaded GLB.
"""
import io
import json
import re
import struct
import sys
from pathlib import Path

from PIL import Image

SIMULATOR = Path(__file__).resolve().parents[1]
REPO = SIMULATOR.parent
VIEWER = SIMULATOR / 'viewer'
MODELS = VIEWER / 'models'
BUDGET = REPO / 'docs' / 'design' / 'asset-budget.json'
sys.path.insert(0, str(SIMULATOR))

from qysim.scenarios import LIBRARY, build  # noqa: E402

COMPONENT = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
LITERAL = re.compile(r'models/[A-Za-z0-9_./-]+\.(?:glb|webp|jpg|jpeg|png|ktx2)')
SPECIES = re.compile(r'^\s{2}([a-z][a-z0-9_]*): \{length:', re.M)
QUOTED = re.compile(r"['\"]([A-Za-z0-9_./-]+)['\"]")


def read_glb(path):
    data = path.read_bytes()
    magic, version, _total = struct.unpack_from('<III', data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError(f'{path} is not a GLB')
    length, _kind = struct.unpack_from('<II', data, 12)
    document = json.loads(data[20:20 + length])
    offset = 20 + length
    bin_length, _bin_kind = struct.unpack_from('<II', data, offset)
    return document, data[offset + 8:offset + 8 + bin_length]


def triangle_count(document):
    total = 0
    for mesh in document.get('meshes') or []:
        for prim in mesh.get('primitives') or []:
            if prim.get('mode', 4) != 4:
                continue
            if 'indices' in prim:
                total += document['accessors'][prim['indices']]['count'] // 3
            else:
                total += document['accessors'][prim['attributes']['POSITION']]['count'] // 3
    return total


def geometry_bytes(document):
    total = 0
    for accessor in document.get('accessors') or []:
        total += accessor['count'] * WIDTH[accessor['type']] * COMPONENT[accessor['componentType']]
    return total


def texture_rows(document, binary):
    rows = []
    for image in document.get('images') or []:
        view = document['bufferViews'][image['bufferView']]
        if (view.get('extensions') or {}).get('EXT_meshopt_compression'):
            continue
        off = view.get('byteOffset', 0)
        blob = binary[off:off + view['byteLength']]
        mime = image.get('mimeType') or ''
        try:
            with Image.open(io.BytesIO(blob)) as picture:
                width, height = picture.size
        except (OSError, ValueError):
            width, height = 0, 0
        if mime == 'image/ktx2':
            gpu = len(blob)
        else:
            gpu = width * height * 4 * 4 // 3
        rows.append({
            'name': image.get('name') or '',
            'mime': mime,
            'width': width,
            'height': height,
            'gpu_bytes': gpu,
        })
    return rows


def source_text():
    parts = []
    for path in list(VIEWER.rglob('*.js')) + list(VIEWER.rglob('*.html')):
        if 'vendor' in path.relative_to(VIEWER).parts:
            continue
        parts.append(path.read_text(encoding='utf-8', errors='ignore'))
    for path in (SIMULATOR / 'qysim').rglob('*.py'):
        parts.append(path.read_text(encoding='utf-8', errors='ignore'))
    return '\n'.join(parts)


def scene_index():
    """Scenario key -> model paths declared on that scenario's field meshes."""
    found = {}
    for key in LIBRARY:
        scenario = build(key)
        for obstacle in scenario.obstacles:
            model = getattr(obstacle, 'model', None)
            if model:
                found.setdefault(model, []).append(key)
    return found


def referenced_paths(text):
    refs = set(LITERAL.findall(text))
    species = SPECIES.findall((VIEWER / 'fish_kit.js').read_text(encoding='utf-8'))
    for name in species:
        refs.add(f'models/fish/{name}.glb')
        refs.add(f'models/fish/{name}_lo.glb')
        refs.add(f'models/fish/{name}_card.webp')
    quoted = set(QUOTED.findall(text))
    for path in MODELS.joinpath('scan').glob('*'):
        stem = path.stem
        ident = stem[:-2] if stem.endswith(('_c', '_n')) else stem
        if stem in quoted or ident in quoted or f'{stem}.webp' in text:
            refs.add('models/scan/' + path.name)
    siblings = set()
    for ref in refs:
        if ref.endswith('.glb'):
            stem = ref[:-4]
            siblings.add(stem + '_lod1.glb')
            siblings.add(stem + '_lod2.glb')
    refs.update(siblings)
    return refs


def rel_model(path):
    return 'models/' + path.relative_to(MODELS).as_posix()


def build_report():
    text = source_text()
    refs = referenced_paths(text)
    scenes = scene_index()
    files = []
    unreferenced = []
    for path in sorted(MODELS.rglob('*')):
        if not path.is_file():
            continue
        rel = rel_model(path)
        loaded = []
        if rel in refs or path.name in text:
            loaded.append('viewer')
        for key in scenes.get(rel, []):
            loaded.append(f'scenario:{key}')
        if not loaded:
            unreferenced.append(rel)
        if path.suffix != '.glb':
            continue
        document, binary = read_glb(path)
        textures = texture_rows(document, binary)
        required = document.get('extensionsRequired') or []
        used = document.get('extensionsUsed') or []
        files.append({
            'path': rel,
            'bytes': path.stat().st_size,
            'triangles': triangle_count(document),
            'textures': textures,
            'gpu_bytes': geometry_bytes(document) + sum(row['gpu_bytes'] for row in textures),
            'meshopt': 'EXT_meshopt_compression' in required or 'EXT_meshopt_compression' in used,
            'loaded_by': loaded,
        })
    return {
        'files': files,
        'unreferenced': unreferenced,
        'total_bytes': sum(path.stat().st_size for path in MODELS.rglob('*') if path.is_file()),
    }


def limit_for(limits, rel, key):
    override = (limits.get('files') or {}).get(rel) or {}
    if key in override:
        return override[key]
    return (limits.get('defaults') or {}).get(key)


def violations(report, limits):
    found = []
    retained = limits.get('retained_unloaded') or {}
    for rel in report['unreferenced']:
        if rel not in retained:
            found.append(f'{rel} is not loaded and is not listed as retained')
    for row in report['files']:
        rel = row['path']
        if not row['meshopt']:
            found.append(f'{rel} is not meshopt-compressed')
        for texture in row['textures']:
            if texture['mime'] not in ('image/webp', 'image/ktx2'):
                found.append(f'{rel} texture {texture["name"] or texture["mime"]} is {texture["mime"] or "unknown"}')
        for key, label in (('max_bytes', 'bytes'), ('max_triangles', 'triangles'), ('max_gpu_bytes', 'gpu_bytes')):
            cap = limit_for(limits, rel, key)
            if cap is not None and row[label] > cap:
                found.append(f'{rel} {label} {row[label]} exceeds {cap}')
    total_cap = (limits.get('totals') or {}).get('max_bytes')
    if total_cap is not None and report['total_bytes'] > total_cap:
        found.append(f'models/ total {report["total_bytes"]} exceeds {total_cap}')
    return found


def check(limits=None):
    if limits is None:
        limits = json.loads(BUDGET.read_text(encoding='utf-8'))
    return violations(build_report(), limits)


def format_report(report):
    lines = []
    for row in report['files']:
        textures = ', '.join(
            f'{item["name"] or item["mime"]} {item["width"]}x{item["height"]} {item["mime"]}'
            for item in row['textures']
        ) or 'none'
        where = ', '.join(row['loaded_by']) or 'not loaded'
        lines.append(
            f'{row["path"]}: {row["bytes"]} bytes, {row["triangles"]} tris, '
            f'{len(row["textures"])} textures ({textures}), gpu {row["gpu_bytes"]} bytes, {where}'
        )
    lines.append(f'total: {report["total_bytes"]} bytes')
    if report['unreferenced']:
        lines.append('unreferenced: ' + ', '.join(report['unreferenced']))
    return '\n'.join(lines)


def main():
    report = build_report()
    if '--json' in sys.argv:
        print(json.dumps(report, indent=2))
        return
    print(format_report(report))
    if '--check' in sys.argv:
        found = violations(report, json.loads(BUDGET.read_text(encoding='utf-8')))
        if found:
            print('\n'.join(found), file=sys.stderr)
            sys.exit(1)
        print('asset budget: ok')


if __name__ == '__main__':
    main()
