"""Build the portable backend using this interpreter's clean dependencies.

Run with the dedicated packaging virtual environment, not a global scientific
Python environment. No optional camera SDK, scientific plotting or IDE packages
are needed by the game server.
"""
import subprocess
import sys
import json
import shutil
import argparse
from importlib import metadata
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent
SIM = DESKTOP.parent
PROJECT = SIM.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--distpath', type=Path, default=DESKTOP / 'backend')
parser.add_argument('--licenses-only', action='store_true')
options = parser.parse_args()
distpath = options.distpath.resolve()

args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--name', 'rov-sim', '--onedir', '--console',
        '--distpath', str(distpath),
        '--workpath', str(PROJECT / '.runtime' / 'pyinstaller-build'),
        '--specpath', str(PROJECT / '.runtime'),
        '--paths', str(SIM),
        '--add-data', f'{SIM / "viewer"}:viewer',
        '--add-data', f'{SIM / "qysim" / "assets"}:qysim/assets',
        '--add-data', f'{SIM / "qysim" / "_cable_accel.py"}:qysim',
        '--collect-all', 'numba', '--collect-all', 'llvmlite',
        '--hidden-import', 'websockets.legacy',
        '--hidden-import', 'websockets.asyncio.server']
for excluded in ('scipy', 'matplotlib', 'pandas', 'cv2', 'IPython', 'jupyter',
                 'pytest', 'tkinter', 'PyQt5', 'PyQt6', 'PIL', 'sympy'):
    args.extend(['--exclude-module', excluded])
args.append(str(SIM / 'tools' / 'desktop_entry.py'))
if not options.licenses_only:
    subprocess.run(args, cwd=PROJECT, check=True)

licenses=distpath/'rov-sim'/'licenses'
licenses.mkdir(exist_ok=True)
versions={}
for package in ('numpy','numba','llvmlite','websockets','pyinstaller'):
    distribution=metadata.distribution(package)
    versions[package]=distribution.version
    for file in distribution.files or []:
        if any(word in file.name.upper() for word in ('LICENSE','COPYING','NOTICE')):
            source=distribution.locate_file(file)
            if source.is_file():
                shutil.copy2(source,licenses/f'{package}-{file.name}')
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():
    shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
(licenses/'versions.json').write_text(json.dumps(versions,indent=2),encoding='utf8')
