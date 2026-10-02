"""PyInstaller entry; keep server modules imported by their package names."""
import os
from pathlib import Path

# The portable application may be installed in a read-only directory.
default_cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ROV Simulator" / "numba-cache"
cache = Path(os.environ.get("NUMBA_CACHE_DIR", str(default_cache)))
cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(cache))
from qysim.server import main

if __name__ == '__main__':
    main()
