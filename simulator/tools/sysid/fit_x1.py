"""Fit X1 suggestions from a pool folder. Never writes qysim/vehicles.py.

Reads timing.csv, coast.csv or video.csv, yaw.csv, an optional confirmed OSD box,
and thrust.csv. Absolute mass and drag are reported only when the thrust scale,
dry mass, motor time constant and bias are all present in the manifest. Missing
scales stay blank instead of being filled with the catalogue's provisional numbers.
"""
import json
from pathlib import Path

import numpy as np

from qysim.physics import Vehicle

from .core import AXES, fit_axis, fit_track, plot, read_csv, rollout
from .field import (
    coast_metrics,
    cross_time,
    read_table,
    steady_speed,
    summarise_speeds,
    track_rows,
    yaw_rates,
)
from .osd import load_image, read_frame, require_roi, write_png

STRINGS = {
    'schema': 'Unsupported manifest schema.',
    'vehicle': 'fit-x1 only reads x1 recordings.',
    'nothing': 'The folder has no timing.csv, coast marks, yaw.csv, OSD or motion.csv.',
    'skip_fit': 'Absolute fit skipped: need thrust.csv plus manifest dry_mass_kg, motor_tau_s and bias_force_n.',
    'speed_warn': 'Open-loop timing and the fitted steady speed differ by more than 10%.',
    'fast': 'A pass is faster than 5 m/s; check the distance unit and the stopwatch.',
    'position': 'position (m)',
    'position_residual': 'position residual (m)',
    'velocity': 'velocity (m/s)',
    'velocity_residual': 'residual (m/s)',
    'snippet_title': '建議稿，不要貼進 qysim/vehicles.py，除非審查者接受來源等級。',
    'snippet_none': 'None 表示這次沒有辨識，不能拿來覆寫目錄裡的現值。',
    'snippet_quad': '目錄的 quadratic_drag 若仍是 None，模擬會用 vmax 回推阻尼；兩項要一起看，不能只改一邊。',
    'snippet_motor': 'thruster_max 是軸向力除以目前配置幾何，幾何仍是暫定值，所以來源等級是 estimated。',
}


def load_manifest(source):
    path = Path(source) / 'manifest.json'
    if not path.exists():
        return {}
    meta = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(meta, dict):
        raise ValueError(STRINGS['schema'])
    if meta.get('schema_version') not in (None, 1):
        raise ValueError(STRINGS['schema'])
    if meta.get('vehicle') not in (None, 'x1'):
        raise ValueError(STRINGS['vehicle'])
    return meta


def _evidence(meta):
    if meta.get('synthetic') is True:
        return 'estimated', 'fit-x1 synthetic fixture; not an X1 measurement'
    if meta.get('synthetic') is False:
        return 'measured', 'fit-x1 own recording; see the run manifest'
    return 'estimated', 'fit-x1; manifest did not set synthetic, so this is not labelled measured'


def _bias_map(meta):
    raw = meta.get('bias_force_n')
    if not isinstance(raw, dict):
        return None
    try:
        return {axis: float(raw[axis]) for axis in AXES}
    except (KeyError, TypeError, ValueError):
        return None


def _scales(meta):
    try:
        dry = float(meta['dry_mass_kg'])
        tau = float(meta['motor_tau_s'])
    except (KeyError, TypeError, ValueError):
        return None
    bias = _bias_map(meta)
    if dry <= 0 or tau <= 0 or bias is None or not np.isfinite([dry, tau, *bias.values()]).all():
        return None
    return dry, tau, bias


def _series(samples):
    time = np.array([sample['time_s'] for sample in samples], float)
    position = np.array([sample['position_m'] for sample in samples], float)
    command = np.array([sample['command'] for sample in samples], float)
    return time, position, command


def _rise_time(time, velocity, start, end):
    segment = velocity[start:end]
    if len(segment) < 8:
        return None
    tail = segment[int(len(segment) * 0.8):]
    plateau = float(np.median(tail))
    if abs(plateau) < 1e-4:
        return None
    level = 0.98 * abs(plateau)
    for index in range(start + 1, end):
        if abs(velocity[index]) >= level:
            left = abs(float(velocity[index - 1]))
            right = abs(float(velocity[index]))
            span = right - left
            frac = 0.0 if span == 0 else (level - left) / span
            frac = min(1.0, max(0.0, float(frac)))
            crossed = time[index - 1] + frac * (time[index] - time[index - 1])
            return float(crossed - time[start])
    return None


def _command_span(command, index):
    end = index + 1
    while end < len(command) and command[end] == command[index]:
        end += 1
    return end


def _model_notes(samples, velocity, curves, fitted):
    """Rise time, coast 1/e time and steady speed from the identified trajectory."""
    time, _position, command = _series(samples)
    notes = {'rise_time_s': {}, 'model_decay_time_s': {}, 'steady_speed_m_s': {}}
    linear = fitted['linear_drag']
    quadratic = fitted['quadratic_drag']
    for direction, sign in (('positive', 1.0), ('negative', -1.0)):
        hits = np.where(np.isclose(command, sign) & (np.r_[0.0, command[:-1]] != sign))[0]
        if len(hits):
            start = int(hits[0])
            end = _command_span(command, start)
            notes['rise_time_s'][direction] = _rise_time(time, velocity, start, end)
        coef = curves[direction]['coefficients']
        force = sign * float(sum(coef))
        notes['steady_speed_m_s'][direction] = float(steady_speed(force, linear, quadratic))
    decays = {}
    for metric in coast_metrics(samples):
        if not metric['full_stick']:
            continue
        start = metric['release_index']
        limit = abs(float(velocity[start])) / np.e
        crossed = cross_time(time, velocity, start, limit)
        if crossed is None:
            continue
        name = 'positive' if metric['previous_command'] > 0 else 'negative'
        decays[name] = float(crossed - time[start])
    notes['model_decay_time_s'] = decays
    mass = fitted['added_mass'] + fitted.get('_dry_mass', 0.0)
    if linear > 0:
        notes['low_speed_time_constant_s'] = float(mass / linear)
    return notes


def _fit_tracks(tracks, calibration, dry, tau, bias, output):
    fitted = {}
    rows_by_axis = {}
    for axis, samples in tracks.items():
        anchor = [row for row in calibration if row['axis'] == axis]
        result, predicted, residual = fit_track(samples, anchor, dry, tau, bias[axis])
        result['_dry_mass'] = dry
        time, position, command = _series(samples)
        curves = result['thrust_curve']
        params = [dry + result['added_mass'], result['linear_drag'], result['quadratic_drag']]
        velocity, _again = rollout(
            time, command, 0.0, params, curves, tau, bias[axis], position[0])
        result.update(_model_notes(samples, velocity, curves, result))
        result.pop('_dry_mass', None)
        plot(output / f'{axis}-overlay.png', time, position, predicted, STRINGS['position'])
        plot(output / f'{axis}-residual.png', time, position, predicted, STRINGS['position_residual'], True)
        fitted[axis] = result
    return fitted


def _fit_motion(rows, calibration, dry, tau, bias, output):
    fitted = {}
    for axis in AXES:
        group = [row for row in rows if row['axis'] == axis]
        if not group:
            continue
        anchor = [row for row in calibration if row['axis'] == axis]
        result, simulated, _residual = fit_axis(group, anchor, dry, tau, bias[axis])
        time = np.array([float(row['time_s']) for row in group])
        velocity = np.array([float(row['velocity_m_s']) for row in group])
        plot(output / f'{axis}-overlay.png', time, velocity, simulated, STRINGS['velocity'])
        plot(output / f'{axis}-residual.png', time, velocity, simulated, STRINGS['velocity_residual'], True)
        curves = result['thrust_curve']
        notes = {'rise_time_s': {}, 'model_decay_time_s': {}, 'steady_speed_m_s': {}}
        for direction, sign in (('positive', 1.0), ('negative', -1.0)):
            coef = curves[direction]['coefficients']
            notes['steady_speed_m_s'][direction] = float(
                steady_speed(sign * float(sum(coef)), result['linear_drag'], result['quadratic_drag']))
        if result['linear_drag'] > 0:
            notes['low_speed_time_constant_s'] = float((dry + result['added_mass']) / result['linear_drag'])
        result.update(notes)
        fitted[axis] = result
    return fitted


def _candidates(fitted):
    reference = Vehicle()
    result = {}
    for index, axis in enumerate(AXES):
        if axis not in fitted:
            continue
        result[axis] = {}
        for direction in ('positive', 'negative'):
            coef = fitted[axis]['thrust_curve'][direction]['coefficients']
            scale = reference.authority[index]
            result[axis][direction] = float(sum(coef) / scale * reference.p.thruster_max)
    return result


def _read_manual_osd(path):
    readings = []
    for row in read_table(path):
        depth = row.get('depth_m', '')
        heading = row.get('heading_deg', '')
        readings.append({
            'time_s': float(row['time_s']),
            'depth_m': None if depth == '' else float(depth),
            'heading_deg': None if heading == '' else float(heading),
            'depth_confidence': 1.0,
            'heading_confidence': 1.0,
        })
    return readings


def _read_osd_images(source, roi, output):
    index_path = source / 'osd_index.csv'
    video = source / 'osd.mp4'
    readings = []
    first = None
    if index_path.exists():
        folder = source / 'osd'
        for row in read_table(index_path):
            image = load_image(folder / row['file'])
            if first is None:
                first = image
            reading = read_frame(image, roi)
            readings.append({
                'time_s': float(row['time_s']),
                'depth_m': reading['depth_value'],
                'heading_deg': reading['heading_value'],
                'depth_confidence': reading['depth_confidence'],
                'heading_confidence': reading['heading_confidence'],
            })
    elif video.exists():
        import cv2
        capture = cv2.VideoCapture(str(video))
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            image = frame[:, :, ::-1]
            if first is None:
                first = image
            reading = read_frame(image, roi)
            readings.append({
                'time_s': index / fps,
                'depth_m': reading['depth_value'],
                'heading_deg': reading['heading_value'],
                'depth_confidence': reading['depth_confidence'],
                'heading_confidence': reading['heading_confidence'],
            })
            index += 1
        capture.release()
    if first is not None:
        for name in ('depth', 'heading'):
            box = roi.get(name)
            if not box:
                continue
            x, y = int(box['x']), int(box['y'])
            crop = first[y:y+int(box['height']), x:x+int(box['width'])]
            write_png(output / f'osd-{name}-crop.png', crop)
    return readings


def _osd_block(source, output):
    manual = source / 'osd_readings.csv'
    if manual.exists():
        readings = _read_manual_osd(manual)
        origin = 'osd_readings.csv'
    else:
        roi_path = source / 'osd_roi.json'
        if not roi_path.exists():
            return None
        roi = require_roi(json.loads(roi_path.read_text(encoding='utf-8')))
        readings = _read_osd_images(source, roi, output)
        origin = 'osd'
    low = 0
    for reading in readings:
        if reading['depth_m'] is None or reading['depth_confidence'] < 0.8:
            low += 1
        if reading['heading_deg'] is None or reading['heading_confidence'] < 0.8:
            low += 1
    _write_readings(output / 'osd_readings.csv', readings)
    return {'frames': len(readings), 'low_confidence': low, 'source': origin, 'readings': readings}


def _write_readings(path, readings):
    if not readings:
        return
    with path.open('w', newline='', encoding='utf-8') as stream:
        fields = ['time_s', 'depth_m', 'heading_deg', 'depth_confidence', 'heading_confidence']
        writer = csv_writer(stream, fields)
        for reading in readings:
            writer.writerow([reading[name] for name in fields])


def csv_writer(stream, fields):
    import csv
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(fields)
    return writer


def _fmt(value):
    if value is None:
        return 'None'
    return format(float(value), '.6g')


def _tuple(values):
    return '(' + ', '.join(_fmt(value) for value in values) + ')'


def _snippet(suggestions):
    lines = [
        '# ' + STRINGS['snippet_title'],
        '# evidence level: ' + suggestions['evidence_level'],
        '# source: ' + suggestions['source'],
        '# ' + STRINGS['snippet_none'],
        '# ' + STRINGS['snippet_quad'],
    ]
    if suggestions.get('added_mass') is not None:
        lines.append('added_mass = ' + _tuple(suggestions['added_mass']) + '  # kg')
        lines.append('linear_drag = ' + _tuple(suggestions['linear_drag']) + '  # N s/m')
        lines.append('quadratic_drag = ' + _tuple(suggestions['quadratic_drag']) + '  # N s^2/m^2')
    if suggestions.get('vmax') is not None:
        lines.append('vmax = ' + _tuple(suggestions['vmax']) + '  # m/s，開迴路正方向計時')
    if suggestions.get('wmax_yaw_rad_s') is not None:
        lines.append('wmax_yaw = ' + _fmt(suggestions['wmax_yaw_rad_s']) + '  # rad/s，僅偏航')
    if suggestions.get('thruster_max_n') is not None:
        lines.append('# ' + STRINGS['snippet_motor'])
        lines.append('thruster_max = ' + _fmt(suggestions['thruster_max_n']) + '  # N，幾何換算，estimated')
    elif suggestions.get('thruster_max_candidates_n'):
        lines.append('# 各軸換算的 thruster_max 不一致，不要取單一值。候選見 report.json。')
    return '\n'.join(lines) + '\n'


def _markdown(report, snippet):
    lines = ['# X1 擬合報告', '']
    if report.get('synthetic') is True:
        lines.append('**這批是合成資料，不是 X1 實測，不能把來源等級升成 measured，也不能寫進 vehicles.py。**')
        lines.append('')
    lines.append('本工具只產出建議。`applied_to_vehicles_py` 為 false。')
    lines.append('')
    if report['warnings']:
        lines.append('## 注意')
        lines.append('')
        for warning in report['warnings']:
            lines.append('- ' + warning)
        lines.append('')
    lines.append('## 計時表極速')
    lines.append('')
    lines.append('| 軸 | 檔位 | 方向 | 次數 | 速度 m/s | 用來建議 vmax |')
    lines.append('|---|---|---|---:|---:|---|')
    for row in report['terminal_speed']:
        used = '是' if row['used_for_vmax'] else '否'
        lines.append(
            f"| {row['axis']} | {row['gear']} | {row['direction']} | {row['samples']} | "
            f"{row['speed_m_s']:.4f} | {used} |")
    if not report['terminal_speed']:
        lines.append('| — | — | — | — | — | 沒有 timing.csv |')
    lines.append('')
    lines.append('只有 manifest 的 `open_loop_gear`（預設 A）正方向拿來建議 vmax。其他檔位可能是速度閉迴路，不拿來擬合阻尼。')
    lines.append('')
    lines.append('## 鬆桿滑行')
    lines.append('')
    lines.append('| 軸 | 先前命令 | 滑行距離 m | 位移 63% 時間 s | 錄到的時長 s | 已停穩 |')
    lines.append('|---|---:|---:|---:|---:|---|')
    for row in report['coast']:
        glide = '—' if row['glide_time_s'] is None else f"{row['glide_time_s']:.3f}"
        settled = '是' if row['settled'] else '否'
        lines.append(
            f"| {row['axis']} | {row['previous_command']:.2f} | {row['coast_distance_m']:.4f} | "
            f"{glide} | {row['coast_duration_s']:.2f} | {settled} |")
    if not report['coast']:
        lines.append('| — | — | — | — | — | 沒有逐格標記 |')
    lines.append('')
    lines.append('滑行距離是標記點的位移，不是外推。位移達到全程 63%（1−1/e）的時間，在線性阻尼時等於時間常數；有二次阻尼時它只是等價的一階時間，真正的阻尼見下面的擬合。')
    lines.append('')
    lines.append('## 偏航率')
    lines.append('')
    lines.append('| 檔位 | 方向 | 圈數 | 時間 s | 角速度 deg/s | 鬆桿角度 deg | 用來建議 |')
    lines.append('|---|---|---:|---:|---:|---:|---|')
    for row in report['yaw']:
        coast = '—' if row['coast_deg'] is None else f"{row['coast_deg']:.2f}"
        used = '是' if row['used_for_wmax'] else '否'
        lines.append(
            f"| {row['gear']} | {row['direction']} | {row['revolutions']:g} | {row['time_s']:.4f} | "
            f"{row['rate_deg_s']:.3f} | {coast} | {used} |")
    if not report['yaw']:
        lines.append('| — | — | — | — | — | — | 沒有 yaw.csv |')
    lines.append('')
    lines.append('圈數除以時間只得到穩態偏航率。單一個鬆桿角度不能分開轉動慣量與阻尼，所以不建議改 inertia。')
    lines.append('')
    lines.append('## App 深度與航向')
    lines.append('')
    osd = report.get('osd')
    if not osd:
        lines.append('沒有已確認的框選，或沒有 OSD 檔。要讀數值時，先把 `osd_roi.json` 的 `confirmed` 設為 true。')
    else:
        lines.append(f"來源 `{osd['source']}`，{osd['frames']} 格，低信心欄位 {osd['low_confidence']}。")
        lines.append(
            '請對一下 `osd-depth-crop.png` 與 `osd-heading-crop.png`。'
            '不對的話改輸出的 `osd_readings.csv`，放回資料夾後重跑，工具會改信那份人工表。')
    lines.append('')
    lines.append('## 最小平方')
    lines.append('')
    fit = report.get('fit')
    if not fit:
        lines.append(STRINGS['skip_fit'])
    else:
        lines.append(f"速度或位置來源：`{fit['source']}`。模型與 `core.fit_axis` 相同：乾重與附加質量、線性阻尼、二次阻尼，推力曲線先由 `thrust.csv` 決定。")
        lines.append('信賴區間是條件在推力校正、乾重、motor_tau、bias 上的局部 95% Student-t，不含那些量本身的誤差。')
        lines.append('')
        lines.append('| 軸 | 附加質量 kg | 線性阻尼 | 二次阻尼 | 位置或速度 RMSE | 正方向 1/e 時間 s |')
        lines.append('|---|---:|---:|---:|---:|---:|')
        for axis in AXES:
            row = fit['axes'].get(axis)
            if not row:
                continue
            rmse = row.get('position_rmse_m', row.get('velocity_rmse_m_s'))
            decay = row.get('model_decay_time_s', {}).get('positive')
            decay_text = '—' if decay is None else f'{decay:.3f}'
            lines.append(
                f"| {axis} | {row['added_mass']:.4f} | {row['linear_drag']:.4f} | "
                f"{row['quadratic_drag']:.4f} | {rmse:.5f} | {decay_text} |")
        lines.append('')
        lines.append('低速時間常數 (乾重+附加質量)/線性阻尼 與上表的 1/e 時間在二次阻尼大時不會一樣。1/e 是擬合軌跡在滿桿鬆開當下算的。')
    lines.append('')
    lines.append('## vehicles.py 建議')
    lines.append('')
    lines.append('```python')
    lines.append(snippet.rstrip('\n'))
    lines.append('```')
    lines.append('')
    lines.append('維持不動的項目：' + '、'.join(report['suggestions']['leave_unchanged']) + '。')
    lines.append('來源等級只會是 measured、published 或 estimated。這支工具不會把其他機型或目錄暫定值寫成 X1 的實測。')
    lines.append('')
    return '\n'.join(lines)


def _jsonify(value):
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError('non-finite fit result')
        return number
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(type(value).__name__)


def _tracks_from(source):
    if (source / 'coast.csv').exists():
        return 'coast.csv', track_rows(read_table(source / 'coast.csv'))
    if (source / 'video.csv').exists():
        return 'video.csv', track_rows(read_table(source / 'video.csv'))
    return None, None


def _attach_model_decay(report_coast, fitted):
    """Copy the identified 1/e time onto the matching full-stick coast row."""
    for row in report_coast:
        axis_fit = fitted.get(row['axis']) if fitted else None
        if not axis_fit or not row['full_stick']:
            row['model_decay_time_s'] = None
            continue
        name = 'positive' if row['previous_command'] > 0 else 'negative'
        row['model_decay_time_s'] = axis_fit.get('model_decay_time_s', {}).get(name)


def fit_x1(source, output=None):
    """Write REPORT.md, report.json and residual plots. Returns the report dict."""
    source = Path(source)
    if output is None:
        output = source / 'fit-report'
    output = Path(output)
    if output.resolve() == source.resolve():
        output = source / 'fit-report'
    output.mkdir(parents=True, exist_ok=True)
    meta = load_manifest(source)
    level, source_text = _evidence(meta)
    gear = str(meta.get('open_loop_gear') or 'A')
    warnings = []
    if meta.get('synthetic') is True:
        warnings.append('合成資料只驗證管線能不能回收已知參數，不是實測證據。')
    summary = []
    if (source / 'timing.csv').exists():
        summary = summarise_speeds(read_table(source / 'timing.csv'), gear)
        for row in summary:
            if abs(row['speed_m_s']) > 5:
                warnings.append(STRINGS['fast'])
                break
    coast_report = []
    track_name, tracks = _tracks_from(source)
    if tracks:
        for axis, samples in tracks.items():
            for metric in coast_metrics(samples):
                coast_report.append({'axis': axis, **metric})
    yaw = []
    if (source / 'yaw.csv').exists():
        yaw = yaw_rates(read_table(source / 'yaw.csv'), gear)
    osd = _osd_block(source, output)
    fit_block = None
    fitted = None
    scales = _scales(meta)
    thrust_path = source / 'thrust.csv'
    motion_path = source / 'motion.csv'
    can_fit = scales is not None and thrust_path.exists() and (tracks or motion_path.exists())
    if not can_fit and (tracks or motion_path.exists() or thrust_path.exists()):
        warnings.append(STRINGS['skip_fit'])
    if can_fit:
        dry, tau, bias = scales
        calibration = read_csv(thrust_path)
        if tracks:
            fitted = _fit_tracks(tracks, calibration, dry, tau, bias, output)
            origin = track_name
        else:
            fitted = _fit_motion(read_csv(motion_path), calibration, dry, tau, bias, output)
            origin = 'motion.csv'
        for axis, row in fitted.items():
            for item in summary:
                if item['axis'] != axis or item['gear'] != gear:
                    continue
                model = row['steady_speed_m_s'][item['direction']]
                if abs(model) > 1e-6 and abs(item['speed_m_s'] / model - 1) > 0.1:
                    warnings.append(STRINGS['speed_warn'] + f' {axis} {item["direction"]}')
        fit_block = {'source': origin, 'axes': fitted}
    _attach_model_decay(coast_report, fitted)
    if not summary and not coast_report and not yaw and not osd and not fit_block:
        raise ValueError(STRINGS['nothing'])
    suggestions = _suggestions(meta, level, source_text, summary, yaw, fitted, gear)
    snippet = _snippet(suggestions)
    report = {
        'applied_to_vehicles_py': False,
        'synthetic': meta.get('synthetic'),
        'open_loop_gear': gear,
        'warnings': warnings,
        'terminal_speed': summary,
        'coast': coast_report,
        'yaw': yaw,
        'osd': osd,
        'fit': fit_block,
        'suggestions': suggestions,
        'vehicles_py_snippet': snippet,
    }
    (output / 'report.json').write_text(
        json.dumps(_jsonify(report), indent=2, ensure_ascii=False, allow_nan=False) + '\n',
        encoding='utf-8')
    (output / 'REPORT.md').write_text(_markdown(report, snippet), encoding='utf-8')
    (output / 'vehicles.py.suggestion').write_text(snippet, encoding='utf-8')
    return report


def _suggestions(meta, level, source_text, summary, yaw, fitted, gear):
    leave = [
        'mass', 'inertia', 'motor_tau', 'net_buoyancy', 'gm', 'reverse_ratio',
        'thruster layout', 'rotational drag',
    ]
    suggestions = {
        'evidence_level': level,
        'source': source_text,
        'dry_mass_kg_input': meta.get('dry_mass_kg'),
        'added_mass': None,
        'linear_drag': None,
        'quadratic_drag': None,
        'vmax': None,
        'wmax_yaw_rad_s': None,
        'thruster_max_n': None,
        'thruster_max_consistent': False,
        'thruster_max_candidates_n': None,
        'leave_unchanged': leave,
        'evidence': {
            'catalogue_note': {
                'level': level,
                'source': source_text,
            },
        },
    }
    speeds = [row for row in summary if row['used_for_vmax']]
    by_axis = {row['axis']: row['speed_m_s'] for row in speeds}
    if by_axis:
        suggestions['vmax'] = [by_axis.get(axis) for axis in AXES]
        suggestions['evidence']['vmax'] = {'level': level, 'source': source_text + '; timing.csv open-loop positive'}
    for row in yaw:
        if row['used_for_wmax']:
            suggestions['wmax_yaw_rad_s'] = row['rate_rad_s']
            suggestions['evidence']['wmax_yaw'] = {
                'level': level, 'source': source_text + '; yaw.csv open-loop positive'}
            break
    if fitted and all(axis in fitted for axis in AXES):
        suggestions['added_mass'] = [fitted[axis]['added_mass'] for axis in AXES]
        suggestions['linear_drag'] = [fitted[axis]['linear_drag'] for axis in AXES] + [None, None, None]
        suggestions['quadratic_drag'] = [fitted[axis]['quadratic_drag'] for axis in AXES] + [None, None, None]
        suggestions['evidence']['added_mass'] = {
            'level': level, 'source': source_text + '; thrust.csv and position or velocity track'}
        suggestions['evidence']['linear_drag'] = suggestions['evidence']['added_mass']
        suggestions['evidence']['quadratic_drag'] = suggestions['evidence']['added_mass']
        candidates = _candidates(fitted)
        suggestions['thruster_max_candidates_n'] = candidates
        values = [candidates[axis][direction] for axis in AXES for direction in ('positive', 'negative')]
        median = float(np.median(values))
        consistent = median > 0 and (max(values) - min(values)) / median < 0.1
        suggestions['thruster_max_consistent'] = bool(consistent)
        suggestions['evidence']['thruster_max'] = {
            'level': 'estimated',
            'source': source_text + '; axis force divided by the provisional allocation geometry',
        }
        if consistent:
            suggestions['thruster_max_n'] = median
    return suggestions
