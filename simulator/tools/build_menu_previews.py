"""Export the reproducible data the offline launch menu reads before any connection exists.

Writes two files into simulator/viewer:
  scene_previews.json   one world description per catalogue scenario (the live 3D background and site cards)
  menu_catalogue.json   vehicle specs and campaign chapters (hangar, story and incident lists)

X1 entries are marked provisional because vehicles.py holds no measured X1 value yet
(see docs/reference/x1-measurement-checklist.md). Run again whenever scenarios, vehicles or chapters change.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qysim.campaign import CHAPTER_FIELDS, Campaign  # noqa: E402
from qysim.engine import Simulator  # noqa: E402
from qysim.scenarios import catalogue  # noqa: E402
from qysim.server import _json_default  # noqa: E402
from qysim.vehicles import VEHICLE_DEFINITIONS, X1_PARAMETERS  # noqa: E402

VIEWER = ROOT / 'viewer'


def write(name, value):
    text = json.dumps(value, default=_json_default, ensure_ascii=False, separators=(',', ':'))
    (VIEWER / name).write_text(text, encoding='utf8')


def scene_previews():
    scenes = []
    for item in catalogue():
        sim = Simulator(item['key'], 42)
        scenes.append({**item, 'world': sim.world_description()})
    return scenes


def provisional_keys(model_id):
    """Parameter names whose value is not a measurement of this vehicle."""
    if model_id != 'x1':
        return []
    return sorted(key for key, item in X1_PARAMETERS.items() if item['level'] != 'measured')


def vehicle_entry(definition):
    public = definition.public()
    sim = Simulator('open_water', 42, model_id=definition.id)
    params = public['params']
    return {
        'id': definition.id,
        'name': definition.name,
        'mass': params.get('mass'),
        'vmax': params.get('vmax'),
        'wmax': params.get('wmax'),
        'thruster_max': params.get('thruster_max'),
        'thrusters': len(public['thrusters']),
        'capabilities': list(public['capabilities']),
        'arm': bool(sim.operations.has_arm),
        'estimated': public.get('estimated', True),
        'provisional': provisional_keys(definition.id),
    }


def chapter_entries():
    campaign = Campaign(None)
    chapters = []
    for script in campaign.ordered_scripts():
        entry = {field: script.get(field) for field in CHAPTER_FIELDS}
        entry['scenario'] = script['scenario']
        entry['mode'] = script['mode']
        chapters.append(entry)
    return chapters


def main():
    scenes = scene_previews()
    write('scene_previews.json', scenes)
    catalogue_data = {
        'vehicles': [vehicle_entry(definition) for definition in VEHICLE_DEFINITIONS.values()],
        'chapters': chapter_entries(),
    }
    write('menu_catalogue.json', catalogue_data)
    print('Exported', len(scenes), 'menu scene previews,', len(catalogue_data['vehicles']), 'vehicles and',
          len(catalogue_data['chapters']), 'chapters')


if __name__ == '__main__':
    main()
