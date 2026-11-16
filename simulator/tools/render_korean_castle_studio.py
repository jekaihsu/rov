"""Render korean_castle before/after under an identical normalized studio camera."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from _browser import launch
from render_vehicle_compare import PAGE, SIZE, VIEWER, serve

OUT = Path(__file__).resolve().parents[2] / "docs/design/wreck"
MODELS = Path(__file__).resolve().parents[1] / "viewer" / "models"

PAGE = PAGE.replace(
    "import { createVehicleModel } from './vehicle_models.js';",
    "import {loadGLTF} from './glb.js';",
)
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
  // Fixed studio rig — same for before and after.
  camera.position.set(1.35, 0.85, 1.65);
  camera.lookAt(0, 0.05, 0);
  renderer.render(scene, camera);
  window.__root = root;
  return {calls:renderer.info.render.calls, triangles:renderer.info.render.triangles};
};
window.__clearShot = () => scene.remove(window.__root);
"""
    + PAGE[b:]
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    after = MODELS / "korean_castle.glb"
    before = Path("/tmp/korean_castle_main.glb")
    if not before.exists():
        raise SystemExit(f"missing {before}; export origin/main korean_castle.glb first")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Serve both via the viewer models dir under distinct names.
        before_served = MODELS / "_studio_before_korean_castle.glb"
        shutil.copyfile(before, before_served)
        try:
            server = serve(VIEWER)
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with sync_playwright() as p:
                browser = launch(p)
                page = browser.new_page(viewport=SIZE)
                page.route(
                    "**/__compare.html",
                    lambda route: route.fulfill(body=PAGE, content_type="text/html"),
                )
                page.goto(base + "/__compare.html")
                page.wait_for_function("window.__ready")
                for label, url in (
                    ("studio-before", "models/_studio_before_korean_castle.glb"),
                    ("studio-after", "models/korean_castle.glb"),
                ):
                    info = page.evaluate("url => window.__renderShot(url)", url)
                    print(label, info, flush=True)
                    page.screenshot(path=str(OUT / f"{label}.jpg"), type="jpeg", quality=90)
                    page.evaluate("window.__clearShot()")
                browser.close()
            server.shutdown()
        finally:
            before_served.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
