"""Memory-bounded preview simplification of the official R3 STL; never release assets."""
from pathlib import Path
import json
import struct
import numpy as np

OUT = Path(__file__).resolve().parents[1] / '.runtime' / 'bluerov-reference'
source = OUT / 'bluerov2-r3-official.stl'
target = OUT / 'bluerov2-r3-preview.stl'
dtype = np.dtype([('normal', '<f4', (3,)), ('v', '<f4', (3, 3)), ('attr', '<u2')])
with source.open('rb') as f:
    f.seek(80)
    count = struct.unpack('<I', f.read(4))[0]
raw = np.memmap(source, dtype=dtype, mode='r', offset=84, shape=(count,))
lo = raw['v'].min(axis=(0, 1)); hi = raw['v'].max(axis=(0, 1))
center = (hi + lo) / 2
grid_mm = 0.6
kept = 0
with target.open('wb') as f:
    f.write(b'Official BlueROV2 R3 local reference; 0.6mm clustered preview'.ljust(80, b' '))
    f.write(struct.pack('<I', 0))
    for start in range(0, count, 100_000):
        vertices = raw['v'][start:start+100_000].copy()
        vertices = np.rint((vertices - center) / grid_mm) * grid_mm
        # Original manufacturer CAD axes: X width, Y height, Z length.
        vertices = vertices[:, :, [2, 0, 1]] * .001
        normal = np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0])
        length = np.linalg.norm(normal, axis=1)
        valid = length > 1e-10
        batch = np.zeros(np.count_nonzero(valid), dtype=dtype)
        batch['v'] = vertices[valid]
        batch['normal'] = normal[valid] / length[valid, None]
        batch.tofile(f)
        kept += len(batch)
    f.seek(80); f.write(struct.pack('<I', kept))
report = dict(source_triangles=count, preview_triangles=kept,
              source_dimensions_mm=(hi-lo).tolist(), grid_mm=grid_mm,
              max_vertex_displacement_mm=float(np.sqrt(3)*grid_mm/2),
              preview_axes='X length; Y width; Z up; meters',
              limitations='R3 standard six-thruster assembly, not Heavy. No source materials. Local reference only; redistribution license unverified.')
(OUT / 'preview.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print(json.dumps(report, indent=2), flush=True)
