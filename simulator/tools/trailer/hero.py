"""Compress a representative trailer frame to JPEG ≤ 300 KB for docs/design/trailer/."""

from __future__ import annotations

import io
from pathlib import Path

LIMIT = 300_000


def write_hero_jpeg(source: Path, dest: Path, *, limit: int = LIMIT, max_edge: int = 1920) -> Path:
    """Write a progressive JPEG of source into dest, shrinking quality until size ≤ limit."""
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError('Pillow is required to write hero frames') from error

    image = Image.open(source).convert('RGB')
    width, height = image.size
    if max(width, height) > max_edge:
        scale = max_edge / float(max(width, height))
        image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)

    dest.parent.mkdir(parents=True, exist_ok=True)
    for quality in (85, 78, 70, 62, 54, 46, 38, 30):
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True, progressive=True)
        if buffer.tell() <= limit:
            dest.write_bytes(buffer.getvalue())
            return dest
    # Last resort: shrink dimensions.
    for scale in (0.85, 0.7, 0.55, 0.4):
        resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                               Image.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format='JPEG', quality=40, optimize=True, progressive=True)
        if buffer.tell() <= limit:
            dest.write_bytes(buffer.getvalue())
            return dest
    dest.write_bytes(buffer.getvalue())
    return dest
