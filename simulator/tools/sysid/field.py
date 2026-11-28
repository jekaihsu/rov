"""Reduce pool logs to speeds, coast distances and yaw rate.

Identification of mass and drag is done by core.fit_track / fit_axis. This module
only reads the tables a person can fill in from a stopwatch, a marked video and a
spin count. It does not borrow numbers from other vehicles.
"""
import csv
from pathlib import Path

import numpy as np

from .core import AXES

STRINGS = {
    'empty': 'The table has no data rows.',
    'column': 'A required column is missing.',
    'axis': 'Axis must be surge, sway or heave. Yaw timing belongs in yaw.csv.',
    'direction': 'Direction must be positive or negative (正 / 負).',
    'timing': 'Marker distance and time must be positive.',
    'yaw': 'Revolutions and spin time must be positive.',
    'scale': 'Scale must be positive and constant within one camera setup.',
    'time': 'Time must be strictly increasing within each axis.',
    'command': 'Command must stay inside [-1, 1].',
}

ALIASES = {
    'axis': 'axis', '軸向': 'axis', '軸': 'axis',
    'gear': 'gear', '檔位': 'gear',
    'direction': 'direction', '方向': 'direction',
    'distance_m': 'distance_m', '距離_m': 'distance_m', '距離': 'distance_m',
    'time_s': 'time_s', '時間_s': 'time_s', '時間': 'time_s',
    'revolutions': 'revolutions', '圈數': 'revolutions',
    'coast_deg': 'coast_deg', '鬆桿角度_deg': 'coast_deg', '鬆桿角度': 'coast_deg',
    'position_m': 'position_m', '位置_m': 'position_m',
    'position_px': 'position_px', '位置_px': 'position_px',
    'scale_px': 'scale_px', '尺_px': 'scale_px',
    'scale_m': 'scale_m', '尺_m': 'scale_m',
    'command': 'command', '命令': 'command',
    'event': 'event', '事件': 'event',
    'file': 'file', '幀': 'file',
    'depth_m': 'depth_m', '深度_m': 'depth_m',
    'heading_deg': 'heading_deg', '航向_deg': 'heading_deg',
}
POSITIVE = {'positive', 'pos', '+', '正'}
NEGATIVE = {'negative', 'neg', '-', '負'}
GLIDE_FRACTION = 1.0 - np.exp(-1.0)


def read_table(path):
    """CSV with English or Chinese headers. UTF-8 with an optional Excel BOM."""
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(STRINGS['empty'])
        rows = []
        for raw in reader:
            row = {}
            for key, value in raw.items():
                if key is None:
                    continue
                canon = ALIASES.get(key.strip(), key.strip())
                row[canon] = value.strip() if isinstance(value, str) else value
            if any(row.values()):
                rows.append(row)
    if not rows:
        raise ValueError(STRINGS['empty'])
    return rows


def _need(row, key):
    if key not in row or row[key] == '':
        raise ValueError(STRINGS['column'])
    return row[key]


def direction_of(token):
    text = str(token).strip().lower()
    if token in POSITIVE or text in POSITIVE:
        return 'positive'
    if token in NEGATIVE or text in NEGATIVE:
        return 'negative'
    raise ValueError(STRINGS['direction'])


def _axis(token):
    name = str(token).strip().lower()
    if name == 'yaw':
        raise ValueError(STRINGS['axis'])
    if name not in AXES:
        raise ValueError(STRINGS['axis'])
    return name


def terminal_speeds(rows):
    """Signed speed = distance / time. Positive follows the body axis sign."""
    items = []
    for row in rows:
        distance = float(_need(row, 'distance_m'))
        elapsed = float(_need(row, 'time_s'))
        if distance <= 0 or elapsed <= 0 or not np.isfinite([distance, elapsed]).all():
            raise ValueError(STRINGS['timing'])
        sign = 1.0 if direction_of(_need(row, 'direction')) == 'positive' else -1.0
        items.append({
            'axis': _axis(_need(row, 'axis')),
            'gear': str(_need(row, 'gear')),
            'direction': 'positive' if sign > 0 else 'negative',
            'distance_m': distance,
            'time_s': elapsed,
            'speed_m_s': sign * distance / elapsed,
        })
    return items


def summarise_speeds(rows, open_loop_gear):
    """Mean speed of repeated passes. Only the open-loop gear's positive pass suggests vmax."""
    grouped = {}
    order = []
    for item in terminal_speeds(rows):
        key = (item['axis'], item['gear'], item['direction'])
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        grouped[key].append(item['speed_m_s'])
    summary = []
    for key in order:
        speeds = np.array(grouped[key], float)
        summary.append({
            'axis': key[0],
            'gear': key[1],
            'direction': key[2],
            'samples': int(len(speeds)),
            'speed_m_s': float(np.mean(speeds)),
            'used_for_vmax': key[1] == open_loop_gear and key[2] == 'positive',
        })
    return summary


def yaw_rates(rows, open_loop_gear):
    """Full-stick yaw rate from revolution count and the stopwatch, not from inertia."""
    items = []
    for row in rows:
        turns = float(_need(row, 'revolutions'))
        elapsed = float(_need(row, 'time_s'))
        if turns <= 0 or elapsed <= 0 or not np.isfinite([turns, elapsed]).all():
            raise ValueError(STRINGS['yaw'])
        direction = direction_of(_need(row, 'direction'))
        sign = 1.0 if direction == 'positive' else -1.0
        rate = sign * turns * 2.0 * np.pi / elapsed
        coast = row.get('coast_deg', '')
        gear = str(_need(row, 'gear'))
        items.append({
            'gear': gear,
            'direction': direction,
            'revolutions': turns,
            'time_s': elapsed,
            'coast_deg': None if coast == '' else float(coast),
            'rate_rad_s': float(rate),
            'rate_deg_s': float(np.rad2deg(rate)),
            'used_for_wmax': gear == open_loop_gear and direction == 'positive',
        })
    return items


def _positions_from_pixels(rows):
    output = []
    for row in rows:
        scale_px = float(_need(row, 'scale_px'))
        scale_m = float(_need(row, 'scale_m'))
        if scale_px <= 0 or scale_m <= 0:
            raise ValueError(STRINGS['scale'])
        copied = dict(row)
        copied['position_m'] = str(float(row['position_px']) * scale_m / scale_px)
        output.append(copied)
    scales = [float(row['scale_m']) / float(row['scale_px']) for row in rows]
    if not np.allclose(scales, scales[0]):
        raise ValueError(STRINGS['scale'])
    return output


def track_rows(rows):
    """One rest-to-rest position track per axis, in metres."""
    if any('position_px' in row and 'position_m' not in row for row in rows):
        rows = _positions_from_pixels(rows)
    grouped = {axis: [] for axis in AXES}
    for row in rows:
        axis = _axis(_need(row, 'axis'))
        command = float(_need(row, 'command'))
        if abs(command) > 1 or not np.isfinite(command):
            raise ValueError(STRINGS['command'])
        grouped[axis].append({
            'time_s': float(_need(row, 'time_s')),
            'position_m': float(_need(row, 'position_m')),
            'command': command,
            'event': row.get('event', ''),
        })
    tracks = {}
    for axis, samples in grouped.items():
        if not samples:
            continue
        time = np.array([sample['time_s'] for sample in samples], float)
        if np.any(np.diff(time) <= 0) or not np.isfinite(time).all():
            raise ValueError(STRINGS['time'])
        tracks[axis] = samples
    if not tracks:
        raise ValueError(STRINGS['empty'])
    return tracks


def _zero_runs(command):
    """Index ranges [start, end) of command==0 that follow a non-zero command."""
    runs = []
    index = 1
    while index < len(command):
        if command[index] == 0 and command[index-1] != 0:
            end = index
            while end < len(command) and command[end] == 0:
                end += 1
            if end - index >= 5:
                runs.append((index, end, float(command[index-1])))
            index = end
        else:
            index += 1
    return runs


def glide_time(time, position):
    """Time to cover (1 - 1/e) of the recorded coast displacement.

    For linear drag this equals the time constant. With quadratic drag it is the
    equivalent first-order time read from the marks, not mass/linear_drag.
    """
    distance = float(position[-1] - position[0])
    if abs(distance) < 1e-9:
        return None
    target = float(position[0] + GLIDE_FRACTION * distance)
    if distance > 0:
        hits = np.where(position >= target)[0]
    else:
        hits = np.where(position <= target)[0]
    if len(hits) == 0:
        return None
    index = int(hits[0])
    if index == 0:
        return 0.0
    span = float(position[index] - position[index-1])
    if span == 0:
        return float(time[index] - time[0])
    frac = (target - float(position[index-1])) / span
    crossed = float(time[index-1] + frac * (time[index] - time[index-1]))
    return crossed - float(time[0])


def coast_metrics(samples):
    """Coast distance is the marked displacement. Glide time comes from that curve."""
    time = np.array([sample['time_s'] for sample in samples], float)
    position = np.array([sample['position_m'] for sample in samples], float)
    command = np.array([sample['command'] for sample in samples], float)
    metrics = []
    for start, end, previous in _zero_runs(command):
        segment_t = time[start:end]
        segment_p = position[start:end]
        distance = float(segment_p[-1] - segment_p[0])
        tail_cut = segment_t[-1] - 1.0
        tail_index = int(np.searchsorted(segment_t, tail_cut))
        tail = abs(float(segment_p[-1] - segment_p[min(tail_index, len(segment_p)-1)]))
        settled = bool(segment_t[-1] - segment_t[0] >= 1.0 and tail < 0.015)
        metrics.append({
            'previous_command': previous,
            'full_stick': bool(abs(previous) == 1.0),
            'coast_distance_m': distance,
            'coast_duration_s': float(segment_t[-1] - segment_t[0]),
            'glide_time_s': glide_time(segment_t, segment_p),
            'settled': settled,
            'release_time_s': float(segment_t[0]),
            'release_index': int(start),
            'end_index': int(end),
        })
    return metrics


def steady_speed(force, linear, quadratic):
    """Real root of linear*|v| + quadratic*v^2 = |force|, with the sign of force."""
    sign = 1.0 if force >= 0 else -1.0
    magnitude = abs(float(force))
    if magnitude == 0:
        return 0.0
    if quadratic <= 1e-12:
        return sign * magnitude / linear
    disc = linear**2 + 4.0 * quadratic * magnitude
    return sign * (-linear + np.sqrt(disc)) / (2.0 * quadratic)


def cross_time(time, values, start, threshold):
    """First time at or after start where |values| drops to threshold."""
    level = abs(float(threshold))
    for index in range(start + 1, len(values)):
        if abs(values[index]) <= level:
            left = abs(float(values[index-1]))
            right = abs(float(values[index]))
            span = left - right
            frac = 0.0 if span == 0 else (left - level) / span
            frac = min(1.0, max(0.0, frac))
            return float(time[index-1] + frac * (time[index] - time[index-1]))
    return None
