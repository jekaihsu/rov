"""Simulated vehicle link in the viewer: degradation shows stale video, comms loss freezes it and disarms.

The instructor injects `link_degrade` and then `comms_loss` with a short reconnect. The check asserts the
viewer marks the video as lagging/frozen, the HUD shows the stale badge and the failsafe, the vehicle
failsafe (disarm) latched, and that after reconnecting the vehicle stays locked until the pilot re-arms.

Injection needs the instructor code, so this script starts its own server on free ports with a private
code (like browser_expedition_perf.py starts its own fixture). Browser launch goes through _browser.py.
"""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright
from websockets.sync.client import connect

from _browser import host, launch, timeout

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'output' / 'link'
SCREENSHOTS = '--screenshots' in sys.argv
ROOM = 'linkcheck'
CODE = secrets.token_urlsafe(16)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def start_server():
    ports = {'http': free_port(), 'ws': free_port(), 'rpc': free_port()}
    env = dict(os.environ, QYSIM_INSTRUCTOR_CODE=CODE, PYTHONUNBUFFERED='1')
    command = [sys.executable, '-m', 'qysim.server', '--host', host(), '--http-port', str(ports['http']),
               '--ws-port', str(ports['ws']), '--rpc-port', str(ports['rpc'])]
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://{host()}:{ports['http']}/", timeout=2).close()
            return process, ports
        except OSError:
            time.sleep(0.5)
    process.kill()
    raise RuntimeError('simulator did not start')


class Instructor:
    def __init__(self, ws_url):
        self.socket = connect(ws_url, max_size=None).__enter__()
        self.socket.send(json.dumps({'type': 'instructor_join', 'room_id': ROOM, 'code': CODE}))
        self.expect('instructor_session')

    def expect(self, kind):
        deadline = time.monotonic() + timeout(30)
        while time.monotonic() < deadline:
            message = json.loads(self.socket.recv(timeout=timeout(30)))
            if message.get('type') == kind:
                return message
            if message.get('type') == 'error':
                raise RuntimeError(message)
        raise TimeoutError(kind)

    def inject(self, **fields):
        self.socket.send(json.dumps({'type': 'instructor', 'action': 'inject', 'vehicle_id': 'v1', **fields}))
        self.expect('instructor_result')


def shot(page, name):
    if SCREENSHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), timeout=120000)


def unlock(page):
    """Press unlock until the server reports it; a resync after any lock re-locks the local switch first."""
    page.wait_for_function("""() => {
      window.__viewer.rc.rc_lock = 0;
      return window.__viewer.S.locked === false;
    }""", polling=500, timeout=timeout(30000))


def link_state(page):
    return page.evaluate('''() => ({
      link: window.__viewer.S?.link, locked: window.__viewer.S?.locked,
      latched: window.__viewer.S?.input_latched, view: document.getElementById('vp').dataset.videoLink,
      status: document.getElementById('flightSystem')?.innerText || '',
      frozen: !document.querySelector('.video-link-frozen')?.hidden,
      onboard: !document.getElementById('xhair')?.hidden })''')


def main():
    process, ports = start_server()
    failures = []
    try:
        with sync_playwright() as playwright:
            browser = launch(playwright)
            page = browser.new_page(viewport={'width': 1280, 'height': 720})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            ws_url = f"ws://{host()}:{ports['ws']}"
            page.goto(f"http://{host()}:{ports['http']}/?ws={ws_url}&play=1&nointro&room={ROOM}&cam=onboard")
            page.wait_for_function('window.__viewer?.S?.link?.state === "healthy"', timeout=timeout(60000))
            page.evaluate('window.__viewer.setCam("onboard")')
            unlock(page)
            instructor = Instructor(ws_url)

            instructor.inject(kind='link_degrade', strength=1, duration=6)
            page.wait_for_function('window.__viewer.S.link.video_lag_s >= 1', timeout=timeout(20000))
            page.wait_for_function('document.getElementById("vp").dataset.videoLink !== "live"',
                                   timeout=timeout(20000))
            state = link_state(page)
            shot(page, 'degraded')
            if state['link']['state'] != 'degraded':
                failures.append(f'degraded link not reported: {state["link"]}')
            # Commands still reach the vehicle: a degraded link never triggers the vehicle failsafe.
            # (S.locked is not asserted: software GL stalls can trip the real network watchdog here.)
            if state['link']['failsafe'] is not None or state['link']['phase'] != 'connected':
                failures.append(f'a degraded link must keep delivering commands: {state["link"]}')
            if '影像' not in state['status']:
                failures.append(f'no stale-video badge: {state["status"]!r}')

            unlock(page)
            # A 1 s loss plus an 8 s reconnect keeps the picture frozen ~9 s, long enough for a slow page.
            instructor.inject(kind='comms_loss', duration=1, failsafe='disarm', reconnect=8)
            page.wait_for_function('window.__viewer.S.link.state === "lost"', timeout=timeout(20000))
            try:
                # Read the viewer flag and the held frame in the same poll: both change in one rendered frame.
                page.wait_for_function('''() => document.getElementById("vp").dataset.videoLink === "frozen"
                  && !document.querySelector(".video-link-frozen").hidden''', timeout=timeout(20000))
            except PlaywrightTimeout:
                failures.append(f'onboard video is not held on the last frame while lost: {link_state(page)}')
            page.wait_for_function('window.__viewer.S.link.failsafe === "disarm"', timeout=timeout(30000))
            state = link_state(page)
            shot(page, 'lost')
            if not state['locked']:
                failures.append(f'failsafe did not disarm and latch: {state}')
            if '失聯保護' not in state['status']:
                failures.append(f'HUD does not show the failsafe: {state["status"]!r}')
            page.wait_for_function('window.__viewer.S.link.phase === "connected"', timeout=timeout(60000))
            page.wait_for_timeout(1000)
            state = link_state(page)
            if not state['locked'] or not state['link']['rearm_required']:
                failures.append(f'vehicle must stay locked until re-armed: {state}')
            if '需重新解鎖' not in state['status']:
                failures.append(f'HUD does not ask for re-arming: {state["status"]!r}')
            unlock(page)
            page.wait_for_function('!window.__viewer.S.link.rearm_required', timeout=timeout(20000))
            page.wait_for_function('document.getElementById("vp").dataset.videoLink === "live"',
                                   timeout=timeout(20000))
            if errors:
                failures.append(f'page errors: {errors}')
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
    if failures:
        print('\n'.join(failures))
        sys.exit(1)
    print('Link degradation, comms loss freeze, disarm failsafe and re-arm passed.')


if __name__ == '__main__':
    main()
