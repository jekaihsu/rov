"""Studio and in-game stills of YX Model R, O and V.

Usage (repository root):
  python simulator/tools/render_yx_vehicle_shots.py --studio --tag before
  python simulator/tools/render_yx_vehicle_shots.py --ingame --tag before

Writes docs/design/vehicle-models/<tag>-studio-<id>-<view>.png and
<tag>-underwater-<id>.png. The studio rig is the same camera and lights for
every vehicle, so before and after frames line up.
"""
import argparse
import functools
import http.server
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base

ROOT = Path(__file__).resolve().parents[2]
VIEWER = ROOT / 'simulator' / 'viewer'
SIM = ROOT / 'simulator'
OUT = ROOT / 'docs' / 'design' / 'vehicle-models'
SIZE = {'width': 1600, 'height': 900}
MODELS = (('x1', 'r'), ('bluerov2_heavy', 'o'), ('falcon', 'v'))
VIEWS = {
    'front34': {'position': [-0.95, 0.42, 1.15], 'target': [0.0, 0.0, 0.05], 'fov': 32},
    'detail': {'position': [-0.42, 0.16, 0.55], 'target': [-0.16, 0.02, 0.22], 'fov': 28},
}

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#10181e;overflow:hidden}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"./vendor/three/build/three.module.js",
"three/addons/":"./vendor/three/examples/jsm/"}}</script></head><body>
<script type="module">
import * as THREE from 'three';
import { createVehicleModel } from './vehicle_models.js';

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
document.body.append(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#10181e');

function buildStudio() {
  const room = new THREE.Scene();
  room.add(new THREE.Mesh(new THREE.SphereGeometry(12, 24, 12),
    new THREE.MeshBasicMaterial({ color: 0x1c2a32, side: THREE.BackSide })));
  const panels = [[[0, 7, 0], [8, 8], 3.2], [[5, 2.5, 3], [3, 5], 2.4], [[-6, 1.5, -1], [3, 4], 1.2]];
  for (const [position, size, power] of panels) {
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(...size),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(power, power, power * 1.04), side: THREE.DoubleSide }));
    panel.position.set(...position);
    panel.lookAt(0, 0, 0);
    room.add(panel);
  }
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  scene.environmentIntensity = 0.6;
}

scene.add(new THREE.HemisphereLight(0xd5e6f2, 0x243038, 1.05));
for (const [color, intensity, position] of [[0xffffff, 2.4, [2.2, 3.6, 2.4]],
    [0xb7d4ea, 0.8, [-3, 1.2, 1.5]], [0xfff4e5, 0.55, [0.4, 1.5, -2.5]]]) {
  const light = new THREE.DirectionalLight(color, intensity);
  light.position.set(...position);
  scene.add(light);
}
const grid = new THREE.GridHelper(6, 24, 0x355363, 0x17313a);
grid.position.y = -0.28;
scene.add(grid);
buildStudio();
const camera = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, 0.02, 40);

window.__renderShot = async function renderShot(modelId, view) {
  const vehicle = await createVehicleModel(modelId, {assets: 'training'});
  scene.add(vehicle.root);
  camera.fov = view.fov;
  camera.position.set(...view.position);
  camera.lookAt(new THREE.Vector3(...view.target));
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  let triangles = 0;
  vehicle.model.traverse((object) => {
    if (object.isMesh) {
      const geometry = object.geometry;
      triangles += (geometry.index ? geometry.index.count : geometry.attributes.position.count) / 3;
    }
  });
  const result = {
    loadError: vehicle.loadError ? String(vehicle.loadError) : null,
    triangles, rotors: vehicle.rotors.length,
    gimbal: !!vehicle.cameraGimbal, lamps: vehicle.lampPivots.length,
  };
  window.__lastVehicle = vehicle;
  return result;
};
window.__clearShot = function clearShot() {
  window.__lastVehicle?.dispose();
  window.__lastVehicle = null;
};
window.__ready = true;
</script></body></html>"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory):
    handler = functools.partial(Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def studio(tag):
    server = serve(VIEWER)
    base = f'http://127.0.0.1:{server.server_address[1]}'
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        page = browser.new_page(viewport=SIZE, device_scale_factor=1)
        page.set_default_timeout(timeout(180000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route(f'{base}/__yx_studio.html', lambda route: route.fulfill(body=PAGE, content_type='text/html'))
        page.goto(f'{base}/__yx_studio.html')
        page.wait_for_function('window.__ready === true')
        for model_id, short in MODELS:
            for view_name, view in VIEWS.items():
                result = page.evaluate('([id, view]) => window.__renderShot(id, view)', [model_id, view])
                path = OUT / f'{tag}-studio-{short}-{view_name}.png'
                page.screenshot(path=str(path))
                page.evaluate('window.__clearShot()')
                report[f'{short}/{view_name}'] = result
                print(tag, short, view_name, json.dumps(result), path.name)
        browser.close()
        if errors:
            raise SystemExit('page errors: ' + '; '.join(errors))
    server.shutdown()
    failed = [key for key, value in report.items() if value.get('loadError')]
    if failed:
        raise SystemExit('fallback geometry: ' + ', '.join(failed))


def free_port():
    import socket
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def ingame(tag):
    """One chase-camera frame per vehicle, a few metres down, from the running viewer."""
    ports = {'http': free_port(), 'ws': free_port(), 'rpc': free_port()}
    log_path = SIM / 'output' / 'yx-vehicle-shots.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, 'w', encoding='utf-8')
    process = subprocess.Popen(
        [sys.executable, '-m', 'qysim.server', '--http-port', str(ports['http']),
         '--ws-port', str(ports['ws']), '--rpc-port', str(ports['rpc'])],
        cwd=str(SIM), stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise SystemExit(f'server exited; see {log_path}')
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{ports['http']}/", timeout=2).close()
                break
            except OSError:
                time.sleep(0.4)
        else:
            raise SystemExit(f'server did not start; see {log_path}')
        import os
        os.environ['ROV_HTTP_PORT'] = str(ports['http'])
        os.environ['ROV_WS_PORT'] = str(ports['ws'])
        OUT.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = launch(playwright, headless=True)
            for model_id, short in MODELS:
                page = browser.new_page(viewport=SIZE, device_scale_factor=1)
                page.set_default_timeout(timeout(120000))
                url = (f"{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&model={model_id}"
                       f"&cam=chase&room=yx{tag}{short}")
                page.goto(url, wait_until='domcontentloaded', timeout=timeout(90000))
                page.wait_for_function(f'window.__modelLoaded === true && window.__loadedModelId === "{model_id}"')
                page.wait_for_timeout(timeout(2500))
                path = OUT / f'{tag}-underwater-{short}.png'
                page.screenshot(path=str(path), timeout=timeout(180000))
                print(tag, 'underwater', short, path.name)
                page.close()
            browser.close()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--tag', required=True, choices=('before', 'after'))
    parser.add_argument('--studio', action='store_true')
    parser.add_argument('--ingame', action='store_true')
    args = parser.parse_args()
    if args.studio:
        studio(args.tag)
    if args.ingame:
        ingame(args.tag)


if __name__ == '__main__':
    main()
