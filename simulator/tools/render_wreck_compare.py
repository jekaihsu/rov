"""Render original wreck, existing wreck and vehicle with identical normalized studio cameras."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import launch
from render_vehicle_compare import PAGE, SIZE, VIEWER, serve

OUT = Path(__file__).resolve().parents[2] / "docs/design/scenes/chenjiao"
PAGE = PAGE.replace("import { createVehicleModel } from './vehicle_models.js';", "import {loadGLTF} from './glb.js';")
a = PAGE.index("window.__renderShot =")
b = PAGE.index("window.__ready =", a)
PAGE = (
    PAGE[:a]
    + """
window.__renderShot = async function(url) {
  const gltf = await loadGLTF(url);
  const root = gltf.scene;
  const bounds = new THREE.Box3().setFromObject(root);
  const size = bounds.getSize(new THREE.Vector3());
  const centre = bounds.getCenter(new THREE.Vector3());
  const scale = 1.5 / Math.max(size.x, size.y, size.z);
  root.position.copy(centre).multiplyScalar(-scale);
  root.scale.setScalar(scale);
  scene.add(root);
  camera.position.set(1.4, 1.0, 1.7);
  camera.lookAt(0, 0, 0);
  renderer.render(scene, camera);
  window.__root = root;
  return {calls:renderer.info.render.calls, triangles:renderer.info.render.triangles};
};
window.__clearShot = () => scene.remove(window.__root);
"""
    + PAGE[b:]
)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = serve(VIEWER)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport=SIZE)
        page.route("**/__compare.html", lambda route: route.fulfill(body=PAGE, content_type="text/html"))
        page.goto(base + "/__compare.html")
        page.wait_for_function("window.__ready")
        for name in ("wreck_chenjiao", "korean_castle", "rov"):
            print(name, page.evaluate("url => window.__renderShot(url)", f"models/{name}.glb"), flush=True)
            page.screenshot(path=str(OUT / f"compare-{name}.jpg"), type="jpeg", quality=90)
            page.evaluate("window.__clearShot()")
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
