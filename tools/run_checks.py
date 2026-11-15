"""Run shared test tiers, optionally selected from the diff against main, with JSON timings."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from check_matrix import ROOT, changed_paths, unit_checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=('quick', 'full'), default='quick')
    parser.add_argument('--changed', action='store_true')
    parser.add_argument('--base', default='origin/main')
    parser.add_argument('--kind', choices=('all', 'unit', 'node', 'browser'), default='all')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    paths = changed_paths(args.base) if args.changed else None
    commands = []
    if args.kind in ('all', 'unit'):
        commands.append(('check_matrix', [sys.executable, '-m', 'unittest', 'discover',
                                          '-s', str(ROOT / 'tools'), '-p', 'test_*.py']))
    if args.kind in ('all', 'unit'):
        for name in unit_checks(args.tier, paths):
            commands.append((name, [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', f'{name}.py']))
    if args.kind in ('all', 'node') and (paths is None or any(
        p.startswith(('simulator/viewer/', 'simulator/desktop/', 'simulator/tests/', 'tools/', '.github/'))
        for p in paths
    )):
        for path in sorted((ROOT / 'simulator/tests').glob('*.mjs')):
            commands.append((path.name, ['node', '--test', str(path)]))
        for path in sorted((ROOT / 'simulator/desktop').glob('test_*.cjs')):
            commands.append((path.name, ['node', str(path)]))
    if args.kind in ('all', 'browser'):
        command = [sys.executable, 'tools/run_browser_checks.py', '--tier', args.tier]
        if args.changed:
            command += ['--changed', '--base', args.base]
        commands.append(('browser', command))
    results = []
    logs = ROOT / 'simulator/output/checks' / args.tier
    logs.mkdir(parents=True, exist_ok=True)
    for name, command in commands:
        started = time.monotonic()
        with (logs / f'{name}.log').open('w') as output:
            result = subprocess.run(command, cwd=ROOT / 'simulator', stdout=output, stderr=subprocess.STDOUT)
        row = {'name': name, 'seconds': round(time.monotonic() - started, 2), 'code': result.returncode}
        results.append(row)
        print(json.dumps(row), flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2) + '\n')
    return int(any(row['code'] for row in results))


if __name__ == '__main__':
    sys.exit(main())
