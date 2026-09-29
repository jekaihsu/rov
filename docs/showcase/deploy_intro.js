// Deployment intro: a work boat lies with its stern at the tether spool. One deck hand crouches,
// lifts the ROV, swings it underhand and lets go over the transom; a second deck hand tends the
// tether off the reel. Splash, then the ROV glides down to its start position while the cable
// pays out.
//
// Open models (see models/CREDITS.md): work boat (OpenGameArt "Fishing Boat", CC0), deck crew
// (Quaternius "Animated Men", CC0), sea + sky (three.js Water / Sky shaders, MIT).
//
//   const assets = await DeployIntro.loadAssets('models/');
//   const intro = new DeployIntro(scene, { spool: [n,e,d], start: [n,e,d], seabed: 30, assets });
//   intro.play(rovObject3D, camera, () => { /* hand control back */ });
//   each frame: intro.update(dt)            // returns true while playing
//   intro.skip()                            // jump to the end
//   intro.aboveWater(camera)                // true while the intro's sea/sky should replace the viewer's surface
// World mapping (same as the viewer): three = (-east, -down, north).
import * as THREE from 'three';
import { loadGLTF } from './glb.js';
import { Water } from 'three/addons/objects/Water.js';
import { Sky } from 'three/addons/objects/Sky.js';
import { Humanoid } from './humanoid.js';
import { Cable } from './cable.js';

const toThree = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const ease = (t) => t * t * (3 - 2 * t);
const clamp01 = (t) => Math.max(0, Math.min(1, t));
const M = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.1, ...o });
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// work-boat model placement (source: 21.6 units long, stern at +X, deck at y = 1.44, transom top 2.2)
const BOAT_LEN = 10.0, BOAT_SRC_LEN = 21.64, BOAT_S = BOAT_LEN / BOAT_SRC_LEN;
const BOAT_SRC = { cx: -1.8, cz: 0.22, keel: -0.4, deck: 1.44, transomTop: 2.2, stern: 9.02 };
const KEEL_Y = -0.45;

function placeModelBoat(src) {
  const boat = new THREE.Group();
  const m = src.clone(true);
  m.scale.setScalar(BOAT_S);
  m.rotation.y = Math.PI / 2;                              // source +X (stern) -> local -Z
  const yOff = KEEL_Y - BOAT_SRC.keel * BOAT_S;
  m.position.set(-BOAT_SRC.cz * BOAT_S, yOff, BOAT_SRC.cx * BOAT_S);
  m.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = true; o.receiveShadow = true;
    const mat = (o.material = o.material.clone());
    if (/glass/i.test(mat.name)) { mat.transparent = true; mat.opacity = 0.45; mat.metalness = 0.6; mat.roughness = 0.1; mat.color.setHex(0x5c7384); }
    else { mat.roughness = Math.max(mat.roughness ?? 0.6, 0.55); mat.metalness = 0.05; }
  });
  boat.add(m);
  const deckY = BOAT_SRC.deck * BOAT_S + yOff;
  const sternZ = -(BOAT_SRC.stern - BOAT_SRC.cx) * BOAT_S;
  boat.userData = { L: BOAT_LEN, deckY, sternZ, transomY: BOAT_SRC.transomTop * BOAT_S + yOff, aftDeck: [sternZ + 0.3, -0.2] };
  return boat;
}

function buildFallbackBoat() {                           // used only if the model fails to load
  const boat = new THREE.Group();
  const L = 10, B = 3.6;
  const s = new THREE.Shape();
  s.moveTo(-B / 2, -L / 2); s.lineTo(B / 2, -L / 2); s.lineTo(B / 2, L / 2 - 3);
  s.quadraticCurveTo(B / 2, L / 2 - 0.4, 0, L / 2); s.quadraticCurveTo(-B / 2, L / 2 - 0.4, -B / 2, L / 2 - 3); s.closePath();
  const g = new THREE.ExtrudeGeometry(s, { depth: 0.85, bevelEnabled: true, bevelSize: 0.08, bevelThickness: 0.08 });
  g.rotateX(Math.PI / 2);
  const hull = new THREE.Mesh(g, M(0xf0f0ea)); hull.position.y = 0.4; boat.add(hull);
  const wh = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.9, 2.8), M(0xf5f5f0)); wh.position.set(0, 1.35, 1.6); boat.add(wh);
  boat.userData = { L, deckY: 0.4, sternZ: -L / 2, transomY: 0.75, aftDeck: [-L / 2 + 0.3, 0] };
  return boat;
}

/** Tether reel: frame, drum with cable wraps, crank and slip-ring box. Axis along local X. */
function buildReel() {
  const reel = new THREE.Group();
  const frameMat = M(0x2f3a44, { metalness: 0.5, roughness: 0.4 });
  for (const x of [-0.36, 0.36]) {
    const plate = new THREE.Mesh(new THREE.CylinderGeometry(0.33, 0.33, 0.025, 36), M(0xd8dde2, { metalness: 0.7, roughness: 0.3 }));
    plate.rotation.z = Math.PI / 2; plate.position.set(x, 0.48, 0); reel.add(plate);
    const legA = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.5, 0.04), frameMat); legA.position.set(x * 1.12, 0.24, 0.16); legA.rotation.x = 0.35; reel.add(legA);
    const legB = legA.clone(); legB.position.z = -0.16; legB.rotation.x = -0.35; reel.add(legB);
  }
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.04, 0.5), frameMat); base.position.y = 0.02; reel.add(base);
  const drum = new THREE.Group(); drum.position.y = 0.48; reel.add(drum);
  const core = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.7, 24), M(0x1d2328)); core.rotation.z = Math.PI / 2; drum.add(core);
  const wrapMat = M(0xe9c534, { roughness: 0.5 });                       // yellow tether wound on the drum
  for (let i = 0; i < 14; i++) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.235 + (i % 2) * 0.006, 0.02, 6, 32), wrapMat);
    ring.rotation.y = Math.PI / 2; ring.position.x = -0.3 + i * 0.046; drum.add(ring);
  }
  const fill = new THREE.Mesh(new THREE.CylinderGeometry(0.235, 0.235, 0.66, 28), wrapMat); fill.rotation.z = Math.PI / 2; drum.add(fill);
  const crank = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.2, 0.03), frameMat); crank.position.set(0.4, -0.08, 0); drum.add(crank);
  const knob = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.09, 10), M(0x111111)); knob.rotation.z = Math.PI / 2; knob.position.set(0.44, -0.17, 0); drum.add(knob);
  const box = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.14, 0.14), M(0x3a7bd5)); box.position.set(-0.47, 0.48, 0); reel.add(box);
  reel.userData = { drum, top: V(0, 0.48 + 0.25, 0) };
  reel.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return reel;
}

function makeParticles(n, color, size) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3).fill(-9999), 3));
  const m = new THREE.PointsMaterial({ color, size, transparent: true, opacity: 0.9, depthWrite: false });
  const p = new THREE.Points(g, m);
  p.frustumCulled = false;
  p.userData.v = new Float32Array(n * 3);
  p.userData.life = new Float32Array(n);
  return p;
}

// launcher key poses (person-local, metres; the deck hand faces +Z = aft). rov = ROV centre.
const KEYS = [
  // t,   pelvis,            bend,  rov,              head
  [0.0, [0, 0, 0], 0.1, [0, 0.2, 0.62], [0, 0.35]],
  [2.0, [0, 0, 0], 0.15, [0, 0.2, 0.62], [0, 0.4]],
  [2.8, [0, -0.44, -0.12], 0.85, [0, 0.2, 0.62], [0, 0.35]],        // crouch, grab the frame
  [3.8, [0, -0.06, 0], 0.12, [0, 1.0, 0.42], [0, 0.1]],             // lift to the chest
  [4.6, [0, -0.3, -0.05], 0.6, [0, 0.5, 0.5], [0, 0.35]],           // backswing low
  [5.3, [0, 0.02, 0.14], -0.08, [0, 1.3, 0.95], [0, -0.05]],        // forward swing up -> release
];
const T_RELEASE = 5.3;

export class DeployIntro {
  static async loadAssets(base = 'models/') {
    const [boat, human, normals] = await Promise.all([
      loadGLTF(base + 'workboat.glb').then((g) => g.scene).catch(() => null),
      Humanoid.load(base + 'worker.glb').catch(() => null),
      new THREE.TextureLoader().loadAsync(base + 'waternormals.jpg').catch(() => null),
    ]);
    return { boat, human, normals };
  }

  constructor(scene, { spool, start, seabed = 30, assets = {} }) {
    this.scene = scene;
    this.spool = toThree(spool);
    this.start = toThree(start);
    this.seabed = seabed;
    this.duration = 10.5;
    this.t = 0;
    this.playing = false;
    this.objects = [];
    const add = (o) => { scene.add(o); this.objects.push(o); return o; };

    // boat: stern (-Z local) at the spool, bow pointing away from the dive site
    this.boat = assets.boat ? placeModelBoat(assets.boat) : buildFallbackBoat();
    const dir = new THREE.Vector3().subVectors(this.start, this.spool); dir.y = 0;
    if (dir.lengthSq() < 1e-6) dir.set(0, 0, -1);
    dir.normalize();
    this.boat.rotation.y = Math.atan2(-dir.x, -dir.z);
    const ud = this.boat.userData;
    this.boat.position.copy(this.spool).addScaledVector(dir, ud.sternZ + 0.15);   // transom just inboard of the spool
    this.boat.position.y = 0;
    add(this.boat);

    this.reel = buildReel();
    this.reel.position.set(-0.75, ud.deckY, ud.sternZ + 2.2);
    this.boat.add(this.reel);
    this.boat.updateMatrixWorld(true);

    // deck crew
    this.launcher = this.tender = null;
    if (assets.human) {
      this.launcher = new Humanoid(assets.human, { shirt: 0x2b3f55, pants: 0x2a2f36, vest: 0xff6a13, helmet: 0xf4f4ef });
      this.launcher.root.position.set(0.25, ud.deckY, ud.sternZ + 1.35);
      this.launcher.root.rotation.y = Math.PI;                    // face aft
      this.launcher.play('Idle');
      this.boat.add(this.launcher.root);
      this.tender = new Humanoid(assets.human, { shirt: 0x5b6770, pants: 0x30343a, vest: 0xffc21a, helmet: 0xf4f4ef, height: 1.7 });
      this.tender.root.position.set(-0.8, ud.deckY, ud.sternZ + 1.55);
      this.tender.root.rotation.y = Math.PI - 0.35;
      this.tender.play('Idle', { at: 1.3 });
      this.boat.add(this.tender.root);
    }

    // sea + sky for the above-water shots
    if (assets.normals) {
      assets.normals.wrapS = assets.normals.wrapT = THREE.RepeatWrapping;
      this.sun = V(0.45, 0.42, -0.8).normalize();
      this.water = add(new Water(new THREE.PlaneGeometry(5000, 5000), {
        textureWidth: 512, textureHeight: 512, waterNormals: assets.normals, sunDirection: this.sun,
        sunColor: 0xfff1d6, waterColor: 0x0a3347, distortionScale: 1.3, fog: false, alpha: 0.98,
      }));
      this.water.rotation.x = -Math.PI / 2; this.water.position.y = 0.005;
      this.water.material.uniforms.size.value = 1.6;
      this.water.material.uniforms.distortionScale.value = 1.3;
      this.sky = add(new Sky());
      this.sky.scale.setScalar(900);
      const u = this.sky.material.uniforms;
      u.turbidity.value = 2.2; u.rayleigh.value = 0.9; u.mieCoefficient.value = 0.003; u.mieDirectionalG.value = 0.85;
      u.sunPosition.value.copy(this.sun).multiplyScalar(400);
    }

    // tether: real-thickness yellow cable, rebuilt each frame
    this.cable = new Cable(M(0xe9c534, { roughness: 0.5, metalness: 0 }), { radius: 0.0065, segments: 160, radial: 6 });
    add(this.cable.mesh);

    this.splash = add(makeParticles(600, 0xf2fbff, 0.1));
    this.spray = add(makeParticles(300, 0xffffff, 0.05));
    this.bubbles = add(makeParticles(260, 0xcfefff, 0.05));
    this.ring = add(new THREE.Mesh(new THREE.RingGeometry(0.8, 1.05, 64),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false })));
    this.ring.rotation.x = -Math.PI / 2; this.ring.visible = false;
    this.foam = add(new THREE.Mesh(new THREE.CircleGeometry(1.4, 48),
      new THREE.MeshBasicMaterial({ color: 0xf4fbff, transparent: true, opacity: 0, depthWrite: false })));
    this.foam.rotation.x = -Math.PI / 2; this.foam.visible = false;
  }

  _boatPoint(x, y, z) { return this.boat.localToWorld(V(x, y, z)); }
  _personPoint(p) { return this.launcher ? this.launcher.root.localToWorld(V(p[0], p[1], p[2])) : this._boatPoint(0.25, this.boat.userData.deckY + p[1], this.boat.userData.sternZ + 1.35 - p[2]); }

  /** true while the intro's own water/sky should be shown instead of the viewer's flat surface. */
  aboveWater(camera) { return !!this.water && this.playing && camera.position.y > 0.02; }

  play(rov, camera, onDone) {
    this.rov = rov;
    this.camera = camera;
    this.onDone = onDone;
    this.t = 0;
    this.playing = true;
    this.splashed = false;
    this.vel = null;
    this._camPos = null;
    this.qStart = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, this.boat.rotation.y + Math.PI, 0));
    if (this.water) { this.water.visible = true; this.sky.visible = true; }
    this.update(0);
  }

  skip() {
    if (!this.playing) return;
    this.t = this.duration;
    this.update(0);
  }

  _key(t) {
    let i = 0;
    while (i < KEYS.length - 2 && t > KEYS[i + 1][0]) i++;
    const a = KEYS[i], b = KEYS[i + 1];
    const k = ease(clamp01((t - a[0]) / (b[0] - a[0])));
    const L = (x, y) => x.map((v, j) => v + (y[j] - v) * k);
    return { pelvis: L(a[1], b[1]), bend: a[2] + (b[2] - a[2]) * k, rov: L(a[3], b[3]), head: L(a[4], b[4]) };
  }

  update(dt) {
    if (!this.playing) { this._particles(dt); return false; }
    this.t += dt;
    const t = Math.min(this.t, this.duration);
    const rov = this.rov;
    this.boat.updateMatrixWorld(true);

    // gentle swell on the boat
    this.boat.rotation.z = Math.sin(t * 0.9) * 0.018;
    this.boat.rotation.x = Math.sin(t * 0.7 + 1) * 0.012;
    this.boat.position.y = Math.sin(t * 0.8) * 0.05;

    // ── launcher + ROV ──
    const k = this._key(Math.min(t, T_RELEASE));
    const carrying = t < T_RELEASE;
    if (rov && carrying) {
      rov.position.copy(this._personPoint(k.rov));
      const swing = t > 3.8 ? Math.sin(clamp01((t - 3.8) / 1.5) * Math.PI) * -0.25 : 0;
      rov.quaternion.copy(this.qStart).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(swing, 0, 0)));
    }
    if (this.launcher) {
      const pose = { pelvis: k.pelvis, bend: k.bend, head: k.head };
      if (carrying) {
        pose.handL = V(k.rov[0] + 0.29, k.rov[1] + 0.06, k.rov[2] - 0.05);
        pose.handR = V(k.rov[0] - 0.29, k.rov[1] + 0.06, k.rov[2] - 0.05);
      } else {
        // follow-through, then relax
        const f = clamp01((t - T_RELEASE) / 1.8);
        pose.pelvis = [0, 0.02 * (1 - f), 0.14 * (1 - f)];
        pose.bend = -0.08 + 0.2 * f;
        pose.head = [0, -0.05 + 0.25 * f];
        if (f < 1) {
          const up = Math.sin(Math.min(1, f * 1.6) * Math.PI) * 0.25;
          pose.handL = V(0.24, 1.35 + up - 0.7 * f, 0.9 - 0.55 * f);
          pose.handR = V(-0.24, 1.35 + up - 0.7 * f, 0.9 - 0.55 * f);
        }
      }
      this.launcher.update(dt, pose);
    }
    if (rov && !carrying) this._flight(dt);

    // ── tether tender: hand over hand once the cable runs ──
    if (this.tender) {
      const run = t > T_RELEASE ? 1 : 0;
      const ph = t * 5.5;
      this.tender.update(dt, {
        pelvis: [0, -0.12, 0], bend: 0.3, head: [0.15, 0.35],
        handL: V(0.08, 0.95 + run * 0.06 * Math.sin(ph), 0.42 + run * 0.08 * Math.cos(ph)),
        handR: V(-0.12, 0.92 - run * 0.06 * Math.sin(ph), 0.62 - run * 0.08 * Math.cos(ph)),
      });
    }
    this.reel.userData.drum.rotation.x += dt * (t > T_RELEASE ? 5 : 0);

    this._drawTether(t);
    this._particles(dt);
    if (this.water) {
      this.water.material.uniforms.time.value += dt * 0.6;
      const above = !this.camera || this.camera.position.y > 0.02;
      this.water.visible = above; this.sky.visible = above;          // under water the viewer's own surface takes over
    }
    this._cameraPath(t);

    if (this.t >= this.duration) {
      this.playing = false;
      if (rov) rov.position.copy(this.start);
      if (this.water) { this.water.visible = false; this.sky.visible = false; }
      this.onDone && this.onDone();
    }
    return this.playing;
  }

  _flight(dt) {
    const rov = this.rov;
    if (!this.splashed) {
      if (!this.vel) {
        const aft = this._boatPoint(0, 0, -1).sub(this._boatPoint(0, 0, 0)).normalize();
        this.vel = aft.multiplyScalar(3.4).add(V(0, 1.6, 0));
        this.spin = 0;
      }
      this.vel.y -= 9.81 * dt;
      rov.position.addScaledVector(this.vel, dt);
      this.spin += dt;
      rov.quaternion.copy(this.qStart).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.25 + this.spin * 0.7, 0, this.spin * 0.12)));
      if (rov.position.y <= 0.12) {
        this.splashed = true;
        this.splashT = this.t;
        this.entry = rov.position.clone();
        this.entryQ = rov.quaternion.clone();
        this._emitSplash(rov.position, this.vel);
      }
      return;
    }
    // underwater: brake hard in the water, right itself, then glide down to the start point
    const s = this.t - this.splashT;
    const k = ease(clamp01((s - 0.3) / (this.duration - this.splashT - 0.5)));
    const plunge = V(this.vel.x, 0, this.vel.z).multiplyScalar(0.25 * (1 - Math.exp(-s * 3)));
    const dip = -0.9 * (1 - Math.exp(-s * 2.5));
    const p = this.entry.clone().add(plunge); p.y += dip;
    rov.position.lerpVectors(p, this.start, k);
    rov.position.y += Math.sin(s * 3) * 0.08 * (1 - k);
    rov.quaternion.slerpQuaternions(this.entryQ, this.qStart, Math.min(1, s * 0.9));
    if (s < 2.5 || Math.random() < 0.5) this._emitBubble(rov.position, s < 1 ? 4 : 1);
  }

  _gland() {
    return this.rov ? this.rov.localToWorld(V(0, 0.06, -0.38)) : this.start.clone();
  }

  _drawTether(t) {
    const ud = this.boat.userData;
    const pts = [];
    const reelTop = this.reel.localToWorld(this.reel.userData.top.clone());
    const hand = this.tender ? this.tender.hand('L').lerp(this.tender.hand('R'), 0.5) : this._boatPoint(-0.8, ud.deckY + 0.9, ud.sternZ + 1.1);
    const end = this._gland();
    pts.push(reelTop, reelTop.clone().lerp(hand, 0.5).add(V(0, -0.12, 0)), hand);
    if (t < T_RELEASE) {
      // slack bight lying on the deck between the tender and the ROV
      const deckY = this._boatPoint(0, ud.deckY + 0.02, 0).y;
      const a = hand.clone(); a.y = deckY;
      const b = end.clone(); b.y = deckY;
      pts.push(hand.clone().lerp(a, 0.75).add(V(0, 0, 0)));
      for (let i = 1; i <= 5; i++) {
        const u = i / 6;
        const p = a.clone().lerp(b, u);
        p.addScaledVector(this._boatPoint(1, 0, 0).sub(this._boatPoint(0, 0, 0)), Math.sin(u * Math.PI) * 0.35);
        p.y = deckY;
        pts.push(p);
      }
      pts.push(end.clone().lerp(b, 0.5), end);
    } else {
      // over the transom, then a slack catenary down to the ROV
      const transom = this._boatPoint(-0.25, ud.transomY + 0.03, ud.sternZ + 0.02);
      pts.push(this._boatPoint(-0.4, ud.deckY + 0.5, ud.sternZ + 0.6), transom);
      const n = 14, sag = 0.6 + Math.min(2.5, (this.t - T_RELEASE) * 0.6);
      for (let i = 1; i <= n; i++) {
        const u = i / n;
        const p = transom.clone().lerp(end, u);
        p.y -= Math.sin(Math.PI * u) * sag * (p.y > 0 ? 0.6 : 1);
        pts.push(p);
      }
    }
    this.cable.update(pts);
  }

  _emitSplash(at, vel) {
    const p = this.splash, pos = p.geometry.attributes.position.array, v = p.userData.v, life = p.userData.life;
    const hv = V(vel.x, 0, vel.z).multiplyScalar(0.35);
    for (let i = 0; i < life.length; i++) {
      const crown = i < life.length * 0.7;
      const a = Math.random() * Math.PI * 2, r = crown ? 0.35 + Math.random() * 0.25 : Math.random() * 0.2;
      pos[i * 3] = at.x + Math.cos(a) * r; pos[i * 3 + 1] = 0.05; pos[i * 3 + 2] = at.z + Math.sin(a) * r;
      const out = crown ? 1.2 + Math.random() * 1.6 : 0.3 + Math.random() * 0.5;
      const up = crown ? 1.5 + Math.random() * 2.2 : 3 + Math.random() * 3;       // crown sheet + central jet
      v[i * 3] = Math.cos(a) * out + hv.x; v[i * 3 + 1] = up; v[i * 3 + 2] = Math.sin(a) * out + hv.z;
      life[i] = 1.0 + Math.random() * 0.8;
    }
    const s = this.spray, sp = s.geometry.attributes.position.array, sv = s.userData.v, sl = s.userData.life;
    for (let i = 0; i < sl.length; i++) {
      const a = Math.random() * Math.PI * 2;
      sp[i * 3] = at.x; sp[i * 3 + 1] = 0.1; sp[i * 3 + 2] = at.z;
      sv[i * 3] = Math.cos(a) * (2 + Math.random() * 3); sv[i * 3 + 1] = 1 + Math.random() * 3; sv[i * 3 + 2] = Math.sin(a) * (2 + Math.random() * 3);
      sl[i] = 0.6 + Math.random() * 0.6;
    }
    this.ring.position.set(at.x, 0.03, at.z); this.ring.visible = true; this.ring.scale.setScalar(0.3); this.ringT = 0;
    this.foam.position.set(at.x, 0.025, at.z); this.foam.visible = true; this.foamT = 0;
  }

  _emitBubble(at, n = 1) {
    const p = this.bubbles, pos = p.geometry.attributes.position.array, v = p.userData.v, life = p.userData.life;
    for (let k = 0; k < n; k++) {
      const i = (this._bi = ((this._bi || 0) + 1) % life.length);
      pos[i * 3] = at.x + (Math.random() - 0.5) * 0.5; pos[i * 3 + 1] = at.y + (Math.random() - 0.5) * 0.3; pos[i * 3 + 2] = at.z + (Math.random() - 0.5) * 0.5;
      v[i * 3] = (Math.random() - 0.5) * 0.2; v[i * 3 + 1] = 0.5 + Math.random() * 0.9; v[i * 3 + 2] = (Math.random() - 0.5) * 0.2;
      life[i] = 2.5;
    }
  }

  _particles(dt) {
    for (const [p, g, drag] of [[this.splash, -9.81, 0.3], [this.spray, -6, 1.2], [this.bubbles, 0.4, 0.5]]) {
      const pos = p.geometry.attributes.position.array, v = p.userData.v, life = p.userData.life;
      for (let i = 0; i < life.length; i++) {
        if (life[i] <= 0) { pos[i * 3 + 1] = -9999; continue; }
        life[i] -= dt;
        v[i * 3 + 1] += g * dt;
        const k = 1 - drag * dt;
        v[i * 3] *= k; v[i * 3 + 2] *= k;
        pos[i * 3] += v[i * 3] * dt; pos[i * 3 + 1] += v[i * 3 + 1] * dt; pos[i * 3 + 2] += v[i * 3 + 2] * dt;
        if (p !== this.bubbles && pos[i * 3 + 1] < 0) life[i] = 0;
        if (p === this.bubbles && pos[i * 3 + 1] > -0.05) life[i] = 0;
      }
      p.geometry.attributes.position.needsUpdate = true;
    }
    if (this.ring.visible) {
      this.ringT += dt;
      this.ring.scale.setScalar(0.3 + this.ringT * 3.2);
      this.ring.material.opacity = Math.max(0, 0.7 - this.ringT * 0.3);
      if (this.ringT > 2.4) this.ring.visible = false;
    }
    if (this.foam.visible) {
      this.foamT += dt;
      this.foam.scale.setScalar(1 + this.foamT * 0.5);
      this.foam.material.opacity = Math.max(0, 0.7 - this.foamT * 0.16);
      if (this.foamT > 4.5) this.foam.visible = false;
    }
  }

  _cameraPath(t) {
    const cam = this.camera;
    if (!cam) return;
    const ud = this.boat.userData, sz = ud.sternZ, dy = ud.deckY;
    const W = (x, y, z) => this._boatPoint(x, y, z);
    const rovP = this.rov ? this.rov.position.clone() : this.start.clone();
    let pos, look;
    const seg = (keys) => {
      let i = 0;
      while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
      const [t0, p0, l0] = keys[i], [t1, p1, l1] = keys[i + 1];
      const k = ease(clamp01((t - t0) / (t1 - t0)));
      return [new THREE.Vector3().lerpVectors(p0, p1, k), new THREE.Vector3().lerpVectors(l0, l1, k)];
    };
    let smooth = 1;
    if (t < T_RELEASE) {
      // establishing shot from off the starboard bow -> low three-quarter on the crew from the sea side
      [pos, look] = seg([
        [0.0, W(13, 5.5, 5), W(0, dy + 0.6, sz + 3)],
        [2.2, W(3.8, dy + 1.3, sz - 2.6), W(0, dy + 0.8, sz + 1.3)],
        [T_RELEASE, W(4.2, dy + 1.0, sz - 3.6), W(0, dy + 0.9, sz + 0.2)],
      ]);
    } else if (!this.splashed || t < this.splashT + 1.0) {
      pos = W(4.2, dy + 1.0, sz - 3.6);
      look = rovP.clone().lerp(W(0, dy + 0.9, sz + 0.2), 0.25);
      smooth = 0.15;
    } else {
      // underwater: circle the sinking ROV with the hull and the cable in view
      const a = 0.9 + (t - this.splashT) * 0.35;
      pos = rovP.clone().add(V(Math.cos(a) * 3.2, 0.9, Math.sin(a) * 3.2));
      look = rovP.clone().add(V(0, -0.2, 0));
      if (pos.y > -0.5) pos.y = -0.5;
      smooth = 0.12;
    }
    if (!this._camPos) { this._camPos = pos.clone(); this._camLook = look.clone(); }
    if (pos.y < 0 && this._camPos.y > 0) { this._camPos.copy(pos); this._camLook.copy(look); }   // cut under water, don't drift through the surface
    this._camPos.lerp(pos, smooth); this._camLook.lerp(look, Math.min(1, smooth * 2));
    cam.position.copy(this._camPos);
    cam.lookAt(this._camLook);
  }

  dispose() {
    for (const o of this.objects) this.scene.remove(o);
    this.cable.dispose();
    if (this.water) { this.water.geometry.dispose(); this.water.material.dispose(); }
  }
}
