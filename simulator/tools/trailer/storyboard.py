"""Parse and validate trailer storyboard JSON (shots, camera, drive, HUD, weather)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catmull import MODES

KNOWN_SCENARIOS = frozenset({
    'tutorial_pool', 'sonar_search', 'open_water', 'jacket_inspection', 'monopile_current',
    'tether_untangle', 'hull_inspection', 'wreck_survey', 'korean_castle', 'coral_reef',
    'seagrass_meadow', 'harbor_inspection', 'aquaculture_pen', 'aquaculture_pen_slack',
    'aquaculture_pen_inside', 'cold_open_jacket',
    'incident_jacket', 'incident_wreck', 'incident_silt', 'incident_compass', 'incident_current',
})

DRIVE_AXES = ('surge', 'sway', 'heave', 'yaw', 'pitch', 'roll')

# Flight instruments a shot may keep; tools / title cards / target aids stay hidden in trailer mode.
HUD_PARTS = ('depth', 'heading', 'attitude', 'map', 'status', 'mission', 'telemetry', 'warning')
HUD_FULL = list(HUD_PARTS)
HUD_MINIMAL = ['depth', 'heading']


def load_storyboard(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding='utf-8')
    data = json.loads(raw)
    return validate_storyboard(data, source=str(path))


def validate_storyboard(data: dict[str, Any], source: str = '<memory>') -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f'{source}: storyboard must be an object')
    if data.get('format') not in (None, 'rov-trailer-1'):
        raise ValueError(f'{source}: unsupported format {data.get("format")!r}')
    shots = data.get('shots')
    if not isinstance(shots, list) or not shots:
        raise ValueError(f'{source}: shots must be a non-empty list')
    ids = set()
    validated = []
    for index, shot in enumerate(shots):
        item = validate_shot(shot, source=f'{source} shot[{index}]')
        if item['id'] in ids:
            raise ValueError(f'{source}: duplicate shot id {item["id"]!r}')
        ids.add(item['id'])
        validated.append(item)
    return {
        'format': data.get('format') or 'rov-trailer-1',
        'title': data.get('title') or '',
        'fps': int(data.get('fps') or 60),
        'width': int(data.get('width') or 1920),
        'height': int(data.get('height') or 1080),
        'shots': validated,
    }


def validate_shot(shot: dict[str, Any], source: str = 'shot') -> dict[str, Any]:
    if not isinstance(shot, dict):
        raise ValueError(f'{source}: shot must be an object')
    shot_id = shot.get('id')
    if not isinstance(shot_id, str) or not shot_id.strip():
        raise ValueError(f'{source}: id is required')
    duration = float(shot.get('duration', 0))
    if duration <= 0:
        raise ValueError(f'{source}: duration must be > 0')
    scenario = shot.get('scenario') or shot.get('source')
    if scenario == 'cold_open':
        scenario = 'cold_open_jacket'
    if not isinstance(scenario, str) or scenario not in KNOWN_SCENARIOS:
        raise ValueError(f'{source}: unknown scenario {scenario!r}')
    seed = int(shot.get('seed', 42))
    camera = validate_camera(shot.get('camera') or {'mode': 'onboard'}, source=f'{source}.camera')
    drive = validate_drive(shot.get('drive') or [], source=f'{source}.drive')
    hud = normalize_hud(shot.get('hud', True), source=f'{source}.hud')
    weather = shot.get('weather') or {}
    if not isinstance(weather, dict):
        raise ValueError(f'{source}: weather must be an object')
    return {
        'id': shot_id.strip(),
        'title': shot.get('title') or shot_id,
        'duration': duration,
        'scenario': scenario,
        'seed': seed,
        'camera': camera,
        'drive': drive,
        'hud': hud,
        'weather': weather,
        'hero_at': float(shot.get('hero_at', duration * 0.45)),
        'cards': shot.get('cards') or {},
        'notes': shot.get('notes') or '',
    }


def normalize_hud(hud: Any, source: str = 'hud') -> list[str] | bool:
    """Return False (off), True (full), or an explicit list of HUD part ids."""
    if hud in (False, 'off'):
        return False
    if hud in (True, 'full'):
        return True
    if hud == 'minimal':
        return list(HUD_MINIMAL)
    if isinstance(hud, list):
        parts: list[str] = []
        allowed = set(HUD_PARTS)
        for index, item in enumerate(hud):
            name = str(item).strip()
            if name not in allowed:
                raise ValueError(f'{source}[{index}]: unknown hud part {name!r}')
            if name not in parts:
                parts.append(name)
        return parts
    if isinstance(hud, dict):
        parts = [name for name in HUD_PARTS if hud.get(name)]
        return parts
    raise ValueError(f'{source}: hud must be bool, minimal/full/off, or a list of {HUD_PARTS}')


def validate_camera(camera: dict[str, Any], source: str = 'camera') -> dict[str, Any]:
    if not isinstance(camera, dict):
        raise ValueError(f'{source}: must be an object')
    mode = camera.get('mode', 'onboard')
    if mode not in MODES:
        raise ValueError(f'{source}: mode must be one of {MODES}')
    keyframes = camera.get('keyframes') or []
    if mode != 'onboard' and not keyframes:
        raise ValueError(f'{source}: keyframes required for mode {mode}')
    cleaned = []
    prev_t = -1.0
    for index, frame in enumerate(keyframes):
        if not isinstance(frame, dict) or 't' not in frame:
            raise ValueError(f'{source}.keyframes[{index}]: needs t')
        t = float(frame['t'])
        if t < prev_t:
            raise ValueError(f'{source}.keyframes[{index}]: times must be non-decreasing')
        prev_t = t
        item = {'t': t}
        for key in ('position', 'lookAt', 'offset', 'lookOffset'):
            if key in frame:
                value = frame[key]
                if not isinstance(value, (list, tuple)) or len(value) != 3:
                    raise ValueError(f'{source}.keyframes[{index}].{key}: need [x,y,z]')
                item[key] = [float(v) for v in value]
        for key in ('azimuth', 'radius', 'height', 'fov'):
            if key in frame:
                item[key] = float(frame[key])
        cleaned.append(item)
    out = {'mode': mode, 'keyframes': cleaned}
    if 'fov' in camera:
        out['fov'] = float(camera['fov'])
    return out


def validate_drive(drive: list, source: str = 'drive') -> list[dict[str, Any]]:
    if not isinstance(drive, list):
        raise ValueError(f'{source}: must be a list')
    cleaned = []
    prev_t = -1.0
    for index, step in enumerate(drive):
        if not isinstance(step, dict) or 't' not in step:
            raise ValueError(f'{source}[{index}]: needs t')
        t = float(step['t'])
        if t < prev_t:
            raise ValueError(f'{source}[{index}]: times must be non-decreasing')
        prev_t = t
        item: dict[str, Any] = {'t': t}
        for axis in DRIVE_AXES:
            if axis in step:
                value = float(step[axis])
                if value < -1.0 or value > 1.0:
                    raise ValueError(f'{source}[{index}].{axis}: must be in [-1, 1]')
                item[axis] = value
        if 'locked' in step:
            item['locked'] = bool(step['locked'])
        if 'keep_depth' in step:
            item['keep_depth'] = bool(step['keep_depth'])
        if 'led' in step:
            item['led'] = int(step['led'])
        cleaned.append(item)
    return cleaned


def drive_at(drive: list[dict[str, Any]], t: float) -> dict[str, Any]:
    """Piecewise-constant hold of the latest drive sample at or before t."""
    current = {
        'surge': 0.0, 'sway': 0.0, 'heave': 0.0, 'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0,
        'locked': False, 'keep_depth': True, 'led': 2,
    }
    for step in drive:
        if step['t'] > t:
            break
        current.update(step)
    return current
