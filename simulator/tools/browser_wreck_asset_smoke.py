"""Verify the shipped wreck's byte budget, meshopt/WebP decoding and complete PBR maps in Chromium.

Run with tools/run_browser_checks.py browser_wreck_asset_smoke.
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout

ROOT = Path(__file__).resolve().parents[1]


def main():
    model = ROOT / "viewer/models/korean_castle.glb"
    assert model.stat().st_size <= 12_000_000, model.stat().st_size
    with sync_playwright() as playwright:
        browser = launch(playwright, headless=True)
        page = browser.new_page(viewport={"width": 960, "height": 540})
        page.set_default_timeout(timeout(120000))
        page.goto(http_base() + "/", wait_until="domcontentloaded")
        result = page.evaluate("""async () => {
            const {loadGLTF} = await import('/glb.js');
            const THREE = await import('three');
            const gltf = await loadGLTF('/models/korean_castle.glb');
            let meshes = 0;
            let triangles = 0;
            const steel = new Map();
            gltf.scene.traverse(object => {
                if (!object.isMesh) return;
                meshes++;
                const geometry = object.geometry;
                triangles += geometry.index ? geometry.index.count / 3 : geometry.attributes.position.count / 3;
                geometry.computeBoundingBox();
                if (!Number.isFinite(geometry.boundingBox.min.x)) throw new Error('Invalid geometry');
                const materials = Array.isArray(object.material) ? object.material : [object.material];
                for (const material of materials) {
                    if (!material.name.startsWith('A2_Steel_atlas')) continue;
                    const maps = [material.map, material.normalMap, material.roughnessMap];
                    if (maps.some(map => !map?.image || map.image.width !== 2048 || map.image.height !== 2048)) {
                        throw new Error('Missing or incorrectly sized PBR map: ' + material.name);
                    }
                    steel.set(material.name, true);
                }
            });
            const renderer = new THREE.WebGLRenderer();
            renderer.setSize(640, 360);
            const scene = new THREE.Scene();
            scene.add(gltf.scene, new THREE.AmbientLight(0xffffff, 2));
            const camera = new THREE.PerspectiveCamera(50, 640 / 360, .1, 1000);
            camera.position.set(180, 108, 165);
            camera.lookAt(76, 3, 0);
            renderer.render(scene, camera);
            const error = renderer.getContext().getError();
            renderer.dispose();
            return {meshes, triangles, steelAtlases: steel.size, webglError: error,
                    extensions: gltf.parser.json.extensionsRequired};
        }""")
        assert result["meshes"] > 0, result
        assert result["steelAtlases"] == 3, result
        assert result["webglError"] == 0, result
        assert "EXT_meshopt_compression" in result["extensions"], result
        assert "EXT_texture_webp" in result["extensions"], result
        print(json.dumps({"bytes": model.stat().st_size, **result}, indent=2))
        browser.close()
    print("Wreck asset smoke passed")


if __name__ == "__main__":
    main()
