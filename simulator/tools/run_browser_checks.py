"""Run browser smoke scripts against a simulator started on free ports and print a pass/fail table.

Usage (from the simulator directory):
  python tools/run_browser_checks.py                      # the default checks
  python tools/run_browser_checks.py browser_menu_smoke   # only the named scripts
  python tools/run_browser_checks.py --list

Each script gets a freshly started server, so rooms and vehicle state never leak between scripts. The ports
are handed to the scripts through ROV_HTTP_PORT / ROV_WS_PORT (see _browser.py). Logs are written to
output/browser-checks/.
"""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
LOGS = ROOT / 'output' / 'browser-checks'
# Checks that need nothing but a stock server. Performance and visual review scripts are not pass/fail checks
# and browser_expedition_perf.py starts its own fixture server, so they only run when named explicitly.
# browser_input_smoke.py asserts RC packets carry no assist fields, which needs a host that predates flight
# assistance; run it by name against such a host. browser_collection_storage.py needs the archive written by
# `node desktop/test_collection_store.cjs`, and browser_campaign_smoke.py records video (Playwright ffmpeg).
DEFAULT_CHECKS = (
    'browser_smoke',
    'browser_menu_smoke',
    'browser_menu_gamepad_smoke',
    'browser_gamepad_matrix_smoke',
    'browser_slow_render_smoke',
    'browser_connection_smoke',
    'browser_hud_smoke',
    'browser_overlay_smoke',
    'browser_camera_smoke',
    'browser_camera_input_smoke',
    'browser_attitude_smoke',
    'browser_pilot_guide_smoke',
    'browser_collection_storage',
    'browser_audio_smoke',
    'browser_audio_review_smoke',
    'browser_mission_smoke',
    'browser_gameplay_smoke',
    'browser_expedition_smoke',
    'browser_paint_smoke',
    'browser_campaign_smoke',
    'observation_smoke',
    # Starts its own server with a private instructor code so it can inject link faults.
    'browser_link_smoke',
    'browser_vehicle_assets_smoke',
)


def available_scripts():
    names = [path.stem for path in sorted(TOOLS.glob('browser_*.py'))]
    names.append('observation_smoke')
    return names


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def start_server(log_path):
    ports = {'http': free_port(), 'ws': free_port(), 'rpc': free_port()}
    command = [sys.executable, '-m', 'qysim.server', '--http-port', str(ports['http']),
               '--ws-port', str(ports['ws']), '--rpc-port', str(ports['rpc'])]
    log = open(log_path, 'w', encoding='utf-8')
    process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{ports['http']}/", timeout=2).close()
            return process, log, ports
        except OSError:
            time.sleep(0.5)
    stop_server(process, log)
    raise RuntimeError(f'Simulator did not start; see {log_path}')


def stop_server(process, log):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    log.close()


def stop_script(child):
    """Kill a timed-out script together with the browser processes it started."""
    if os.name == 'posix':
        os.killpg(child.pid, signal.SIGKILL)
    else:
        child.kill()
    child.wait()


def script_environment(ports):
    env = dict(os.environ)
    env['ROV_HTTP_PORT'] = str(ports['http'])
    env['ROV_WS_PORT'] = str(ports['ws'])
    # browser_audio_smoke.py screenshots a comparison server; without one, compare against the same server.
    env.setdefault('ROV_BEFORE_HTTP_PORT', str(ports['http']))
    env.setdefault('ROV_BEFORE_WS_PORT', str(ports['ws']))
    env['PYTHONUNBUFFERED'] = '1'
    return env


def run_script(name, limit):
    """Run one script against its own server. Returns (status, seconds, detail)."""
    started = time.monotonic()
    try:
        process, log, ports = start_server(LOGS / f'{name}.server.log')
    except RuntimeError as error:
        return 'ERROR', time.monotonic() - started, str(error)
    output_path = LOGS / f'{name}.log'
    try:
        with open(output_path, 'w', encoding='utf-8') as output:
            child = subprocess.Popen([sys.executable, str(TOOLS / f'{name}.py')], cwd=ROOT, stdout=output,
                                     stderr=subprocess.STDOUT, env=script_environment(ports),
                                     start_new_session=True)
            try:
                code = child.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                stop_script(child)
                return 'TIMEOUT', time.monotonic() - started, f'exceeded {limit} s'
    finally:
        stop_server(process, log)
    if code == 0:
        return 'PASS', time.monotonic() - started, ''
    return 'FAIL', time.monotonic() - started, last_line(output_path)


def last_line(path):
    lines = [line.strip() for line in path.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip()]
    for line in reversed(lines):
        if 'Error' in line or 'error' in line or 'Timeout' in line:
            return line[:160]
    return lines[-1][:160] if lines else 'no output'


def print_table(results):
    width = max(len(name) for name, *_ in results)
    print()
    print(f"{'script'.ljust(width)}  result   seconds  detail")
    for name, status, seconds, detail in results:
        print(f'{name.ljust(width)}  {status.ljust(7)}  {seconds:7.1f}  {detail}')
    passed = sum(1 for _, status, *_ in results if status == 'PASS')
    print(f'\n{passed}/{len(results)} passed. Logs: {LOGS}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('scripts', nargs='*', help='script names without .py; default is the standard check list')
    parser.add_argument('--list', action='store_true', help='list runnable scripts and exit')
    parser.add_argument('--timeout', type=int, default=900, help='seconds allowed per script (default 900)')
    args = parser.parse_args()
    known = available_scripts()
    if args.list:
        for name in known:
            print(name + ('' if name in DEFAULT_CHECKS else '  (only when named)'))
        return 0
    names = [name.removesuffix('.py') for name in args.scripts] or list(DEFAULT_CHECKS)
    unknown = [name for name in names if name not in known]
    if unknown:
        parser.error(f"unknown script(s): {', '.join(unknown)}; use --list")
    LOGS.mkdir(parents=True, exist_ok=True)
    results = []
    for name in names:
        print(f'Running {name} ...', flush=True)
        status, seconds, detail = run_script(name, args.timeout)
        print(f'  {status} in {seconds:.0f} s', flush=True)
        results.append((name, status, seconds, detail))
    print_table(results)
    return 0 if all(status == 'PASS' for _, status, *_ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
