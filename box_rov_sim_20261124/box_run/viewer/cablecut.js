// ROV-01 · Cable Cut — clean fullscreen game view. Blender-authored GLBs (ROV-01A holder, ROV-01B cutter, cable, seabed).
// Blender frame (x fwd, y left, z up) is used for gameplay math; converted to three (x, z, -y) at the scene boundary.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const Q = new URLSearchParams(location.search);
const LOD = Q.get('lod') === '0' ? '0' : '1';
const LOWQ = Q.get('q') === 'low';
const A = './cablecut_assets/';
const $ = (id) => document.getElementById(id);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
const B2T = (x, y, z) => new THREE.Vector3(x, z, -y);
const L_UP = 0.40, L_FORE = 0.36;

const G = { ready: false, state: 'loading', fps: 0, frames: 0, holder: { t: -1, ready: false }, cut: { stage: 'idle', t: 0 },
  pos: [0, 0, 0], yaw: 0, inRange: false, armReady: false, cam: 'chase', notes: [] };
window.__game = G;

// ------------------------------------------------------------------ renderer / scene
const renderer = new THREE.WebGLRenderer({ antialias: !LOWQ, powerPreference: 'high-performance' });
renderer.setPixelRatio(LOWQ ? 0.6 : Math.min(window.devicePixelRatio || 1, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.15;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const WATER = new THREE.Color(0.012, 0.085, 0.115);
scene.background = WATER; scene.fog = new THREE.FogExp2(WATER.clone().multiplyScalar(1.15), 0.135);
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.05, 60);
addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); });

// procedural env map (soft teal sky over sandy ground) for believable metal/paint
{
  const envScene = new THREE.Scene();
  const sky = new THREE.Mesh(new THREE.SphereGeometry(10, 24, 12), new THREE.ShaderMaterial({ side: THREE.BackSide,
    uniforms: {}, vertexShader: 'varying vec3 p; void main(){p=normalize(position);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: 'varying vec3 p; void main(){float h=p.y*.5+.5; vec3 top=vec3(.35,.8,.9)*1.6; vec3 mid=vec3(.06,.28,.34); vec3 bot=vec3(.34,.30,.22)*.7; vec3 c=mix(bot,mid,smoothstep(.0,.5,h)); c=mix(c,top,smoothstep(.55,1.,h)); gl_FragColor=vec4(c,1.);}' }));
  envScene.add(sky);
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromScene(envScene, 0.04).texture; scene.environmentIntensity = 0.9;
}
scene.add(new THREE.HemisphereLight(0x7fd8e6, 0x4a4430, 0.9));
const sun = new THREE.DirectionalLight(0xbfeaf2, 1.4); sun.position.set(2, 10, 3); scene.add(sun);

// marine snow
const SNOW_N = LOWQ ? 250 : 650;
const snowGeo = new THREE.BufferGeometry(); const snowPos = new Float32Array(SNOW_N * 3);
for (let i = 0; i < SNOW_N; i++) { snowPos[i * 3] = (Math.random() - .5) * 14; snowPos[i * 3 + 1] = Math.random() * 5; snowPos[i * 3 + 2] = (Math.random() - .5) * 14; }
snowGeo.setAttribute('position', new THREE.BufferAttribute(snowPos, 3));
const snow = new THREE.Points(snowGeo, new THREE.PointsMaterial({ color: 0xcfeff2, size: 0.018, transparent: true, opacity: 0.7, depthWrite: false }));
snow.frustumCulled = false; scene.add(snow);

// ------------------------------------------------------------------ load
const loader = new GLTFLoader();
const load = (f) => new Promise((res, rej) => loader.load(A + f, res, undefined, rej));
const L = {};      // layout
let world, holderGLB, cutterGLB;
const H = { root: null, j: {}, spin: [], lights: {} };
const C = { root: null, j: {}, spin: [], lights: {}, vel: new THREE.Vector3(), yawRate: 0, p: { x: 0, y: 0, z: 0 }, yaw: 0, toolDz: 0, blade: 0 };
const cable = { L: [], stub: [], far: [], lift: 0, pivot: null, severed: false };
let seabedMeshes = [];

function nodes(root, prefix) {
  const j = {};
  for (const n of ['j_slew', 'j_shoulder', 'j_elbow', 'j_wrist', 'j_roll', 'jaw_up', 'jaw_lo', 'blade_slide', 'tool_point']) {
    const o = root.getObjectByName(`${prefix}_${n}`); if (o) j[n] = o;
  }
  const spin = []; root.traverse((o) => { if (/^prop_\d+_spin$/.test(o.name)) spin.push(o); });
  const lights = {}; root.traverse((o) => { const m = o.name.match(/_light_(FL|FR|RL|RR)$/); if (m) lights[m[1]] = o; });
  return { j, spin, lights };
}

async function init() {
  const [lay, w, hg, cg] = await Promise.all([fetch(A + 'layout.json').then((r) => r.json()), load('cablecut_world.glb'), load(`rov01a_holder_lod${LOD}.glb`), load(`rov01b_cutter_lod${LOD}.glb`)]);
  Object.assign(L, lay);
  world = w.scene; scene.add(world);
  world.traverse((o) => {
    if (!o.isMesh) return;
    if (/^seabed/.test(o.name)) seabedMeshes.push(o);
    if (/^cable_L/.test(o.name)) cable.L.push(o); else if (/^cable_stub/.test(o.name)) cable.stub.push(o); else if (/^cable_far/.test(o.name)) cable.far.push(o);
    o.frustumCulled = false;
  });
  // stub shares one pivot so it can drop away after the cut
  const pivB = [L.cut_x + L.stub_len, 0, lieZ(L.cut_x + L.stub_len)];
  cable.pivot = new THREE.Group(); cable.pivot.position.copy(B2T(...pivB)); cable.pivot0 = cable.pivot.position.clone();
  scene.add(cable.pivot); cable.pivot.updateMatrixWorld(true);
  for (const m of cable.stub) cable.pivot.attach(m);
  // vehicles
  H.root = hg.scene; C.root = cg.scene; scene.add(H.root); scene.add(C.root);
  Object.assign(H, nodes(H.root, 'holder')); Object.assign(C, nodes(C.root, 'cutter'));
  for (const R of [H.root, C.root]) R.traverse((o) => { o.frustumCulled = false; });
  // spot lights from the vehicle lamps
  for (const R of [H, C]) {
    for (const k of (LOWQ && R === H ? [] : ['FL', 'FR'])) {
      const n = R.lights[k]; if (!n) continue;
      const s = new THREE.SpotLight(0xfff0dc, 38, 14, 0.85, 0.6, 1.6); n.add(s);
      const tg = new THREE.Object3D(); tg.position.set(6, -0.8, 0); n.add(tg); s.target = tg;
    }
  }
  resetGame();
  G.ready = true; G.state = 'approach';
  $('load').style.opacity = 0; $('fade').style.opacity = 0;
  note('Reach the marked point on the cable', 0);
  hint('W A S D move · Q E depth · ← → turn · ↑ ↓ tool height · Space cut · C camera', 12000);
}

// ------------------------------------------------------------------ helpers
function lieZ(x) {
  const s = L.lie_z_samples; if (x <= s[0][0]) return s[0][1]; if (x >= s[s.length - 1][0]) return s[s.length - 1][1];
  for (let i = 0; i < s.length - 1; i++) if (x >= s[i][0] && x <= s[i + 1][0]) return lerp(s[i][1], s[i + 1][1], (x - s[i][0]) / (s[i + 1][0] - s[i][0]));
  return 0;
}
function liftAt(x) { const u = (x - L.grip_x) / L.lift_w; return Math.abs(u) < 1 ? L.lift * Math.pow(Math.cos(Math.PI * u / 2), 2) : 0; }
function cableZ(x) { return lieZ(x) + liftAt(x) * cable.lift; }
const ray = new THREE.Raycaster(); const DOWN = new THREE.Vector3(0, -1, 0);
function groundZ(xb, yb) {   // seabed height (Blender z) below a Blender xy
  if (!seabedMeshes.length) return 0;
  ray.set(new THREE.Vector3(xb, 30, -yb), DOWN); ray.far = 60;
  const hit = ray.intersectObjects(seabedMeshes, false)[0]; return hit ? hit.point.y : 0;
}
function setPose(root, p, yaw) { root.position.copy(B2T(p.x, p.y, p.z)); root.rotation.set(0, yaw, 0); }
function toLocal(rootP, yaw, t) {
  const dx = t.x - rootP.x, dy = t.y - rootP.y, c = Math.cos(-yaw), s = Math.sin(-yaw);
  return { x: c * dx - s * dy, y: s * dx + c * dy, z: t.z - rootP.z };
}
// planar 2-link IK for the manipulator (arm base at local (0.80,-0.28,-0.30), shoulder +0.13 up)
function ik(local, toolFwd, toolUp) {
  const rel = { x: local.x - L.arm_base_local[0], y: local.y - L.arm_base_local[1], z: local.z - (L.arm_base_local[2] + 0.13) };
  const slew = Math.atan2(rel.y, rel.x), d = Math.hypot(rel.x, rel.y);
  const wd = d - toolFwd, wh = rel.z - toolUp;
  const Dr = Math.hypot(wd, wh); const D = clamp(Dr, 0.06, L_UP + L_FORE - 0.004);
  const p1 = Math.atan2(wh, wd) + Math.acos(clamp((L_UP * L_UP + D * D - L_FORE * L_FORE) / (2 * L_UP * D), -1, 1));
  const ex = L_UP * Math.cos(p1), ey = L_UP * Math.sin(p1);
  const p2 = Math.atan2(wh - ey, wd - ex);
  return { slew, p1, p2, p3: 0, reach: Dr, ok: Dr <= L_UP + L_FORE - 0.004 && Dr > 0.2 && Math.abs(slew) < 0.62 };
}
const STOW = { slew: 0, p1: -62 * Math.PI / 180, p2: -168 * Math.PI / 180, p3: -120 * Math.PI / 180 };
function applyArm(R, a, jaw, blade, roll = 0) {
  const j = R.j; if (!j.j_slew) return;
  j.j_slew.rotation.y = a.slew; j.j_shoulder.rotation.z = a.p1; j.j_elbow.rotation.z = a.p2 - a.p1; j.j_wrist.rotation.z = a.p3 - a.p2;
  j.j_roll.rotation.x = roll;
  if (j.jaw_up) { j.jaw_up.rotation.z = jaw * Math.PI / 180; j.jaw_lo.rotation.z = -jaw * Math.PI / 180; }
  if (j.blade_slide) j.blade_slide.position.y = blade;
}
const mixArm = (a, b, t) => ({ slew: lerp(a.slew, b.slew, t), p1: lerp(a.p1, b.p1, t), p2: lerp(a.p2, b.p2, t), p3: lerp(a.p3, b.p3, t) });
function spinProps(R, dt, rate) { R.spin.forEach((s, i) => { s.rotation.y += (i % 2 ? -1 : 1) * rate * dt; }); }
function setLift(v) { cable.lift = v; for (const m of [...cable.L, ...cable.stub]) if (m.morphTargetInfluences) m.morphTargetInfluences[m.morphTargetDictionary?.lift ?? 0] = v; }

// ------------------------------------------------------------------ game state
const HOLD = { start: { x: 0, y: 0, z: 0 }, end: { x: 0, y: 0, z: 0 }, yaw: Math.PI / 2 };
const TOOLS = { grip: { fwd: 0.07 + 0.232, up: 0 }, shear: { fwd: 0.07 + 0.185, up: -0.005 } };
let gripTarget, preTarget, gripArm, preArm, markerRing, silt = null;
function resetGame() {
  setLift(0); cable.severed = false; cable.pivot.position.copy(cable.pivot0); cable.pivot.rotation.set(0, 0, 0);
  const hp = L.holder.pos; HOLD.end = { x: hp[0], y: hp[1], z: hp[2] }; HOLD.start = { x: hp[0] - 0.5, y: hp[1] - 2.6, z: hp[2] + 0.1 }; HOLD.yaw = L.holder.yaw_deg * Math.PI / 180;
  G.holder = { t: -1, ready: false };
  setPose(H.root, HOLD.start, HOLD.yaw); applyArm(H, STOW, 8, 0);
  const cp = L.cutter.pos;
  C.p = { x: cp[0] + 5.2, y: cp[1] + 3.4, z: 1.3 }; C.yaw = Math.atan2(cp[1] - C.p.y, cp[0] - C.p.x);
  C.vel.set(0, 0, 0); C.yawRate = 0; C.toolDz = 0; C.blade = 0; C.arm = { ...STOW }; setPose(C.root, C.p, C.yaw); applyArm(C, STOW, 0, 0);
  G.cut = { stage: 'idle', t: 0 }; G.state = 'approach';
  // marker ring at the cut point
  if (markerRing) scene.remove(markerRing);
  markerRing = new THREE.Mesh(new THREE.TorusGeometry(0.095, 0.0035, 8, 48), new THREE.MeshBasicMaterial({ color: 0x57f2ff, transparent: true, opacity: 0.8, depthWrite: false, fog: false }));
  markerRing.rotation.y = Math.PI / 2; scene.add(markerRing);
  if (silt) { scene.remove(silt); silt = null; }
  gripTarget = { x: L.grip_x, y: 0, z: lieZ(L.grip_x) + liftAt(L.grip_x) };
  const rootH = L.holder.pos; const fwdH = { x: Math.cos(HOLD.yaw), y: Math.sin(HOLD.yaw) };
  preTarget = { x: gripTarget.x - fwdH.x * 0.3, y: gripTarget.y - fwdH.y * 0.3, z: gripTarget.z + 0.10 };
  const lh = toLocal(HOLD.end, HOLD.yaw, gripTarget), lp = toLocal(HOLD.end, HOLD.yaw, preTarget);
  gripArm = ik(lh, TOOLS.grip.fwd, TOOLS.grip.up); preArm = ik(lp, TOOLS.grip.fwd, TOOLS.grip.up);
  G.state = 'approach'; note('Reach the marked point on the cable', 0);
}

function holderUpdate(dt) {
  const h = G.holder;
  const cutPtB = { x: L.cut_x, y: 0 };
  const dist = Math.hypot(C.p.x - cutPtB.x, C.p.y - cutPtB.y);
  if (h.t < 0 && dist < 7.5) { h.t = 0; note('ROV-01A is taking hold of the cable', 0); G.state = 'holder'; }
  if (h.t >= 0) h.t += dt;
  const t = Math.max(h.t, 0);
  const move = ease(t / 4.0);
  const p = { x: lerp(HOLD.start.x, HOLD.end.x, move), y: lerp(HOLD.start.y, HOLD.end.y, move), z: lerp(HOLD.start.z, HOLD.end.z, move) + 0.03 * Math.sin(performance.now() / 700) };
  setPose(H.root, p, HOLD.yaw);
  const a1 = ease((t - 4.0) / 3.0), a2 = ease((t - 7.0) / 2.0), jc = ease((t - 9.0) / 1.2), lf = ease((t - 10.2) / 2.4);
  const arm = t < 7.0 ? mixArm(STOW, preArm, a1) : mixArm(preArm, gripArm, a2);
  const jaw = t < 9.0 ? lerp(8, 52, ease((t - 4.0) / 2.0)) : lerp(52, L.grip_angle, jc);
  applyArm(H, arm, jaw, 0);
  setLift(lf);
  if (!h.ready && t > 12.8) { h.ready = true; note('Cable held. Align the shear on the ring and cut.', 0); hint('Space / A — cut', 9000); }
  spinProps(H, dt, t > 0 && t < 5 ? 40 : 6);
}

// ------------------------------------------------------------------ input
const keys = {};
addEventListener('keydown', (e) => { keys[e.code] = true; if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
  if (e.code === 'KeyC') { G.cam = G.cam === 'chase' ? 'rov' : 'chase'; }
  if (e.code === 'KeyR') { resetGame(); }
  if (e.code === 'Space' || e.code === 'KeyF') tryCut(); });
addEventListener('keyup', (e) => { keys[e.code] = false; });
let padPrev = {};
function readPad() {
  const o = { fwd: 0, str: 0, up: 0, yaw: 0, tool: 0 };
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  for (const p of pads) {
    if (!p) continue; const dz = (v) => (Math.abs(v) < 0.15 ? 0 : v);
    o.str += dz(p.axes[0] || 0); o.fwd += -dz(p.axes[1] || 0); o.yaw += -dz(p.axes[2] || 0); o.tool += -dz(p.axes[3] || 0);
    o.up += ((p.buttons[7]?.value || 0) - (p.buttons[6]?.value || 0)) + ((p.buttons[5]?.pressed ? 1 : 0) - (p.buttons[4]?.pressed ? 1 : 0));
    const b = (i) => !!p.buttons[i]?.pressed;
    if (b(0) && !padPrev[0]) tryCut(); if (b(3) && !padPrev[3]) G.cam = G.cam === 'chase' ? 'rov' : 'chase'; if (b(9) && !padPrev[9]) resetGame();
    padPrev = { 0: b(0), 3: b(3), 9: b(9) };
  }
  return o;
}

function tryCut() {
  if (G.cut.stage !== 'idle') return;
  if (!G.holder.ready) { note('Wait for ROV-01A to secure the cable', 4000); return; }
  if (!G.inRange) { note('Align the shear with the ring first', 4000); return; }
  G.cut = { stage: 'closing', t: 0 }; G.state = 'cutting';
}

// ------------------------------------------------------------------ cutter update
const tmpV = new THREE.Vector3();
function cutterUpdate(dt) {
  const pad = readPad();
  const K = (a) => (keys[a] ? 1 : 0);
  const locked = G.cut.stage !== 'idle';
  const fwd = clamp(K('KeyW') - K('KeyS') + pad.fwd, -1, 1) * (locked ? 0 : 1), str = clamp(K('KeyA') - K('KeyD') - pad.str, -1, 1) * (locked ? 0 : 1);
  const up = clamp(K('KeyE') - K('KeyQ') + pad.up, -1, 1) * (locked ? 0 : 1), yawIn = clamp(K('ArrowLeft') - K('ArrowRight') + pad.yaw, -1, 1) * (locked ? 0 : 1);
  const toolIn = clamp(K('ArrowUp') - K('ArrowDown') + pad.tool, -1, 1);
  const acc = 2.6, drag = 1.7;
  const c = Math.cos(C.yaw), s = Math.sin(C.yaw);
  C.vel.x += (c * fwd - s * str) * acc * dt; C.vel.y += (s * fwd + c * str) * acc * dt; C.vel.z += up * acc * 0.8 * dt;
  const dmp = Math.exp(-drag * dt); C.vel.multiplyScalar(dmp);
  const sp = Math.hypot(C.vel.x, C.vel.y); if (sp > 2.2) { C.vel.x *= 2.2 / sp; C.vel.y *= 2.2 / sp; }
  C.yawRate += (yawIn * 1.5 - C.yawRate) * Math.min(1, dt * 5); C.yaw += C.yawRate * dt;
  C.p.x += C.vel.x * dt; C.p.y += C.vel.y * dt; C.p.z += C.vel.z * dt;
  C.p.x = clamp(C.p.x, -9, 9); C.p.y = clamp(C.p.y, -8, 9);
  // keep clear of the holder ROV and the seabed
  const hx = C.p.x - H.root.position.x, hy = C.p.y + H.root.position.z;
  const hd = Math.hypot(hx, hy); if (hd < 1.5 && C.p.z < 1.7) { C.p.x += hx / hd * (1.5 - hd); C.p.y += hy / hd * (1.5 - hd); C.vel.multiplyScalar(0.8); }
  const gz = groundZ(C.p.x, C.p.y) + 0.6; if (C.p.z < gz) { C.p.z = gz; C.vel.z = Math.max(0, C.vel.z); }
  C.p.z = Math.min(C.p.z, 4.0);
  const bob = Math.sin(performance.now() / 900) * 0.012;
  setPose(C.root, { x: C.p.x, y: C.p.y, z: C.p.z + bob }, C.yaw);
  // pitch/roll cue from acceleration for a floaty feel
  const lv = toLocal({ x: 0, y: 0, z: 0 }, C.yaw, { x: C.vel.x, y: C.vel.y, z: 0 });
  C.root.rotation.z = clamp(lv.x * 0.05, -0.1, 0.1); C.root.rotation.x = clamp(-lv.y * 0.05, -0.1, 0.1);
  spinProps(C, dt, 6 + (Math.abs(fwd) + Math.abs(str) + Math.abs(up) + Math.abs(yawIn)) * 30);

  // arm: tool tracks the cut point while the ring is reachable; otherwise stowed
  C.toolDz = clamp(C.toolDz + toolIn * 0.12 * dt, -0.12, 0.12);
  const cutB = { x: L.cut_x, y: 0, z: cableZ(L.cut_x) };
  const loc = toLocal(C.p, C.yaw, cutB);
  const tgt = { x: loc.x, y: loc.y, z: loc.z + C.toolDz };
  const sol = ik(tgt, TOOLS.shear.fwd, TOOLS.shear.up);
  const near = Math.hypot(C.p.x - cutB.x, C.p.y) < 1.9 && !cable.severed;
  const want = near && sol.ok ? sol : STOW;
  const k = Math.min(1, dt * 3.2); const cur = C.arm;
  for (const key of ['slew', 'p1', 'p2', 'p3']) cur[key] += (want[key] - cur[key]) * k;
  const armErr = Math.abs(cur.p1 - want.p1) + Math.abs(cur.p2 - want.p2) + Math.abs(cur.slew - want.slew);
  G.armReady = near && sol.ok && armErr < 0.08;
  // blade
  if (G.cut.stage === 'closing') { G.cut.t += dt; C.blade = lerp(0, L.blade_stroke ?? -0.123, ease(G.cut.t / 0.6)); if (G.cut.t >= 0.6) { severCable(); G.cut = { stage: 'open', t: 0 }; } }
  else if (G.cut.stage === 'open') { G.cut.t += dt; C.blade = lerp(L.blade_stroke ?? -0.123, 0, ease((G.cut.t - 0.5) / 1.2)); if (G.cut.t > 2.0) G.cut.stage = 'done'; }
  applyArm(C, cur, 0, C.blade);
  // in range: arm on target, aligned height, holder ready, cable intact
  G.inRange = G.armReady && Math.abs(C.toolDz) < 0.045 && !cable.severed;
  G.pos = [C.p.x, C.p.y, C.p.z]; G.yaw = C.yaw;
  if (markerRing) {
    markerRing.position.copy(B2T(L.cut_x, 0, cableZ(L.cut_x)));
    markerRing.visible = !cable.severed; markerRing.material.opacity = (G.inRange ? 0.95 : 0.45) + 0.25 * Math.sin(performance.now() / 260);
    markerRing.material.color.set(G.inRange && G.holder.ready ? 0x7dffb2 : 0x57f2ff);
  }
}

function severCable() {
  cable.severed = true; G.cut.severedAt = performance.now(); G.state = 'cut';
  // silt burst
  const n = 90, g = new THREE.BufferGeometry(), pos = new Float32Array(n * 3), vel = [];
  const o = B2T(L.cut_x, 0, cableZ(L.cut_x));
  for (let i = 0; i < n; i++) { pos[i * 3] = o.x; pos[i * 3 + 1] = o.y; pos[i * 3 + 2] = o.z; vel.push(new THREE.Vector3((Math.random() - .5) * 0.8, Math.random() * 0.5 - 0.1, (Math.random() - .5) * 0.8)); }
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  silt = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xb8c4b0, size: 0.05, transparent: true, opacity: 0.8, depthWrite: false })); silt.userData = { vel, t: 0 };
  silt.frustumCulled = false; scene.add(silt);
  note('', 0); hint('', 0);
  setTimeout(() => { msg('CABLE SEVERED', 5500); note('Mission complete — R to restart', 0); }, 1400);
  G.state = 'done';
}

function postCut(dt) {
  if (!cable.severed) return;
  const t = (performance.now() - G.cut.severedAt) / 1000;
  const a = ease(t / 2.6);
  cable.pivot.position.set(cable.pivot0.x + 0.15 * a, cable.pivot0.y, cable.pivot0.z);
  cable.pivot.rotation.z = a * 8.6 * Math.PI / 180;   // Blender -Y rot (drop) == +Z in three
  cable.pivot.rotation.y = a * 7.0 * Math.PI / 180;
  if (silt) {
    const p = silt.geometry.attributes.position, v = silt.userData.vel; silt.userData.t += dt;
    for (let i = 0; i < v.length; i++) { p.array[i * 3] += v[i].x * dt; p.array[i * 3 + 1] += v[i].y * dt; p.array[i * 3 + 2] += v[i].z * dt; v[i].multiplyScalar(Math.exp(-1.1 * dt)); }
    p.needsUpdate = true; silt.material.opacity = Math.max(0, 0.8 - silt.userData.t * 0.18);
    silt.material.size = 0.05 + silt.userData.t * 0.05;
  }
}

// ------------------------------------------------------------------ camera
const camPos = new THREE.Vector3(), camLook = new THREE.Vector3(); let camInit = false;
function cameraUpdate(dt) {
  const c = Math.cos(C.yaw), s = Math.sin(C.yaw);
  const near = clamp(1 - (Math.hypot(C.p.x - L.cut_x, C.p.y - 0.4) - 1.5) / 2.2, 0, 1);
  let desired, look;
  if (G.cam === 'rov') {
    const n = C.root.getObjectByName('cutter_root') || C.root;
    desired = B2T(C.p.x + c * 0.9, C.p.y + s * 0.9, C.p.z + 0.07); look = B2T(C.p.x + c * 4, C.p.y + s * 4, C.p.z - 0.35); camera.fov = 78;
  } else {
    const off = (ox, oy) => ({ x: C.p.x + c * ox - s * oy, y: C.p.y + s * ox + c * oy });
    const ox = lerp(-3.6, -1.7, near), oy = lerp(0.0, -2.5, near), hgt = lerp(1.35, 1.0, near);
    const w = off(ox, oy); desired = B2T(w.x, w.y, C.p.z + hgt);
    const ah = off(1.6, 0); look = B2T(ah.x, ah.y, C.p.z - 0.15);
    if (near > 0.05) look.lerp(B2T(L.cut_x, 0.0, cableZ(L.cut_x) - 0.05), near * 0.85);
    camera.fov = 62;
  }
  const gz = groundZ(desired.x, -desired.z) + 0.25; if (desired.y < gz) desired.y = gz;
  const k = camInit ? Math.min(1, dt * (G.cam === 'rov' ? 12 : 3.2)) : 1; camInit = true;
  camPos.lerp(desired, k); camLook.lerp(look, k);
  camera.position.copy(camPos); camera.lookAt(camLook); camera.updateProjectionMatrix();
}

// ------------------------------------------------------------------ text (tiny, fading)
let noteTimer, hintTimer, msgTimer;
function setText(id, text, ms, tm) { const el = $(id); clearTimeout(tm); if (!text) { el.style.opacity = 0; return; } el.textContent = text; el.style.opacity = 0.9; if (ms > 0) return setTimeout(() => { el.style.opacity = 0; }, ms); }
function note(t, ms) { noteTimer = setText('obj', t, ms, noteTimer); }
function hint(t, ms) { hintTimer = setText('hint', t, ms, hintTimer); }
function msg(t, ms) { msgTimer = setText('msg', t, ms, msgTimer); }

// ------------------------------------------------------------------ loop
let last = performance.now(), fAcc = 0, fN = 0;
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  fAcc += dt > 0 ? (now - (frame.p || now)) / 1000 : 0; frame.p = now; fN++;
  if (fAcc >= 1) { G.fps = fN / fAcc; fN = 0; fAcc = 0; }
  G.frames++;
  if (G.ready) {
    holderUpdate(dt); cutterUpdate(dt); postCut(dt); cameraUpdate(dt);
    snow.position.set(camPos.x, 0, camPos.z);
    const a = snowGeo.attributes.position; for (let i = 0; i < SNOW_N; i++) { a.array[i * 3 + 1] += (Math.sin(now / 1500 + i) * 0.01 - 0.02) * dt; if (a.array[i * 3 + 1] < -0.5) a.array[i * 3 + 1] = 4.5; } a.needsUpdate = true;
    snow.position.y = camPos.y - 1.5;
  }
  renderer.render(scene, camera);
}
renderer.setAnimationLoop(frame);
// test / debug hooks (no on-screen output)
G.teleportToStation = () => { const p = L.cutter.pos; C.p = { x: p[0], y: p[1], z: p[2] }; C.yaw = L.cutter.yaw_deg * Math.PI / 180; C.vel.set(0, 0, 0); };
G.skipHolder = () => { G.holder.t = Math.max(G.holder.t, 13.0); };
G.layout = L;
init().catch((e) => { console.error('cablecut init failed', e); $('load').textContent = 'failed to load assets'; $('load').style.opacity = 0.9; G.state = 'error'; G.error = String(e); });
