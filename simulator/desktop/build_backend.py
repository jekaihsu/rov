"""Build the portable backend using this interpreter's clean dependencies.

Run with the dedicated packaging virtual environment, not a global scientific
Python environment. No optional camera SDK, scientific plotting or IDE packages
are needed by the game server.
"""
import os
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
edition = os.environ.get('ROV_BUILD_EDITION', 'internal')
if edition not in ('internal', 'steam'):
    parser.error('ROV_BUILD_EDITION must be internal or steam')
if edition == 'steam':
    # Packaging settings are applied (no instructor UI). Remaining brand/content blockers:
    # see desktop/steam/RELEASE.md — do not upload until the content manifest is reviewed.
    print('ROV_BUILD_EDITION=steam: packaging Steam viewer without instructor UI', flush=True)

distpath = options.distpath.resolve()

# Steam and internal packages both omit the instructor console from the frozen viewer.
packaged_viewer = PROJECT / '.runtime' / 'steam-viewer'
if not options.licenses_only:
    shutil.rmtree(packaged_viewer, ignore_errors=True)
    shutil.copytree(SIM / 'viewer', packaged_viewer, ignore=shutil.ignore_patterns('instructor'))

args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--name', 'rov-sim', '--onedir', '--console',
        # Frozen builds ignore PYTHONUTF8; force UTF-8 mode so no file read depends on the Windows code page.
        '--python-option', 'X utf8',
        '--distpath', str(distpath),
        '--workpath', str(PROJECT / '.runtime' / 'pyinstaller-build'),
        '--specpath', str(PROJECT / '.runtime'),
        '--paths', str(SIM),
        '--add-data', f'{packaged_viewer}:viewer',
        '--add-data', f'{SIM / "campaign"}:campaign',
        '--add-data', f'{SIM / "qysim" / "assets"}:qysim/assets',
        '--add-data', f'{SIM / "qysim" / "_cable_accel.py"}:qysim',
        '--collect-all', 'numba', '--collect-all', 'llvmlite',
        '--collect-all', 'jsonschema_specifications',
        '--hidden-import', 'websockets.legacy',
        '--hidden-import', 'websockets.asyncio.server']
for excluded in ('scipy', 'matplotlib', 'pandas', 'cv2', 'IPython', 'jupyter',
                 'pytest', 'tkinter', 'PyQt5', 'PyQt6', 'PIL', 'sympy'):
    args.extend(['--exclude-module', excluded])
args.append(str(DESKTOP / 'backend_entry.py'))
if not options.licenses_only:
    subprocess.run(args, cwd=PROJECT, check=True)

licenses=distpath/'rov-sim'/'licenses'
licenses.mkdir(exist_ok=True)
versions={}
for package in ('numpy','numba','llvmlite','websockets','pyinstaller','jsonschema',
                'jsonschema-specifications','referencing','rpds-py','attrs'):
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
notices = DESKTOP / 'THIRD_PARTY_NOTICES.txt'
if notices.is_file():
    shutil.copy2(notices, licenses / 'THIRD_PARTY_NOTICES.txt')
