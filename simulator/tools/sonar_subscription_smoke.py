"""Live three-client subscription isolation check against a running server (address from _browser.py)."""
import asyncio
import json
import time

import websockets

from _browser import ws_base


async def state(ws):
    while True:
        message = json.loads(await asyncio.wait_for(ws.recv(), 10))
        if message['type'] == 'state':
            return message


async def main():
    clients = []
    try:
        for i in range(3):
            ws = await websockets.connect(ws_base())
            clients.append(ws)
            await ws.send(json.dumps(dict(type='join', room_id='sonarcheck', name=str(i))))
            assert 'sonar' not in await state(ws)
        for ws in clients:
            await ws.send(json.dumps(dict(type='operation', action='sonar_subscribe', enabled=True)))
        begin = time.monotonic()
        samples = []
        while time.monotonic() - begin < 4:
            samples.append(await state(clients[0]))
        assert any(sample.get('sonar') for sample in samples)
        await clients[0].send(json.dumps(dict(type='operation', action='sonar_subscribe', enabled=False)))
        for _ in range(5):
            last = await state(clients[0])
        assert 'sonar' not in last
        print('PASS three clients subscribe/unsubscribe:', len(samples), 'states in 4s')
    finally:
        for ws in clients:
            await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
