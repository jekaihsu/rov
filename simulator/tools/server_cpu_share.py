"""CPU share of the simulator server process with one viewer connected, per site (Linux /proc only).

Usage (from the simulator directory): python tools/server_cpu_share.py [--sites a,b] [--seconds 20]

Starts `python -m qysim.server` on free ports, joins one player over the WebSocket like the viewer (static_once
caps, receives every state) and measures the server's user + system CPU time over the window: 100 % is one core.
Also reports the state messages per second and their mean size, and the idle share before anyone joins.
"""
import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
TICKS = os.sysconf('SC_CLK_TCK')


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def cpu_seconds(pid):
    fields = Path(f'/proc/{pid}/stat').read_text(encoding='ascii').rsplit(')', 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / TICKS


async def viewer(ws_port, site, seconds, pid):
    async with websockets.connect(f'ws://127.0.0.1:{ws_port}', max_size=None) as ws:
        await ws.send(json.dumps({'type': 'join', 'room_id': f'cpu-{site}', 'name': 'bench', 'model_id': 'x1',
                                  'caps': ['static_once']}))
        await ws.send(json.dumps({'type': 'scenario', 'key': site, 'seed': 1}))
        settle = time.monotonic() + 4
        while time.monotonic() < settle:
            await ws.recv()
        sizes = []
        start_cpu = cpu_seconds(pid)
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            message = await ws.recv()
            if '"type":"state"' in message[:40] or '"type": "state"' in message[:40]:
                sizes.append(len(message))
        elapsed = time.monotonic() - started
        used = cpu_seconds(pid) - start_cpu
        return {'site': site, 'cpu_share_pct': round(used / elapsed * 100, 1),
                'states_per_s': round(len(sizes) / elapsed, 1),
                'state_bytes_mean': int(sum(sizes) / max(1, len(sizes)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sites', default='open_water,harbor_inspection,jacket_inspection,hull_inspection')
    parser.add_argument('--seconds', type=float, default=20)
    args = parser.parse_args()
    http, ws, rpc = free_port(), free_port(), free_port()
    process = subprocess.Popen([sys.executable, '-m', 'qysim.server', '--http-port', str(http), '--ws-port', str(ws),
                                '--rpc-port', str(rpc)], cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{http}/', timeout=2).close()
                break
            except OSError:
                time.sleep(.5)
        before = cpu_seconds(process.pid)
        time.sleep(5)
        print(json.dumps({'idle_cpu_share_pct': round((cpu_seconds(process.pid) - before) / 5 * 100, 1)}), flush=True)
        for site in args.sites.split(','):
            print(json.dumps(asyncio.run(viewer(ws, site, args.seconds, process.pid))), flush=True)
    finally:
        process.terminate()
        process.wait(timeout=10)
    return 0


if __name__ == '__main__':
    sys.exit(main())
