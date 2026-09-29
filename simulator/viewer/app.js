// X1 ROV training viewer / pilot console.
// Renders the qysim state stream (PROTOCOL.md §2–4) and sends the pilot's RC channels back.
// Frames: server NED world / FRD body  →  three.js Y-up: three(x,y,z) = (−east, −down, north).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { DeployIntro } from './deploy_intro.js';
import { PilotPiP } from './pilot_pip.js';

const $ = (id) => document.getElementById(id);
const DEG = Math.PI / 180, KNOT = 0.514444;
const WARN_N = 250, BREAK_N = 300 * 9.80665;          // tether.py TetherParams warn_n / breaking_n
const css = getComputedStyle(document.documentElement);
const C = (n) => css.getPropertyValue(n).trim();
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const fmtT = (s) => { s = Math.max(0, Math.round(s || 0)); return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; };
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// NED point → three
const P = (p, out = new THREE.Vector3()) => out.set(-p[1], -p[2], p[0]);
// body→world quaternion [w,x,y,z] (FRD→NED) → three (vector part mapped like points)
const Q = (q, out = new THREE.Quaternion()) => out.set(-q[2], -q[3], q[1], q[0]);

/* ═════════════════════════ renderer / scene ═════════════════════════ */
const vp = $('vp');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.domElement.className = 'gl';
vp.prepend(renderer.domElement);

const scene = new THREE.Scene();
const waterSurf = new THREE.Color('#1d6378'), waterDeep = new THREE.Color('#04151e'), siltCol = new THREE.Color('#3b3a26');
scene.background = new THREE.Color('#0a2a38');
scene.fog = new THREE.Fog(0x0a2a38, 0.3, 12);
const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 1500);
camera.position.set(-3, 1.5, -3);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.minDistance = 0.8; controls.maxDistance = 120; controls.enabled = false;

scene.add(new THREE.HemisphereLight(0xa8dcf0, 0x1a2a22, 1.5));
const sun = new THREE.DirectionalLight(0xdff4ff, 1.6); sun.position.set(20, 60, 10); scene.add(sun);

// seabed + grid
const seabed = new THREE.Group(); scene.add(seabed);
{
  const g = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), new THREE.MeshStandardMaterial({ color: 0x4a4636, roughness: 1 }));
  g.rotation.x = -Math.PI / 2; seabed.add(g);
  const grid = new THREE.GridHelper(200, 100, 0x6a7a66, 0x39443a); grid.position.y = 0.02; seabed.add(grid);
  const big = new THREE.GridHelper(800, 40, 0x7d8a70, 0x7d8a70); big.position.y = 0.03; seabed.add(big);
}
seabed.position.y = -30;
// sea surface
const surface = new THREE.Mesh(new THREE.PlaneGeometry(800, 800),
  new THREE.MeshBasicMaterial({ color: 0x6fc3d8, transparent: true, opacity: 0.32, side: THREE.DoubleSide, depthWrite: false }));
surface.rotation.x = -Math.PI / 2; scene.add(surface);

/* ═════════════════════════ ROV ═════════════════════════ */
const rovG = new THREE.Group(); scene.add(rovG);            // posed from state
const body = new THREE.Group(); rovG.add(body);             // model in body frame (three-mapped FRD)
const placeholder = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.3, 0.6), new THREE.MeshStandardMaterial({ color: 0xf2b705, roughness: .6 }));
body.add(placeholder);
let noseZ = 0.34;
const rotors = [];            // model rotor nodes {o, base, axis, pos}
let rotorOf = [];             // physics thruster index → rotor
const leds = [];
for (const x of [0.12, -0.12]) {
  const l = new THREE.SpotLight(0xf4f8ff, 0, 25, 0.55, 0.6, 1.2);
  l.position.set(x, -0.02, noseZ); l.target.position.set(x * 3, -0.4, 6);
  body.add(l); body.add(l.target); leds.push(l);
}

// top-view marker: arrow on the ROV pointing along the nose (scaled with view height)
const topMark = new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape([new THREE.Vector2(0, .9), new THREE.Vector2(.5, -.5), new THREE.Vector2(0, -.2), new THREE.Vector2(-.5, -.5)])),
  new THREE.MeshBasicMaterial({ color: 0xf2b705, fog: false, transparent: true, opacity: .85, depthTest: false, side: THREE.DoubleSide }));
topMark.renderOrder = 10; topMark.visible = false; scene.add(topMark);

function loadModel() {
  new GLTFLoader().load('rov.glb', (gltf) => {
    const root = gltf.scene;
    const box = new THREE.Box3().setFromObject(root);
    const ctr = box.getCenter(new THREE.Vector3());
    const holder = new THREE.Group(); holder.add(root); root.position.sub(ctr);
    holder.updateMatrixWorld(true);
    noseZ = box.max.z - ctr.z;
    root.traverse((o) => {
      if (o.userData.role !== 'rotor') return;
      const wq = o.getWorldQuaternion(new THREE.Quaternion());
      const axis = new THREE.Vector3(...(o.userData.axis || [0, 0, 1])).applyQuaternion(wq.clone().invert()).normalize();
      rotors.push({ o, base: o.quaternion.clone(), axis, pos: o.getWorldPosition(new THREE.Vector3()), ang: 0 });
    });
    body.remove(placeholder); body.add(holder);
    leds.forEach((l) => l.position.setZ(noseZ));
    matchThrusters();
  }, undefined, (e) => { console.warn('rov.glb 載入失敗，使用簡化模型', e?.message || e); });
}

// Map each physics thruster to the GLB rotor nearest in model space (names in the GLB are L/R-swapped).
function matchThrusters() {
  const th = W?.thrusters; if (!th || !rotors.length) return;
  const pp = th.map((t) => new THREE.Vector3(-t.pos[1], -t.pos[2], t.pos[0]));
  const mP = pp.reduce((a, v) => a.add(v), new THREE.Vector3()).divideScalar(pp.length);
  const mR = rotors.reduce((a, r) => a.add(r.pos), new THREE.Vector3()).divideScalar(rotors.length);
  const A = pp.map((v) => v.clone().sub(mP)), B = rotors.map((r) => r.pos.clone().sub(mR));
  const n = A.length, used = new Array(B.length).fill(false), cur = [];
  let best = null, bestCost = Infinity;
  (function rec(i, cost) {                       // exhaustive assignment (6! = 720)
    if (cost >= bestCost) return;
    if (i === n) { bestCost = cost; best = cur.slice(); return; }
    for (let j = 0; j < B.length; j++) if (!used[j]) {
      used[j] = true; cur.push(j); rec(i + 1, cost + A[i].distanceToSquared(B[j])); cur.pop(); used[j] = false;
    }
  })(0, 0);
  rotorOf = best ? best.map((j) => rotors[j]) : [];
}

/* ═════════════════════════ world objects ═════════════════════════ */
const worldG = new THREE.Group(); scene.add(worldG);
const obstacleMeshes = new Map();       // name → {mesh, ob}
const objG = new THREE.Group(); scene.add(objG);
let objMarkers = [];
const OB_COL = { pile: 0x6f6a58, monopile: 0x7c6f4f, jacket_leg: 0xb38a3a, brace: 0x9a7c44, mast: 0x5d5d5d, hull: 0x5a2626, wreck: 0x4e4234, wall: 0x5b605a };

let spoolMarker = [];
function buildWorld() {
  worldG.clear(); obstacleMeshes.clear();
  seabed.position.y = -W.seabed_depth;
  for (const ob of W.obstacles || []) {
    const mat = new THREE.MeshStandardMaterial({ color: OB_COL[ob.kind] ?? 0x666666, roughness: .85, metalness: .1 });
    let mesh;
    if (ob.type === 'cylinder') {
      const a = P(ob.p0), b = P(ob.p1), len = a.distanceTo(b);
      mesh = new THREE.Mesh(new THREE.CylinderGeometry(ob.radius, ob.radius, len, 24, 1), mat);
      mesh.position.copy(a).add(b).multiplyScalar(.5);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    } else if (ob.type === 'box') {
      const [hx, hy, hz] = ob.half;
      mesh = new THREE.Mesh(new THREE.BoxGeometry(2 * hy, 2 * hz, 2 * hx), mat);   // local: x=−starboard-ish, y=up, z=along heading
      P(ob.center, mesh.position); mesh.rotation.y = -ob.yaw_deg * DEG;
    } else if (ob.type === 'wall') {
      const h = W.seabed_depth - ob.top, a = ob.normal_deg * DEG, th = 0.6;
      mesh = new THREE.Mesh(new THREE.BoxGeometry(ob.width, h, th), mat);
      const nrm = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a));
      P([ob.point[0], ob.point[1], (ob.top + W.seabed_depth) / 2], mesh.position).addScaledVector(nrm, -th / 2);
      mesh.rotation.y = -a;
    }
    if (mesh) { worldG.add(mesh); obstacleMeshes.set(ob.name, { mesh, ob }); }
  }
  // spool / deployment point
  const sp = P(W.spool || [0, 0, 0]);
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(.45, .45, .7, 20), new THREE.MeshStandardMaterial({ color: 0xf2b705, roughness: .5 }));
  drum.rotation.z = Math.PI / 2; drum.position.copy(sp).add(new THREE.Vector3(0, .5, 0)); worldG.add(drum); spoolMarker = [drum];
  const deck = new THREE.Mesh(new THREE.BoxGeometry(2.2, .3, 3.2), new THREE.MeshStandardMaterial({ color: 0x8795a0 }));
  deck.position.copy(sp).add(new THREE.Vector3(0, .1, -.6)); worldG.add(deck); spoolMarker.push(deck);
  buildObjectives(W.objectives || []);
  buildThrBars();
  matchThrusters();
  fillCurrentSliders();
}

function buildObjectives(list) {
  objG.clear(); objMarkers = [];
  list.forEach((o) => {
    const g = new THREE.Group(); P(o.point, g.position);
    const mat = new THREE.MeshBasicMaterial({ color: 0x7f99a8, transparent: true, opacity: .75, depthWrite: false });
    const wire = new THREE.MeshBasicMaterial({ color: 0x7f99a8, transparent: true, opacity: .18, wireframe: true, depthWrite: false });
    let bill = null;
    const r = Math.max(.3, o.radius || 1);
    if (o.kind === 'checkpoint') {
      bill = new THREE.Mesh(new THREE.TorusGeometry(r, .06, 8, 48), mat); g.add(bill);
      g.add(new THREE.Mesh(new THREE.SphereGeometry(.08, 10, 8), mat));
    } else if (o.kind === 'inspect') {
      g.add(new THREE.Mesh(new THREE.OctahedronGeometry(.18), mat));
      g.add(new THREE.Mesh(new THREE.SphereGeometry(r, 16, 10), wire));
    } else {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r, .07, 8, 48), mat); ring.rotation.x = Math.PI / 2; g.add(ring);
      g.add(new THREE.Mesh(new THREE.SphereGeometry(r, 16, 10), wire));
    }
    objG.add(g);
    objMarkers.push({ o, g, mat, wire, bill });
  });
}

// route / guide line
const MAXR = 400;
const routeLine = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXR * 3), 3)),
  new THREE.LineBasicMaterial({ color: 0xc792ff, fog: false }));
routeLine.frustumCulled = false; scene.add(routeLine);
const navTarget = new THREE.Mesh(new THREE.SphereGeometry(.2, 12, 8), new THREE.MeshBasicMaterial({ color: 0xc792ff, fog: false, wireframe: true }));
scene.add(navTarget);
const guide = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3)),
  new THREE.LineDashedMaterial({ color: 0xf2b705, dashSize: .4, gapSize: .3, transparent: true, opacity: .7, fog: false }));
guide.frustumCulled = false; scene.add(guide);

/* ═════════════════════════ tether ═════════════════════════ */
const MAXN = 1024;
const tetherLine = new THREE.Line(new THREE.BufferGeometry()
  .setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXN * 3), 3))
  .setAttribute('color', new THREE.BufferAttribute(new Float32Array(MAXN * 3), 3)),
new THREE.LineBasicMaterial({ vertexColors: true }));
tetherLine.frustumCulled = false; scene.add(tetherLine);
const brokenLine = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXN * 3), 3)),
  new THREE.LineDashedMaterial({ color: 0xff4757, dashSize: .35, gapSize: .25 }));
brokenLine.frustumCulled = false; brokenLine.visible = false; scene.add(brokenLine);
const tubeMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .55, metalness: 0 });
const GLAND_LOCAL = new THREE.Vector3(0, .06, -.38);   // tether.py GLAND_BODY (FRD -0.38, 0, -0.06) in model space
let tetherTarget = [], tetherDisp = [], tetherInfo = null;
let tube = null;
const contactMesh = new THREE.InstancedMesh(new THREE.SphereGeometry(.08, 8, 6), new THREE.MeshBasicMaterial({ color: 0xff4757 }), 256);
contactMesh.count = 0; contactMesh.frustumCulled = false; scene.add(contactMesh);
const wrapG = new THREE.Group(); scene.add(wrapG);

const colLow = new THREE.Color('#e9c534'), colWarn = new THREE.Color('#ffb020'), colBreak = new THREE.Color('#ff3040');
function tensionColor(T, out) {
  if (T <= WARN_N) return out.copy(colLow).lerp(colWarn, Math.pow(clamp(T / WARN_N, 0, 1), 1.6));
  return out.copy(colWarn).lerp(colBreak, clamp((T - WARN_N) / (BREAK_N - WARN_N), 0, 1) ** .6);
}

function distToObstacle(p, ob) {        // p NED; approximate surface distance
  if (ob.type === 'cylinder') {
    const a = ob.p0, b = ob.p1, ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], ap = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
    const L = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2, t = clamp((ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L, 0, 1);
    return Math.hypot(ap[0] - ab[0] * t, ap[1] - ab[1] * t, ap[2] - ab[2] * t) - ob.radius;
  }
  if (ob.type === 'box') {
    const y = ob.yaw_deg * DEG, r = [p[0] - ob.center[0], p[1] - ob.center[1], p[2] - ob.center[2]];
    const l = [r[0] * Math.cos(y) + r[1] * Math.sin(y), -r[0] * Math.sin(y) + r[1] * Math.cos(y), r[2]];
    const q = l.map((v, i) => Math.max(Math.abs(v) - ob.half[i], 0));
    return Math.hypot(...q);
  }
  if (ob.type === 'wall') {
    const a = ob.normal_deg * DEG, n = [Math.cos(a), Math.sin(a)], r = [p[0] - ob.point[0], p[1] - ob.point[1]];
    if (Math.abs(-r[0] * n[1] + r[1] * n[0]) > ob.width / 2 || p[2] < ob.top) return 1e3;
    return Math.abs(r[0] * n[0] + r[1] * n[1]);
  }
  return 1e3;
}

const _c = new THREE.Color(), _m = new THREE.Matrix4();
let wrapLabels = [];
function updateTether(t) {
  const nodes = t.nodes || [];
  const n = Math.min(nodes.length, MAXN);
  const pts = []; for (let i = 0; i < n; i++) pts.push(P(nodes[i]));
  const ts = t.tension_spool || 0, tr = t.tension_rov || 0;
  const Tat = (s) => { const T = ts + (tr - ts) * s; return t.warn ? Math.max(T, WARN_N) : T; };
  // polyline (always visible)
  const lp = tetherLine.geometry.attributes.position.array, lc = tetherLine.geometry.attributes.color.array;
  for (let i = 0; i < n; i++) {
    lp[i * 3] = pts[i].x; lp[i * 3 + 1] = pts[i].y; lp[i * 3 + 2] = pts[i].z;
    tensionColor(Tat(i / Math.max(1, n - 1)), _c); lc[i * 3] = _c.r; lc[i * 3 + 1] = _c.g; lc[i * 3 + 2] = _c.b;
  }
  tetherLine.geometry.setDrawRange(0, n);
  tetherLine.geometry.attributes.position.needsUpdate = true; tetherLine.geometry.attributes.color.needsUpdate = true;
  tetherLine.visible = !t.broken;
  // broken: dashed red
  brokenLine.visible = !!t.broken;
  if (t.broken) {
    const bp = brokenLine.geometry.attributes.position.array;
    for (let i = 0; i < n; i++) { bp[i * 3] = pts[i].x; bp[i * 3 + 1] = pts[i].y; bp[i * 3 + 2] = pts[i].z; }
    brokenLine.geometry.setDrawRange(0, n); brokenLine.geometry.attributes.position.needsUpdate = true;
    brokenLine.computeLineDistances();
  }
  // tube: rebuilt every frame from smoothed nodes (see renderTether)
  tetherTarget = pts; tetherInfo = t;
  if (tetherDisp.length !== pts.length) tetherDisp = pts.map((p) => p.clone());
  // contact nodes (client-side proximity; server only reports the count)
  let k = 0;
  if (t.contact_nodes > 0 && W) {
    for (let i = 0; i < n && k < 256; i++) {
      for (const ob of W.obstacles || []) {
        if (distToObstacle(nodes[i], ob) < .2) { _m.makeTranslation(pts[i].x, pts[i].y, pts[i].z); contactMesh.setMatrixAt(k++, _m); break; }
      }
      if (k < 256 && nodes[i][2] > (W.seabed_depth - .12)) { _m.makeTranslation(pts[i].x, pts[i].y, pts[i].z); contactMesh.setMatrixAt(k++, _m); }
    }
  }
  contactMesh.count = k; contactMesh.instanceMatrix.needsUpdate = true;
  // snag / wrap highlight
  const snag = new Set(t.snagged_on || []), wraps = t.wraps || {};
  for (const [name, { mesh }] of obstacleMeshes) {
    const hot = snag.has(name) || Math.abs(wraps[name] || 0) >= .25;
    mesh.material.emissive.setHex(hot ? 0x4a0a10 : 0x000000);
  }
  wrapG.clear(); wrapLabels = [];
  for (const [name, turns] of Object.entries(wraps)) {
    const e = obstacleMeshes.get(name); if (!e || Math.abs(turns) < .05) continue;
    const ob = e.ob; let best = null, bd = 1e9;
    for (let i = 0; i < n; i++) { const d = distToObstacle(nodes[i], ob); if (d < bd) { bd = d; best = i; } }
    if (best == null) continue;
    const at = pts[best].clone();
    if (ob.type === 'cylinder') {
      const a = P(ob.p0), b = P(ob.p1), ax = b.clone().sub(a).normalize();
      const c = a.clone().addScaledVector(ax, at.clone().sub(a).dot(ax));
      const ring = new THREE.Mesh(new THREE.TorusGeometry(ob.radius + .1, .05, 8, 40), new THREE.MeshBasicMaterial({ color: 0xff4757, fog: false }));
      ring.position.copy(c); ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), ax); wrapG.add(ring);
      at.copy(c).add(new THREE.Vector3(0, .6, 0));
    }
    wrapLabels.push({ id: 'wrap:' + name, text: `纏繞 ${name} ${turns > 0 ? '↻' : '↺'} ${Math.abs(turns).toFixed(2)} 圈`, pos: at, cls: 'bad' });
  }
}

/* ═════════════════════════ current: arrow + drifting particles ═════════════════════════ */
const curArrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 1, 0x4fd1ff, .25, .16);
scene.add(curArrow);
function layer(kn, dir) { const a = dir * DEG; return [Math.cos(a) * kn * KNOT, Math.sin(a) * kn * KNOT]; }
function currentAt(depth) {           // replicates world.CurrentProfile.mean_at (horizontal NED m/s)
  const c = W?.current; if (!c) return [0, 0];
  const sb = W.seabed_depth, s = layer(c.surface_kn, c.surface_dir), m = layer(c.mid_kn, c.mid_dir), b = layer(c.bottom_kn, c.bottom_dir);
  const md = sb / 2; let v;
  if (depth <= md) { const t = clamp(depth / md, 0, 1); v = [s[0] * (1 - t) + m[0] * t, s[1] * (1 - t) + m[1] * t]; }
  else { const t = clamp((depth - md) / Math.max(sb - md, 1e-6), 0, 1); v = [m[0] * (1 - t) + b[0] * t, m[1] * (1 - t) + b[1] * t]; }
  const above = sb - depth; if (above < 1) { const f = Math.max(0, above); v = [v[0] * f, v[1] * f]; }
  return v;
}
const NP = 900, HB = [9, 5, 9];
const partPos = new Float32Array(NP * 3);
for (let i = 0; i < NP; i++) for (let k = 0; k < 3; k++) partPos[i * 3 + k] = (Math.random() * 2 - 1) * HB[k];
const partGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(partPos, 3));
const dot = (() => { const c = document.createElement('canvas'); c.width = c.height = 32; const x = c.getContext('2d');
  const g = x.createRadialGradient(16, 16, 0, 16, 16, 16); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(.4, 'rgba(255,255,255,.6)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 32, 32); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
const particles = new THREE.Points(partGeo, new THREE.PointsMaterial({ color: 0xbfe3ef, size: .035, map: dot, transparent: true, opacity: .8, depthWrite: false }));
particles.frustumCulled = false; scene.add(particles);
let partCentre = null;
function updateParticles(dt, centre) {
  particles.visible = $('optFlow').checked;
  if (!particles.visible) return;
  if (!partCentre) partCentre = centre.clone();
  for (let i = 0; i < NP; i++) {
    const j = i * 3; let x = partPos[j], y = partPos[j + 1], z = partPos[j + 2];
    const depth = -y; const v = currentAt(depth);
    x += -v[1] * dt; z += v[0] * dt; y += (Math.sin(i * 12.9 + x) * .02) * dt;
    // keep inside a box around the camera target (world-fixed particles, wrapped)
    const dx = x - centre.x, dy = y - centre.y, dz = z - centre.z;
    if (dx > HB[0]) x -= 2 * HB[0]; else if (dx < -HB[0]) x += 2 * HB[0];
    if (dy > HB[1]) y -= 2 * HB[1]; else if (dy < -HB[1]) y += 2 * HB[1];
    if (dz > HB[2]) z -= 2 * HB[2]; else if (dz < -HB[2]) z += 2 * HB[2];
    if (W && (y < -W.seabed_depth || y > 0)) y = centre.y + (Math.random() * 2 - 1) * HB[1] * .5;
    partPos[j] = x; partPos[j + 1] = y; partPos[j + 2] = z;
  }
  partGeo.attributes.position.needsUpdate = true;
}

/* ═════════════════════════ networking ═════════════════════════ */
const params = new URLSearchParams(location.search);
const WS_URL = params.get('ws') || `ws://${location.hostname || '127.0.0.1'}:8765`;
let ws = null, wsOpen = false, retry = 0, retryAt = 0, needResync = true, lastT = -1;
let W = null, S = null, stateCount = 0;
$('offUrl').textContent = WS_URL;

function send(obj) { if (ws && wsOpen) { try { ws.send(JSON.stringify(obj)); return true; } catch { } } return false; }
function setConn(kind, text) { const el = $('conn'); el.className = 'pill ' + kind; el.textContent = text; }
function connect() {
  setConn('wait', '連線中…');
  try { ws = new WebSocket(WS_URL); } catch (e) { scheduleRetry(); return; }
  ws.onopen = () => { wsOpen = true; retry = 0; needResync = true; setConn('wait', '已連線 · 等待資料'); lastSent = ''; };
  ws.onmessage = (ev) => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'world') onWorld(m); else if (m.type === 'state') onState(m);
  };
  ws.onclose = () => { wsOpen = false; ws = null; setConn('stop', '離線'); $('offline').hidden = false; scheduleRetry(); };
  ws.onerror = () => { };
}
function scheduleRetry() {
  const d = Math.min(5000, 800 * 2 ** retry++);
  retryAt = performance.now() + d;
  setTimeout(connect, d);
}
setInterval(() => {
  const r = retryAt - performance.now();
  $('offRetry').textContent = !wsOpen && r > 0 ? `（${Math.ceil(r / 1000)} 秒後重試）` : !wsOpen ? '（連線中…）' : '';
}, 250);

function onWorld(m) {
  const firstOrNew = !W || W.scenario?.key !== m.scenario?.key || W.scenario?.seed !== m.scenario?.seed;
  W = m;
  buildWorld();
  $('scnName').textContent = m.scenario?.name || '—';
  $('brief').textContent = m.scenario?.brief || '';
  fillCatalogue(firstOrNew);
  $('offline').hidden = true;
  if (firstOrNew) startIntro();
}

function onState(m) {
  if (lastT >= 0 && m.t < lastT - 0.5) needResync = true;    // scenario loaded / reset → server RC reset to locked
  lastT = m.t;
  S = m; stateCount++;
  if (needResync && !m.remote_control && m.rc) {
    rc.rc_lock = m.rc.rc_lock; rc.keep_depth = m.rc.keep_depth; rc.left_switch = m.rc.left_switch; rc.right_switch = m.rc.right_switch;
    needResync = false;
  }
  setConn('run', m.paused ? '已連線 · 暫停' : '已連線');
  if (W) $('offline').hidden = true;
  target.pos = P(m.pos, target.pos); Q(m.q, target.q);
  if (!target.init) { rovG.position.copy(target.pos); rovG.quaternion.copy(target.q); target.init = true; }
  updateTether(m.tether || {});
  updateRoute(m.nav);
  const ch = m.current_here || [0, 0, 0], cv = P(ch), sp = cv.length();
  if (sp > 1e-3) curArrow.setDirection(cv.clone().normalize());
  curArrow.setLength(.3 + sp / KNOT * .45, .16, .1);
  curArrow.visible = sp > 1e-3 && !introActive();
  checkEvents(m.events || []);
  uiDirty = true;
}
const target = { pos: new THREE.Vector3(), q: new THREE.Quaternion(), init: false };

function updateRoute(nav) {
  const r = nav?.route || [];
  const a = routeLine.geometry.attributes.position.array, n = Math.min(r.length, MAXR);
  const v = new THREE.Vector3();
  for (let i = 0; i < n; i++) { P(r[i], v); a[i * 3] = v.x; a[i * 3 + 1] = v.y; a[i * 3 + 2] = v.z; }
  routeLine.geometry.setDrawRange(0, n); routeLine.geometry.attributes.position.needsUpdate = true;
  routeLine.visible = n > 1;
  navTarget.visible = !!nav?.target; if (nav?.target) P(nav.target, navTarget.position);
}

let lastEvT = null;
function checkEvents(evs) {
  if (!evs.length) { lastEvT = lastEvT ?? -1; return; }
  const newest = evs[evs.length - 1];
  if (lastEvT === null) { lastEvT = newest.t; return; }       // don't flash history on connect
  if (newest.t > lastEvT) {
    lastEvT = newest.t;
    const f = $('flash'); f.className = 'flash ' + (newest.severity || 'touch');
    setTimeout(() => (f.className = 'flash'), 350);
  }
}

/* ═════════════════════════ input → RC ═════════════════════════ */
const CH = ['left_ud', 'left_lr', 'right_ud', 'right_lr', 'left_wave', 'right_wave'];
const CH_NAME = { left_ud: '左搖桿 上下', left_lr: '左搖桿 左右', right_ud: '右搖桿 上下', right_lr: '右搖桿 左右', left_wave: '左滾輪', right_wave: '右滾輪' };
const CH_KEYS = { left_ud: ['W', 'S'], left_lr: ['D', 'A'], right_ud: ['↑', '↓'], right_lr: ['→', '←'], left_wave: ['E', 'Q'], right_wave: ['C', 'Z'] };
const MAP = {        // qysim/rc.py _MAP: axis → [channel, sign]
  ROV_USA: { pitch: ['left_ud', -1], yaw: ['left_lr', 1], surge: ['right_ud', 1], roll: ['right_lr', 1], heave: ['left_wave', 1], sway: ['right_wave', 1] },
  ROV_JPN: { surge: ['left_ud', 1], yaw: ['left_lr', 1], pitch: ['right_ud', -1], roll: ['right_lr', 1], heave: ['left_wave', 1], sway: ['right_wave', 1] },
  ROV_CHN: { surge: ['left_ud', 1], roll: ['left_lr', 1], pitch: ['right_ud', -1], yaw: ['right_lr', 1], heave: ['left_wave', 1], sway: ['right_wave', 1] },
  UAV_USA: { heave: ['left_ud', 1], yaw: ['left_lr', 1], surge: ['right_ud', 1], sway: ['right_lr', 1], pitch: ['left_wave', 1], roll: ['right_wave', 1] },
  UAV_JPN: { surge: ['left_ud', 1], yaw: ['left_lr', 1], heave: ['right_ud', 1], sway: ['right_lr', 1], pitch: ['left_wave', 1], roll: ['right_wave', 1] },
  UAV_CHN: { surge: ['left_ud', 1], sway: ['left_lr', 1], heave: ['right_ud', 1], yaw: ['right_lr', 1], pitch: ['left_wave', 1], roll: ['right_wave', 1] },
};
const AX = { surge: ['前進', '後退', '前後'], sway: ['右移', '左移', '橫移'], heave: ['上浮', '下潛', '升降'], roll: ['右滾', '左滾', '橫滾'], pitch: ['抬頭', '低頭', '俯仰'], yaw: ['右轉', '左轉', '轉向'] };
function chanMeaning(mode, ch) {
  const t = MAP[mode] || MAP.ROV_USA;
  for (const [axis, [c, sign]] of Object.entries(t)) if (c === ch) {
    const [p, n, name] = AX[axis];
    return { axis, name, pos: sign > 0 ? p : n, neg: sign > 0 ? n : p };
  }
  return { axis: '', name: '—', pos: '', neg: '' };
}

const rc = { rc_lock: 1, keep_depth: 0, left_switch: 0, right_switch: 0 };
const hold = { photo: new Set(), record: new Set() };
const keys = new Set();
const touch = Object.fromEntries(CH.map((c) => [c, 0]));
const out = Object.fromEntries(CH.map((c) => [c, 0]));   // combined −1..1
let padPrev = [], padName = '';

const toggleLock = () => { rc.rc_lock = rc.rc_lock ? 0 : 1; };
const toggleDepth = () => { rc.keep_depth = rc.keep_depth ? 0 : 1; };
const cycleMode = () => { rc.left_switch = (rc.left_switch + 1) % 3; };
const cycleLed = () => { rc.right_switch = (rc.right_switch + 1) % 3; };

const FLIGHT = new Set(['KeyW', 'KeyS', 'KeyA', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyQ', 'KeyE', 'KeyZ', 'KeyC', 'Space', 'KeyH', 'KeyP', 'KeyR', 'KeyM', 'KeyL', 'KeyV']);
const isText = (el) => el && (el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !['range', 'checkbox'].includes(el.type)));
addEventListener('keydown', (e) => {
  if (isText(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.code.startsWith('Shift')) keys.add(e.code);
  if (!FLIGHT.has(e.code)) return;
  e.preventDefault();
  if (e.repeat) return;
  keys.add(e.code);
  switch (e.code) {
    case 'Space': toggleLock(); break;
    case 'KeyH': toggleDepth(); break;
    case 'KeyM': cycleMode(); break;
    case 'KeyL': cycleLed(); break;
    case 'KeyV': cycleCam(); break;
    case 'KeyP': hold.photo.add('kb'); break;
    case 'KeyR': hold.record.add('kb'); break;
  }
  inputTick();
});
addEventListener('keyup', (e) => {
  keys.delete(e.code);
  if (e.code === 'KeyP') hold.photo.delete('kb');
  if (e.code === 'KeyR') hold.record.delete('kb');
  if (FLIGHT.has(e.code) && !isText(e.target)) e.preventDefault();
});
addEventListener('blur', () => { keys.clear(); hold.photo.delete('kb'); hold.record.delete('kb'); });

// on-screen sticks and wheels
function bindStick(el, chUD, chLR) {
  let id = null;
  const set = (e) => {
    const r = el.getBoundingClientRect(), R = r.width / 2;
    let x = (e.clientX - r.left - R) / (R * .8), y = -(e.clientY - r.top - R) / (R * .8);
    const m = Math.hypot(x, y); if (m > 1) { x /= m; y /= m; }
    touch[chLR] = x; touch[chUD] = y;
  };
  el.addEventListener('pointerdown', (e) => { id = e.pointerId; el.setPointerCapture(id); set(e); e.preventDefault(); });
  el.addEventListener('pointermove', (e) => { if (e.pointerId === id) set(e); });
  const end = (e) => { if (e.pointerId !== id) return; id = null; touch[chLR] = 0; touch[chUD] = 0; };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
}
function bindWheel(el, ch) {
  let id = null;
  const set = (e) => { const r = el.getBoundingClientRect(); touch[ch] = clamp(((e.clientX - r.left) / r.width - .5) * 2.3, -1, 1); };
  el.addEventListener('pointerdown', (e) => { id = e.pointerId; el.setPointerCapture(id); set(e); e.preventDefault(); });
  el.addEventListener('pointermove', (e) => { if (e.pointerId === id) set(e); });
  const end = (e) => { if (e.pointerId !== id) return; id = null; touch[ch] = 0; };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
}
bindStick($('stickL'), 'left_ud', 'left_lr'); bindStick($('stickR'), 'right_ud', 'right_lr');
bindWheel($('wheelL'), 'left_wave'); bindWheel($('wheelR'), 'right_wave');

// panel buttons
$('bLock').onclick = () => { toggleLock(); inputTick(); };
$('bDepth').onclick = () => { toggleDepth(); inputTick(); };
$('bMode').onclick = () => { cycleMode(); inputTick(); };
$('bLed').onclick = () => { cycleLed(); inputTick(); };
for (const [id, k] of [['bPhoto', 'photo'], ['bRec', 'record']]) {
  const b = $(id);
  b.addEventListener('pointerdown', (e) => { b.setPointerCapture(e.pointerId); hold[k].add('ui'); inputTick(); });
  const up = () => { hold[k].delete('ui'); inputTick(); };
  b.addEventListener('pointerup', up); b.addEventListener('pointercancel', up);
}
addEventListener('gamepadconnected', (e) => { padName = e.gamepad.id; });
addEventListener('gamepaddisconnected', () => { padName = ''; });

function readPad() {
  const gp = navigator.getGamepads ? [...navigator.getGamepads()].find((g) => g && g.connected) : null;
  if (!gp) { padPrev = []; hold.photo.delete('pad'); hold.record.delete('pad'); return null; }
  const b = (i) => gp.buttons[i] ? (gp.buttons[i].value || (gp.buttons[i].pressed ? 1 : 0)) : 0;
  const pr = (i) => !!gp.buttons[i]?.pressed;
  const edge = (i) => pr(i) && !padPrev[i];
  if (edge(2)) toggleDepth();
  if (edge(3)) toggleLock();
  if (edge(8)) cycleMode();
  if (edge(9)) cycleLed();
  pr(0) ? hold.photo.add('pad') : hold.photo.delete('pad');
  pr(1) ? hold.record.add('pad') : hold.record.delete('pad');
  padPrev = gp.buttons.map((x) => x.pressed);
  const dz = (v) => (Math.abs(v || 0) < .08 ? 0 : (v - Math.sign(v) * .08) / .92);
  return {
    left_lr: dz(gp.axes[0]), left_ud: -dz(gp.axes[1]), right_lr: dz(gp.axes[2]), right_ud: -dz(gp.axes[3]),
    left_wave: b(7) - b(6), right_wave: b(5) - b(4), id: gp.id,
  };
}

let lastSent = '', lastSentAt = 0;
function rcMessage() {
  const m = {};
  for (const c of CH) m[c] = Math.round(1500 + 500 * out[c]);
  m.rc_lock = rc.rc_lock; m.keep_depth = rc.keep_depth; m.left_switch = rc.left_switch; m.right_switch = rc.right_switch;
  m.photo = hold.photo.size ? 1 : 0; m.record = hold.record.size ? 1 : 0;
  return m;
}
function inputTick() {
  const shift = keys.has('ShiftLeft') || keys.has('ShiftRight');
  const g = shift ? 1 : +$('kbGain').value;
  const k = (a, b) => ((keys.has(a) ? 1 : 0) - (keys.has(b) ? 1 : 0)) * g;
  const kb = { left_ud: k('KeyW', 'KeyS'), left_lr: k('KeyD', 'KeyA'), right_ud: k('ArrowUp', 'ArrowDown'), right_lr: k('ArrowRight', 'ArrowLeft'), left_wave: k('KeyE', 'KeyQ'), right_wave: k('KeyC', 'KeyZ') };
  const pad = readPad();
  for (const c of CH) out[c] = clamp(kb[c] + touch[c] + (pad ? pad[c] : 0), -1, 1);
  const msg = rcMessage(), js = JSON.stringify(msg), now = performance.now();
  if (js !== lastSent || now - lastSentAt > 450) {
    if (send({ type: 'rc', rc: msg })) { lastSent = js; lastSentAt = now; }
  }
  $('padInfo').textContent = pad ? `手把：${pad.id.slice(0, 48)}` : '未偵測到手把（按任一手把按鍵喚醒）。';
  drawSticks(msg);
}
setInterval(inputTick, 33);

function drawSticks(msg) {
  const place = (el, x, y) => { const r = el.clientWidth / 2 * .62; el.querySelector('.knob').style.transform = `translate(${x * r}px, ${-y * r}px)`; };
  place($('stickL'), out.left_lr, out.left_ud); place($('stickR'), out.right_lr, out.right_ud);
  for (const [id, c] of [['wheelL', 'left_wave'], ['wheelR', 'right_wave']]) {
    const el = $(id); el.querySelector('.wk').style.transform = `translateX(${out[c] * (el.clientWidth / 2 - 14)}px)`;
  }
  // panel mirror
  for (const c of CH) {
    const row = mapRows[c]; if (!row) continue;
    row.pwm.textContent = msg[c];
    const v = out[c], pct = Math.abs(v) * 50;
    row.fill.style.left = v >= 0 ? '50%' : (50 - pct) + '%'; row.fill.style.width = pct + '%';
  }
  $('bLock').classList.toggle('on', !!rc.rc_lock); $('bLock').textContent = rc.rc_lock ? '已鎖定' : '已解鎖';
  $('bDepth').classList.toggle('on', !!rc.keep_depth);
  $('bMode').textContent = '模式 ' + 'ASC'[rc.left_switch];
  $('bLed').textContent = 'LED ' + rc.right_switch; $('bLed').classList.toggle('on', rc.right_switch > 0);
  $('bPhoto').classList.toggle('on', hold.photo.size > 0); $('bRec').classList.toggle('on', hold.record.size > 0);
}

const mapRows = {};
let mapMode = '';
function buildMapTable(mode) {
  if (mode === mapMode) return; mapMode = mode;
  const tb = $('mapTbl'); tb.innerHTML = '';
  for (const c of CH) {
    const m = chanMeaning(mode, c), tr = document.createElement('tr');
    tr.innerHTML = `<td>${CH_NAME[c]}</td><td>${m.name}<span class="hint"> ${c.endsWith('ud') ? '↑' : '→'}${m.pos}</span></td><td class="bar"><div class="track c"><div class="fill"></div></div></td><td class="pwm">1500</td>`;
    tb.appendChild(tr); mapRows[c] = { pwm: tr.querySelector('.pwm'), fill: tr.querySelector('.fill') };
    const kk = CH_KEYS[c];
    if (c.endsWith('wave')) {
      $('lbl_' + c).innerHTML = `${m.neg} <kbd>${kk[1]}</kbd> ◀ ${c === 'left_wave' ? '左' : '右'}滾輪 ▶ <kbd>${kk[0]}</kbd> ${m.pos}`;
    } else {
      $(`lbl_${c}_p`).innerHTML = `<kbd>${kk[0]}</kbd>${m.pos}`;
      $(`lbl_${c}_n`).innerHTML = c.endsWith('lr') ? `${m.neg}<kbd>${kk[1]}</kbd>` : `<kbd>${kk[1]}</kbd>${m.neg}`;
    }
  }
}
buildMapTable('ROV_USA');

/* ═════════════════════════ training / panel controls ═════════════════════════ */
function fillCatalogue(select) {
  const sel = $('scnSel'), cat = W?.catalogue || [];
  const prev = sel.value;
  sel.innerHTML = cat.map((c) => `<option value="${esc(c.key)}">${esc(c.name)}</option>`).join('');
  sel.value = select ? W.scenario.key : (prev || W.scenario.key);
  if (select && W.scenario.seed != null) $('seed').value = W.scenario.seed;
  syncSeed();
}
function syncSeed() { $('seed').disabled = $('scnSel').value !== 'random'; }
$('scnSel').onchange = () => {
  syncSeed();
  const c = (W?.catalogue || []).find((x) => x.key === $('scnSel').value);
  if (c) $('brief').textContent = c.brief + (c.key !== W.scenario.key ? '（按「載入」開始）' : '');
};
$('btnLoad').onclick = () => {
  const key = $('scnSel').value; if (!key) return;
  const msg = { type: 'scenario', key };
  if (key === 'random' && $('seed').value !== '') msg.seed = +$('seed').value;
  send(msg);
};
$('btnReset').onclick = () => send({ type: 'reset' });
$('btnPause').onclick = () => send({ type: 'pause', value: !(S && S.paused) });
$('btnRelease').onclick = () => send({ type: 'remote_release' });
$('opMode').onchange = () => send({ type: 'operation_mode', value: $('opMode').value });
$('autoPay').onchange = () => send({ type: 'auto_payout', value: $('autoPay').checked });
document.querySelectorAll('[data-pay]').forEach((b) => (b.onclick = () => send({ type: 'payout', metres: +b.dataset.pay })));
$('kbGain').oninput = () => ($('kbGainV').textContent = Math.round($('kbGain').value * 100) + '%'); $('kbGain').oninput();

// current override sliders
const CUR_KEYS = [['surface', '表層'], ['mid', '中層'], ['bottom', '底層']];
{
  const host = $('curSliders');
  for (const [k, lbl] of CUR_KEYS) {
    host.insertAdjacentHTML('beforeend',
      `<div class="sl"><div class="row"><label for="c_${k}_kn">${lbl}流速</label><span id="c_${k}_knV"></span></div><input type="range" id="c_${k}_kn" min="0" max="4" step="0.1" value="0"></div>` +
      `<div class="sl"><div class="row"><label for="c_${k}_dir">${lbl}流向</label><span id="c_${k}_dirV"></span></div><input type="range" id="c_${k}_dir" min="0" max="355" step="5" value="90"></div>`);
  }
  host.parentElement.querySelectorAll('input[type=range]').forEach((el) => {
    const u = () => { $(el.id + 'V').textContent = el.id.endsWith('kn') ? (+el.value).toFixed(1) + ' kn' : el.id.endsWith('dir') ? String(el.value).padStart(3, '0') + '°' : (+el.value).toFixed(2); };
    el.addEventListener('input', u); u();
  });
}
function fillCurrentSliders() {
  const c = W?.current; if (!c) return;
  for (const [k] of CUR_KEYS) {
    for (const f of ['kn', 'dir']) { const el = $(`c_${k}_${f}`); if (document.activeElement !== el) { el.value = c[`${k}_${f}`]; el.dispatchEvent(new Event('input')); } }
  }
  const t = $('c_turbulence'); t.value = c.turbulence ?? .15; t.dispatchEvent(new Event('input'));
}
$('btnCur').onclick = () => {
  const m = { type: 'current', turbulence: +$('c_turbulence').value };
  for (const [k] of CUR_KEYS) { m[`${k}_kn`] = +$(`c_${k}_kn`).value; m[`${k}_dir`] = +$(`c_${k}_dir`).value; }
  send(m);
};

/* ═════════════════════════ camera modes ═════════════════════════ */
const CAMS = ['chase', 'orbit', 'top', 'onboard'];
const CAM_NAME = { chase: '追蹤', orbit: '環繞', top: '俯視', onboard: '機載' };
let camMode = CAMS.includes(params.get('cam')) ? params.get('cam') : 'chase', topH = 22;
function setCam(m) {
  camMode = m;
  $('camBtn').textContent = `視角：${CAM_NAME[m]}（V）`;
  controls.enabled = m === 'orbit';
  camera.up.set(0, 1, 0);
  camera.fov = m === 'onboard' ? 70 : 55; camera.updateProjectionMatrix();
  if (m === 'orbit') {
    const f = new THREE.Vector3(0, 0, 1).applyQuaternion(rovG.quaternion); f.y = 0; f.normalize();
    camera.position.copy(rovG.position).addScaledVector(f, -3.5).add(new THREE.Vector3(1.2, 1.6, 0));
    controls.target.copy(rovG.position); controls.update();
  }
  $('xhair').hidden = m !== 'onboard';
  body.visible = m !== 'onboard';
}
function cycleCam() { setCam(CAMS[(CAMS.indexOf(camMode) + 1) % CAMS.length]); }
$('camBtn').onclick = cycleCam;
renderer.domElement.addEventListener('wheel', (e) => { if (camMode === 'top') { topH = clamp(topH * (e.deltaY > 0 ? 1.12 : 1 / 1.12), 4, 150); e.preventDefault(); } }, { passive: false });

const _f = new THREE.Vector3(), _v = new THREE.Vector3(), _q = new THREE.Quaternion(), FLIP = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI);
let chaseFwd = new THREE.Vector3(0, 0, 1);
function updateCamera(dt) {
  const p = rovG.position;
  if (camMode === 'chase') {
    _f.set(0, 0, 1).applyQuaternion(rovG.quaternion); _f.y = 0;
    if (_f.lengthSq() > 1e-4) chaseFwd.lerp(_f.normalize(), 1 - Math.exp(-dt * 5)).normalize();
    _v.copy(p).addScaledVector(chaseFwd, -2.6).add(new THREE.Vector3(0, .85, 0));
    camera.position.lerp(_v, 1 - Math.exp(-dt * 6));
    camera.lookAt(_v.copy(p).addScaledVector(chaseFwd, 1.5));
  } else if (camMode === 'orbit') {
    _v.copy(p).sub(controls.target); camera.position.add(_v); controls.target.copy(p); controls.update();
  } else if (camMode === 'top') {
    camera.up.set(0, 0, 1);
    camera.position.set(p.x, p.y + topH, p.z); camera.lookAt(p);
  } else {
    camera.position.set(0, .03, noseZ + .04).applyQuaternion(rovG.quaternion).add(p);
    camera.quaternion.copy(rovG.quaternion).multiply(FLIP);
  }
}

/* ═════════════════════════ labels ═════════════════════════ */
const labelEls = new Map();
function drawLabels(list, w, h) {
  const show = $('optLabels').checked, seen = new Set();
  if (show) for (const L of list) {
    _v.copy(L.pos).project(camera);
    if (_v.z > 1 || _v.z < -1 || Math.abs(_v.x) > 1.05 || Math.abs(_v.y) > 1.05) continue;
    let el = labelEls.get(L.id);
    if (!el) { el = document.createElement('div'); $('labels').appendChild(el); labelEls.set(L.id, el); }
    el.className = 'lbl ' + (L.cls || ''); if (el.textContent !== L.text) el.textContent = L.text;
    el.style.left = ((_v.x + 1) / 2 * w + 8) + 'px'; el.style.top = ((1 - _v.y) / 2 * h) + 'px'; el.hidden = false;
    seen.add(L.id);
  }
  for (const [id, el] of labelEls) if (!seen.has(id)) el.hidden = true;
}

/* ═════════════════════════ instruments ═════════════════════════ */
const adi = $('adi'), actx = adi.getContext('2d');
function drawADI(pitch, roll, hdg) {
  const Wd = adi.width, H = adi.height; actx.save(); actx.clearRect(0, 0, Wd, H);
  actx.translate(Wd / 2, H / 2); actx.rotate(-roll);
  const k = H / 1.2, py = pitch * k;
  actx.fillStyle = '#123b52'; actx.fillRect(-Wd, -H * 2 + py, Wd * 2, H * 2);
  actx.fillStyle = '#2a2217'; actx.fillRect(-Wd, py, Wd * 2, H * 2);
  actx.strokeStyle = '#d6e4ec'; actx.lineWidth = 2; actx.beginPath(); actx.moveTo(-Wd, py); actx.lineTo(Wd, py); actx.stroke();
  actx.lineWidth = 1; actx.font = '18px ' + C('--f-data'); actx.fillStyle = '#7f99a8'; actx.textAlign = 'left';
  for (let d = -60; d <= 60; d += 15) { if (!d) continue; const y = py - d * DEG * k; actx.beginPath(); actx.moveTo(-30, y); actx.lineTo(30, y); actx.strokeStyle = '#7f99a8'; actx.stroke(); actx.fillText(d, 36, y + 6); }
  actx.restore();
  actx.strokeStyle = '#f2b705'; actx.lineWidth = 4; actx.beginPath();
  actx.moveTo(Wd / 2 - 90, H / 2); actx.lineTo(Wd / 2 - 30, H / 2); actx.lineTo(Wd / 2, H / 2 + 16); actx.lineTo(Wd / 2 + 30, H / 2); actx.lineTo(Wd / 2 + 90, H / 2); actx.stroke();
  actx.fillStyle = '#d6e4ec'; actx.font = '600 22px ' + C('--f-data'); actx.textAlign = 'center';
  actx.textAlign = 'left'; actx.fillText('HDG ' + String(Math.round(hdg) % 360).padStart(3, '0') + '°', 12, 28);
}
const tape = $('tape'), tctx = tape.getContext('2d');
function drawTape(hdg) {
  const Wd = tape.width, H = tape.height, ppd = 5;
  tctx.clearRect(0, 0, Wd, H);
  tctx.fillStyle = 'rgba(6,16,24,.55)'; tctx.fillRect(0, 0, Wd, H);
  tctx.strokeStyle = '#d6e4ec'; tctx.fillStyle = '#d6e4ec'; tctx.textAlign = 'center'; tctx.font = '600 26px ' + C('--f-data');
  const card = { 0: 'N', 90: 'E', 180: 'S', 270: 'W' };
  for (let d = Math.floor((hdg - 64) / 5) * 5; d <= hdg + 64; d += 5) {
    const x = Wd / 2 + (d - hdg) * ppd, dd = ((d % 360) + 360) % 360;
    tctx.lineWidth = dd % 30 === 0 ? 2 : 1;
    tctx.beginPath(); tctx.moveTo(x, H); tctx.lineTo(x, H - (dd % 30 === 0 ? 16 : dd % 10 === 0 ? 10 : 6)); tctx.stroke();
    if (dd % 30 === 0) { tctx.fillStyle = card[dd] ? '#f2b705' : '#d6e4ec'; tctx.fillText(card[dd] || String(dd / 10).padStart(2, '0'), x, 24); }
  }
  tctx.fillStyle = '#f2b705'; tctx.beginPath(); tctx.moveTo(Wd / 2 - 9, H); tctx.lineTo(Wd / 2 + 9, H); tctx.lineTo(Wd / 2, H - 14); tctx.fill();
  tctx.fillStyle = '#061018'; tctx.fillRect(Wd / 2 - 40, 0, 80, 32);
  tctx.strokeStyle = '#f2b705'; tctx.lineWidth = 2; tctx.strokeRect(Wd / 2 - 40, 1, 80, 31);
  tctx.fillStyle = '#f2b705'; tctx.font = '600 28px ' + C('--f-data'); tctx.fillText(String(Math.round(hdg) % 360).padStart(3, '0'), Wd / 2, 26);
}

const prof = $('profile'), pctx = prof.getContext('2d');
function arrow(ctx, x, y, dirDeg, len, col, lw = 2) {
  const a = dirDeg * DEG, dx = Math.sin(a) * len, dy = -Math.cos(a) * len;
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = lw;
  ctx.beginPath(); ctx.moveTo(x - dx / 2, y - dy / 2); ctx.lineTo(x + dx / 2, y + dy / 2); ctx.stroke();
  const hx = x + dx / 2, hy = y + dy / 2, ang = Math.atan2(dy, dx);
  ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(hx - 9 * Math.cos(ang - .45), hy - 9 * Math.sin(ang - .45)); ctx.lineTo(hx - 9 * Math.cos(ang + .45), hy - 9 * Math.sin(ang + .45)); ctx.fill();
}
function drawProfile() {
  const Wd = prof.width, H = prof.height; pctx.clearRect(0, 0, Wd, H);
  pctx.font = '16px ' + C('--f-data'); pctx.textBaseline = 'middle';
  if (!W) { pctx.fillStyle = '#7f99a8'; pctx.fillText('等待世界資料…', 20, H / 2); return; }
  const c = W.current, sb = W.seabed_depth, y0 = 22, y1 = H - 18, x0 = 58, x1 = 300;
  const maxKn = Math.max(1, c.surface_kn, c.mid_kn, c.bottom_kn) * 1.1;
  const Y = (d) => y0 + (d / sb) * (y1 - y0), X = (kn) => x0 + kn / maxKn * (x1 - x0);
  pctx.strokeStyle = '#1f3a4a'; pctx.lineWidth = 1;
  for (const d of [0, sb / 2, sb]) { pctx.beginPath(); pctx.moveTo(x0, Y(d)); pctx.lineTo(Wd - 10, Y(d)); pctx.stroke(); }
  pctx.fillStyle = '#4a4636'; pctx.fillRect(x0, y1, Wd - 10 - x0, H - y1);
  pctx.fillStyle = '#7f99a8'; pctx.textAlign = 'right';
  for (const d of [0, sb / 2, sb]) pctx.fillText(Math.round(d) + 'm', x0 - 6, Y(d));
  // speed profile curve
  pctx.strokeStyle = '#4fd1ff'; pctx.lineWidth = 2.5; pctx.beginPath();
  for (let i = 0; i <= 40; i++) { const d = sb * i / 40, v = currentAt(d), kn = Math.hypot(v[0], v[1]) / KNOT; i ? pctx.lineTo(X(kn), Y(d)) : pctx.moveTo(X(kn), Y(d)); }
  pctx.stroke();
  // layer arrows
  pctx.textAlign = 'left';
  const rows = [['表層', 0, c.surface_kn, c.surface_dir], ['中層', sb / 2, c.mid_kn, c.mid_dir], ['底層', sb, c.bottom_kn, c.bottom_dir]];
  for (const [n, d, kn, dir] of rows) {
    const y = clamp(Y(d), y0 + 8, y1 - 8);
    arrow(pctx, 330, y, dir, 12 + kn * 8, '#4fd1ff');
    pctx.fillStyle = '#d6e4ec'; pctx.fillText(`${n} ${kn.toFixed(1)}kn ${String(Math.round(dir)).padStart(3, '0')}°`, 356, y);
  }
  // ROV depth + local current
  if (S) {
    const d = S.pos[2], y = Y(clamp(d, 0, sb)), ch = S.current_here || [0, 0, 0];
    pctx.strokeStyle = '#f2b705'; pctx.setLineDash([6, 4]); pctx.lineWidth = 1.5; pctx.beginPath(); pctx.moveTo(x0, y); pctx.lineTo(x1, y); pctx.stroke(); pctx.setLineDash([]);
    const kn = S.current_kn || 0, dir = (Math.atan2(ch[1], ch[0]) / DEG + 360) % 360;
    pctx.fillStyle = '#f2b705'; pctx.beginPath(); pctx.arc(X(kn), y, 5, 0, 7); pctx.fill();
    pctx.textAlign = 'left'; pctx.fillText(`ROV ${kn.toFixed(2)}kn ${String(Math.round(dir)).padStart(3, '0')}°`, x0 + 4, y - 12 < y0 ? y + 12 : y - 12);
  }
  pctx.fillStyle = '#7f99a8'; pctx.textAlign = 'left'; pctx.fillText('↑N 流向 = 水流去向', 330, 10);
}

let thrRows = [];
const THR_ZH = { PORT_FRONT: '左前', STBD_FRONT: '右前', PORT_AFT: '左後', STBD_AFT: '右後', PORT_LONG: '左縱', STBD_LONG: '右縱' };
function thrLabel(name) { const [t, k] = String(name).split(' '); return `${t} ${THR_ZH[k] || k || ''}`; }
function buildThrBars() {
  const host = $('thrBars'); host.innerHTML = ''; thrRows = [];
  (W?.thrusters || []).forEach((t) => {
    const row = document.createElement('div'); row.className = 'thr';
    row.innerHTML = `<span class="nm">${esc(thrLabel(t.name))}</span><div class="track c"><div class="fill"></div></div><span class="pc">0</span><span class="hp">100%</span>`;
    host.appendChild(row); thrRows.push({ row, fill: row.querySelector('.fill'), pc: row.querySelector('.pc'), hp: row.querySelector('.hp') });
  });
}

/* ═════════════════════════ UI refresh (throttled) ═════════════════════════ */
let uiDirty = false, uiLast = 0;
const setTxt = (id, v) => { const el = $(id); if (el.textContent !== String(v)) el.textContent = v; };
const setHTML = (id, v) => { const el = $(id); if (el._h !== v) { el.innerHTML = v; el._h = v; } };
function updateUI() {
  const s = S; if (!s) return;
  const [roll, pitch, hdg] = s.euler || [0, 0, 0];
  const depth = s.pos[2], alt = W ? W.seabed_depth - depth : null;
  setTxt('gDepth', depth.toFixed(2)); setTxt('gHdg', String(Math.round(hdg) % 360).padStart(3, '0'));
  setTxt('gAtt', `${pitch.toFixed(0)}° / ${roll.toFixed(0)}°`); setTxt('gSpd', (s.speed_kn ?? 0).toFixed(2));
  setTxt('gBat', (s.battery ?? 0).toFixed(0)); $('gBat').closest('.g').classList.toggle('low', s.battery < 20);
  setTxt('gAlt', alt == null ? '—' : alt.toFixed(2)); $('gAlt').closest('.g').classList.toggle('low', alt != null && alt < 1);
  setTxt('gHold', s.depth_hold != null ? `定深設定點 ${s.depth_hold.toFixed(2)} m` : '');
  setTxt('rDepth', depth.toFixed(1)); setTxt('rAlt', alt == null ? '—' : alt.toFixed(1)); setTxt('rSpd', (s.speed_kn ?? 0).toFixed(2)); setTxt('rCur', (s.current_kn ?? 0).toFixed(2));
  drawADI(pitch * DEG, roll * DEG, hdg); drawTape(hdg);

  // HUD
  const lk = $('lockBadge');
  lk.classList.toggle('locked', !!s.locked);
  lk.querySelector('b').textContent = s.locked ? '馬達鎖定' : '馬達解鎖';
  lk.querySelector('span').textContent = s.locked ? '按 Space / 手把 Y 解鎖' : '推進器可動作 · Space 上鎖';
  const hm = $('hMode'); hm.textContent = `${s.ctrl_mode} 模式`; hm.className = 'chip ' + (s.ctrl_mode === 'A' ? '' : s.ctrl_mode === 'S' ? 'on' : 'warn');
  const hh = $('hHold'); hh.textContent = s.keep_depth ? `定深 ${s.depth_hold != null ? s.depth_hold.toFixed(1) + ' m' : '開'}` : '定深 關'; hh.className = 'chip ' + (s.keep_depth ? 'on' : 'dim');
  setTxt('hOp', s.operation_mode);
  const led = s.rc?.right_switch || 0; $('hLed').hidden = !led; setTxt('hLed', `LED ${led}`);
  $('hRec').hidden = !s.recording;
  $('hPaused').hidden = !s.paused;
  const nav = s.nav || {}; $('hNav').hidden = !nav.mode || nav.mode === 'IDLE'; setTxt('hNav', `NAV ${nav.mode || ''}${nav.route?.length ? ` ${nav.route_i}/${nav.route.length}` : ''}`);
  $('hRemote').hidden = !s.remote_control;
  if (document.activeElement !== $('opMode')) $('opMode').value = s.operation_mode;
  buildMapTable(s.operation_mode);
  $('btnPause').textContent = s.paused ? '繼續' : '暫停'; $('btnPause').classList.toggle('on', !!s.paused);
  leds.forEach((l) => (l.intensity = [0, 18, 45][led] || 0));

  // thrusters
  (s.thrust || []).forEach((t, j) => {
    const r = thrRows[j]; if (!r) return;
    const pct = Math.min(1, Math.abs(t)) * 50, h = s.health?.[j] ?? 1;
    r.fill.style.left = t >= 0 ? '50%' : (50 - pct) + '%'; r.fill.style.width = pct + '%';
    r.fill.style.background = Math.abs(t) > .95 ? C('--warn') : C('--jet');
    r.pc.textContent = Math.round(t * 100);
    r.hp.textContent = h <= 0.01 ? '失效' : Math.round(h * 100) + '%';
    r.row.classList.toggle('dmg', h < .999);
  });

  // tether
  const t = s.tether || {};
  setTxt('tLen', (t.length ?? 0).toFixed(1)); setTxt('tMax', (t.max_length ?? 0).toFixed(0));
  $('tLenFill').style.width = (100 * (t.length || 0) / (t.max_length || 1)) + '%';
  const gw = (T) => Math.sqrt(clamp(T / BREAK_N, 0, 1)) * 100;
  for (const [k, id] of [['tension_rov', 'tRov'], ['tension_spool', 'tSpool']]) {
    const T = t[k] || 0; setTxt(id, `${T.toFixed(0)} N`);
    const f = $(id + 'Fill'); f.style.width = gw(T) + '%'; f.style.background = '#' + tensionColor(T, _c).getHexString();
  }
  document.querySelectorAll('.tgauge .wmark').forEach((m) => (m.style.left = gw(WARN_N) + '%'));
  const ts = $('tState');
  if (t.broken) { ts.textContent = '已斷裂'; ts.className = 'chip bad'; }
  else if (t.warn) { ts.textContent = '張力過高'; ts.className = 'chip warn'; }
  else if (t.snagged_on?.length) { ts.textContent = '卡纜'; ts.className = 'chip warn'; }
  else { ts.textContent = '正常'; ts.className = 'chip on'; }
  if (document.activeElement !== $('autoPay')) $('autoPay').checked = !!t.auto_payout;
  const wr = Object.entries(t.wraps || {}).filter(([, v]) => Math.abs(v) >= .05);
  setHTML('tWraps', [
    wr.length ? '纏繞：' + wr.map(([n, v]) => `<b style="color:${Math.abs(v) >= .25 ? 'var(--bad)' : 'var(--amber)'}">${esc(n)} ${v > 0 ? '↻' : '↺'}${Math.abs(v).toFixed(2)} 圈</b>`).join('、') : '無纏繞',
    t.snagged_on?.length ? `卡在：<b style="color:var(--amber)">${t.snagged_on.map(esc).join('、')}</b>` : '',
    t.contact_nodes ? `接觸節點 ${t.contact_nodes}` : '',
  ].filter(Boolean).join(' · '));

  // collisions / damage / log
  const ev = (s.events || []).slice().reverse().slice(0, 8);
  const SEV = { touch: '輕觸', hard: '撞擊', severe: '嚴重' };
  setHTML('events', ev.length ? ev.map((e) => `<li><span class="t">${fmtT(e.t)}</span><span class="sev ${esc(e.severity)}">${SEV[e.severity] || esc(e.severity)}</span><span class="x">${esc(e.obstacle)} · ${(+e.speed || 0).toFixed(2)} m/s${e.where ? ' · ' + esc(e.where) : ''}</span></li>`).join('') : '<li class="hint">無碰撞紀錄</li>');
  const dm = (s.damage || []).slice().reverse();
  setHTML('damage', dm.map((d) => `<li><span class="t">${fmtT(d.t)}</span><span class="sev severe">損傷</span><span class="x">${esc(typeof d.thruster === 'number' ? thrLabel(W?.thrusters?.[d.thruster]?.name ?? 'T' + (d.thruster + 1)) : thrLabel(d.thruster))} 健康 ${Math.round((d.health ?? 0) * 100)}%</span></li>`).join(''));
  setHTML('log', (s.log || []).slice().reverse().map((l) => `<li><span class="t">${fmtT(l.t)}</span><span class="x">${esc(l.text)}</span></li>`).join(''));

  // training
  const sc = s.score || {}, lim = W?.scenario?.time_limit_s;
  setTxt('score', sc.score ?? '—');
  setTxt('timer', `${fmtT(sc.elapsed)} / ${lim ? fmtT(lim) : '—'}`);
  $('timeFill').style.width = lim ? clamp(100 * (sc.elapsed || 0) / lim, 0, 100) + '%' : '0%';
  $('timeFill').style.background = lim && sc.elapsed > lim * .85 ? C('--warn') : C('--jet');
  const objs = sc.objectives || [];
  const nDone = objs.filter((o) => o.done).length;
  setTxt('scoreState', sc.failed ? `失敗：${sc.failed}` : sc.finished ? '任務完成' : `目標 ${nDone}/${objs.length} · 扣分 ${sc.penalty_total || 0}`);
  setHTML('objs', objs.map((o, i) => {
    const cls = o.done ? 'done' : i === sc.current_index ? 'cur' : '';
    return `<li class="${cls}"><span class="ic">${o.done ? '✓' : i === sc.current_index ? '▶' : '○'}</span><span>${esc(o.label)}${o.hold_s ? `<span class="hint"> · 停留 ${o.hold_s}s</span>` : ''}</span><span></span><div class="track"><div class="fill" style="width:${(o.done ? 1 : o.progress || 0) * 100}%"></div></div></li>`;
  }).join(''));
  const pens = sc.penalties || [];
  setHTML('pens', pens.slice(-6).reverse().map((p) => `<div class="row"><span>${fmtT(p.t)} ${esc(p.reason)}</span><span>−${p.points}</span></div>`).join(''));

  // banner
  const bn = $('banner');
  if (sc.failed) { bn.className = 'banner fail'; bn.innerHTML = `任務失敗<small>${esc(sc.failed)}</small>`; bn.hidden = false; }
  else if (t.broken) { bn.className = 'banner fail'; bn.innerHTML = '纜線斷裂<small>ROV 失去連線，請重置情境</small>'; bn.hidden = false; }
  else if (sc.finished) { bn.className = 'banner win'; bn.innerHTML = `任務完成 · ${sc.score} 分<small>用時 ${fmtT(sc.elapsed)}，扣分 ${sc.penalty_total || 0}</small>`; bn.hidden = false; }
  else if (t.warn) { bn.className = 'banner warn'; bn.innerHTML = `纜線張力 ${Math.round(t.tension_max || 0)} N<small>減少拉扯、檢查纏繞</small>`; bn.hidden = false; }
  else bn.hidden = true;
  drawProfile();
}

function updateObjectives(time) {
  const objs = S?.score?.objectives; if (!objs) return null;
  const ci = S.score.current_index; let cur = null;
  objMarkers.forEach((m, i) => {
    const o = objs[i] || m.o, isCur = i === ci && !o.done;
    const col = o.done ? 0x3ddc97 : isCur ? 0xf2b705 : 0x7f99a8;
    m.mat.color.setHex(col); m.wire.color.setHex(col);
    m.mat.fog = !isCur; m.wire.fog = !isCur;
    m.mat.opacity = isCur ? .6 + .35 * Math.sin(time * 5) : o.done ? .55 : .45;
    m.g.scale.setScalar(isCur ? 1 + .06 * Math.sin(time * 5) : 1);
    if (m.bill) { _v.copy(camera.position).sub(m.g.position); m.bill.rotation.set(0, Math.atan2(_v.x, _v.z), 0); }
    if (isCur) cur = { o, m };
  });
  return cur;
}

/* ═════════════════════════ render loop ═════════════════════════ */
function resize() {
  const r = vp.getBoundingClientRect();
  renderer.setSize(Math.max(1, r.width), Math.max(1, r.height), false);
  camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix();
}

// Smooth the cable like the ROV pose (states arrive at 30 Hz), pin its end to the rendered gland
// so it never detaches from the vehicle, and draw it as a real-thickness (9.5 mm) cable.
const _gl = new THREE.Vector3();
function renderTether(dt) {
  const t = tetherInfo, n = tetherDisp.length;
  if (tube) { scene.remove(tube); tube.geometry.dispose(); tube = null; }
  if (!t || n < 2) return;
  const a = 1 - Math.exp(-dt * 20);
  for (let i = 0; i < n; i++) tetherDisp[i].lerp(tetherTarget[i], a);
  if (!t.broken && target.init) { rovG.updateMatrixWorld(); tetherDisp[n - 1].copy(rovG.localToWorld(_gl.copy(GLAND_LOCAL))); }
  const lp = tetherLine.geometry.attributes.position.array;
  for (let i = 0; i < n; i++) { lp[i * 3] = tetherDisp[i].x; lp[i * 3 + 1] = tetherDisp[i].y; lp[i * 3 + 2] = tetherDisp[i].z; }
  tetherLine.geometry.attributes.position.needsUpdate = true;
  if (t.broken) return;
  const ts = t.tension_spool || 0, tr = t.tension_rov || 0;
  const segs = Math.min(480, (n - 1) * 6), rad = 8;
  const geo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(tetherDisp, false, 'centripetal'), segs, .0065, rad, false);
  const cnt = geo.attributes.position.count, col = new Float32Array(cnt * 3);
  for (let v = 0; v < cnt; v++) {
    const s = Math.floor(v / (rad + 1)) / segs, T = ts + (tr - ts) * s;
    tensionColor(t.warn ? Math.max(T, WARN_N) : T, _c); col[v * 3] = _c.r; col[v * 3 + 1] = _c.g; col[v * 3 + 2] = _c.b;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  tube = new THREE.Mesh(geo, tubeMat); scene.add(tube);
}

/* ═════════════════════════ deploy intro + pilot PiP ═════════════════════════ */
let introAssetsP = null, intro = null, pip = null;
const loadIntroAssets = () => (introAssetsP ||= DeployIntro.loadAssets('models/'));
function introActive() { return !!(intro && intro.playing); }
function endIntroUI() {
  vp.classList.remove('intro'); $('skipIntro').hidden = true;
  tetherLine.visible = true;
}
async function startIntro() {
  if (!W || !$('optIntro').checked || params.has('nointro')) return;
  const assets = await loadIntroAssets();
  introStarts++;
  if (intro) { intro.dispose(); intro = null; }
  intro = new DeployIntro(scene, { spool: W.spool || [-4, 0, 0], start: W.start_pos || S?.pos || [0, 0, 3], seabed: W.seabed_depth || 30, assets });
  vp.classList.add('intro'); $('skipIntro').hidden = false;
  const wasPaused = !!S?.paused;
  if (!wasPaused) send({ type: 'pause', value: true });
  intro.play(rovG, camera, () => {
    endIntroUI();
    target.init = false;                        // snap back to the simulated pose
    if (!wasPaused) send({ type: 'pause', value: false });
  });
}
$('skipIntro').onclick = () => intro?.skip();
let introStarts = 0;
window.__intro = () => intro && { t: intro.t, playing: intro.playing, starts: introStarts };
addEventListener('keydown', (e) => { if (e.code === 'Escape' && introActive()) { e.preventDefault(); intro.skip(); } });
async function ensurePip() {
  const on = $('optPip').checked && !params.has('nopip');
  $('pip').hidden = !on;
  if (!on || pip) return;
  const assets = await loadIntroAssets();
  pip = new PilotPiP($('pip'), { mirror: renderer.domElement, human: assets.human, width: 300, height: 190 });
}
$('optPip').addEventListener('change', ensurePip);
ensurePip();
new ResizeObserver(resize).observe(vp);
const _wc = new THREE.Color();
let last = performance.now(), fpsN = 0, fpsT = 0, fps = 0;
function frame(now) {
  const dt = Math.min(.25, (now - last) / 1000); last = now;
  // pose (smoothed toward latest state)
  const inIntro = introActive();
  if (intro) intro.update(dt);
  if (inIntro) { /* the intro poses the ROV and the camera */ }
  else if (target.init) {
    const a = 1 - Math.exp(-dt * 20);
    rovG.position.lerp(target.pos, a); rovG.quaternion.slerp(target.q, a);
  }
  if (!inIntro) renderTether(dt); else if (tube) { scene.remove(tube); tube.geometry.dispose(); tube = null; tetherLine.visible = false; }
  // rotors
  if (S && rotorOf.length) {
    rotorOf.forEach((r, j) => {
      if (!r) return; r.ang += (S.thrust?.[j] || 0) * 40 * dt * (S.locked ? 0 : 1);
      r.o.quaternion.copy(r.base).multiply(_q.setFromAxisAngle(r.axis, r.ang));
    });
  }
  if (!inIntro) updateCamera(dt);
  // water colour + fog from camera depth, visibility and silt
  const camDepth = clamp(-camera.position.y, 0, 60);
  _wc.copy(waterSurf).lerp(waterDeep, clamp(camDepth / 45, 0, 1)).lerp(siltCol, clamp((S?.silt || 0) * .7, 0, .7));
  scene.background.copy(_wc); scene.fog.color.copy(_wc);
  const vis = (W?.scenario?.visibility_m || 12) * (1 - .75 * clamp(S?.silt || 0, 0, 1));
  const real = $('optFog').checked && camMode !== 'top';
  scene.fog.near = real ? .3 : 5; scene.fog.far = real ? vis * 1.35 : Math.max(90, topH * 4);
  surface.visible = camMode !== 'top' || camera.position.y < 0;
  for (const m of spoolMarker) m.visible = !intro;            // the work boat replaces the placeholder reel
  objG.visible = !inIntro; if (inIntro) { curArrow.visible = false; particles.visible = false; }
  if (inIntro && camera.position.y > 0) { surface.visible = !intro.aboveWater(camera); scene.fog.near = 60; scene.fog.far = 900; }
  if (!inIntro) updateParticles(dt, rovG.position);
  topMark.visible = camMode === 'top';
  if (topMark.visible) {
    _f.set(0, 0, 1).applyQuaternion(rovG.quaternion);
    topMark.position.copy(rovG.position).add(new THREE.Vector3(0, .6, 0));
    topMark.rotation.set(-Math.PI / 2, 0, Math.atan2(-_f.x, -_f.z), 'XYZ');
    topMark.scale.setScalar(topH / 22);
  }
  curArrow.position.copy(rovG.position).add(new THREE.Vector3(0, .55, 0));
  // objectives + guide line
  const cur = updateObjectives(now / 1000);
  const gp = guide.geometry.attributes.position.array;
  if (cur) {
    const a = rovG.position, b = cur.m.g.position;
    gp.set([a.x, a.y, a.z, b.x, b.y, b.z]); guide.geometry.attributes.position.needsUpdate = true; guide.computeLineDistances();
    guide.visible = camMode !== 'onboard';
  } else guide.visible = false;
  renderer.render(scene, camera);
  if (pip && !$('pip').hidden) pip.update(dt, S?.rc || rc);
  // labels
  const r = vp.getBoundingClientRect();
  const L = [];
  if (W?.spool) L.push({ id: 'spool', text: '纜盤 / 投放點', pos: P(W.spool).add(new THREE.Vector3(0, 1.2, 0)), cls: 'spool' });
  if (cur) L.push({ id: 'obj', text: `${cur.o.label} · ${cur.m.g.position.distanceTo(rovG.position).toFixed(1)} m`, pos: cur.m.g.position, cls: 'obj' });
  for (const w of wrapLabels) L.push(w);
  for (const n of S?.tether?.snagged_on || []) { const e = obstacleMeshes.get(n); if (e && !wrapLabels.some((w) => w.id === 'wrap:' + n)) { const p = e.mesh.position.clone(); if (e.ob.type === 'cylinder') p.y = rovG.position.y + 1; L.push({ id: 'snag:' + n, text: `卡纜：${n}`, pos: p, cls: 'bad' }); } }
  drawLabels(L, r.width, r.height);
  if (uiDirty && now - uiLast > 110) { uiDirty = false; uiLast = now; updateUI(); }
  fpsN++; fpsT += dt; if (fpsT > .5) { fps = Math.round(fpsN / fpsT); fpsN = 0; fpsT = 0; setTxt('meta', `${fps} FPS${S ? ` · t=${S.t.toFixed(1)} s` : ''}`); }
  requestAnimationFrame(frame);
}

$('optSticks').onchange = () => ($('sticks').hidden = !$('optSticks').checked);
if (matchMedia('(max-width: 720px)').matches) $('optLabels').checked = false;
setCam(camMode); resize(); drawProfile(); loadModel(); connect(); requestAnimationFrame(frame);
window.__viewer = { THREE, scene, camera, rovG, worldG, get W() { return W; }, get S() { return S; }, rotors, get rotorOf() { return rotorOf; }, setCam, rc };
