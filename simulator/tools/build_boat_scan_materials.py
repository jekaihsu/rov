"""Build CC0 boat materials and props into simulator/viewer/models/boat/.

Sources (all CC0 1.0; see viewer/models/CREDITS.md): Poly Haven wood_floor_deck, lifebuoy, ocean_buoy;
ambientCG Plastic010 (gelcoat-like paint) and DiamondPlate008C (non-slip plate). Rust and coated steel
reuse the existing scan/ maps from build_scan_materials.py.

  python simulator/tools/build_boat_scan_materials.py --list
  python simulator/tools/build_boat_scan_materials.py --source <scratch>
  python simulator/tools/build_boat_scan_materials.py --source <scratch> --record

Poly Haven asks not to scrape: download the listed files by hand into the scratch folder. Lifebuoy diffuse
stencils ("Lifebuoy" / "PH-…" style marks) are scrubbed before packaging so the game does not ship baked Latin
markings. Blender is required only for packing the prop GLBs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'simulator/viewer/models/boat'
SCAN = ROOT / 'simulator/viewer/models/scan'
CHECKSUMS = Path(__file__).with_name('boat_scan_sources.json')
PH = 'https://dl.polyhaven.org/file/ph-assets'
ACG = 'https://ambientcg.com/get?file='
SIZE = 1024
NORMAL_Q = 70
MAX_PROP_BYTES = 2 * 1024 * 1024
BLENDER = os.environ.get('BLENDER') or shutil.which('blender') or str(Path.home() / 'blender/blender')


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def source_files():
    files = [
        ('wood_floor_deck/wood_floor_deck_diff_1k.jpg',
         f'{PH}/Textures/jpg/1k/wood_floor_deck/wood_floor_deck_diff_1k.jpg'),
        ('wood_floor_deck/wood_floor_deck_nor_gl_1k.jpg',
         f'{PH}/Textures/jpg/1k/wood_floor_deck/wood_floor_deck_nor_gl_1k.jpg'),
        ('wood_floor_deck/wood_floor_deck_rough_1k.jpg',
         f'{PH}/Textures/jpg/1k/wood_floor_deck/wood_floor_deck_rough_1k.jpg'),
        ('acg_Plastic010/Plastic010.zip', f'{ACG}Plastic010_1K-JPG.zip'),
        ('acg_DiamondPlate008C/DiamondPlate008C.zip', f'{ACG}DiamondPlate008C_1K-JPG.zip'),
        ('lifebuoy/lifebuoy_1k.gltf', f'{PH}/Models/gltf/1k/lifebuoy/lifebuoy_1k.gltf'),
        ('lifebuoy/lifebuoy.bin', f'{PH}/Models/gltf/8k/lifebuoy/lifebuoy.bin'),
        ('lifebuoy/textures/lifebuoy_diff_1k.jpg', f'{PH}/Models/jpg/1k/lifebuoy/lifebuoy_diff_1k.jpg'),
        ('lifebuoy/textures/lifebuoy_nor_gl_1k.jpg', f'{PH}/Models/jpg/1k/lifebuoy/lifebuoy_nor_gl_1k.jpg'),
        ('lifebuoy/textures/lifebuoy_arm_1k.jpg', f'{PH}/Models/jpg/1k/lifebuoy/lifebuoy_arm_1k.jpg'),
        ('ocean_buoy/ocean_buoy_1k.gltf', f'{PH}/Models/gltf/1k/ocean_buoy/ocean_buoy_1k.gltf'),
        ('ocean_buoy/ocean_buoy.bin', f'{PH}/Models/gltf/8k/ocean_buoy/ocean_buoy.bin'),
        ('ocean_buoy/textures/ocean_buoy_diff_1k.jpg', f'{PH}/Models/jpg/1k/ocean_buoy/ocean_buoy_diff_1k.jpg'),
        ('ocean_buoy/textures/ocean_buoy_nor_gl_1k.jpg', f'{PH}/Models/jpg/1k/ocean_buoy/ocean_buoy_nor_gl_1k.jpg'),
        ('ocean_buoy/textures/ocean_buoy_arm_1k.jpg', f'{PH}/Models/jpg/1k/ocean_buoy/ocean_buoy_arm_1k.jpg'),
        ('ocean_buoy/textures/ocean_buoy_emission_1k.jpg',
         f'{PH}/Models/jpg/1k/ocean_buoy/ocean_buoy_emission_1k.jpg'),
    ]
    return files


def verify(source):
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
        raise SystemExit('Source files do not match boat_scan_sources.json:\n  ' + '\n  '.join(bad))


def record(source):
    sums = {relative: hashlib.sha256((source / relative).read_bytes()).hexdigest()
            for relative, _ in source_files()}
    CHECKSUMS.write_text(json.dumps(sums, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def array(image, size=SIZE):
    if image.size != (size, size):
        image = image.resize((size, size), Image.LANCZOS)
    return np.asarray(image).astype(np.float64) / 255


def normal_array(image, size=SIZE):
    n = array(image, size)[..., :3] * 2 - 1
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8
    return n


def pack(rgb, alpha=None):
    data = np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)
    if alpha is None:
        return Image.fromarray(data, 'RGB')
    a = np.clip(np.round(alpha * 255), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([data, a]), 'RGBA')


def webp(image, quality, alpha_quality=35):
    buffer = io.BytesIO()
    image.save(buffer, 'WEBP', quality=quality, method=6, alpha_quality=alpha_quality)
    return buffer.getvalue()


def normal_rgb(n):
    return np.clip(n * 0.5 + 0.5, 0, 1)


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


def scrub_lifebuoy_diffuse(image):
    """Remove pale Latin stencils from the lifebuoy albedo while keeping white reflective tape."""
    arr = np.asarray(image.convert('RGB')).astype(np.float32)
    boxes = [(640, 640, 1000, 1000), (640, 200, 1000, 520), (200, 560, 560, 780),
             (40, 200, 400, 520), (480, 40, 700, 200)]
    for x0, y0, x1, y1 in boxes:
        patch = arr[y0:y1, x0:x1]
        r, g, b = patch[..., 0], patch[..., 1], patch[..., 2]
        tape = ((r + g + b) / 3 > 150) & (np.abs(r - g) < 35) & (np.abs(g - b) < 35) & (np.abs(r - b) < 45)
        red = (r > 90) & (r > g + 8) & (r > b + 8) & ~tape
        lum = 0.3 * r + 0.5 * g + 0.2 * b
        med = float(np.median(lum[red])) if red.any() else float(np.median(lum))
        base = np.where(red, lum, med)
        local = np.asarray(Image.fromarray(base.astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))).astype(np.float32)
        glyphs = red & (lum > local + 18) & ((g + b) / 2 > 90)
        glyphs = np.asarray(Image.fromarray((glyphs.astype(np.uint8) * 255)).filter(ImageFilter.MaxFilter(5))) > 0
        glyphs &= ~tape
        out = patch.copy()
        src = patch.copy()
        ys, xs = np.where(glyphs)
        for y, x in zip(ys, xs):
            y0b, y1b = max(0, y - 10), min(patch.shape[0], y + 11)
            x0b, x1b = max(0, x - 10), min(patch.shape[1], x + 11)
            win = src[y0b:y1b, x0b:x1b]
            keep = ~glyphs[y0b:y1b, x0b:x1b] & ~tape[y0b:y1b, x0b:x1b]
            samp = win[keep]
            if len(samp):
                out[y, x] = np.median(samp, axis=0)
        blur = np.asarray(Image.fromarray(out.astype('uint8')).filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32)
        mix = glyphs[..., None].astype(np.float32)
        arr[y0:y1, x0:x1] = out * (1 - mix) + blur * mix
    return Image.fromarray(arr.astype(np.uint8))


def whitened_paint(rgb):
    """Plastic010 as a pale gelcoat: shift mean toward white while keeping micro-variation."""
    linear = srgb_to_linear(rgb)
    mean = linear.mean(-1, keepdims=True)
    lifted = np.clip(linear + (0.78 - mean) * 0.55, 0, 1)
    return linear_to_srgb(lifted)


def write_textures(src):
    OUT.mkdir(parents=True, exist_ok=True)
    teak_c = array(src.image('wood_floor_deck/wood_floor_deck_diff_1k.jpg'))
    teak_n = normal_array(src.image('wood_floor_deck/wood_floor_deck_nor_gl_1k.jpg'))
    teak_r = array(src.image('wood_floor_deck/wood_floor_deck_rough_1k.jpg', 'L'))
    (OUT / 'teak_c.webp').write_bytes(webp(pack(teak_c), 82))
    (OUT / 'teak_n.webp').write_bytes(webp(pack(normal_rgb(teak_n), teak_r), NORMAL_Q))

    paint_c = whitened_paint(array(src.acg('Plastic010', 'Color')))
    paint_n = normal_array(src.acg('Plastic010', 'NormalGL'))
    paint_r = array(src.acg('Plastic010', 'Roughness', 'L'))
    (OUT / 'paint_c.webp').write_bytes(webp(pack(paint_c), 82))
    (OUT / 'paint_n.webp').write_bytes(webp(pack(normal_rgb(paint_n), paint_r), NORMAL_Q))

    plate_c = array(src.acg('DiamondPlate008C', 'Color'))
    plate_n = normal_array(src.acg('DiamondPlate008C', 'NormalGL'))
    plate_r = array(src.acg('DiamondPlate008C', 'Roughness', 'L'))
    (OUT / 'plate_c.webp').write_bytes(webp(pack(plate_c), 80))
    (OUT / 'plate_n.webp').write_bytes(webp(pack(normal_rgb(plate_n), plate_r), NORMAL_Q))

    # Rust maps are already in scan/; copy for a self-contained boat rebuild path.
    for name in ('rust_c.webp', 'rust_n.webp', 'coating_c.webp', 'coating_n.webp'):
        shutil.copy2(SCAN / name, OUT / name)


def pack_prop(source_dir, gltf_name, out_name, node_name):
    sys.path.insert(0, str(ROOT / 'simulator'))
    from tools.build_support_assets import compress, glb_report

    work = Path(tempfile.mkdtemp(prefix=f'boat-{out_name}-'))
    raw = work / f'{out_name}_raw.glb'
    # Point the glTF at a cleaned diffuse when present.
    staging = work / 'src'
    shutil.copytree(source_dir, staging)
    clean = staging / 'textures' / f'{node_name}_diff_clean.jpg'
    target = staging / 'textures' / f'{node_name}_diff_1k.jpg'
    if clean.is_file():
        shutil.copy2(clean, target)
    gltf = staging / gltf_name
    script = work / 'pack.py'
    script.write_text(
        'import bpy\nfrom pathlib import Path\n'
        f'source, out, name = Path({str(gltf)!r}), Path({str(raw)!r}), {node_name!r}\n'
        'bpy.ops.wm.read_factory_settings(use_empty=True)\n'
        'bpy.ops.import_scene.gltf(filepath=str(source))\n'
        'root = bpy.data.objects.new(name, None)\n'
        'bpy.context.scene.collection.objects.link(root)\n'
        'for obj in list(bpy.context.scene.objects):\n'
        '    if obj != root and obj.parent is None:\n'
        '        obj.parent = root\n'
        "bpy.ops.export_scene.gltf(filepath=str(out), export_format='GLB', export_yup=True, export_apply=True)\n"
        "print('exported', out)\n",
        encoding='utf-8',
    )
    subprocess.run([BLENDER, '-b', '--python', str(script)], check=True)
    out = OUT / f'{out_name}.glb'
    # Downscale embedded maps to 512 so props stay inside the 2 MB file budget.
    compress(raw, out, (('*', 512),))
    report = glb_report(out)
    print(f"{out.name}: {report['triangles']} tris, {report['bytes']/1e6:.2f} MB, "
          f"GPU ~{report['gpu_bytes']/1024/1024:.1f} MiB")
    if report['bytes'] > MAX_PROP_BYTES:
        raise SystemExit(f'{out.name} exceeds {MAX_PROP_BYTES} bytes')
    return report


def build_props(source):
    scrubbed = scrub_lifebuoy_diffuse(Image.open(source / 'lifebuoy/textures/lifebuoy_diff_1k.jpg'))
    clean_path = source / 'lifebuoy/textures/lifebuoy_diff_clean.jpg'
    scrubbed.save(clean_path, quality=92)
    pack_prop(source / 'lifebuoy', 'lifebuoy_1k.gltf', 'lifebuoy', 'lifebuoy')
    pack_prop(source / 'ocean_buoy', 'ocean_buoy_1k.gltf', 'ocean_buoy', 'ocean_buoy')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--source', type=Path, help='scratch folder with the listed downloads')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--record', action='store_true', help='rewrite boat_scan_sources.json checksums')
    parser.add_argument('--textures-only', action='store_true')
    parser.add_argument('--props-only', action='store_true')
    args = parser.parse_args()
    if args.list:
        for relative, url in source_files():
            print(f'{relative}\n  {url}')
        return
    if not args.source:
        raise SystemExit('--source is required (or use --list)')
    source = args.source.resolve()
    if args.record:
        record(source)
        print('Wrote', CHECKSUMS)
        return
    verify(source)
    src = Source(source)
    if not args.props_only:
        write_textures(src)
        print('Wrote textures to', OUT)
    if not args.textures_only:
        if not Path(BLENDER).is_file():
            raise SystemExit(f'Blender not found at {BLENDER}')
        build_props(source)
        print('Wrote props to', OUT)


if __name__ == '__main__':
    main()
