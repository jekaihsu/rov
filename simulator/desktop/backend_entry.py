"""Frozen desktop entry: use UTF-8 logs even when Windows defaults to cp1252."""
import os
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='backslashreplace')

default_cache = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ROV Simulator' / 'numba-cache'
cache = Path(os.environ.get('NUMBA_CACHE_DIR', str(default_cache)))
cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('NUMBA_CACHE_DIR', str(cache))

from qysim.server import main

if __name__ == '__main__':
    main()
