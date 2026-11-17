"""Build the CC0 scanned seabed, structure and rock assets in viewer/models/scan/ from the original downloads.

Sources (all CC0 1.0; see viewer/models/CREDITS.md for pages and licence proof): Poly Haven texture and model
scans and ambientCG materials, at 1K. Download them by hand into a scratch folder outside the repository (the
Poly Haven terms ask not to scrape the site, so this script never downloads anything) with this layout:

  <source>/<polyhaven id>/<file>             e.g. sand_03/sand_03_diff_1k.jpg, rock_07/rock_07_1k.gltf + .bin
  <source>/acg_<ambientCG id>/<id>.zip       the 1K-JPG zip, read in place (not extracted)

  python simulator/tools/build_scan_materials.py --list                  # what to download, and where to put it
  python simulator/tools/build_scan_materials.py --source <scratch>      # check checksums, write the assets
  python simulator/tools/build_scan_materials.py --source <scratch> --check   # rebuild in memory and compare

Downloads are treated as data: checksums are verified before anything is read, images are decoded with Pillow,
the rock glTF files are opened by Blender's importer in a background process with factory settings, and nothing
from the downloads is executed. Blender (4.x, `blender` on PATH or $BLENDER) is needed for the rocks only.

Outputs (WebP, 1024 px unless noted; `_c` colour in sRGB, `_n` OpenGL tangent-space normal in RGB with roughness
or height in alpha):
  seabed  sand, shell, gravel, mud, rockbed (`_c` normalised so each channel's linear mean is 0.4: the viewer
          tints them with the site palette), ripple_n (sand-ripple normal, height in alpha), macro_c (256 px,
          large-scale colour variation)
  steel   coating (paint over steel: grey paint luminance or rust colour in RGB, rust propensity in alpha),
          rust, plate (diamond plate), grating (perforated walkway, opacity in alpha), concrete
  rocks   rocks_c / rocks_n (2x2 atlas of the four rock scans, 512 px each; colour normalised like the seabed so
          the reddish desert stones take the site's tint) and rocks.glb (three decimated levels per rock, made
          blockier, positions about the rock's inner centre, every vertex inside the unit sphere; node extras
          carry the inner radius as a share of the bounding radius, see viewer/scan_materials.js)
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

OUT = Path(__file__).resolve().parents[1] / 'viewer/models/scan'
SIZE = 1024
MEAN = 0.4
MAX_FILE_BYTES = 600 * 1024
PH = 'https://dl.polyhaven.org/file/ph-assets'
CHECKSUMS = Path(__file__).with_name('scan_materials_sources.json')
ACG = 'https://ambientcg.com/get?file='

# Poly Haven texture scans (1K JPG maps) and model scans (1K glTF), ambientCG materials (1K-JPG zip).
PH_TEXTURES = ('sand_03', 'shell_floor_01', 'coral_gravel', 'low_tide_rocks', 'aerial_beach_01', 'coast_sand_01',
               'green_metal_rust', 'rust_coarse_01', 'concrete')
PH_MODELS = ('rock_07', 'rock_09', 'boulder_01', 'stone_01')
ACG_MATERIALS = ('Ground054', 'PaintedMetal016', 'DiamondPlate008C', 'MetalWalkway014')
# Rock levels of detail (triangles) and the atlas quadrant of each rock.
ROCK_LODS = (1200, 320, 96)
ATLAS_GUTTER = 8
NORMAL_Q = 70


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def source_files():
    """(relative path, url) of every file the build reads."""
    files = []
    for pid in PH_TEXTURES:
        folder = 'jpg/1k'
        for map_name in ('diff', 'nor_gl', 'rough', 'disp'):
            if map_name == 'disp' and pid != 'aerial_beach_01':
                continue
            name = f'{pid}_{map_name}_1k.jpg'
            files.append((f'{pid}/{name}', f'{PH}/Textures/{folder}/{pid}/{name}'))
    for pid in PH_MODELS:
        files.append((f'{pid}/{pid}_1k.gltf', f'{PH}/Models/gltf/1k/{pid}/{pid}_1k.gltf'))
        files.append((f'{pid}/{pid}.bin', f'{PH}/Models/gltf/8k/{pid}/{pid}.bin'))
        for map_name in ('diff', 'nor_gl', 'arm'):
            name = f'{pid}_{map_name}_1k.jpg'
            files.append((f'{pid}/textures/{name}', f'{PH}/Models/jpg/1k/{pid}/{name}'))
    for aid in ACG_MATERIALS:
        files.append((f'acg_{aid}/{aid}.zip', f'{ACG}{aid}_1K-JPG.zip'))
    return files


def verify(source):
    """Check every source file against the recorded SHA-256; fail before decoding anything."""
    recorded = json.loads(CHECKSUMS.read_text(encoding='utf-8'))
    bad = []
    for relative, _ in source_files():
        path = source / relative
        if not path.is_file():
            bad.append(f'missing {relative}')
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if recorded.get(relative) != digest:
            bad.append(f'checksum {relative}')
    if bad:
        raise SystemExit('Source files do not match scan_materials_sources.json:\n  ' + '\n  '.join(bad))


def record(source):
    """Write the SHA-256 of the current downloads (first build only; review the list before committing)."""
    sums = {}
    for relative, _ in source_files():
        sums[relative] = hashlib.sha256((source / relative).read_bytes()).hexdigest()
    CHECKSUMS.write_text(json.dumps(sums, indent=1, sort_keys=True) + '\n', encoding='utf-8')


# ── image helpers ────────────────────────────────────────────────────────────────────────────────────────
class Source:
    def __init__(self, root):
        self.root = root
        self.zips = {}

    def image(self, relative, mode='RGB'):
        return Image.open(self.root / relative).convert(mode)

    def acg(self, aid, suffix, mode='RGB'):
        if aid not in self.zips:
            self.zips[aid] = zipfile.ZipFile(self.root / f'acg_{aid}/{aid}.zip')
        data = self.zips[aid].read(f'{aid}_1K-JPG_{suffix}.jpg')
        return Image.open(io.BytesIO(data)).convert(mode)

    def ph(self, pid, map_name, mode='RGB'):
        return self.image(f'{pid}/{pid}_{map_name}_1k.jpg', mode)


def array(image, size=SIZE):
    if image.size != (size, size):
        image = image.resize((size, size), Image.LANCZOS)
    return np.asarray(image).astype(np.float64) / 255


def normal_array(image, size=SIZE):
    n = array(image, size)[..., :3] * 2 - 1
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8
    return n


def normalised_colour(image, size=SIZE, mean=MEAN):
    """Linear colour scaled per channel to the given mean, back in sRGB (the viewer tints by site)."""
    linear = srgb_to_linear(array(image, size)[..., :3])
    linear *= mean / linear.reshape(-1, 3).mean(0)
    return linear_to_srgb(linear)


def pack(rgb, alpha=None):
    data = np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)
    if alpha is None:
        return Image.fromarray(data, 'RGB')
    a = np.clip(np.round(alpha * 255), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([data, a]), 'RGBA')


def webp(image, quality, alpha_quality=35):
    """Lossy WebP; alpha (roughness, height) is quantised harder than colour unless it is a mask."""
    buffer = io.BytesIO()
    image.save(buffer, 'WEBP', quality=quality, method=6, alpha_quality=alpha_quality)
    return buffer.getvalue()


def normal_rgb(n):
    return np.clip(n * 0.5 + 0.5, 0, 1)


def blend_normals(a, b):
    """Whiteout blend of two tangent-space normals."""
    n = np.dstack([a[..., 0] + b[..., 0], a[..., 1] + b[..., 1], a[..., 2] * b[..., 2]])
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8)


def hue_sat_value(rgb):
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    delta = mx - mn + 1e-8
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.where(mx == r, ((g - b) / delta) % 6, np.where(mx == g, (b - r) / delta + 2, (r - g) / delta + 4))
    return hue * 60, (mx - mn) / (mx + 1e-8), mx


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ── materials ────────────────────────────────────────────────────────────────────────────────────────────
def seabed_set(src, name, colour, normal, rough):
    return {f'{name}_c.webp': webp(pack(normalised_colour(colour)), 80),
            f'{name}_n.webp': webp(pack(normal_rgb(normal_array(normal, SIZE // 2)), array(rough.convert('L'), SIZE // 2)),
                                   NORMAL_Q)}


def ph_seabed(src, name, pid):
    return seabed_set(src, name, src.ph(pid, 'diff'), src.ph(pid, 'nor_gl'), src.ph(pid, 'rough'))


def ripple(src):
    height = array(src.ph('aerial_beach_01', 'disp', 'L'))
    height = (height - height.min()) / (np.ptp(height) + 1e-8)
    return {'ripple_n.webp': webp(pack(normal_rgb(normal_array(src.ph('aerial_beach_01', 'nor_gl'))), height),
                                  NORMAL_Q)}


def macro(src):
    image = src.ph('coast_sand_01', 'diff').filter(ImageFilter.GaussianBlur(6))
    return {'macro_c.webp': webp(pack(normalised_colour(image, 256)), 85)}


def tileable_noise(size, cells, seed):
    """Smooth periodic noise in 0..1: white noise low-passed in the frequency domain (wraps at the edges)."""
    rng = np.random.default_rng(seed)
    spectrum = np.fft.fft2(rng.standard_normal((size, size)))
    f = np.fft.fftfreq(size) * size
    radius = np.hypot(*np.meshgrid(f, f, indexing='ij'))
    field = np.real(np.fft.ifft2(spectrum * np.exp(-(radius / cells) ** 2)))
    field = (field - field.min()) / np.ptp(field)
    return smooth(field, 0.2, 0.8)


def coating(src):
    """Paint over steel: chipped-paint and rust areas of PaintedMetal016 with the rust spots and streaks of
    green_metal_rust. Paint pixels keep only their luminance (the viewer applies the coat colour)."""
    chip = array(src.acg('PaintedMetal016', 'Color'))
    chip_hue, chip_sat, chip_val = hue_sat_value(chip)
    # rust is orange-brown and moderately saturated; the yellow and black stripes are both paint
    chip_rust = smooth(chip_sat, 0.3, 0.5) * (1 - smooth(chip_hue, 34, 44)) * smooth(chip_val, 0.12, 0.2)
    spots = array(src.ph('green_metal_rust', 'diff'))
    spot_hue, spot_sat, _ = hue_sat_value(spots)
    spot_rust = (1 - smooth(spot_hue, 48, 70)) * smooth(spot_sat, 0.25, 0.4)
    # graded propensity: chips are spread over 0.25-1 by a tileable noise, so the viewer's threshold sets how much
    # of the coat has broken down (new paint shows only the spots and streaks)
    rust = np.maximum(chip_rust * (0.25 + 0.75 * tileable_noise(SIZE, 24, seed=7)), spot_rust * 0.95)
    rust = np.asarray(Image.fromarray((rust * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255
    paint_lum = srgb_to_linear(spots).mean(-1)
    paint_lum *= MEAN / paint_lum.mean()
    grey = linear_to_srgb(np.repeat(paint_lum[..., None], 3, -1))
    rust_colour = np.where(chip_rust[..., None] >= spot_rust[..., None], chip, spots)
    exposed = smooth(np.maximum(chip_rust, spot_rust), 0.2, 0.5)[..., None]
    rgb = grey * (1 - exposed) + rust_colour * exposed
    normal = blend_normals(normal_array(src.acg('PaintedMetal016', 'NormalGL')),
                           normal_array(src.ph('green_metal_rust', 'nor_gl')))
    rough = array(src.acg('PaintedMetal016', 'Roughness', 'L')) * rust + \
        array(src.ph('green_metal_rust', 'rough', 'L')) * (1 - rust)
    return {'coating_c.webp': webp(pack(rgb, rust), 80, 70), 'coating_n.webp': webp(pack(normal_rgb(normal), rough), NORMAL_Q)}


def plain(src, name, colour, normal, rough, alpha=None, colour_fn=None):
    rgb = array(colour)
    if colour_fn:
        rgb = colour_fn(rgb)
    return {f'{name}_c.webp': webp(pack(rgb, alpha), 80, 70),
            f'{name}_n.webp': webp(pack(normal_rgb(normal_array(normal)), array(rough.convert('L'))), NORMAL_Q)}


def galvanised(rgb):
    """Walkway plate as weathered galvanised steel: mostly grey, keeping a share of the scan's rust."""
    grey = rgb.mean(-1, keepdims=True) * np.array([0.98, 1.0, 1.02])
    return np.clip(grey * 0.65 + rgb * 0.35, 0, 1)


def textures(src):
    out = {}
    out.update(ph_seabed(src, 'sand', 'sand_03'))
    out.update(ph_seabed(src, 'shell', 'shell_floor_01'))
    out.update(ph_seabed(src, 'gravel', 'coral_gravel'))
    out.update(ph_seabed(src, 'rockbed', 'low_tide_rocks'))
    out.update(seabed_set(src, 'mud', src.acg('Ground054', 'Color'), src.acg('Ground054', 'NormalGL'),
                          src.acg('Ground054', 'Roughness')))
    out.update(ripple(src))
    out.update(macro(src))
    out.update(coating(src))
    out.update(plain(src, 'rust', src.ph('rust_coarse_01', 'diff'), src.ph('rust_coarse_01', 'nor_gl'),
                     src.ph('rust_coarse_01', 'rough')))
    out.update(plain(src, 'concrete', src.ph('concrete', 'diff'), src.ph('concrete', 'nor_gl'),
                     src.ph('concrete', 'rough')))
    out.update(plain(src, 'plate', src.acg('DiamondPlate008C', 'Color'), src.acg('DiamondPlate008C', 'NormalGL'),
                     src.acg('DiamondPlate008C', 'Roughness')))
    out.update(plain(src, 'grating', src.acg('MetalWalkway014', 'Color'), src.acg('MetalWalkway014', 'NormalGL'),
                     src.acg('MetalWalkway014', 'Roughness'), array(src.acg('MetalWalkway014', 'Opacity', 'L')),
                     galvanised))
    return out


# ── rocks ────────────────────────────────────────────────────────────────────────────────────────────────
BLENDER_SCRIPT = r'''
import bpy, json, sys
argv = sys.argv[sys.argv.index('--') + 1:]
with open(argv[0]) as handle:
    source = json.load(handle)
out, targets = argv[1], [int(v) for v in argv[2].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('rock')
mesh.from_pydata(source['position'], [], source['faces'])
layer = mesh.uv_layers.new(name='uv')
uv = source['uv']
for poly, corners in zip(mesh.polygons, source['corners']):
    for loop, corner in zip(poly.loop_indices, corners):
        layer.data[loop].uv = uv[corner]
obj = bpy.data.objects.new('rock', mesh)
bpy.context.scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
result = {'levels': []}
for target in targets:
    mod = obj.modifiers.new('decimate', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = min(1.0, target / len(source['faces']))
    mod.use_collapse_triangulate = True
    graph = bpy.context.evaluated_depsgraph_get()
    level = obj.evaluated_get(graph).to_mesh()
    level.calc_loop_triangles()
    data = level.uv_layers.active.data
    seen, position, uvs, vid, index = {}, [], [], [], []
    for tri in level.loop_triangles:
        for loop, vertex in zip(tri.loops, tri.vertices):
            key = (vertex, round(data[loop].uv[0], 6), round(data[loop].uv[1], 6))
            if key not in seen:
                seen[key] = len(position)
                position.append(list(level.vertices[vertex].co))
                uvs.append([data[loop].uv[0], data[loop].uv[1]])
                vid.append(vertex)
            index.append(seen[key])
    result['levels'].append({'position': position, 'uv': uvs, 'vid': vid, 'index': index})
    obj.evaluated_get(graph).to_mesh_clear()
    obj.modifiers.remove(mod)
with open(out, 'w') as handle:
    json.dump(result, handle)
'''
COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
DTYPES = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}


def read_gltf(path):
    """Positions, UVs and triangles of every primitive of a .gltf with one external .bin (read as data)."""
    document = json.loads(path.read_text(encoding='utf-8'))
    buffer = document['buffers'][0]['uri']
    if '/' in buffer or '\\' in buffer or buffer.startswith('.'):
        raise ValueError(f'unexpected buffer uri {buffer!r}')
    binary = (path.parent / buffer).read_bytes()

    def accessor(index):
        item = document['accessors'][index]
        view = document['bufferViews'][item['bufferView']]
        components = COMPONENTS[item['type']]
        dtype = DTYPES[item['componentType']]
        if view.get('byteStride') and view['byteStride'] != components * np.dtype(dtype).itemsize:
            raise ValueError('interleaved accessors are not supported')
        start = view.get('byteOffset', 0) + item.get('byteOffset', 0)
        return np.frombuffer(binary, dtype=dtype, count=item['count'] * components, offset=start).reshape(
            item['count'], components)

    positions, uvs, triangles = [], [], []
    base = 0
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            position = accessor(primitive['attributes']['POSITION']).astype(np.float64)
            positions.append(position)
            uvs.append(accessor(primitive['attributes']['TEXCOORD_0']).astype(np.float64))
            triangles.append(accessor(primitive['indices']).reshape(-1, 3).astype(np.int64) + base)
            base += len(position)
    return np.concatenate(positions), np.concatenate(uvs), np.concatenate(triangles)


def blender_levels(gltf):
    """Decimated levels (ROCK_LODS triangles) of a rock scan; Blender only sees plain vertex lists."""
    blender = os.environ.get('BLENDER') or shutil.which('blender')
    if not blender:
        raise SystemExit('Blender is needed for the rocks: put it on PATH or set $BLENDER')
    position, uv, triangles = read_gltf(gltf)
    # weld the glTF's seam splits so decimation keeps the surface closed; UVs stay per corner
    welded, remap = np.unique(np.round(position, 6), axis=0, return_inverse=True)
    remap = remap.reshape(-1)
    source = {'position': welded.tolist(), 'faces': remap[triangles].tolist(), 'corners': triangles.tolist(),
              'uv': uv.tolist()}
    with tempfile.TemporaryDirectory() as work:
        script = Path(work) / 'decimate.py'
        script.write_text(BLENDER_SCRIPT, encoding='utf-8')
        data = Path(work) / 'source.json'
        data.write_text(json.dumps(source), encoding='utf-8')
        out = Path(work) / 'levels.json'
        subprocess.run([blender, '-b', '--factory-startup', '-noaudio', '--python-exit-code', '1', '--python',
                        str(script), '--', str(data), str(out), ','.join(str(v) for v in ROCK_LODS)],
                       check=True, cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = json.loads(out.read_text(encoding='utf-8'))
    result['source_triangles'] = len(triangles)
    return result


def vertex_normals(position, index, vid):
    """Smooth normals shared across UV seams (same Blender vertex)."""
    tri = index.reshape(-1, 3)
    face = np.cross(position[tri[:, 1]] - position[tri[:, 0]], position[tri[:, 2]] - position[tri[:, 0]])
    accum = np.zeros((vid.max() + 1, 3))
    for k in range(3):
        np.add.at(accum, vid[tri[:, k]], face)
    n = accum[vid]
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


def point_triangle_distance(points, a, b, c):
    """Distance from each point (P x 3) to the nearest of the triangles (T x 3 each); P x T evaluated in blocks."""
    best = np.full(len(points), np.inf)
    for start in range(0, len(a), 256):
        ta, tb, tc = a[start:start + 256], b[start:start + 256], c[start:start + 256]
        p = points[:, None, :]
        ab, ac, ap = tb - ta, tc - ta, p - ta
        n = np.cross(ab, ac)
        nn = (n * n).sum(-1) + 1e-18
        # barycentric projection, clamped to the triangle by testing the edges
        v = ((np.cross(ap, ac) * n).sum(-1)) / nn
        w = ((np.cross(ab, ap) * n).sum(-1)) / nn
        inside = (v >= 0) & (w >= 0) & (v + w <= 1)
        plane = np.abs((ap * n).sum(-1)) / np.sqrt(nn)
        edge = np.minimum(np.minimum(segment_distance(p, ta, tb), segment_distance(p, ta, tc)),
                          segment_distance(p, tb, tc))
        dist = np.where(inside, plane, edge)
        best = np.minimum(best, dist.min(1))
    return best


def segment_distance(p, a, b):
    ab = b - a
    t = np.clip(((p - a) * ab).sum(-1) / ((ab * ab).sum(-1) + 1e-18), 0, 1)
    return np.linalg.norm(p - (a + t[..., None] * ab), axis=-1)


def winding(points, a, b, c):
    """Generalised winding number of a closed or nearly closed triangle soup at each point."""
    total = np.zeros(len(points))
    for start in range(0, len(a), 256):
        ra = a[start:start + 256] - points[:, None, :]
        rb = b[start:start + 256] - points[:, None, :]
        rc = c[start:start + 256] - points[:, None, :]
        la, lb, lc = (np.linalg.norm(r, axis=-1) for r in (ra, rb, rc))
        num = (ra * np.cross(rb, rc)).sum(-1)
        den = la * lb * lc + (ra * rb).sum(-1) * lc + (rb * rc).sum(-1) * la + (rc * ra).sum(-1) * lb
        total += 2 * np.arctan2(num, den).sum(1)
    return total / (4 * np.pi)


def inner_centre(levels):
    """Point inside every level that is furthest from all their surfaces, and that distance."""
    lo = np.min([lv['position'].min(0) for lv in levels], 0)
    hi = np.max([lv['position'].max(0) for lv in levels], 0)
    grid = np.stack(np.meshgrid(*[np.linspace(lo[k], hi[k], 13)[1:-1] for k in range(3)], indexing='ij'), -1)
    points = grid.reshape(-1, 3)
    clearance = np.full(len(points), np.inf)
    for lv in levels:
        tri = lv['position'][lv['index'].reshape(-1, 3)]
        inside = np.abs(winding(points, tri[:, 0], tri[:, 1], tri[:, 2])) > 0.5
        dist = point_triangle_distance(points, tri[:, 0], tri[:, 1], tri[:, 2])
        clearance = np.minimum(clearance, np.where(inside, dist, -1))
    best = int(np.argmax(clearance))
    return points[best], float(clearance[best])


def rounding(position, strength=0.8):
    """Linear map that evens out a scan's principal extents (strength 1: equal), keeping its orientation. Flat
    or long stones become blockier, so the collision sphere the viewer fits inside a rock fills more of it."""
    centred = position - position.mean(0)
    values, vectors = np.linalg.eigh(np.cov(centred.T))
    scale = (values.mean() / values) ** (0.5 * strength)
    return vectors @ np.diag(scale) @ vectors.T


def spherify(position, centre, typical, keep=0.55):
    """Compress each vertex's distance from the centre towards the typical one (distance ratio to the power
    `keep`): bumps and hollows stay, deep notches and long spurs shrink."""
    offset = position - centre
    radius = np.linalg.norm(offset, axis=1, keepdims=True)
    return centre + offset / (radius + 1e-12) * typical * (radius / typical) ** keep


def rocks(src):
    """Decimated rock levels in a single GLB plus the 2x2 texture atlas."""
    meshes = []
    colour = np.zeros((SIZE, SIZE, 3))
    normal = np.zeros((SIZE, SIZE, 3))
    rough = np.zeros((SIZE, SIZE))
    half = SIZE // 2
    inner = half - 2 * ATLAS_GUTTER
    for slot, pid in enumerate(PH_MODELS):
        data = blender_levels(src.root / f'{pid}/{pid}_1k.gltf')
        levels = [{key: np.asarray(lv[key]) for key in ('position', 'uv', 'vid', 'index')} for lv in data['levels']]
        rounder = rounding(levels[0]['position'])
        for lv in levels:
            lv['position'] = lv['position'] @ rounder.T
        centre, _ = inner_centre(levels[:1])
        typical = np.median(np.linalg.norm(levels[0]['position'] - centre, axis=1))
        for lv in levels:
            lv['position'] = spherify(lv['position'], centre, typical)
        centre, clearance = inner_centre(levels)
        radius = max(np.linalg.norm(lv['position'] - centre, axis=1).max() for lv in levels)
        ox, oy = slot % 2, slot // 2
        for lod, lv in enumerate(levels):
            position = (lv['position'] - centre) / radius
            uv = np.mod(lv['uv'], 1.0)
            uv = (np.array([ox, oy]) * half + ATLAS_GUTTER + uv * inner) / SIZE
            meshes.append({'name': f'{pid}_lod{lod}', 'rock': pid, 'lod': lod, 'inner': clearance / radius,
                           'position': position.astype(np.float32), 'uv': uv.astype(np.float32),
                           'normal': vertex_normals(position, lv['index'], lv['vid']).astype(np.float32),
                           'index': lv['index'].astype(np.uint16)})
        print(f'{pid}: source {data["source_triangles"]} tris -> {[len(lv["index"]) // 3 for lv in levels]}, '
              f'inner radius {clearance / radius:.3f} of the bounding radius', flush=True)
        for target, image, mode in ((colour, f'{pid}/textures/{pid}_diff_1k.jpg', 'c'),
                                    (normal, f'{pid}/textures/{pid}_nor_gl_1k.jpg', 'n'),
                                    (rough, f'{pid}/textures/{pid}_arm_1k.jpg', 'r')):
            tile = src.image(image).resize((inner, inner), Image.LANCZOS)
            pixels = normalised_colour(tile, inner) if mode == 'c' else np.asarray(tile).astype(np.float64) / 255
            padded = np.pad(pixels,
                            ((ATLAS_GUTTER, ATLAS_GUTTER), (ATLAS_GUTTER, ATLAS_GUTTER), (0, 0)),
                            mode='wrap')
            y0, x0 = oy * half, ox * half
            if mode == 'c':
                target[y0:y0 + half, x0:x0 + half] = padded
            elif mode == 'n':
                target[y0:y0 + half, x0:x0 + half] = padded * 2 - 1
            else:
                target[y0:y0 + half, x0:x0 + half] = padded[..., 1]
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True) + 1e-8
    return {'rocks_c.webp': webp(pack(colour), 82), 'rocks_n.webp': webp(pack(normal_rgb(normal), rough), NORMAL_Q),
            'rocks.glb': glb(meshes)}


def glb(meshes):
    """Minimal glTF 2.0 binary: one mesh and one node per level, extras {rock, lod, inner}."""
    binary = bytearray()
    document = {'asset': {'version': '2.0', 'generator': 'build_scan_materials.py'}, 'scene': 0,
                'scenes': [{'nodes': list(range(len(meshes)))}], 'nodes': [], 'meshes': [], 'accessors': [],
                'bufferViews': [], 'buffers': []}

    def add(data, kind, component, target):
        while len(binary) % 4:
            binary.append(0)
        view = {'buffer': 0, 'byteOffset': len(binary), 'byteLength': data.nbytes, 'target': target}
        binary.extend(data.tobytes())
        document['bufferViews'].append(view)
        item = {'bufferView': len(document['bufferViews']) - 1, 'componentType': component,
                'count': len(data) if data.ndim > 1 else data.size, 'type': kind}
        if kind == 'VEC3':
            item['min'] = data.min(0).tolist()
            item['max'] = data.max(0).tolist()
        document['accessors'].append(item)
        return len(document['accessors']) - 1

    for i, mesh in enumerate(meshes):
        attributes = {'POSITION': add(mesh['position'], 'VEC3', 5126, 34962),
                      'NORMAL': add(mesh['normal'], 'VEC3', 5126, 34962),
                      'TEXCOORD_0': add(mesh['uv'], 'VEC2', 5126, 34962)}
        indices = add(mesh['index'], 'SCALAR', 5123, 34963)
        document['meshes'].append({'name': mesh['name'], 'primitives': [{'attributes': attributes,
                                                                          'indices': indices}]})
        document['nodes'].append({'name': mesh['name'], 'mesh': i, 'extras': {
            'rock': mesh['rock'], 'lod': mesh['lod'], 'inner': round(float(mesh['inner']), 4)}})
    document['buffers'].append({'byteLength': len(binary)})
    text = json.dumps(document, separators=(',', ':')).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    binary += b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(text) + 8 + len(binary)
    return (struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(text), 0x4E4F534A) + text +
            struct.pack('<II', len(binary), 0x004E4942) + bytes(binary))


def build(source, only_textures=False):
    src = Source(source)
    out = textures(src)
    if not only_textures:
        out.update(rocks(src))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, help='scratch folder with the downloads (outside the repository)')
    parser.add_argument('--list', action='store_true', help='print the files to download and exit')
    parser.add_argument('--check', action='store_true', help='compare a fresh build with the committed files')
    parser.add_argument('--record', action='store_true', help='record the checksums of the current downloads')
    args = parser.parse_args()
    if args.list:
        for relative, url in source_files():
            print(f'{url}\n    -> <source>/{relative}')
        return 0
    if not args.source:
        parser.error('--source is required')
    source = args.source.resolve()
    if source.is_relative_to(OUT.parents[3]):
        parser.error('keep the downloads outside the repository')
    if args.record:
        record(source)
    verify(source)
    out = build(source)
    if args.check:
        # WebP and Blender's decimation are deterministic for the same versions; report differences only.
        changed = [name for name, data in out.items() if (OUT / name).read_bytes() != data]
        print('identical' if not changed else 'differs: ' + ', '.join(changed))
        return 1 if changed else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(out.items()):
        if len(data) > MAX_FILE_BYTES:
            raise SystemExit(f'{name} is {len(data)} bytes, above the {MAX_FILE_BYTES} byte budget')
        (OUT / name).write_bytes(data)
        print(f'{name:18s} {len(data) / 1024:7.1f} KiB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
