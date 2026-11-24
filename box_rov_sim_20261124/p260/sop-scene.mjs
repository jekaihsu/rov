import * as THREE from 'three';
import { createRov01IndustrialMesh } from './rov01_mesh.mjs';

const FOG = '#0b2b39';
const v3 = p => new THREE.Vector3(p[0], p[1], p[2]);
const same3 = (a, b, e = 1e-4) => Math.abs(a.x - b.x) < e && Math.abs(a.y - b.y) < e && Math.abs(a.z - b.z) < e;

function disposeTree(root) {
  const seen = new Set();
  root?.traverse(o => {
    if (o.geometry && !seen.has(o.geometry)) { seen.add(o.geometry); o.geometry.dispose(); }
    for (const m of o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : []) {
      if (seen.has(m)) continue;
      seen.add(m);
      Object.values(m).forEach(v => { if (v?.isTexture && !seen.has(v)) { seen.add(v); v.dispose(); } });
      m.dispose();
    }
  });
}

function labelSprite(text, accent = '#7de3d6') {
  const c = document.createElement('canvas'); c.width = 512; c.height = 112;
  const g = c.getContext('2d'); g.fillStyle = 'rgba(7,24,33,.86)'; g.strokeStyle = accent; g.lineWidth = 3;
  g.fillRect(8, 8, 496, 96); g.strokeRect(8, 8, 496, 96); g.fillStyle = '#ecf7f5';
  g.font = '700 28px "Microsoft JhengHei",sans-serif'; g.fillText(text, 26, 66);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false, depthWrite: false }));
  s.scale.set(7.4, 1.62, 1); return s;
}

/**
 * Procedural 3D Shipwreck matching wreck_manifest.json bounds_z_up:
 * X: [69.54 .. 105.43], Y: [-21.64 .. 8.64], Z: [-1.60 .. 18.59]
 */
export function buildProceduralWreckGroup() {
  const wreck = new THREE.Group();
  wreck.name = 'P260_Procedural_Shipwreck';

  const hullMat = new THREE.MeshStandardMaterial({
    color: 0x4b5f66,
    roughness: 0.84,
    metalness: 0.28,
  });
  const ribMat = new THREE.MeshStandardMaterial({
    color: 0x394b52,
    roughness: 0.78,
    metalness: 0.36,
  });
  const rustMat = new THREE.MeshStandardMaterial({
    color: 0x6e533e,
    roughness: 0.88,
    metalness: 0.18,
  });
  const highlightMat = new THREE.MeshStandardMaterial({
    color: 0x5d828a,
    roughness: 0.65,
    metalness: 0.32,
  });

  // Main hull body centered around (87.5, -3.5, 8.2)
  const mainHull = new THREE.Mesh(new THREE.BoxGeometry(33.5, 13.6, 11.4), hullMat);
  mainHull.position.set(87.5, -2.2, 6.2);
  wreck.add(mainHull);

  // A-end rounded bow/stern structure (X ~ 70..78)
  const aEnd = new THREE.Mesh(new THREE.CylinderGeometry(6.6, 5.2, 11.4, 18), rustMat);
  aEnd.position.set(73.2, -2.4, 6.2);
  wreck.add(aEnd);

  // Deckhouse / A-end recessed openings (target of detail inspection at [75.5, -4.2, 9.5])
  const aDeckHouse = new THREE.Mesh(new THREE.BoxGeometry(7.2, 8.4, 5.2), highlightMat);
  aDeckHouse.position.set(76.2, -3.6, 10.6);
  wreck.add(aDeckHouse);

  // Structural ribs along MID section facing camera (Y ~ -7.8 .. -4.5, X ~ 82..92, Z ~ 6..13)
  for (let x = 79.0; x <= 95.5; x += 1.65) {
    const rib = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.85, 11.2), ribMat);
    rib.position.set(x, -6.15, 6.6);
    wreck.add(rib);
  }
  // Horizontal stringers / layer strakes (Layers 1, 2, 3 at Z = 12.0, 10.7, 9.4)
  for (const z of [7.8, 9.4, 10.7, 12.0]) {
    const strake = new THREE.Mesh(new THREE.BoxGeometry(20.0, 0.55, 0.28), rustMat);
    strake.position.set(87.0, -6.25, z);
    wreck.add(strake);
  }

  // B-end gantry / mast truss (X ~ 98..105)
  const bBase = new THREE.Mesh(new THREE.BoxGeometry(7.5, 11.2, 9.8), hullMat);
  bBase.position.set(100.8, -2.0, 6.0);
  wreck.add(bBase);
  for (const y of [-5.8, 1.8]) {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.52, 16.5, 12), ribMat);
    post.rotation.x = Math.PI / 2;
    post.position.set(101.5, y, 10.2);
    wreck.add(post);
  }
  const crossBeam = new THREE.Mesh(new THREE.BoxGeometry(1.1, 8.4, 0.9), highlightMat);
  crossBeam.position.set(101.5, -2.0, 16.8);
  wreck.add(crossBeam);

  // Deck equipment / winches / hatches for visual richness in onboard camera
  for (let i = 0; i < 6; i++) {
    const winch = new THREE.Mesh(new THREE.CylinderGeometry(0.65, 0.65, 1.6, 14), highlightMat);
    winch.rotation.z = Math.PI / 2;
    winch.position.set(75.5 + i * 3.8, -4.8, 9.2 + (i % 2) * 1.4);
    wreck.add(winch);
  }

  return wreck;
}

export async function createSopScene(externalEl, cameraEl, { onStatus = () => {} } = {}) {
  let extR, camR, observer, scene;
  const dispose = () => {
    observer?.disconnect(); disposeTree(scene);
    for (const r of [extR, camR]) if (r) { r.dispose(); r.domElement.remove(); }
  };
  try {
    onStatus('Loading ROV-01 and wreck scene');
    const makeR = (el, exp) => {
      const r = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: true });
      r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      r.outputColorSpace = THREE.SRGBColorSpace; r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = exp;
      r.domElement.style.cssText = 'display:block;width:100%;height:100%'; el.querySelectorAll("canvas").forEach(c => c.remove()); el.prepend(r.domElement); return r;
    };
    extR = makeR(externalEl, 1.18); camR = makeR(cameraEl, 1.32);
    scene = new THREE.Scene(); scene.background = new THREE.Color(FOG); scene.fog = new THREE.FogExp2(FOG, 0.015);
    const extCam = new THREE.PerspectiveCamera(42, 1, 0.08, 400); extCam.up.set(0, 0, 1);
    const rovCam = new THREE.PerspectiveCamera(56, 1, 0.08, 160); rovCam.up.set(0, 0, 1);

    const hemi = new THREE.HemisphereLight(0xbbeeff, 1452851, 2.2); hemi.position.set(0, 0, 1); scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xd9f5ff, 2.8); sun.position.set(52, -46, 85); scene.add(sun);
    const rim = new THREE.DirectionalLight(0x6bd4cb, 1.5); rim.position.set(112, 34, 28); scene.add(rim);

    // Build procedural shipwreck & seabed
    const wreck = buildProceduralWreckGroup();
    scene.add(wreck);
    wreck.updateMatrixWorld(true);
    const wb = new THREE.Box3().setFromObject(wreck), ws = wb.getSize(new THREE.Vector3()), wc = wb.getCenter(new THREE.Vector3());

    const bed = new THREE.Mesh(
      new THREE.PlaneGeometry(260, 260, 28, 28),
      new THREE.MeshStandardMaterial({ color: 1521732, roughness: 0.96, metalness: 0.04 })
    );
    bed.position.set(wc.x, wc.y, wb.min.z - 0.35);
    const grid = new THREE.GridHelper(180, 36, 0x3b7f86, 2051929);
    grid.rotation.x = Math.PI / 2; grid.position.set(wc.x, wc.y, wb.min.z - 0.3);
    grid.material.transparent = true; grid.material.opacity = 0.25;
    scene.add(bed, grid);

    // CORR-ROV-01: Self-designed ROV-01 open-frame industrial ROV mesh (zero external commercial shell dependency)
    const rovRoot = new THREE.Group();
    rovRoot.name = 'ROV01_Scene_Actor';
    const rov01 = createRov01IndustrialMesh({ frame: 'p260' });
    rov01.root.scale.setScalar(1.9);
    rovRoot.add(rov01.root);

    const lampL = new THREE.SpotLight(0xfff4d8, 24, 34, 0.58, 0.55, 1.3);
    const lampR = lampL.clone();
    lampL.position.set(-0.28, 0.55, 0.08);
    lampR.position.set(0.28, 0.55, 0.08);
    const lampTarget = new THREE.Object3D();
    lampTarget.position.set(0, 8, -0.3);
    rovRoot.add(lampL, lampR, lampTarget);
    lampL.target = lampTarget;
    lampR.target = lampTarget;
    scene.add(rovRoot);

    const segments = new THREE.Group(); scene.add(segments);
    [['A 端', '#7bdff2'], ['中段 · 示範採集區', '#72efdd'], ['B 端', '#f7d08a']].forEach(([title, col], i) => {
      const g = new THREE.BoxGeometry(ws.x / 3, ws.y * 1.02, ws.z * 1.02);
      const x = wb.min.x + ws.x * (i + 0.5) / 3;
      const box = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: i === 1 ? 0.07 : 0.03, depthWrite: false, side: THREE.DoubleSide }));
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(g), new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: i === 1 ? 0.72 : 0.34, depthWrite: false }));
      const tag = labelSprite(`0${i + 1} ${title}`, col); tag.position.set(x, wc.y, wb.max.z + 2.2);
      box.position.set(x, wc.y, wc.z); edge.position.copy(box.position); segments.add(box, edge, tag);
    });

    const routeGroup = new THREE.Group(); scene.add(routeGroup);
    const routePts = [
      [84, -8, 12], [90, -8, 12], [90, -8, 10.7], [84, -8, 10.7], [84, -8, 9.4], [90, -8, 9.4],
    ].map(v3);
    const fullCurve = new THREE.CatmullRomCurve3(routePts, false, 'catmullrom', 0.08);
    const plannedTube = new THREE.Mesh(
      new THREE.TubeGeometry(fullCurve, 72, 0.065, 8, false),
      new THREE.MeshBasicMaterial({ color: 0x4ea8b4, transparent: true, opacity: 0.34, depthWrite: false })
    );
    const activeMat = new THREE.MeshBasicMaterial({ color: 0x72efdd, transparent: true, opacity: 0.92 });
    const activeTube = new THREE.Mesh(new THREE.BufferGeometry(), activeMat);
    routeGroup.add(plannedTube, activeTube);
    for (const p of routePts) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 12), new THREE.MeshBasicMaterial({ color: 0xb8fff4 }));
      m.position.copy(p); routeGroup.add(m);
    }

    const aimMat = new THREE.LineBasicMaterial({ color: 0x72efdd, transparent: true, opacity: 0.45 });
    const aimGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    const aimLine = new THREE.Line(aimGeo, aimMat); scene.add(aimLine);

    const resize = () => {
      for (const [el, r, cam] of [[externalEl, extR, extCam], [cameraEl, camR, rovCam]]) {
        const w = Math.max(el.clientWidth, 1), h = Math.max(el.clientHeight, 1);
        cam.aspect = w / h; cam.updateProjectionMatrix(); r.setSize(w, h, false);
      }
    };
    observer = new ResizeObserver(resize); observer.observe(externalEl); observer.observe(cameraEl); resize();

    let lastState = null;
    const render = state => {
      lastState = state;
      const pos = v3(state.cameraOrigin), target = v3(state.target), ext = v3(state.external), extTarget = v3(state.externalTarget);
      rovRoot.position.copy(pos);
      const dir = target.clone().sub(pos); dir.z *= 0.35;
      if (dir.lengthSq() > 1e-5) {
        const yaw = Math.atan2(dir.x, dir.y);
        rovRoot.rotation.set(0, 0, -yaw);
      }
      // Spin ROV-01 6 rotors and animate thrust plumes
      const synthThrust = [0.65, 0.65, 0.55, 0.55, 0.35, 0.35];
      const synthHealth = [1, 1, 1, 1, 1, 1];
      const utRingMode = (state.t >= 24 && state.t <= 90) ? "coupled" : (state.t >= 16 && state.t < 24) ? "aligning" : "searching";
      rov01.updateThrusters(synthThrust, 0.016, synthHealth, utRingMode);

      segments.visible = Boolean(state.showSegments);
      routeGroup.visible = state.t >= 24 && state.t <= 90;
      const trail = (state.scanTrail || []).map(v3).filter((p, i, a) => i === 0 || !same3(p, a[i - 1]));
      activeTube.geometry.dispose();
      activeTube.geometry = trail.length >= 2
        ? new THREE.TubeGeometry(new THREE.CatmullRomCurve3(trail, false, 'catmullrom', 0.05), 48, 0.1, 8, false)
        : new THREE.BufferGeometry();
      aimGeo.setFromPoints([pos, pos.clone().lerp(target, 0.55)]);

      extCam.position.copy(ext); extCam.lookAt(extTarget);
      const viewDir = target.clone().sub(pos).normalize();
      rovCam.position.copy(pos).addScaledVector(viewDir, 0.65); rovCam.lookAt(target);

      rovRoot.visible = true; aimLine.visible = true;
      extR.render(scene, extCam);

      rovRoot.visible = false; segments.visible = false; routeGroup.visible = false; aimLine.visible = false;
      camR.render(scene, rovCam);
      rovRoot.visible = true;
    };

    const capture = () => camR.domElement.toDataURL('image/jpeg', 0.84);
    const inspect = () => ({
      wreckBounds: { min: wb.min.toArray(), max: wb.max.toArray(), size: ws.toArray() },
      rovLoaded: true,
      rovModel: 'ROV-01',
      rovThrusters: rov01.rotors.length,
      lastTime: lastState?.t ?? null,
      externalCanvas: [extR.domElement.width, extR.domElement.height],
      cameraCanvas: [camR.domElement.width, camR.domElement.height],
    });
    onStatus('ROV-01 scene ready');
    return { render, resize, dispose, capture, inspect, scene };
  } catch (e) {
    dispose();
    throw e;
  }
}
