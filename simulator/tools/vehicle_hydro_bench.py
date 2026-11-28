"""100 Hz open-loop step, release and isolated Vehicle.step cost.

Run with PYTHONPATH pointing at the revision's simulator directory. An optional
CSV includes all samples (speed over ground in body FRD, still water).
"""
import argparse
import csv
import time

import numpy as np

from qysim.physics import Vehicle


def run(model, axis, writer):
    vehicle = Vehicle(model_id=model)
    vehicle.s.pos[2] = 15.
    vehicle.p.net_buoyancy = 0.
    drive = vehicle.allocate(.65 * np.eye(6)[axis])
    idle = np.zeros_like(drive)
    costs = []
    cpu_costs = []
    for tick in range(600):
        command = drive if tick < 300 else idle
        cpu_start = time.thread_time_ns()
        start = time.perf_counter_ns()
        vehicle.step(.01, command)
        costs.append((time.perf_counter_ns() - start) / 1e6)
        cpu_costs.append((time.thread_time_ns() - cpu_start) / 1e6)
        if writer:
            writer.writerow([model, axis, (tick + 1) / 100, vehicle.s.vel[0], vehicle.s.omega[2]])
    median, p99 = np.percentile(costs, (50, 99))
    print(f'{model:16} axis {axis}  median {median:.3f}  p99 {p99:.3f}  max {max(costs):.3f} ms  CPU max {max(cpu_costs):.3f} ms')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=argparse.FileType('w'))
    args = parser.parse_args()
    writer = csv.writer(args.csv) if args.csv else None
    if writer:
        writer.writerow(['model', 'axis', 'time_s', 'surge_m_s', 'yaw_rad_s'])
    for model in ('x1', 'bluerov2_heavy', 'falcon'):
        for axis in (0, 5):
            run(model, axis, writer)
    if args.csv:
        args.csv.close()


if __name__ == '__main__':
    main()
