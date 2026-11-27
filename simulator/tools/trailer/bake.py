"""Bake a storyboard shot into a qysim-replay-2 clip using the real fixed-step simulator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from qysim.engine import Simulator  # noqa: E402
from qysim.server import _json_default  # noqa: E402

from .storyboard import drive_at, validate_shot  # noqa: E402

SIM_HZ = 100.0
CTRL = 'QYRovControllerManage'

# Keep the same slim fields as tools/record_demo.py so the viewer replay path works unchanged.
_KEEP = (
    't', 'pos', 'q', 'euler', 'vel', 'speed_kn', 'thrust', 'health', 'rc', 'remote_control',
    'operation_mode', 'ctrl_mode', 'locked', 'keep_depth', 'depth_hold', 'battery', 'recording',
    'photos', 'current_here', 'current_kn', 'tether', 'events', 'damage', 'silt', 'turbidity',
    'nav', 'score', 'log', 'sensors', 'link',
)


def _round(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: _round(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(item) for item in value]
    if isinstance(value, np.generic):
        return _round(value.item())
    return value


def _slim(state: dict) -> dict:
    out = {key: state[key] for key in _KEEP if key in state}
    out['tether'] = {
        **state['tether'],
        'nodes': [[round(float(c), 2) for c in node] for node in state['tether']['nodes']],
    }
    nav = dict(state['nav'])
    nav.pop('route', None)
    out['nav'] = nav
    out['log'] = state.get('log', [])[-6:]
    return _round(out)


def _pwm(unit: float) -> int:
    return int(max(1000, min(2000, round(1500 + 500 * float(unit)))))


def _apply_drive(sim: Simulator, sample: dict[str, Any]) -> None:
    rc = sim.rc_physical
    # ROV_USA: surge→right_ud, yaw→left_lr, heave→left_wave, sway→right_wave, pitch→left_ud, roll→right_lr
    mapping = {
        'surge': 'right_ud',
        'yaw': 'left_lr',
        'heave': 'left_wave',
        'sway': 'right_wave',
        'pitch': 'left_ud',
        'roll': 'right_lr',
    }
    for axis, channel in mapping.items():
        if axis in sample:
            sign = -1 if axis == 'pitch' else 1
            setattr(rc, channel, _pwm(sign * sample[axis]))
    rc.rc_lock = 1 if sample.get('locked', False) else 0
    rc.keep_depth = 1 if sample.get('keep_depth', True) else 0
    if 'led' in sample:
        rc.right_switch = int(sample['led'])


def _apply_weather(sim: Simulator, weather: dict[str, Any]) -> None:
    cur = sim.world.current
    if 'surface_kn' in weather:
        cur.surface_kn = float(weather['surface_kn'])
    if 'current_kn' in weather:
        kn = float(weather['current_kn'])
        cur.surface_kn = kn
        cur.mid_kn = kn * 0.7
        cur.bottom_kn = kn * 0.25
    if 'surface_dir' in weather:
        cur.surface_dir = float(weather['surface_dir'])
    if 'visibility_m' in weather:
        sim.scenario.visibility_m = float(weather['visibility_m'])
        sim.world.visibility_m = float(weather['visibility_m'])


def bake_shot(shot: dict[str, Any], fps: int = 60, sim_hz: float = SIM_HZ) -> dict[str, Any]:
    """Run the fixed-step simulator and return a single-clip replay document."""
    shot = validate_shot(shot)
    sim = Simulator(shot['scenario'], seed=shot['seed'])
    _apply_weather(sim, shot.get('weather') or {})
    sim.sdk_call(CTRL, 'set_remote_control_status', ['ON'], {})
    sim.sdk_call(CTRL, 'set_rc_lock_button', [0], {})
    sim.remote_control = False
    sim.rc_physical = sim.rc_sdk

    frames = []
    duration = float(shot['duration'])
    # Unlock and settle briefly before the shot clock so the first trailer second is already moving.
    for _ in range(int(0.5 * sim_hz)):
        _apply_drive(sim, drive_at(shot['drive'], 0.0))
        sim.step(1.0 / sim_hz)

    t0 = sim.t
    next_sample = 0.0
    while sim.t - t0 < duration + 1e-9:
        local_t = sim.t - t0
        _apply_drive(sim, drive_at(shot['drive'], local_t))
        sim.step(1.0 / sim_hz)
        local_t = sim.t - t0
        if local_t + 1e-9 >= next_sample:
            state = _slim(sim.viewer_state())
            # Shot-local time so replay duration matches the storyboard.
            state['t'] = round(next_sample, 6)
            frames.append(state)
            next_sample = len(frames) / float(fps)

    if not frames:
        raise RuntimeError(f'shot {shot["id"]} produced no frames')
    # Ensure the last frame lands on duration.
    frames[-1]['t'] = round(duration, 6)

    return {
        'format': 'qysim-replay-2',
        'hz': fps,
        'clips': [{
            'key': shot['id'],
            'title': shot.get('title') or shot['id'],
            'world': sim.world_description(),
            'frames': frames,
            'script': [],
            'trailer': {
                'camera': shot['camera'],
                'hud': shot['hud'],
                'duration': duration,
                'hero_at': shot['hero_at'],
            },
        }],
    }


def write_clip(shot: dict[str, Any], out_path: Path, fps: int = 60) -> Path:
    doc = bake_shot(shot, fps=fps)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, default=_json_default, ensure_ascii=False, separators=(',', ':')),
                        encoding='utf-8')
    return out_path
