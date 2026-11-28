"""Calibrated single-axis identification using trajectory residuals and local 95% intervals."""
import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.stats import t as student_t

from qysim.controller import FlightController
from qysim.physics import Vehicle, q_from_euler

AXES = ('surge', 'sway', 'heave')
STRINGS = {
    'finite': 'Need finite samples and strictly increasing time.',
    'anchor': 'Independent thrust calibration with multiple levels in both directions is required.',
    'rank': 'Unidentifiable fit: collect more command levels, step and coast data.',
    'schema': 'Unsupported manifest schema or axis.',
    'observed': 'observed',
    'simulation': 'simulation',
    'time': 'time (s)',
    'velocity': 'velocity (m/s)',
    'residual': 'residual (m/s)',
    'depth': 'depth (m)',
    'heading': 'heading (deg)',
    'interval': 'Local 95% Student-t; motion intervals conditional on thrust calibration, mass, tau and bias.',
    'physical': 'Nonphysical fit or active parameter bound; review experiment and model.',
}


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def numeric(rows, keys):
    data = np.array([[float(row[k]) for k in keys] for row in rows])
    if len(data) < 3 or not np.isfinite(data).all():
        raise ValueError(STRINGS['finite'])
    return data.T


def time_check(time):
    if np.any(np.diff(time) <= 0):
        raise ValueError(STRINGS['finite'])


def interval(jac, residual, estimate):
    """Local Student-t interval, conditional on calibration/model and independent errors."""
    if np.linalg.matrix_rank(jac) != len(estimate) or len(residual) <= len(estimate):
        raise ValueError(STRINGS['rank'])
    dof = len(residual) - len(estimate)
    covariance = np.linalg.inv(jac.T @ jac) * (residual @ residual) / dof
    width = student_t.ppf(.975, dof) * np.sqrt(np.maximum(np.diag(covariance), 0))
    return np.column_stack((estimate - width, estimate + width)).tolist()


def fit_thrust(rows):
    """Piecewise signed quadratic F = a*u + b*u*abs(u); independent directions."""
    u, force = numeric(rows, ('command', 'force_n'))
    if np.any(abs(u) > 1):
        raise ValueError(STRINGS['anchor'])
    curves = {}
    for sign, name in ((1, 'positive'), (-1, 'negative')):
        select = u * sign > 0
        x = abs(u[select])
        y = force[select] * sign
        design = np.column_stack((x, x*x))
        if len(x) < 4 or np.linalg.matrix_rank(design) < 2:
            raise ValueError(STRINGS['anchor'])
        coef = np.linalg.lstsq(design, y, rcond=None)[0]
        if min(coef[0], coef[0] + 2*coef[1]) <= 0:
            raise ValueError(STRINGS['physical'])
        residual = design @ coef - y
        curves[name] = {'coefficients': coef.tolist(), 'ci95': interval(design, residual, coef)}
    return curves


def thrust(u, curves):
    name = 'positive' if u >= 0 else 'negative'
    a, b = curves[name]['coefficients']
    return a*u + b*u*abs(u)


def trajectory(time, command, initial, parameters, curves, motor_tau, bias, implicit_drag=False):
    """Isolated force-actuator rig at <= 0.01 s, including archived explicit-Euler records.

    command[i] is held until time[i+1]; every run starts with settled zero thrust.
    """
    mass, linear, quadratic = parameters
    velocity = initial
    force = 0.0
    output = [velocity]
    for start, end, u in zip(time[:-1], time[1:], command[:-1]):
        count = max(1, int(np.ceil((end-start) / .010000001)))
        dt = (end-start) / count
        target = thrust(u, curves)
        for _ in range(count):
            force += (target-force)*min(1.0, dt/motor_tau)
            damping = linear + quadratic * abs(velocity)
            denominator = mass + dt * damping if implicit_drag else mass
            velocity += dt * (force + bias - damping * velocity) / denominator
        output.append(velocity)
    return np.array(output)


def fit_axis(rows, calibration, dry_mass, motor_tau, bias=0.0, implicit_drag=False):
    time, velocity, command = numeric(rows, ('time_s', 'velocity_m_s', 'command'))
    time_check(time)
    if dry_mass <= 0 or motor_tau <= 0 or not np.isfinite([dry_mass, motor_tau, bias]).all():
        raise ValueError(STRINGS['physical'])
    if np.any(abs(command) > 1) or not np.any(command == 0) or not np.any(command != 0):
        raise ValueError(STRINGS['rank'])
    curves = fit_thrust(calibration)

    def residual(parameters):
        return trajectory(time, command, velocity[0], parameters, curves, motor_tau, bias, implicit_drag) - velocity

    fit = least_squares(residual, [dry_mass*1.5, 10, 100],
                        bounds=([dry_mass, 0, 0], [np.inf]*3), x_scale='jac')
    if not fit.success or np.any(fit.active_mask):
        raise ValueError(STRINGS['physical'])
    ci = interval(fit.jac, fit.fun, fit.x)
    mass, linear, quadratic = fit.x
    return {
        'added_mass': float(mass-dry_mass), 'linear_drag': float(linear),
        'quadratic_drag': float(quadratic), 'thrust_curve': curves,
        'ci95': {'added_mass': [x-dry_mass for x in ci[0]], 'linear_drag': ci[1], 'quadratic_drag': ci[2]},
        'velocity_rmse_m_s': float(np.sqrt(np.mean(fit.fun**2))),
    }, velocity + fit.fun, fit.fun


def tether(rows):
    length, dry, wet, diameter, water = numeric(
        rows, ('length_m', 'dry_mass_kg', 'wet_force_n', 'diameter_m', 'water_density_kg_m3'))
    if np.any(length <= 0) or np.any(dry <= 0) or np.any(diameter <= 0) or np.any(water <= 0):
        raise ValueError(STRINGS['physical'])
    area = np.pi*diameter**2/4
    values = {
        'wet_weight_n_m': wet/length,
        'buoyancy_n_m': (dry*9.81-wet)/length,
        'density': dry/(length*area),
        'hydrostatic_residual_n_m': (dry*9.81-wet)/length-water*area*9.81,
    }
    result = {}
    for name, samples in values.items():
        mean = float(np.mean(samples))
        width = float(student_t.ppf(.975, len(samples)-1)*np.std(samples, ddof=1)/np.sqrt(len(samples)))
        result[name] = {'value': mean, 'ci95': [mean-width, mean+width]}
    return result


def controller_replay(rows):
    """Replay fixed depth/heading targets through the existing controller and 6-DOF engine."""
    time, depth, yaw, depth_target, yaw_target = numeric(
        rows, ('time_s', 'depth_m', 'yaw_deg', 'depth_target_m', 'yaw_target_deg'))
    time_check(time)
    vehicle = Vehicle()
    vehicle.s.pos[2] = depth[0]
    vehicle.s.q = q_from_euler(0, 0, np.deg2rad(yaw[0]))
    controller = FlightController(vehicle)
    output = [[depth[0], yaw[0]]]
    for i, duration in enumerate(np.diff(time)):
        count = max(1, int(np.ceil(duration/.010000001)))
        dt = duration/count
        controller.depth_hold = depth_target[i]
        for _ in range(count):
            motors = controller.update(dt, {}, 'A', False, True, np.deg2rad(yaw_target[i]))
            vehicle.step(dt, motors)
        output.append([vehicle.s.pos[2], np.rad2deg(vehicle.euler[2])])
    simulated = np.array(output)
    errors = simulated - np.column_stack((depth, yaw))
    errors[:, 1] = (errors[:, 1]+180) % 360-180
    tracking = np.column_stack((depth-depth_target, (yaw-yaw_target+180) % 360-180))
    return {'depth_rmse_m': float(np.sqrt(np.mean(errors[:, 0]**2))),
            'heading_rmse_deg': float(np.sqrt(np.mean(errors[:, 1]**2))),
            'tracking_rmse': np.sqrt(np.mean(tracking**2, axis=0)).tolist()}, simulated


def plotting_available():
    """Matplotlib is optional (PSF-based licence, outside the core dependency list); without it no PNGs."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def plot(path, time, measured, simulated, label, residual=False):
    if not plotting_available():
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3))
    if residual:
        ax.plot(time, simulated-measured)
        ax.axhline(0, color='black', linewidth=.5)
    else:
        ax.plot(time, measured, label=STRINGS['observed'], linewidth=1)
        ax.plot(time, simulated, label=STRINGS['simulation'], linewidth=1)
        ax.legend()
    ax.set(xlabel=STRINGS['time'], ylabel=label)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def analyze(source, output):
    source, output = Path(source), Path(output)
    meta = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if meta.get('schema_version') != 1 or not isinstance(meta.get('synthetic'), bool):
        raise ValueError(STRINGS['schema'])
    traces = read_csv(source/'motion.csv')
    calibration = read_csv(source/'thrust.csv')
    if any(r['axis'] not in AXES for r in traces + calibration):
        raise ValueError(STRINGS['schema'])
    result = {'synthetic': meta['synthetic'], 'axes': {}, 'interval_method': STRINGS['interval']}
    output.mkdir(parents=True, exist_ok=True)
    for axis in AXES:
        rows = [r for r in traces if r['axis'] == axis]
        anchor = [r for r in calibration if r['axis'] == axis]
        fitted, simulated, residual = fit_axis(
            rows, anchor, meta['dry_mass_kg'], meta['motor_tau_s'], meta['bias_force_n'][axis], meta.get('implicit_drag', False))
        result['axes'][axis] = fitted
        time, velocity = numeric(rows, ('time_s', 'velocity_m_s'))
        plot(output/f'{axis}-overlay.png', time, velocity, simulated, STRINGS['velocity'])
        plot(output/f'{axis}-residual.png', time, velocity, simulated, STRINGS['residual'], True)
    result['tether'] = tether(read_csv(source/'tether.csv'))
    rows = read_csv(source/'control.csv')
    result['controller'], simulated = controller_replay(rows)
    time, depth, yaw = numeric(rows, ('time_s', 'depth_m', 'yaw_deg'))
    plot(output/'depth-overlay.png', time, depth, simulated[:, 0], STRINGS['depth'])
    plot(output/'heading-overlay.png', time, np.rad2deg(np.unwrap(np.deg2rad(yaw))),
         np.rad2deg(np.unwrap(np.deg2rad(simulated[:, 1]))), STRINGS['heading'])
    # Only measured axes are suggested; rotational entries remain explicitly unresolved.
    result['vehicles_py_suggestions'] = {
        key: [result['axes'][axis][key] for axis in AXES] + ([None]*3 if key != 'added_mass' else [])
        for key in ('added_mass', 'linear_drag', 'quadratic_drag')}
    reference = Vehicle()
    result['thruster_max_candidates_n'] = {
        axis: {direction: sum(result['axes'][axis]['thrust_curve'][direction]['coefficients'])
               / reference.authority[i] * reference.p.thruster_max
               for direction in ('positive', 'negative')}
        for i, axis in enumerate(AXES)}
    result['units'] = {'added_mass': 'kg', 'linear_drag': 'N s/m', 'quadratic_drag': 'N s^2/m^2',
                       'thrust_curve': 'N', 'tether_density': 'kg/m^3'}
    result['vehicles_py_suggestions']['tether_density'] = result['tether']['density']['value']
    (output/'report.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return result
