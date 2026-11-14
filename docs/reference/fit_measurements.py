"""Fit measured step/coast traces; never applies suggestions to vehicle parameters.

Run: python docs/reference/fit_measurements.py docs/reference/own/trace.csv
CSV: axis,time_s,velocity,command,effective_mass
Velocity: signed m/s (surge/sway/heave) or rad/s (yaw); command: signed [-1,1].
Effective mass: kg including added mass, or kg m² for yaw. Each axis must contain
both step and coast samples at multiple speeds; still water, no tether/contacts.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np


def fit(rows):
    """Estimate F*u - L*v - Q*v*abs(v) = M*dv/dt, with identifiability checks."""
    result = {}
    for axis in sorted({row['axis'] for row in rows}):
        if axis not in ('surge', 'sway', 'heave', 'yaw'):
            raise ValueError('unsupported axis')
        samples = [row for row in rows if row['axis'] == axis]
        data = np.array([[float(row[key]) for key in
                          ('time_s', 'velocity', 'command', 'effective_mass')] for row in samples])
        if len(data) < 5 or not np.isfinite(data).all():
            raise ValueError('need at least five finite samples per axis')
        t, v, u, mass = data.T
        if np.any(np.diff(t) <= 0) or np.any(mass <= 0) or not np.allclose(mass, mass[0]):
            raise ValueError('time must increase and effective mass must be constant and positive')
        if np.any(abs(u) > 1):
            raise ValueError('command outside [-1,1]')
        # Command is held from sample i until i+1; midpoint drag reduces discretisation bias.
        vm = (v[1:] + v[:-1]) / 2
        design = np.column_stack((u[:-1], -vm, -vm * abs(vm)))
        force = mass[0] * np.diff(v) / np.diff(t)
        coefficients, _, rank, _ = np.linalg.lstsq(design, force, rcond=None)
        if rank < 3 or np.any(coefficients < -1e-6):
            raise ValueError('unidentifiable or nonphysical fit; collect step and coast data')
        result[axis] = dict(zip(('thrust', 'linear_drag', 'quadratic_drag'), coefficients.tolist()))
        result[axis]['force_rmse'] = float(np.sqrt(np.mean((design @ coefficients - force) ** 2)))
        result[axis]['samples'] = len(data)
    if not result:
        raise ValueError('empty measurement file')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    args = parser.parse_args()
    with args.csv.open(newline='') as stream:
        print(json.dumps(fit(list(csv.DictReader(stream))), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
