"""Update a workspace desktop backend without touching its viewer or running app.

Files are replaced atomically. A locked executable stops the update before any
other file changes; the separately built source remains available for later use.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
source, destination = args.source.resolve(), args.destination.resolve()
for location in (source, destination):
    if not location.is_relative_to(ROOT) or location == ROOT:
        raise ValueError('Backend paths must be inside this workspace')
if source == destination:
    raise ValueError('Source and destination must differ')
if not (source / 'rov-sim.exe').is_file():
    raise FileNotFoundError(source / 'rov-sim.exe')


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


files = sorted((file for file in source.rglob('*') if file.is_file()),
               key=lambda file: (file.name != 'rov-sim.exe', str(file)))
updated = []
for file in files:
    relative = file.relative_to(source)
    if relative.parts[:2] == ('_internal', 'viewer'):
        continue
    target = destination / relative
    if target.is_file() and target.stat().st_size == file.stat().st_size and digest(target) == digest(file):
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_name(target.name + '.pending-update')
    try:
        shutil.copy2(file, pending)
        os.replace(pending, target)
    finally:
        if pending.exists():
            pending.unlink()
    updated.append(str(relative))
print(json.dumps({'destination': str(destination), 'updated': updated, 'viewer_preserved': True}))
