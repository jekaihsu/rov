"""Exercise the actual frozen executable: local assets + live room transport."""
import asyncio
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

import websockets

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / 'simulator/desktop/backend/rov-sim/rov-sim.exe'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exe', type=Path, default=EXE)
EXE = parser.parse_args().exe.resolve()
runtime = ROOT / '.runtime'


def ports():
    sockets = [socket.socket() for _ in range(3)]
    try:
        for s in sockets:
            s.bind(('127.0.0.1', 0))
        return [s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets:
            s.close()


async def check(ws_port):
    async with websockets.connect(f'ws://127.0.0.1:{ws_port}', open_timeout=90) as ws:
        await ws.send(json.dumps({'type': 'join', 'name': 'Desktop smoke', 'model_id': 'falcon'}))
        session = state = paint_result = None
        paint_sent = False
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), 90))
            if msg.get('type') == 'session':
                session = msg
            if msg.get('type') == 'state' and msg.get('vehicle_id') and msg.get('t', 0) > 0:
                state = msg
            if msg.get('type') == 'operation_result' and msg.get('action') == 'paint':
                assert msg.get('ok'), msg
                paint_result = msg
            if session and state:
                assert session['capacity'] == 3, session
                assert state['room']['capacity'] == 3, state['room']
                assert state['model_id'] == 'falcon', state['model_id']
                assert len(state['thrust']) == 5
                assert isinstance(state['paint_marks'], list)
                if not paint_sent:
                    await ws.send(json.dumps({'type': 'operation', 'action': 'paint',
                                              'pos': state['pos'], 'normal': [0, 0, -1],
                                              'radius': .12, 'color': '#f0c75e'}))
                    paint_sent = True
                if paint_result and any(mark['id'] == paint_result['id'] for mark in state['paint_marks']):
                    result = {'session': True, 'model': state['model_id'], 'time': state['t'],
                              'thrusters': len(state['thrust']), 'paint_replicated': True,
                              'room_capacity': state['room']['capacity']}
                    assert session['is_host'], session
                    for mode in ('free_explore', 'inspection_coop'):
                        await ws.send(json.dumps({'type': 'operation', 'action': 'mission_mode', 'mode': mode}))
                        acknowledgement = snapshot = None
                        while time.monotonic() < deadline:
                            reply = json.loads(await asyncio.wait_for(ws.recv(), 30))
                            if reply.get('type') == 'error':
                                raise AssertionError(reply)
                            if reply.get('type') == 'operation_result' and reply.get('action') == 'mission_mode':
                                assert reply.get('ok'), reply
                                acknowledgement = reply['mission']
                                assert acknowledgement['mode'] == mode
                            if reply.get('type') == 'state' and reply.get('mission', {}).get('mode') == mode:
                                snapshot = reply['mission']
                            if acknowledgement and snapshot:
                                expected = 3 if mode == 'inspection_coop' else 0
                                assert len(snapshot['targets']) == expected, snapshot
                                assert [target['id'] for target in snapshot['targets']] == [target['id'] for target in acknowledgement['targets']]
                                assert all(len(target['point']) == 3 for target in snapshot['targets'])
                                break
                        else:
                            raise RuntimeError(f'No mission snapshot for {mode}')
                    result.update(mission_modes=['free_explore', 'inspection_coop'], coop_targets=3)
                    return result
        raise RuntimeError('No live state from frozen backend')


http, ws, rpc = ports()
env = dict(os.environ, PYTHONUTF8='1', NUMBA_CACHE_DIR=str(runtime / 'desktop-smoke-numba'))
with (runtime / 'desktop-backend-smoke.log').open('w', encoding='utf8') as log:
    process = subprocess.Popen([str(EXE), '--host', '127.0.0.1', '--http-port', str(http),
                                '--ws-port', str(ws), '--rpc-port', str(rpc)],
                               cwd=EXE.parent, env=env, stdout=log, stderr=log,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError('Frozen backend exited; see smoke log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{http}/', timeout=1) as response:
                    assert response.status == 200 and b'<html' in response.read()
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError('Frozen HTTP timeout')
        for asset in ('vendor/three/build/three.module.js', 'models/falcon.glb', 'vehicle_models.js'):
            with urllib.request.urlopen(f'http://127.0.0.1:{http}/{asset}', timeout=20) as response:
                payload=response.read()
                assert response.status == 200 and len(payload) > 100
                if asset.endswith('.glb'):
                    assert payload[:4] == b'glTF'
        result = asyncio.run(check(ws))
        result['http_assets'] = True
        (runtime / 'desktop-backend-smoke.json').write_text(json.dumps(result), encoding='utf8')
        print(json.dumps(result))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
