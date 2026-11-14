"""Build the original fleet with Blender, Basis and meshopt; enforce shipping budgets."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / 'simulator/viewer/models'
FLEET = {'x1': 'observation', 'falcon': 'work', 'bluerov2_heavy': 'openframe'}
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.vehicles import VEHICLE_DEFINITIONS


def document(path):
    data = path.read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    return json.loads(data[20:20 + length])


def report():
    rows = []
    for slug in FLEET.values():
        counts = []
        for lod in range(3):
            path = MODELS / f'{slug}-lod{lod}.glb'
            doc = document(path)
            triangles = sum(doc['accessors'][p['indices']]['count'] // 3
                            for m in doc['meshes'] for p in m['primitives'])
            assert triangles <= 80000, path
            assert path.stat().st_size <= 8 * 1024 * 1024, path
            assert 'EXT_meshopt_compression' in doc['extensionsUsed'], path
            assert 'KHR_texture_basisu' in doc['extensionsUsed'], path
            texture_bytes = 0
            for image in doc.get('images', []):
                view = doc['bufferViews'][image['bufferView']]
                # All authored maps are 128 square, RGBA8 worst-case fallback incl. mips.
                texture_bytes += 128 * 128 * 4 * 4 // 3
            counts.append(triangles)
            rows.append({'asset': path.name, 'triangles': triangles, 'bytes': path.stat().st_size,
                         'texture_gpu_rgba8_bytes_with_mips': texture_bytes, 'max_texture': 128})
        assert counts[0] > counts[1] > counts[2], counts
    total = sum(p.stat().st_size for p in MODELS.glob('*.glb'))
    assert total <= 120 * 1024 * 1024
    result = {'models_total_bytes': total, 'assets': rows}
    (MODELS / 'assets-report.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        blender = shutil.which('blender')
        transform = shutil.which('gltf-transform')
        if not blender or not transform or not shutil.which('toktx'):
            parser.error('Requires Blender, @gltf-transform/cli 4.4.0 and KTX-Software toktx 4.4.2 on PATH')
        subprocess.run([blender, '-b', '--factory-startup', '--python',
                        str(ROOT / 'cad/build_original_vehicles.py'), '--', str(ROOT)], check=True)
        for identifier, slug in FLEET.items():
            definition = VEHICLE_DEFINITIONS[identifier]
            proxy = {'coordinates': 'FRD metres about CG', 'spheres': definition.hull_spheres}
            (MODELS / f'{slug}-collision.json').write_text(json.dumps(proxy, indent=2) + '\n')
            for lod in range(3):
                raw = ROOT / f'.runtime/assets/{slug}-lod{lod}.glb'
                basis = raw.with_suffix('.basis.glb')
                subprocess.run([transform, 'uastc', str(raw), str(basis)], check=True)
                subprocess.run([transform, 'meshopt', str(basis), str(MODELS / raw.name)], check=True)
    print(json.dumps(report(), indent=2))


if __name__ == '__main__':
    main()
