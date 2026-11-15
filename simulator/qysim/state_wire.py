"""Bound presentation-only float precision without changing physics or SDK methods.

Six significant decimal digits bound relative error to 5e-6 while retaining tiny
values (unlike a global decimal-place cutoff). Keys, integers and flags survive.
"""
import math

import numpy as np


# Clocks and event identifiers can be echoed back as exact command selectors.
EXACT_KEYS = frozenset({'t', 'timestamp', 'start', 'end', 'since', 'id', 'seq'})
# Leaf types returned unchanged without further checks (the common case in a snapshot).
PLAIN_TYPES = (int, str, bool, type(None))


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
