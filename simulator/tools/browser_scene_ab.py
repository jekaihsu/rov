"""Same-page A/B frame cost of the dressed sites against the plain primitives they replaced.

Not a pass/fail check. On a shared machine, separate before/after runs drift by several times; this script
alternates frame by frame inside one page, so both sides see the same load:

  A  the pre-dressing look rebuilt in the page: one single-colour primitive per primary member (piles, legs,
     braces, masts, hull and wreck boxes, walls; the ship hull drawn as the old hull box), none of the fittings,
     the old canvas sand texture on the seabed, no structure life (kelp and anemones on structures)
  B  the current scene for the chosen quality tier (structures.js, seabed.js, structure life)

Everything else (vehicle, fish, habitat, silt, HUD canvas, the effects pipeline on medium and high) is shared. For each site, tier and view it renders
A and B alternately (``ROV_AB_FRAMES`` pairs, default 20) at 800x450 with a pixel read-back after each frame
and reports the median ms of each side. ``ROV_AB_SIDES=A,B,C,D`` adds two diagnostics: C is the current
structures over the old sand seabed, D the old primitives over the current seabed.
Output: output/scene-review/ab.json.

  python tools/run_browser_checks.py browser_scene_ab
  ROV_SCENE_SITES=monopile_current ROV_SCENE_TIERS=medium python tools/run_browser_checks.py browser_scene_ab
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from _browser import launch, timeout
from browser_scene_review import SITES, TIERS, open_site

OUT = Path(__file__).resolve().parents[1] / 'output' / 'scene-review'

SETUP = '''() => {
  const v = window.__viewer, THREE = v.THREE, scene = v.scene, W = v.W;
  const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
  const legacy = new THREE.Group();
  const PRIMARY = new Set(['pile', 'monopile', 'jacket_leg', 'brace', 'mast', 'hull', 'wreck', 'wall', 'quay']);
  const colours = {pile: 0x6f6a58, monopile: 0x7c6f4f, jacket_leg: 0xb38a3a, brace: 0x9a7c44, mast: 0x5d5d5d,
    hull: 0x5a2626, wreck: 0x4e4234, wall: 0x5b605a};
  for (const ob of W.obstacles || []) {
    if (!PRIMARY.has(ob.kind) || ob.type === 'model' || ob.type === 'snag') continue;   // only what was drawn before
    const mat = new THREE.MeshStandardMaterial({color: colours[ob.kind] ?? 0x666666, roughness: .85, metalness: .1});
    let mesh = null;
    if (ob.type === 'cylinder') {
      const a = P(ob.p0), b = P(ob.p1);
      mesh = new THREE.Mesh(new THREE.CylinderGeometry(ob.radius, ob.radius, a.distanceTo(b), 24, 1), mat);
      mesh.position.copy(a).add(b).multiplyScalar(.5);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    } else if (ob.type === 'box' || ob.type === 'ship_hull') {
      const half = ob.half || [ob.length / 2, ob.beam / 2, ob.draft / 2];
      const centre = ob.half ? ob.center : [ob.center[0], ob.center[1], ob.draft / 2];
      mesh = new THREE.Mesh(new THREE.BoxGeometry(2 * half[1], 2 * half[2], 2 * half[0]), mat);
      P(centre, mesh.position);
      mesh.rotation.y = -ob.yaw_deg * Math.PI / 180;
    } else if (ob.type === 'wall') {
      const h = W.seabed_depth - ob.top, a = ob.normal_deg * Math.PI / 180, th = 0.6;
      mesh = new THREE.Mesh(new THREE.BoxGeometry(ob.width, h, th), mat);
      const n = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a));
      P([ob.point[0], ob.point[1], (ob.top + W.seabed_depth) / 2], mesh.position).addScaledVector(n, -th / 2);
      mesh.rotation.y = -a;
    }
    if (mesh) legacy.add(mesh);
  }
  // the old sand texture (environment.js before the per-site seabeds)
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  for (let y = 0; y < 256; y++) {
    for (let x = 0; x < 256; x += 2) {
      const r = Math.sin((y + Math.sin(x * 0.05) * 6) * 0.35) * 0.5 + 0.5;
      const l = 0.82 + 0.28 * r + Math.random() * 0.1;
      g.fillStyle = `rgb(${Math.round(109 * l)},${Math.round(102 * l)},${Math.round(80 * l)})`;
      g.fillRect(x, y, 2, 1);
    }
  }
  const sand = new THREE.CanvasTexture(c);
  sand.wrapS = sand.wrapT = THREE.RepeatWrapping;
  sand.colorSpace = THREE.SRGBColorSpace;
  const sandSeabed = new THREE.MeshStandardMaterial({color: 0xffffff, map: sand, roughness: 1});
  const seabeds = [];
  const life = [];
  let structures = null;
  scene.traverse((o) => {
    if (o.name === 'structures') structures = o;
    if (o.material?.userData?.seabedProfile) seabeds.push({mesh: o, material: o.material});
    if (o.userData?.structureLife) life.push(o);
  });
  legacy.visible = false;
  scene.add(legacy);
  window.__ab = {
    // A: before, B: after; diagnostics: C after with the old seabed, D before with the new seabed
    set(side) {
      const oldStructures = side === 'A' || side === 'D';
      const oldSeabed = side === 'A' || side === 'C';
      legacy.visible = oldStructures;
      if (structures) structures.visible = !oldStructures;
      for (const s of seabeds) s.mesh.material = oldSeabed ? sandSeabed : s.material;
      for (const o of life) o.visible = !oldStructures;
    },
    counts: {legacy: legacy.children.length, seabeds: seabeds.length, life: life.length, structures: !!structures},
  };
  return window.__ab.counts;
}'''

RUN = '''([view, real, pairs, sides]) => {
  const v = window.__viewer, THREE = v.THREE, renderer = v.renderer, camera = v.camera, scene = v.scene;
  const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
  window.__skipRender = true;
  const keep = {ratio: renderer.getPixelRatio(), size: renderer.getSize(new THREE.Vector2()),
    pos: camera.position.clone(), q: camera.quaternion.clone(), fov: camera.fov, aspect: camera.aspect,
    near: scene.fog.near, far: scene.fog.far};
  renderer.setPixelRatio(1);
  renderer.setSize(800, 450, false);
  camera.aspect = 800 / 450;
  if (real) camera.fov = 70;
  camera.position.copy(P(view[0]));
  camera.lookAt(P(view[1]));
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  scene.fog.near = real ? .3 : 5;
  scene.fog.far = real ? (v.W?.scenario?.visibility_m || 12) * 1.35 : 70;
  // the optics pipeline (fx/water_optics.js) takes visibility from what the silt module publishes
  keep.visibility = scene.userData.waterVisibility;
  scene.userData.waterVisibility = scene.fog.far / 1.35;
  const gl = renderer.getContext(), pixel = new Uint8Array(4);
  const times = {}, info = {};
  // the effects pipeline (fx/pipeline.js) renders several passes per frame: count all of them
  renderer.info.autoReset = false;
  for (const side of sides) {                // warm every program
    times[side] = [];
    window.__ab.set(side);
    renderer.render(scene, camera);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  }
  for (let i = 0; i < pairs; i++) {
    for (const side of (i % 2 ? sides.slice().reverse() : sides)) {
      window.__ab.set(side);
      renderer.info.reset();
      const t0 = performance.now();
      renderer.render(scene, camera);
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
      times[side].push(performance.now() - t0);
      info[side] = {calls: renderer.info.render.calls, triangles: renderer.info.render.triangles};
    }
  }
  window.__ab.set('B');
  renderer.info.autoReset = true;
  renderer.setPixelRatio(keep.ratio);
  renderer.setSize(keep.size.x, keep.size.y, false);
  camera.position.copy(keep.pos);
  camera.quaternion.copy(keep.q);
  camera.fov = keep.fov;
  camera.aspect = keep.aspect;
  camera.updateProjectionMatrix();
  scene.fog.near = keep.near;
  scene.fog.far = keep.far;
  scene.userData.waterVisibility = keep.visibility;
  window.__skipRender = false;
  const median = (a) => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
  return Object.fromEntries(sides.map((side) => [side, {...info[side], ms: median(times[side])}]));
}'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = [s for s in os.environ.get('ROV_SCENE_SITES', '').split(',') if s]
    sites = {k: v for k, v in SITES.items() if not only or k in only}
    tiers = [t for t in os.environ.get('ROV_SCENE_TIERS', ','.join(TIERS)).split(',') if t in TIERS]
    pairs = int(os.environ.get('ROV_AB_FRAMES', '20'))
    sides = os.environ.get('ROV_AB_SIDES', 'A,B').split(',')
    report = {}
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        for key, views in sites.items():
            for tier in tiers:
                page, errors = open_site(browser, key, tier)
                page.wait_for_timeout(timeout(2000))
                counts = page.evaluate(SETUP)
                entry = report.setdefault(key, {}).setdefault(tier, {'counts': counts})
                for name, view in views.items():
                    entry[name] = page.evaluate(RUN, [view, name == 'onboard', pairs, sides])
                entry['errors'] = errors
                page.close()
                print(key, tier, json.dumps(entry), flush=True)
        browser.close()
    path = OUT / 'ab.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('A/B report written to', path)


if __name__ == '__main__':
    main()
