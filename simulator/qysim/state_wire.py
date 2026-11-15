"""Bound presentation-only float precision without changing physics or SDK methods.

Six significant decimal digits bound relative error to 5e-6 while retaining tiny
values (unlike a global decimal-place cutoff). Keys, integers and flags survive.

Also implements the optional ``static_once`` capability: omit unchanged static and
low-frequency fields for clients that negotiated it (see PROTOCOL.md).
"""
import json
import math

import numpy as np


# Clocks and event identifiers can be echoed back as exact command selectors.
EXACT_KEYS = frozenset({'t', 'timestamp', 'start', 'end', 'since', 'id', 'seq'})
# Leaf types returned unchanged without further checks (the common case in a snapshot).
PLAIN_TYPES = (int, str, bool, type(None))

# Capability name echoed in join / hello / instructor_join.
STATIC_ONCE = 'static_once'
KNOWN_CAPS = frozenset({STATIC_ONCE})

# Top-level state fields that a static_once client may omit when unchanged.
# Definitions + campaign, world-sticky seat/scene mirrors, and low-frequency systems.
STATIC_ONCE_FIELDS = frozenset({
    'vehicle', 'campaign',
    'appearance', 'paint_marks', 'room', 'mission', 'expedition', 'operation_mode', 'turbidity',
    'power', 'thermal', 'flow_field', 'link', 'leak', 'assist', 'health', 'nav', 'log',
    'events', 'damage', 'photos', 'recording', 'remote_control', 'input_latched',
    'control_generation', 'owner_id', 'vehicle_id', 'model_id', 'paused', 'battery',
    'keep_depth', 'ctrl_mode', 'locked', 'depth_hold',
})

# Per-fleet-entry fields eligible for the same omission contract.
STATIC_ONCE_VEHICLE_FIELDS = frozenset({
    'vehicle', 'power', 'thermal', 'appearance', 'paint_marks', 'link', 'leak', 'assist',
    'health', 'nav', 'log', 'events', 'damage', 'photos', 'mission', 'expedition',
    'operation_mode', 'turbidity', 'recording', 'remote_control', 'input_latched',
    'control_generation', 'owner_id', 'vehicle_id', 'model_id', 'paused', 'battery',
    'keep_depth', 'ctrl_mode', 'locked', 'depth_hold',
})


def compact_state(value, key=None):
    """Copy a snapshot; never mutate shared physics arrays or cached telemetry.

    Built-in types are dispatched by exact type first: this runs for every vehicle at the
    publication rate, so the walk must stay cheap next to the physics tick.
    """
    if key in EXACT_KEYS:
        return value
    kind = type(value)
    if kind is float:
        return float(format(value, '.6g')) if math.isfinite(value) else value
    if kind is dict:
        return {name: compact_state(item, name) for name, item in value.items()}
    if kind is list or kind is tuple:
        return [compact_state(item, key) for item in value]
    if kind in PLAIN_TYPES:
        return value
    if isinstance(value, dict):
        return {name: compact_state(item, name) for name, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [compact_state(item, key) for item in value]
    if isinstance(value, (float, np.floating)) and math.isfinite(value):
        return float(format(value, '.6g'))
    return value


def parse_caps(raw):
    """Accept an optional caps list; unknown names are ignored; order is stable."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ValueError('caps must be an array of strings')
    accepted = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError('caps must be an array of strings')
        if item in KNOWN_CAPS and item not in seen:
            accepted.append(item)
            seen.add(item)
    return tuple(accepted)


def _json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(type(value))


def _fingerprint(name, value):
    """Cheap stable fingerprint; prefer structural keys over full JSON dumps."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if name == 'vehicle' and isinstance(value, dict):
        # Vehicle definitions are immutable per model id.
        return ('vehicle', value.get('id'))
    if name == 'flow_field' and isinstance(value, dict):
        return ('flow', value.get('seq'), value.get('t'))
    if name == 'appearance' and isinstance(value, dict):
        return ('appearance', value.get('sticker'), tuple(sorted(value.items())))
    if name in ('power', 'thermal', 'link', 'leak', 'assist') and isinstance(value, dict):
        return (name, tuple(sorted((key, _scalar(item)) for key, item in value.items())))
    if name in ('health',) and isinstance(value, list):
        return (name, tuple(value))
    if name in ('events', 'damage', 'photos', 'log', 'paint_marks') and isinstance(value, list):
        if not value:
            return (name, 0)
        return (name, json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                 default=_json_default))
    # Campaign, room, mission, nav, turbidity and other nested objects.
    return (name, json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                             default=_json_default))


def _scalar(value):
    if isinstance(value, list):
        return tuple(_scalar(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _scalar(item)) for key, item in value.items()))
    return value


# Fingerprint stand-in for "never sent", so a newly present explicit null is forwarded.
_MISSING = object()

# Marker on states that omit fields. Unmarked states are complete snapshots.
DELTA_KEY = 'delta'


class StaticOnceTracker:
    """Per-connection omit state for the static_once capability.

    The first state after construction or ``reset()`` is always a full snapshot.
    Later messages drop allowlisted fields whose fingerprint matches the last send and
    carry ``"delta": true``. Explicit nulls and value changes are always forwarded.
    When a previously sent allowlisted field (or a whole fleet seat) disappears, the
    state is sent complete and unmarked, so clients replace their retained snapshot.
    """

    def __init__(self):
        self._last = {}
        self._force_full = True

    def reset(self):
        self._last.clear()
        self._force_full = True

    def strip(self, state):
        """Return a state dict safe to encode; never mutates ``state`` or shared arrays."""
        if self._force_full or self._removed(state):
            self._last.clear()
            self._remember(state)
            self._force_full = False
            return state
        out = {}
        omitted = False
        for key, value in state.items():
            if key == 'vehicles' and isinstance(value, list):
                fleet, fleet_omitted = self._strip_fleet(value)
                out[key] = fleet
                omitted = omitted or fleet_omitted
                continue
            if key in STATIC_ONCE_FIELDS and self._unchanged(('top', key), key, value):
                omitted = True
                continue
            out[key] = value
            if key in STATIC_ONCE_FIELDS:
                self._last[('top', key)] = _fingerprint(key, value)
        if omitted:
            out[DELTA_KEY] = True
        return out

    def _strip_fleet(self, fleet):
        result = []
        omitted = False
        for entry in fleet:
            vehicle_id = _vehicle_key(entry)
            item = {}
            for key, value in entry.items():
                path = ('vehicle', vehicle_id, key)
                if key in STATIC_ONCE_VEHICLE_FIELDS and self._unchanged(path, key, value):
                    omitted = True
                    continue
                item[key] = value
                if key in STATIC_ONCE_VEHICLE_FIELDS:
                    self._last[path] = _fingerprint(key, value)
            result.append(item)
        return result, omitted

    def _unchanged(self, path, name, value):
        return self._last.get(path, _MISSING) == _fingerprint(name, value)

    def _paths(self, state):
        paths = set()
        for key, value in state.items():
            if key == 'vehicles' and isinstance(value, list):
                for entry in value:
                    vehicle_id = _vehicle_key(entry)
                    paths.update(('vehicle', vehicle_id, field) for field in entry
                                 if field in STATIC_ONCE_VEHICLE_FIELDS)
            elif key in STATIC_ONCE_FIELDS:
                paths.add(('top', key))
        return paths

    def _removed(self, state):
        """True when a remembered field or seat is absent now (explicit removal)."""
        return not self._paths(state).issuperset(self._last)

    def _remember(self, state):
        for key, value in state.items():
            if key == 'vehicles' and isinstance(value, list):
                for entry in value:
                    vehicle_id = _vehicle_key(entry)
                    for field, field_value in entry.items():
                        if field in STATIC_ONCE_VEHICLE_FIELDS:
                            self._last[('vehicle', vehicle_id, field)] = _fingerprint(field, field_value)
                continue
            if key in STATIC_ONCE_FIELDS:
                self._last[('top', key)] = _fingerprint(key, value)


def _vehicle_key(entry):
    return entry.get('vehicle_id') or entry.get('id')
