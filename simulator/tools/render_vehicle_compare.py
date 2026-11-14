"""Render vehicle models side by side with an identical camera and lighting rig (no simulator needed).

Usage (from the repository root):
  python simulator/tools/render_vehicle_compare.py [--out docs/design/vehicle] [--only x1-training]

Each shot is rendered through createVehicleModel(), the same loader the game uses, at 1600x900 with
deviceScaleFactor 1. The viewer directory is served by a throwaway static HTTP server; the comparison
page itself is injected with Playwright routing so nothing is added to the shipped viewer.
"""
import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import launch

ROOT = Path(__file__).resolve().parents[2]
VIEWER = ROOT / 'simulator' / 'viewer'
SIZE = {'width': 1600, 'height': 900}

# Camera presets in Three.js vehicle coordinates (+Z forward, +Y up, +X port), metres.
VIEWS = {
    'front34': {'position': [-0.9, 0.46, 1.05], 'target': [0, -0.03, 0.03], 'fov': 34},
    'side': {'position': [-2.15, 0.05, 0.0], 'target': [0, 0, 0], 'fov': 30},
    'top': {'position': [0.0, 2.3, 0.0001], 'target': [0, 0, 0], 'fov': 30},
    'thruster': {'position': [-0.62, 0.42, 0.62], 'target': [-0.19, 0.0, 0.25], 'fov': 26},
}
# variant name -> createVehicleModel options
VARIANTS = {
    'x1-training': {'assets': 'training'},
    'observation-generic': {'assets': 'generic'},
}

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#0b1820;overflow:hidden}canvas{display:block}</style>
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
scene.background = new THREE.Color('#0b1820');

function buildStudio() {
  // A soft studio environment so metals and glossy polymers have something to reflect.
  const room = new THREE.Scene();
  const shell = new THREE.Mesh(new THREE.SphereGeometry(10, 32, 16),
    new THREE.MeshBasicMaterial({ color: 0x24333c, side: THREE.BackSide }));
  room.add(shell);
  const panels = [[[0, 8, 0], [10, 10], 4.0], [[6, 3, 4], [4, 6], 2.2], [[-7, 2, -2], [4, 5], 1.4]];
  for (const [position, size, power] of panels) {
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(...size),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(power, power, power * 1.05), side: THREE.DoubleSide }));
    panel.position.set(...position);
    panel.lookAt(0, 0, 0);
    room.add(panel);
  }
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(room, 0.03).texture;
  scene.environmentIntensity = 0.55;
}

function buildLights() {
  scene.add(new THREE.HemisphereLight(0xe2efff, 0x283039, 1.1));
  const rig = [[0xffffff, 2.2, [2, 4, 3]], [0xb6d6ee, 0.9, [-3, 1, 2]], [0xffffff, 0.8, [0, 2, -3]]];
  for (const [color, intensity, position] of rig) {
    const light = new THREE.DirectionalLight(color, intensity);
    light.position.set(...position);
    scene.add(light);
  }
  const grid = new THREE.GridHelper(8, 32, 0x355363, 0x142c38);
  grid.position.y = -0.24;
  scene.add(grid);
}

const camera = new THREE.PerspectiveCamera(34, innerWidth / innerHeight, 0.01, 50);
buildStudio();
buildLights();

function modelSize(model) {
  const size = new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3());
  return size.toArray().map((v) => +v.toFixed(3));
}

window.__renderShot = async function renderShot(options, view) {
  const vehicle = await createVehicleModel('x1', options);
  scene.add(vehicle.root);
  camera.fov = view.fov;
  camera.position.set(...view.position);
  camera.lookAt(new THREE.Vector3(...view.target));
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  let triangles = 0;
  vehicle.model.traverse((o) => {
    if (o.isMesh) triangles += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
  });
  const result = { loadError: vehicle.loadError ? String(vehicle.loadError) : null, triangles,
    rotors: vehicle.rotors.length, calls: renderer.info.render.calls,
    size: modelSize(vehicle.model) };
  window.__lastVehicle = vehicle;
  return result;
};
window.__clearShot = function clearShot() {
  window.__lastVehicle?.dispose();
  window.__lastVehicle = null;
};
window.__ready = true;
</script></body></html>"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory):
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def render(out, only):
    server = serve(VIEWER)
    base = f'http://127.0.0.1:{server.server_address[1]}'
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as playwright:
        browser = launch(playwright)
        page = browser.new_page(viewport=SIZE, device_scale_factor=1)
        # Software GL on a busy machine can take minutes per frame; nothing here is timing-sensitive.
        page.set_default_timeout(600000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route(f'{base}/__vehicle_compare.html',
                   lambda route: route.fulfill(body=PAGE, content_type='text/html'))
        page.goto(f'{base}/__vehicle_compare.html')
        page.wait_for_function('window.__ready === true')
        for variant, options in VARIANTS.items():
            if only and variant not in only:
                continue
            for view_name, view in VIEWS.items():
                result = page.evaluate('([o, v]) => window.__renderShot(o, v)', [options, view])
                path = out / f'compare-{view_name}-{variant}.png'
                page.screenshot(path=str(path))
                page.evaluate('window.__clearShot()')
                report[f'{variant}/{view_name}'] = result
                print(variant, view_name, json.dumps(result), path.name)
        browser.close()
        if errors:
            raise SystemExit('page errors: ' + '; '.join(errors))
    server.shutdown()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', default=str(ROOT / 'docs' / 'design' / 'vehicle'))
    parser.add_argument('--only', nargs='*', default=None)
    parser.add_argument('--view', action='append', default=[],
                        help='extra view name=px,py,pz,tx,ty,tz,fov (renders only the given views)')
    args = parser.parse_args()
    if args.view:
        VIEWS.clear()
        for item in args.view:
            name, numbers = item.split('=')
            values = [float(v) for v in numbers.split(',')]
            VIEWS[name] = {'position': values[0:3], 'target': values[3:6], 'fov': values[6]}
    report = render(Path(args.out), args.only)
    failed = [key for key, value in report.items() if value['loadError']]
    if failed:
        raise SystemExit('fallback geometry was rendered for: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
