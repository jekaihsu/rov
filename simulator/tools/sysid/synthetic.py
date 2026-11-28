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
            'motor_tau_s': baseline.p.motor_tau, 'implicit_drag': True, 'bias_force_n': dict.fromkeys(AXES, 0),
            'conditions': 'Guided tow rig, calibrated external force actuator, still water, neutral trim.',
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
        tow_force = 0.0
        idle = np.zeros(len(vehicle.thrusters))
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
            # The single-axis identification experiment requires an independently
            # calibrated force source. Installed propellers have inflow-dependent thrust.
            tow_force += (u * vehicle.authority[axis_index] - tow_force) * .01 / vehicle.p.motor_tau
            wrench[2] = vehicle.p.net_buoyancy
            wrench[axis_index] += tow_force
            vehicle.step(.01, idle, wrench)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    args = parser.parse_args()
    generate(args.destination)


if __name__ == '__main__':
    main()
