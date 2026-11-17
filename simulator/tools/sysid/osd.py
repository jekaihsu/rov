"""Read depth and heading from a confirmed OSD region.

The operator draws the boxes. This module only classifies separated light digits
on a dark field, using a built-in bitmap so the synthetic fixture needs no extra
font file. App typefaces that do not separate cleanly stay blank for a human to type.
"""
import struct
import zlib
from pathlib import Path

import numpy as np

STRINGS = {
    'confirm': 'OSD regions must be confirmed by a person before values are read.',
    'roi': 'OSD region is outside the frame or has no size.',
    'image': 'Could not read the OSD frame. Export PNG frames or install opencv/Pillow.',
    'empty': 'No OSD frames were listed.',
    'glyph': 'OSD text uses digits, a decimal point and a leading minus only.',
}

SCALE = 3
LINE_ROWS = 7
LINE_COLS = 5
# Each glyph is 5 columns by 7 rows, '1' = ink. The advance width is fixed so a
# fixed character count always occupies the same rectangle.
GLYPHS = {
    '0': ('11111', '10001', '10001', '10001', '10001', '10001', '11111'),
    '1': ('00100', '01100', '00100', '00100', '00100', '00100', '01110'),
    '2': ('11111', '00001', '00001', '11111', '10000', '10000', '11111'),
    '3': ('11111', '00001', '00001', '11111', '00001', '00001', '11111'),
    '4': ('10001', '10001', '10001', '11111', '00001', '00001', '00001'),
    '5': ('11111', '10000', '10000', '11111', '00001', '00001', '11111'),
    '6': ('11111', '10000', '10000', '11111', '10001', '10001', '11111'),
    '7': ('11111', '00001', '00001', '00010', '00100', '00100', '00100'),
    '8': ('11111', '10001', '10001', '11111', '10001', '10001', '11111'),
    '9': ('11111', '10001', '10001', '11111', '00001', '00001', '11111'),
    '.': ('00000', '00000', '00000', '00000', '00000', '01100', '01100'),
    '-': ('00000', '00000', '00000', '11111', '00000', '00000', '00000'),
}
TEMPLATES = {}


def write_png(path, rgb):
    """Write an 8-bit RGB PNG with filter 0. Stdlib only, no Pillow."""
    image = np.ascontiguousarray(rgb, dtype=np.uint8)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(STRINGS['image'])
    height, width, _ = image.shape

    def chunk(tag, payload):
        head = tag + payload
        return struct.pack('>I', len(payload)) + head + struct.pack('>I', zlib.crc32(head) & 0xffffffff)

    raw = b''.join(b'\x00' + image[y].tobytes() for y in range(height))
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9))
    data += chunk(b'IEND', b'')
    Path(path).write_bytes(data)


def read_png(path):
    """Read the PNGs this module writes. Other filters need opencv or Pillow."""
    data = Path(path).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(STRINGS['image'])
    pos = 8
    width = height = None
    compressed = []
    while pos + 8 <= len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        tag = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+length]
        pos += 12 + length
        if tag == b'IHDR':
            width, height, bit, color, *_rest = struct.unpack('>IIBBBBB', payload)
            if bit != 8 or color != 2:
                raise ValueError(STRINGS['image'])
        elif tag == b'IDAT':
            compressed.append(payload)
        elif tag == b'IEND':
            break
    raw = zlib.decompress(b''.join(compressed))
    stride = width * 3
    rows = []
    cursor = 0
    for _ in range(height):
        if raw[cursor] != 0:
            raise ValueError(STRINGS['image'])
        cursor += 1
        rows.append(raw[cursor:cursor+stride])
        cursor += stride
    return np.frombuffer(b''.join(rows), dtype=np.uint8).reshape((height, width, 3)).copy()


def load_image(path):
    """Load RGB. opencv and Pillow cover operator screenshots; PNG fallback covers fixtures."""
    try:
        import cv2
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is not None:
            return image[:, :, ::-1].copy()
    except ImportError:
        pass
    try:
        from PIL import Image
        return np.asarray(Image.open(path).convert('RGB'))
    except ImportError:
        pass
    return read_png(path)


def raster_text(text, scale=SCALE):
    """Return a boolean ink image for text. Every glyph has the same advance."""
    if any(ch not in GLYPHS for ch in text):
        raise ValueError(STRINGS['glyph'])
    gap = scale
    advance = LINE_COLS * scale
    width = len(text) * advance + (len(text) - 1) * gap
    height = LINE_ROWS * scale
    ink = np.zeros((height, width), dtype=bool)
    x = 0
    for index, ch in enumerate(text):
        glyph = GLYPHS[ch]
        for col in range(LINE_COLS):
            for row in range(LINE_ROWS):
                if glyph[row][col] == '1':
                    y0 = row * scale
                    x0 = x + col * scale
                    ink[y0:y0+scale, x0:x0+scale] = True
        x += advance
        if index != len(text) - 1:
            x += gap
    return ink


def paint_readout(depth_text, heading_text, scale=SCALE):
    """Paint two readouts on black and return the image plus tight boxes around each."""
    depth = raster_text(depth_text, scale)
    heading = raster_text(heading_text, scale)
    margin = 4
    gap = 28
    height = depth.shape[0] + margin * 2
    width = margin + depth.shape[1] + gap + heading.shape[1] + margin
    image = np.zeros((height, width, 3), dtype=np.uint8)
    y = margin
    x = margin
    image[y:y+depth.shape[0], x:x+depth.shape[1]] = depth[:, :, None] * 255
    depth_box = {'x': x, 'y': y, 'width': int(depth.shape[1]), 'height': int(depth.shape[0])}
    x2 = x + depth.shape[1] + gap
    image[y:y+heading.shape[0], x2:x2+heading.shape[1]] = heading[:, :, None] * 255
    heading_box = {'x': x2, 'y': y, 'width': int(heading.shape[1]), 'height': int(heading.shape[0])}
    return image, depth_box, heading_box


def _templates():
    if TEMPLATES:
        return TEMPLATES
    for ch, glyph in GLYPHS.items():
        if ch == '.':
            continue
        if ch == '-':
            continue
        ink = raster_text(ch, SCALE)
        ys = np.where(ink.any(axis=1))[0]
        xs = np.where(ink.any(axis=0))[0]
        TEMPLATES[ch] = _resample(ink[ys[0]:ys[-1]+1, xs[0]:xs[-1]+1])
    return TEMPLATES


def _resample(ink):
    """Block-average a glyph to the 5 by 7 template grid."""
    height, width = ink.shape
    out = np.zeros((LINE_ROWS, LINE_COLS), dtype=bool)
    for row in range(LINE_ROWS):
        y0 = int(row * height / LINE_ROWS)
        y1 = int((row + 1) * height / LINE_ROWS)
        for col in range(LINE_COLS):
            x0 = int(col * width / LINE_COLS)
            x1 = int((col + 1) * width / LINE_COLS)
            block = ink[y0:y1, x0:x1]
            if block.size and block.mean() >= 0.35:
                out[row, col] = True
    return out


def _ink_mask(rgb):
    gray = rgb.astype(float).mean(axis=2)
    # Light digits on a dark plate. A bright plate is inverted once.
    if float(np.median(gray)) > 140:
        gray = 255 - gray
    return gray >= max(80.0, float(np.percentile(gray, 90)) * 0.55)


def _groups(mask):
    columns = mask.any(axis=0)
    groups = []
    start = None
    for index, flag in enumerate(columns):
        if flag and start is None:
            start = index
        if not flag and start is not None:
            groups.append((start, index))
            start = None
    if start is not None:
        groups.append((start, columns.size))
    return groups


def read_text(rgb):
    """Return (text, confidence) for one cropped readout. Blank when the ink is ambiguous."""
    if rgb.size == 0:
        return '', 0.0
    mask = _ink_mask(rgb)
    rows = np.where(mask.any(axis=1))[0]
    if rows.size == 0:
        return '', 0.0
    line_height = int(rows[-1] - rows[0] + 1)
    characters = []
    scores = []
    templates = _templates()
    for x0, x1 in _groups(mask):
        piece = mask[:, x0:x1]
        ys = np.where(piece.any(axis=1))[0]
        ink_height = int(ys[-1] - ys[0] + 1)
        width = x1 - x0
        if ink_height < 0.55 * line_height:
            if width >= 0.6 * line_height:
                characters.append('-')
                scores.append(1.0)
            else:
                characters.append('.')
                scores.append(1.0)
            continue
        sample = _resample(piece[ys[0]:ys[-1]+1, :])
        best_ch = ''
        best_score = -1.0
        second = -1.0
        for ch, template in templates.items():
            score = float(np.mean(sample == template))
            if score > best_score:
                second = best_score
                best_score = score
                best_ch = ch
            elif score > second:
                second = score
        # A perfect bitmap match is unique even when two glyphs share most pixels.
        if best_score < 0.85:
            return '', 0.0
        if best_score < 0.98 and best_score - second < 0.08:
            return '', 0.0
        characters.append(best_ch)
        scores.append(best_score)
    if not characters:
        return '', 0.0
    text = ''.join(characters)
    if text.count('-') > 1 or (text.startswith('-') is False and '-' in text):
        return '', 0.0
    if text.count('.') > 1:
        return '', 0.0
    return text, float(min(scores))


def _crop(image, box):
    height, width = image.shape[:2]
    try:
        x = int(box['x'])
        y = int(box['y'])
        box_w = int(box['width'])
        box_h = int(box['height'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(STRINGS['roi']) from exc
    if box_w <= 0 or box_h <= 0 or x < 0 or y < 0 or x + box_w > width or y + box_h > height:
        raise ValueError(STRINGS['roi'])
    return image[y:y+box_h, x:x+box_w]


def read_frame(image, roi):
    """Read one frame. roi must already have been confirmed by a person."""
    if roi.get('confirmed') is not True:
        raise ValueError(STRINGS['confirm'])
    reading = {}
    for name in ('depth', 'heading'):
        box = roi.get(name)
        if not box:
            reading[name+'_text'] = ''
            reading[name+'_confidence'] = 0.0
            reading[name+'_value'] = None
            continue
        text, confidence = read_text(_crop(image, box))
        value = None
        if text not in ('', '-', '.', '-.'):
            try:
                value = float(text)
            except ValueError:
                text = ''
                confidence = 0.0
        reading[name+'_text'] = text
        reading[name+'_confidence'] = confidence
        reading[name+'_value'] = value
    return reading


def require_roi(payload):
    if not isinstance(payload, dict) or payload.get('confirmed') is not True:
        raise ValueError(STRINGS['confirm'])
    return payload
