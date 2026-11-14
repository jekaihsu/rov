"""Reproducible still-water acceptance measurements using real vehicle dynamics."""
import json

import numpy as np

from qysim.controller import FlightController
from qysim.physics import Vehicle

MODELS = ('x1', 'bluerov2_heavy', 'falcon')


def measure(model, profile, assist=1, push_seconds=10):
    vehicle = Vehicle(model_id=model)
    vehicle.s.pos[2] = 20
    controller = FlightController(vehicle)
    velocities = [0.0]
    positions = [0.0]
    max_force = 0.0
    for i in range((push_seconds + 15) * 100):
        motors = controller.update(.01, {'surge': 1 if i < push_seconds * 100 else 0},
                                   'A', False, False, assist=assist, profile=profile)
        max_force = max(max_force, float(np.max(np.abs(controller.last_wrench[:3]))))
        vehicle.step(.01, motors)
        velocities.append(float(vehicle.world_velocity()[0]))
        positions.append(float(vehicle.s.pos[0]))
    release = push_seconds * 100
    speed = np.asarray(velocities)
    limit = controller.assist_state()['speed_limit'][0] if assist else float(max(speed[:release]))
    reach = np.flatnonzero(speed[:release] >= .9 * limit)
    stop = np.flatnonzero(np.abs(speed[release:]) < .05)
    stop_index = release + int(stop[0]) if len(stop) else len(speed) - 1
    return {
        'model': model,
        'profile': profile if assist else 'manual',
        'limit': round(limit, 4),
        'peak': round(float(max(speed[:release])), 4),
        'rise_s': round(float(reach[0]) * .01, 3) if len(reach) else None,
        'stop_s': round(float(stop[0]) * .01, 3) if len(stop) else None,
        'stop_m': round(positions[stop_index] - positions[release], 4),
        'reverse_m': round(max(positions[release:]) - min(positions[stop_index:]), 4),
        'max_force': round(max_force, 6),
        'curve': {t: round(velocities[t * 100], 4) for t in (0, 1, 2, 3, 4, 6, 10)},
    }


def main():
    for model in MODELS:
        for profile in ('manual', 'cine', 'normal', 'sport'):
            print(json.dumps(measure(model, profile if profile != 'manual' else 'normal',
                                     assist=0 if profile == 'manual' else 1)))
    for model in MODELS:
        for assist in (0, 2):
            print(json.dumps({'push_seconds': 2, 'assist': assist, **measure(model, 'normal', assist, 2)}))


if __name__ == '__main__':
    main()
