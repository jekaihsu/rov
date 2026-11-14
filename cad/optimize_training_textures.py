"""Losslessly repack exported PNGs; assert identical decoded RGB(A) pixels before accepting output."""
import io
import json
from pathlib import Path
import struct
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for model in ('falcon', 'bluerov2_heavy'):
    data = (ROOT / '.runtime/a3' / (model + '-materials.glb')).read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    document = json.loads(data[20:20 + length])
    binary_offset = 20 + length + 8
    out = ROOT / '.runtime/a3/optimized' / model
    out.mkdir(parents=True, exist_ok=True)
    for item in document.get('images', []):
        if item['mimeType'] != 'image/png':
            continue
        view = document['bufferViews'][item['bufferView']]
        start = binary_offset + view.get('byteOffset', 0)
        image = Image.open(io.BytesIO(data[start:start + view['byteLength']])).convert('RGB')
        # All model data maps are opaque RGB. Reject accidental alpha loss.
        original = Image.open(io.BytesIO(data[start:start + view['byteLength']])).convert('RGBA')
        assert original.getchannel('A').getextrema() == (255, 255)
        optimized = image.quantize(colors=256) if image.getcolors(256) is not None else image
        path = out / (item['name'] + '.png')
        optimized.save(path, optimize=True)
        assert Image.open(path).convert('RGB').tobytes() == image.tobytes()
        print(model, item['name'], view['byteLength'], '->', path.stat().st_size)
