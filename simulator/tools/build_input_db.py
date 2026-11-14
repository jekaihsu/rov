"""Convert SDL_GameControllerDB Linux axis/button records to browser vendor/product lookup.

Usage: python3 tools/build_input_db.py /path/to/gamecontrollerdb.txt
Input source: https://github.com/mdqinc/SDL_GameControllerDB (zlib).
"""
import json
import re
import sys
from pathlib import Path

records = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    parts = line.split(',')
    if len(parts) < 3 or len(parts[0]) != 32:
        continue
    fields = dict(p.split(':', 1) for p in parts[2:] if ':' in p)
    if fields.get('platform') != 'Linux':
        continue
    guid = parts[0]
    key = f'{guid[10:12]}{guid[8:10]}:{guid[18:20]}{guid[16:18]}'
    axes = [fields.get(k, '') for k in ('leftx', 'lefty', 'rightx', 'righty')]
    buttons = [fields.get(k, '') for k in ('a', 'b', 'x', 'y', 'leftshoulder', 'rightshoulder',
        'lefttrigger', 'righttrigger', 'back', 'start', 'leftstick', 'rightstick',
        'dpup', 'dpdown', 'dpleft', 'dpright', 'guide')]
    if all(re.fullmatch(r'-?a\d+', x) for x in axes):
        records[key] = {'axes': axes, 'buttons': buttons}
output = Path(__file__).resolve().parents[1] / 'viewer/input/controller-db.json'
output.write_text(json.dumps(records, separators=(',', ':')) + '\n')
print(f'{len(records)} mappings -> {output}')
