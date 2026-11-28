"""Compose a PNG sequence into a video with ffmpeg (H.264 or lossless)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def find_ffmpeg(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    found = shutil.which('ffmpeg')
    if not found:
        raise RuntimeError('ffmpeg not found on PATH; install it or pass --ffmpeg')
    return found


def encode_sequence(
    frames_dir: Path,
    out_path: Path,
    *,
    fps: int = 60,
    lossless: bool = False,
    ffmpeg: str | None = None,
) -> Path:
    """Encode frame_XXXXXX.png under frames_dir into out_path."""
    pattern = frames_dir / 'frame_%06d.png'
    if not any(frames_dir.glob('frame_*.png')):
        raise FileNotFoundError(f'no PNG frames in {frames_dir}')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    binary = find_ffmpeg(ffmpeg)
    if lossless:
        # utvideo or ffv1 keep every pixel; H.264 CRF 0 is near-lossless and more portable.
        command = [
            binary, '-y', '-loglevel', 'error',
            '-framerate', str(fps),
            '-i', str(pattern),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '0', '-pix_fmt', 'yuv444p',
            str(out_path),
        ]
    else:
        command = [
            binary, '-y', '-loglevel', 'error',
            '-framerate', str(fps),
            '-i', str(pattern),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            str(out_path),
        ]
    subprocess.run(command, check=True)
    return out_path
