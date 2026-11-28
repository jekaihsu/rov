"""Photograph live, undriven mission rooms twelve seconds after the first onboard state."""
import json
import os
from functools import partial
from pathlib import Path
from threading import Thread
from uuid import uuid4

from playwright.sync_api import sync_playwright
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect
from websockets.sync.server import serve

from _browser import http_base, launch, timeout, ws_base

SCENES = ('cold_open_jacket', 'harbor_inspection', 'hull_inspection', 'aquaculture_pen',
          'open_water', 'wreck_survey', 'tutorial_pool')
OUT = Path(__file__).resolve().parents[2] / 'docs/design/scene-look-v1'


def forward_commands(viewer, host):
    try:
        for message in viewer:
            host.send(message)
    except ConnectionClosed:
        pass
    finally:
        host.close()


def hold_frame(viewer, key):
    """Forward the real host stream through the first snapshot at 12 s, then hold the shutter."""
    with connect(ws_base(), max_size=None) as host:
        commands = Thread(target=forward_commands, args=(viewer, host), daemon=True)
        commands.start()
        selected = False
        held = False
        for message in host:
            if held:
                continue
            packet = json.loads(message)
            if packet['type'] == 'world':
                selected = packet['scenario']['key'] == key and packet['scenario']['seed'] == 42
            viewer.send(message)
            held = selected and packet['type'] == 'state' and packet['t'] >= 12


def main():
    tag = os.getenv('ROV_LOOKS_TAG', 'after')
    selected = set(filter(None, os.getenv('ROV_LOOKS_ONLY', '').split(',')))
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        for key in SCENES:
            if selected and key not in selected:
                continue
            page = browser.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
            shutter = serve(partial(hold_frame, key=key), '127.0.0.1', 0, max_size=None)
            try:
                port = shutter.socket.getsockname()[1]
                Thread(target=shutter.serve_forever, daemon=True).start()
                room = uuid4().hex[:12]
                url = (f'{http_base()}/?play=1&nointro&room={room}&scenario={key}&seed=42'
                       f'&ws=ws://127.0.0.1:{port}&quality=medium&cam=onboard&fidelity=real')
                page.goto(url, wait_until='domcontentloaded')
                page.wait_for_function('key => window.__viewer?.W?.scenario?.key === key && !!window.__viewer.S',
                                       arg=key, timeout=timeout(90000))
                page.wait_for_function('window.__viewer.S.t >= 12', timeout=timeout(90000))
                if key == 'open_water':
                    page.wait_for_function("!!window.__viewer.scene.getObjectByName('spool-station-boat')",
                                           timeout=timeout(90000))
                if key == 'wreck_survey':
                    wreck_ready = "window.__viewer.scene.getObjectByName('WreckChenjiaoLOD')?.levels.length === 3"
                    page.wait_for_function(wreck_ready, timeout=timeout(90000))
                state = page.evaluate('() => window.__viewer.S')
                assert 12 <= state['t'] < 13, state['t']
                assert state['rc']['right_switch'] == 0
                page.screenshot(path=str(OUT / f'{key}-{tag}.jpg'), type='jpeg', quality=88, timeout=timeout(90000))
                print(key, state['t'], state['pos'], state['euler'], flush=True)
            finally:
                page.close()
                shutter.shutdown()
        browser.close()


if __name__ == '__main__':
    main()
