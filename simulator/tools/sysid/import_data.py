"""Convert timestamped SDK controller logs or calibrated side-view annotations to analysis CSV."""
import argparse
import json
from pathlib import Path

import numpy as np

from .core import AXES, numeric, read_csv, time_check
from .synthetic import write_csv

STRINGS = {
    'sdk': 'SDK failure or missing depth/heading targets; cannot compare controller response.',
    'scale': 'Scale must be positive and constant within each fixed-camera run.',
    'axis': 'Unsupported axis.',
}


def telemetry_control(path):
    rows = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        response = record['get_rov_data']
        if response['status'] != 'ok':
            raise ValueError(STRINGS['sdk'])
        rov = response['data']['rov']
        targets = record['targets']
        state = record['state']
        if state['mode'] != 'A' or state['locked'] or not state['keep_depth']:
            raise ValueError(STRINGS['sdk'])
        rows.append({'time_s': record['time_s'], 'depth_m': rov['depth'], 'yaw_deg': rov['yaw'],
                     'depth_target_m': targets['depth_m'], 'yaw_target_deg': targets['yaw_deg']})
    time, *_ = numeric(rows, ('time_s', 'depth_m', 'yaw_deg', 'depth_target_m', 'yaw_target_deg'))
    time_check(time)
    return rows


def video_motion(path):
    rows = read_csv(path)
    output = []
    if any(row['axis'] not in AXES for row in rows):
        raise ValueError(STRINGS['axis'])
    for axis in AXES:
        group = [r for r in rows if r['axis'] == axis]
        if not group:
            continue
        time, position, scale_px, scale_m, command = numeric(
            group, ('time_s', 'position_px', 'scale_px', 'scale_m', 'command'))
        time_check(time)
        scale = scale_m/scale_px
        if np.any(scale_px <= 0) or np.any(scale_m <= 0) or not np.allclose(scale, scale[0]):
            raise ValueError(STRINGS['scale'])
        velocity = np.gradient(position*scale, time, edge_order=2)
        for t, v, u in zip(time, velocity, command):
            output.append({'axis': axis, 'time_s': t, 'velocity_m_s': v, 'command': u})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('telemetry', 'video'))
    parser.add_argument('source')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = telemetry_control(args.source) if args.kind == 'telemetry' else video_motion(args.source)
    write_csv(args.output, rows)


if __name__ == '__main__':
    main()
