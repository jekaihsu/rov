"""Seeded synthetic fixtures from Vehicle.step and FlightController, never real measurements."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from qysim.physics import Vehicle
from qysim.vehicles import X1_TETHER_PARAMETERS
from .core import AXES, controller_replay


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def generate(destination, seed=51):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    baseline = Vehicle()
    meta = {'schema_version': 1, 'synthetic': True, 'seed': seed, 'dry_mass_kg': baseline.p.mass,
            'motor_tau_s': baseline.p.motor_tau, 'bias_force_n': dict.fromkeys(AXES, 0),
            'conditions': 'Still water, isolated axis, buoyancy compensated, no tether/contact; initial thrust zero.',
            'noise': {'velocity_sigma_m_s': .001, 'thrust_sigma_n': .01},
            'truth': {}}
    motion, anchors, annotations = [], [], []
    levels = [0, .25, 0, .5, 0, 1, 0, -.25, 0, -.5, 0, -1, 0]
    for axis_index, axis in enumerate(AXES):
        vehicle = Vehicle()
        vehicle.s.pos[2] = 10
        vehicle.seabed_depth = 1000
        meta['truth'][axis] = {'added_mass': vehicle.p.added_mass[axis_index],
                               'linear_drag': vehicle.p.linear_drag[axis_index],
                               'quadratic_drag': vehicle.quad_drag[axis_index],
                               'thrust_linear': vehicle.authority[axis_index], 'thrust_quadratic': 0}
        for u in [-1, -.75, -.5, -.25, .25, .5, .75, 1]:
            for _ in range(3):
                anchors.append({'axis': axis, 'command': u,
                                'force_n': vehicle.authority[axis_index]*u+rng.normal(0, .01)})
        for step in range(len(levels)*400+1):
            time = step*.01
            u = levels[min(step//400, len(levels)-1)]
            if step % 10 == 0:
                motion.append({'axis': axis, 'time_s': round(time, 4),
                               'velocity_m_s': float(vehicle.s.vel[axis_index]+rng.normal(0, .001)), 'command': u})
                annotations.append({'axis': axis, 'time_s': round(time, 4), 'scale_px': 100,
                                    'scale_m': 1, 'command': u, 'position_px': float(vehicle.s.pos[axis_index]*100),
                                    'event': 'command_change' if step % 400 == 0 else ''})
            wrench = np.zeros(6)
            wrench[axis_index] = u
            # Isolated-axis rig: cancel buoyancy; tiny numerical cross-axis components removed.
            vehicle.step(.01, vehicle.allocate(wrench), np.array([0, 0, vehicle.p.net_buoyancy, 0, 0, 0]))
            vehicle.s.omega[:] = 0
            vehicle.s.q[:] = [1, 0, 0, 0]
            for other in range(3):
                if other != axis_index:
                    vehicle.s.vel[other] = 0
    control = [{'time_s': i*.1, 'depth_m': 10., 'yaw_deg': 350.,
                'depth_target_m': 10.5 if i >= 10 else 10., 'yaw_target_deg': 10. if i >= 10 else 350.}
               for i in range(201)]
    _, replay = controller_replay(control)
    telemetry = []
    for row, (depth, yaw) in zip(control, replay):
        row['depth_m'] = float(depth+rng.normal(0, .002))
        row['yaw_deg'] = float((yaw+rng.normal(0, .02)) % 360)
        telemetry.append({'time_s': row['time_s'],
                          'get_rov_data': {'status': 'ok', 'status_code': '200', 'text': '',
                                           'data': {'rov': {'depth': row['depth_m'], 'yaw': row['yaw_deg']}}},
                          'state': {'mode': 'A', 'locked': False, 'keep_depth': True},
                          'targets': {'depth_m': row['depth_target_m'], 'yaw_deg': row['yaw_target_deg']}})
    diameter = X1_TETHER_PARAMETERS['diameter']['value']
    density = X1_TETHER_PARAMETERS['density']['value']
    area = np.pi*diameter**2/4
    cables = [{'length_m': 10, 'dry_mass_kg': density*area*10+rng.normal(0, .0001),
               'wet_force_n': (density-1025)*area*10*9.81+rng.normal(0, .001),
               'diameter_m': diameter, 'water_density_kg_m3': 1025} for _ in range(8)]
    for name, rows in [('motion', motion), ('thrust', anchors), ('video', annotations),
                       ('control', control), ('tether', cables)]:
        write_csv(destination/f'{name}.csv', rows)
    (destination/'telemetry.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in telemetry), encoding='utf-8')
    (destination/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')


def _isolated_samples(axis_index, pieces, dt=0.01):
    """Sample-then-step log. pieces are (duration_s, command). Final sample is after the last step."""
    vehicle = Vehicle()
    vehicle.s.pos[2] = 10
    vehicle.seabed_depth = 1000
    samples = []
    time = 0.0
    for duration, command in pieces:
        steps = int(round(duration / dt))
        for _ in range(steps):
            samples.append((time, float(vehicle.s.pos[axis_index]), float(vehicle.s.vel[axis_index]), float(command)))
            wrench = np.zeros(6)
            wrench[axis_index] = command
            extra = np.array([0.0, 0.0, vehicle.p.net_buoyancy, 0.0, 0.0, 0.0])
            vehicle.step(dt, vehicle.allocate(wrench), extra)
            vehicle.s.omega[:] = 0
            vehicle.s.q[:] = [1.0, 0.0, 0.0, 0.0]
            for other in range(3):
                if other != axis_index:
                    vehicle.s.vel[other] = 0
            time += dt
    last = pieces[-1][1]
    samples.append((time, float(vehicle.s.pos[axis_index]), float(vehicle.s.vel[axis_index]), float(last)))
    return vehicle, samples


def _passage(samples, distance):
    """Time to cover `distance` after speed has stayed within 1% of the steady value."""
    time = np.array([sample[0] for sample in samples])
    position = np.array([sample[1] for sample in samples])
    velocity = np.array([sample[2] for sample in samples])
    steady = float(np.median(velocity[-40:]))
    band = 0.01 * abs(steady)
    ready = np.where(np.abs(velocity - steady) <= band)[0]
    if abs(steady) < 1e-6 or len(ready) == 0:
        raise RuntimeError('isolated run did not reach a steady speed')
    start = int(ready[0])
    target = position[start] + np.sign(steady) * distance
    if steady > 0:
        hits = np.where(position[start:] >= target)[0]
    else:
        hits = np.where(position[start:] <= target)[0]
    if len(hits) == 0:
        raise RuntimeError('marker distance is longer than the steady run')
    index = start + int(hits[0])
    span = position[index] - position[index - 1]
    frac = 0.0 if span == 0 else (target - position[index - 1]) / span
    elapsed = float(time[index - 1] + frac * (time[index] - time[index - 1]) - time[start])
    return elapsed, steady


def _one_over_e(samples, previous):
    """Release speed and time to fall to 1/e on a dense isolated log."""
    command = np.array([sample[3] for sample in samples])
    velocity = np.array([sample[2] for sample in samples])
    time = np.array([sample[0] for sample in samples])
    position = np.array([sample[1] for sample in samples])
    hits = np.where((command[:-1] == previous) & (command[1:] == 0))[0]
    start = int(hits[0]) + 1
    end = start
    while end < len(command) and command[end] == 0:
        end += 1
    release = float(velocity[start])
    limit = abs(release) / np.e
    index = start
    while index < end and abs(velocity[index]) > limit:
        index += 1
    return {
        'distance_m': float(position[end - 1] - position[start]),
        'one_over_e_s': float(time[index] - time[start]),
        'release_speed_m_s': release,
    }


def _yaw_spin(revolutions, command, dt=0.01):
    """Full-stick yaw until `revolutions` are complete, then the coast angle after release."""
    from qysim.physics import q_to_euler
    vehicle = Vehicle()
    vehicle.s.pos[2] = 5
    vehicle.seabed_depth = 1000
    extra = np.array([0.0, 0.0, vehicle.p.net_buoyancy, 0.0, 0.0, 0.0])

    def step(value):
        wrench = np.zeros(6)
        wrench[5] = value
        vehicle.step(dt, vehicle.allocate(wrench), extra)

    for _ in range(600):
        step(command)
    turned = 0.0
    elapsed = 0.0
    previous = q_to_euler(vehicle.s.q)[2]
    target = revolutions * 2.0 * np.pi
    while turned < target and elapsed < 80:
        step(command)
        elapsed += dt
        now = q_to_euler(vehicle.s.q)[2]
        turned += abs((now - previous + np.pi) % (2.0 * np.pi) - np.pi)
        previous = now
    rate = float(vehicle.s.omega[2])
    coast = 0.0
    release = abs(rate)
    for _ in range(4000):
        step(0.0)
        now = q_to_euler(vehicle.s.q)[2]
        coast += (now - previous + np.pi) % (2.0 * np.pi) - np.pi
        previous = now
        if abs(vehicle.s.omega[2]) < 0.02 * max(release, 1e-6):
            break
    return rate, elapsed, float(np.rad2deg(coast))


def generate_field(destination, seed=51):
    """Pool-style fixture: timing table, coast marks, yaw stopwatch and OSD frames.

    Parameters are whatever Vehicle() currently uses. They are recorded as truth for the
    test and are not written back into the catalogue.
    """
    from .osd import paint_readout, write_png
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'osd').mkdir(exist_ok=True)
    rng = np.random.default_rng(seed)
    baseline = Vehicle()
    pieces = (
        (1.0, 0.0), (4.0, 0.25), (6.0, 0.0), (4.0, 0.5), (6.0, 0.0),
        (4.0, 1.0), (16.0, 0.0), (4.0, -0.25), (6.0, 0.0), (4.0, -0.5), (6.0, 0.0),
        (4.0, -1.0), (16.0, 0.0),
    )
    meta = {
        'schema_version': 1, 'synthetic': True, 'vehicle': 'x1', 'seed': seed,
        'dry_mass_kg': baseline.p.mass, 'motor_tau_s': baseline.p.motor_tau,
        'bias_force_n': dict.fromkeys(AXES, 0.0), 'open_loop_gear': 'A',
        'position_noise_m': 0.001, 'timing_noise_s': 0.002,
        'conditions': 'Synthetic pool fixture. Isolated axis, buoyancy cancelled, no tether. Not an X1 measurement.',
        'truth': {
            'added_mass': list(baseline.p.added_mass),
            'linear_drag': list(baseline.p.linear_drag[:3]),
            'quadratic_drag': [float(value) for value in baseline.quad_drag],
            'thruster_max': baseline.p.thruster_max,
            'vmax': list(baseline.p.vmax),
            'wmax_yaw': baseline.p.wmax[2],
            'coast': {},
        },
    }
    coast_rows = []
    timing_rows = []
    anchors = []
    for axis_index, axis in enumerate(AXES):
        vehicle, samples = _isolated_samples(axis_index, pieces)
        meta['truth']['coast'][axis] = {
            'positive': _one_over_e(samples, 1.0),
            'negative': _one_over_e(samples, -1.0),
        }
        for sign, name in ((1.0, 'positive'), (-1.0, 'negative')):
            segment = [sample for sample in samples if sample[3] == sign]
            # The segment includes only samples whose upcoming command is `sign`, so the
            # speed during that window is still rising at the first sample. Passage uses
            # the whole constant-command record, which starts from the previous coast.
            elapsed, _steady = _passage(segment, 1.0)
            elapsed += float(rng.normal(0.0, meta['timing_noise_s']))
            timing_rows.append({
                'axis': axis, 'gear': 'A', 'direction': name,
                'distance_m': 1.0, 'time_s': round(elapsed, 6),
            })
        slow_pieces = ((1.0, 0.0), (8.0, 0.5), (1.0, 0.0), (8.0, -0.5))
        _vehicle, slow = _isolated_samples(axis_index, slow_pieces)
        for sign, name in ((0.5, 'positive'), (-0.5, 'negative')):
            segment = [sample for sample in slow if sample[3] == sign]
            elapsed, _steady = _passage(segment, 0.5)
            timing_rows.append({
                'axis': axis, 'gear': 'S', 'direction': name,
                'distance_m': 0.5, 'time_s': round(float(elapsed), 6),
            })
        for sample_index in range(0, len(samples), 10):
            time, position, _velocity, command = samples[sample_index]
            event = ''
            if sample_index > 0 and samples[sample_index - 1][3] != command:
                event = 'release' if command == 0.0 else 'command_change'
            coast_rows.append({
                'axis': axis, 'time_s': round(time, 4),
                'position_m': float(position + rng.normal(0.0, meta['position_noise_m'])),
                'command': command, 'event': event,
            })
        for command in (-1.0, -0.75, -0.5, -0.25, 0.25, 0.5, 0.75, 1.0):
            for _repeat in range(3):
                anchors.append({
                    'axis': axis, 'command': command,
                    'force_n': float(vehicle.authority[axis_index] * command + rng.normal(0.0, 0.01)),
                })
    yaw_rows = []
    meta['truth']['yaw'] = {}
    for command, name in ((1.0, 'positive'), (-1.0, 'negative')):
        rate, elapsed, coast = _yaw_spin(5.0, command)
        noisy_time = elapsed + float(rng.normal(0.0, 0.002))
        yaw_rows.append({
            'gear': 'A', 'direction': name, 'revolutions': 5.0,
            'time_s': round(noisy_time, 6), 'coast_deg': round(coast, 4),
        })
        meta['truth']['yaw'][name] = {'rate_rad_s': rate, 'time_s': elapsed, 'coast_deg': coast}
    osd_rows = []
    readings = []
    roi = None
    for index in range(12):
        depth = 10.0 + index * 0.05
        heading = (358.0 + index * 0.5) % 360.0
        depth_text = format(depth, '05.2f')
        heading_text = format(heading, '05.1f')
        image, depth_box, heading_box = paint_readout(depth_text, heading_text)
        if roi is None:
            roi = {'schema_version': 1, 'confirmed': True, 'depth': depth_box, 'heading': heading_box}
        name = f'frame_{index:04d}.png'
        write_png(destination / 'osd' / name, image)
        osd_rows.append({'file': name, 'time_s': round(index * 0.1, 4)})
        readings.append({'time_s': index * 0.1, 'depth_m': float(depth_text), 'heading_deg': float(heading_text)})
    meta['truth']['osd'] = readings
    for name, rows in (
            ('coast', coast_rows), ('timing', timing_rows), ('thrust', anchors), ('yaw', yaw_rows)):
        write_csv(destination / f'{name}.csv', rows)
    write_csv(destination / 'osd_index.csv', osd_rows)
    (destination / 'osd_roi.json').write_text(json.dumps(roi, indent=2) + '\n', encoding='utf-8')
    (destination / 'manifest.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    parser.add_argument('--field', action='store_true')
    parser.add_argument('--seed', type=int, default=51)
    args = parser.parse_args()
    if args.field:
        generate_field(args.destination, args.seed)
    else:
        generate(args.destination, args.seed)


if __name__ == '__main__':
    main()
