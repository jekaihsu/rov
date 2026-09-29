// Deployment intro: work boat with A-frame and tether reel; a deck hand lifts the ROV and
// tosses it over the stern; splash; the ROV sinks to its start position while the tether pays out.
//
// Usage:
//   const intro = new DeployIntro(scene, { spool: [n,e,d], start: [n,e,d], seabed: 30 });
//   intro.play(rovObject3D, camera, () => { /* hand control back */ });
//   each frame: intro.update(dt)          // returns true while playing
//   intro.skip()                          // jump to the end
// World mapping (same as the viewer): three = (-east, -down, north).
import * as THREE from 'three';
import { makePerson, POSES, applyPose, lerpPose } from './figures.js';

const toThree = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const ease = (t) => t * t * (3 - 2 * t);
const clamp01 = (t) => Math.max(0, Math.min(1, t));
const M = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.1, ...o });

function buildBoat() {
  const boat = new THREE.Group();
  const L = 14, B = 4.6;
  // hull: plan-view shape with a pointed bow (+Z), extruded downwards
  const s = new THREE.Shape();
  s.moveTo(-B / 2, -L / 2); s.lineTo(B / 2, -L / 2); s.lineTo(B / 2, L / 2 - 3.5);
  s.quadraticCurveTo(B / 2, L / 2 - 0.5, 0, L / 2); s.quadraticCurveTo(-B / 2, L / 2 - 0.5, -B / 2, L / 2 - 3.5); s.closePath();
  const hullGeo = new THREE.ExtrudeGeometry(s, { depth: 2.2, bevelEnabled: false });
  hullGeo.rotateX(Math.PI / 2);            // extrude along -Y
  const hull = new THREE.Mesh(hullGeo, M(0x1d3557));
  hull.position.y = 1.2; boat.add(hull);
  const stripeGeo = new THREE.ExtrudeGeometry(s, { depth: 0.25, bevelEnabled: false }); stripeGeo.rotateX(Math.PI / 2);
  const stripe = new THREE.Mesh(stripeGeo, M(0xc1121f)); stripe.scale.set(1.01, 1, 1.005); stripe.position.y = 0.05; boat.add(stripe);
  const deckGeo = new THREE.ShapeGeometry(s); deckGeo.rotateX(-Math.PI / 2);
  const deck = new THREE.Mesh(deckGeo, M(0x8d99a6, { roughness: 0.95 })); deck.position.y = 1.21; boat.add(deck);
  // bulwark rails
  const railMat = M(0xe9eef2);
  for (const x of [-B / 2 + 0.05, B / 2 - 0.05]) {
    const r = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.7, L - 4), railMat); r.position.set(x, 1.55, 0.3); boat.add(r);
  }
  // wheelhouse (forward)
  const wh = new THREE.Mesh(new THREE.BoxGeometry(3.4, 2.2, 3.6), M(0xf1f3f5)); wh.position.set(0, 2.3, 2.6); boat.add(wh);
  const win = new THREE.Mesh(new THREE.BoxGeometry(3.42, 0.6, 3.0), M(0x10202e, { metalness: 0.6, roughness: 0.15 }));
  win.position.set(0, 2.9, 2.6); boat.add(win);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.2), railMat); mast.position.set(0, 4.5, 3.2); boat.add(mast);
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.12), M(0xffe9a8, { emissive: 0xffd36b, emissiveIntensity: 1.2 }));
  lamp.position.set(0, 5.6, 3.2); boat.add(lamp);
  // A-frame at the stern (-Z) with a sheave block
  const aMat = M(0xf2b705, { metalness: 0.3 });
  for (const x of [-1.4, 1.4]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 3.4), aMat);
    leg.position.set(x, 2.8, -L / 2 + 0.2); leg.rotation.x = -0.28; boat.add(leg);
  }
  const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 2.9), aMat);
  bar.rotation.z = Math.PI / 2; bar.position.set(0, 4.42, -L / 2 - 0.25); boat.add(bar);
  const sheave = new THREE.Mesh(new THREE.TorusGeometry(0.22, 0.06, 8, 20), M(0x333333));
  sheave.position.set(0, 4.15, -L / 2 - 0.3); boat.add(sheave);
  // tether reel mid-deck
  const reel = new THREE.Group(); reel.position.set(0, 1.95, -1.2); boat.add(reel);
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 1.2, 28), M(0xe0822c));
  drum.rotation.z = Math.PI / 2; reel.add(drum);
  for (const x of [-0.65, 0.65]) {
    const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.75, 0.06, 28), M(0x3d4852));
    flange.rotation.z = Math.PI / 2; flange.position.x = x; reel.add(flange);
  }
  const frame = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.5, 1.0), M(0x3d4852)); frame.position.y = -0.55; reel.add(frame);
  boat.userData = { L, B, deckY: 1.21, reel, drum, sheaveLocal: sheave.position.clone(), sternZ: -L / 2 };
  boat.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return boat;
}

function makeParticles(n, color, size) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  const m = new THREE.PointsMaterial({ color, size, transparent: true, opacity: 0.9, depthWrite: false });
  const p = new THREE.Points(g, m);
  p.frustumCulled = false;
  p.userData.v = new Float32Array(n * 3);
  p.userData.life = new Float32Array(n);
  return p;
}

export class DeployIntro {
  constructor(scene, { spool, start, seabed = 30 }) {
    this.scene = scene;
    this.spool = toThree(spool);
    this.start = toThree(start);
    this.seabed = seabed;
    this.duration = 10.5;
    this.t = 0;
    this.playing = false;

    // boat: stern (-Z local) faces the ROV start point
    this.boat = buildBoat();
    const dir = new THREE.Vector3().subVectors(this.start, this.spool); dir.y = 0;
    if (dir.lengthSq() < 1e-6) dir.set(0, 0, -1);
    dir.normalize();
    this.boat.rotation.y = Math.atan2(-dir.x, -dir.z);
    const ud = this.boat.userData;
    this.boat.position.copy(this.spool).add(dir.clone().multiplyScalar(-(ud.L / 2 - 0.6)));   // stern at the spool, hull away from the dive site
    this.boat.position.y = 0;
    scene.add(this.boat);
    this.boat.updateMatrixWorld(true);
    this.sheaveWorld = this.boat.localToWorld(ud.sheaveLocal.clone());
    this.reelWorld = this.boat.localToWorld(new THREE.Vector3(0, 2.55, -1.2));

    // deck hand near the stern, facing aft
    this.person = makePerson();
    this.person.root.position.set(1.45, ud.deckY, ud.sternZ + 1.6);
    this.person.root.rotation.y = Math.PI;       // face -Z (aft)
    this.boat.add(this.person.root);
    applyPose(this.person.j, POSES.stand);

    // tether from reel over the sheave to the ROV
    this.tetherGeo = new THREE.BufferGeometry();
    this.tetherGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(40 * 3), 3));
    this.tether = new THREE.Line(this.tetherGeo, new THREE.LineBasicMaterial({ color: 0xffb020 }));
    this.tether.frustumCulled = false;
    this.tether.visible = false;
    scene.add(this.tether);

    this.splash = makeParticles(500, 0xeaf6ff, 0.12);
    this.bubbles = makeParticles(220, 0xbfe8ff, 0.06);
    scene.add(this.splash, this.bubbles);
    this.ring = new THREE.Mesh(new THREE.RingGeometry(0.8, 1.1, 48),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }));
    this.ring.rotation.x = -Math.PI / 2; this.ring.visible = false; scene.add(this.ring);
    this.foam = new THREE.Mesh(new THREE.CircleGeometry(1.6, 40),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false }));
    this.foam.rotation.x = -Math.PI / 2; this.foam.visible = false; scene.add(this.foam);
  }

  /** Stage positions in world space for the ROV at each beat. */
  _deckPoint(localX, localY, localZ) {
    return this.boat.localToWorld(new THREE.Vector3(localX, localY, localZ));
  }

  play(rov, camera, onDone) {
    this.rov = rov;
    this.camera = camera;
    this.onDone = onDone;
    this.t = 0;
    this.playing = true;
    this.splashed = false;
    this.tether.visible = true;
    const ud = this.boat.userData;
    // ROV beats in boat-local space (deck hand stands at x = 1.45 on the stern quarter, facing aft)
    this.pDeck = this._deckPoint(1.45, ud.deckY + 0.22, ud.sternZ + 0.85);
    this.pChest = this._deckPoint(1.45, ud.deckY + 1.1, ud.sternZ + 1.2);
    this.pWind = this._deckPoint(1.45, ud.deckY + 2.0, ud.sternZ + 1.72);
    this.pRelease = this._deckPoint(1.6, ud.deckY + 1.5, ud.sternZ + 0.55);
    const out = this._deckPoint(0.45, 0, -1).sub(this._deckPoint(0, 0, 0)).normalize();   // aft and a little outboard
    this.vRelease = out.multiplyScalar(4.6).add(new THREE.Vector3(0, 1.1, 0));
    this.qStart = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, this.boat.rotation.y + Math.PI, 0));
  }

  skip() {
    if (!this.playing) return;
    this.t = this.duration;
    this.update(0);
  }

  update(dt) {
    if (!this.playing) { this._particles(dt); return false; }
    this.t += dt;
    const t = this.t;
    const j = this.person.j;
    const rov = this.rov;
    const tRelease = 5.3;

    // ── deck hand choreography ──
    let pose;
    if (t < 2.0) pose = POSES.stand;
    else if (t < 2.8) pose = lerpPose(POSES.stand, POSES.crouch, (t - 2.0) / 0.8);
    else if (t < 3.8) pose = lerpPose(POSES.crouch, POSES.carry, (t - 2.8) / 1.0);
    else if (t < 4.7) pose = lerpPose(POSES.carry, POSES.windup, (t - 3.8) / 0.9);
    else if (t < tRelease) pose = lerpPose(POSES.windup, POSES.release, (t - 4.7) / (tRelease - 4.7));
    else if (t < 7) pose = lerpPose(POSES.release, POSES.stand, clamp01((t - tRelease - 0.4) / 1.3));
    else pose = POSES.stand;
    applyPose(j, pose);

    // ── ROV path ──
    if (rov) {
      if (t < 2.8) {
        rov.position.copy(this.pDeck);
        rov.quaternion.copy(this.qStart);
      } else if (t < 3.8) {
        rov.position.lerpVectors(this.pDeck, this.pChest, ease((t - 2.8) / 1.0));
      } else if (t < 4.7) {
        rov.position.lerpVectors(this.pChest, this.pWind, ease((t - 3.8) / 0.9));
      } else if (t < tRelease) {
        rov.position.lerpVectors(this.pWind, this.pRelease, ease((t - 4.7) / (tRelease - 4.7)));
      } else {
        this._flight(dt);
      }
    }

    // ── tether: reel -> sheave -> ROV gland ──
    this._drawTether(t);
    this.boat.userData.drum.rotation.x += dt * (t > tRelease ? 4 : 0);
    this._particles(dt);
    this._cameraPath(t);

    if (t >= this.duration) {
      this.playing = false;
      if (rov) { rov.position.copy(this.start); }
      this.onDone && this.onDone();
    }
    return this.playing;
  }

  _flight(dt) {
    const rov = this.rov;
    if (!this.splashed) {
      if (!this.vel) { this.vel = this.vRelease.clone(); this.spin = 0; }
      this.vel.y -= 9.81 * dt;
      rov.position.addScaledVector(this.vel, dt);
      this.spin += dt * 1.6;
      rov.quaternion.copy(this.qStart).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(this.spin * 0.6, 0, this.spin * 0.25)));
      if (rov.position.y <= 0.1) {
        this.splashed = true;
        this.splashT = this.t;
        this.entry = rov.position.clone();
        this.entryQ = rov.quaternion.clone();
        this._emitSplash(rov.position);
      }
      return;
    }
    // underwater: decelerate, right itself, glide to the start position/depth
    const k = ease(clamp01((this.t - this.splashT) / (this.duration - this.splashT - 0.2)));
    const bob = Math.sin((this.t - this.splashT) * 5) * 0.12 * (1 - k);
    rov.position.lerpVectors(this.entry, this.start, k).y += bob;
    rov.quaternion.slerpQuaternions(this.entryQ, this.qStart, Math.min(1, k * 1.6));
    if (Math.random() < 0.9) this._emitBubble(rov.position);
  }

  _drawTether(t) {
    const pos = this.tetherGeo.attributes.position.array;
    const reel = this.reelWorld, sheave = this.sheaveWorld;
    const end = this.rov ? this.rov.position : this.start;
    const pts = [];
    const nA = 8;
    for (let i = 0; i < nA; i++) pts.push(new THREE.Vector3().lerpVectors(reel, sheave, i / (nA - 1)));
    const n = 40 - nA;
    const slack = t < 5.3 ? 0.5 : 1.8;
    for (let i = 1; i <= n; i++) {
      const u = i / n;
      const p = new THREE.Vector3().lerpVectors(sheave, end, u);
      p.y -= Math.sin(Math.PI * u) * slack;                   // catenary-ish sag
      pts.push(p);
    }
    pts.slice(0, 40).forEach((p, i) => { pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = p.z; });
    this.tetherGeo.attributes.position.needsUpdate = true;
  }

  _emitSplash(at) {
    const p = this.splash, pos = p.geometry.attributes.position.array, v = p.userData.v, life = p.userData.life;
    for (let i = 0; i < life.length; i++) {
      const a = Math.random() * Math.PI * 2, r = Math.random() * 0.6, up = 2 + Math.random() * 4.5;
      pos[i * 3] = at.x + Math.cos(a) * r; pos[i * 3 + 1] = 0.05; pos[i * 3 + 2] = at.z + Math.sin(a) * r;
      v[i * 3] = Math.cos(a) * (1 + Math.random() * 2.5); v[i * 3 + 1] = up; v[i * 3 + 2] = Math.sin(a) * (1 + Math.random() * 2.5);
      life[i] = 1.2 + Math.random() * 0.8;
    }
    this.ring.position.set(at.x, 0.03, at.z); this.ring.visible = true; this.ring.scale.setScalar(0.3); this.ringT = 0;
    this.foam.position.set(at.x, 0.02, at.z); this.foam.visible = true; this.foamT = 0;
  }

  _emitBubble(at) {
    const p = this.bubbles, pos = p.geometry.attributes.position.array, v = p.userData.v, life = p.userData.life;
    const i = (this._bi = ((this._bi || 0) + 1) % life.length);
    pos[i * 3] = at.x + (Math.random() - 0.5) * 0.5; pos[i * 3 + 1] = at.y + (Math.random() - 0.5) * 0.3; pos[i * 3 + 2] = at.z + (Math.random() - 0.5) * 0.5;
    v[i * 3] = (Math.random() - 0.5) * 0.2; v[i * 3 + 1] = 0.6 + Math.random() * 0.8; v[i * 3 + 2] = (Math.random() - 0.5) * 0.2;
    life[i] = 2.5;
  }

  _particles(dt) {
    for (const [p, g, drag] of [[this.splash, -9.81, 0.2], [this.bubbles, 0.4, 0.5]]) {
      const pos = p.geometry.attributes.position.array, v = p.userData.v, life = p.userData.life;
      for (let i = 0; i < life.length; i++) {
        if (life[i] <= 0) { pos[i * 3 + 1] = -9999; continue; }
        life[i] -= dt;
        v[i * 3 + 1] += g * dt;
        const k = 1 - drag * dt;
        v[i * 3] *= k; v[i * 3 + 2] *= k;
        pos[i * 3] += v[i * 3] * dt; pos[i * 3 + 1] += v[i * 3 + 1] * dt; pos[i * 3 + 2] += v[i * 3 + 2] * dt;
        if (p === this.splash && pos[i * 3 + 1] < 0) life[i] = 0;
        if (p === this.bubbles && pos[i * 3 + 1] > -0.05) life[i] = 0;
      }
      p.geometry.attributes.position.needsUpdate = true;
    }
    if (this.ring.visible) {
      this.ringT += dt;
      this.ring.scale.setScalar(0.3 + this.ringT * 4.5);
      this.ring.material.opacity = Math.max(0, 0.8 - this.ringT * 0.35);
      if (this.ringT > 2.4) this.ring.visible = false;
    }
    if (this.foam.visible) {
      this.foamT += dt;
      this.foam.scale.setScalar(1 + this.foamT * 0.6);
      this.foam.material.opacity = Math.max(0, 0.65 - this.foamT * 0.18);
      if (this.foamT > 3.6) this.foam.visible = false;
    }
  }

  _cameraPath(t) {
    const cam = this.camera;
    if (!cam) return;
    const b = this.boat;
    const W = (x, y, z) => b.localToWorld(new THREE.Vector3(x, y, z));
    const rovP = this.rov ? this.rov.position.clone() : this.start.clone();
    let pos, look;
    const seg = (keys) => {
      let i = 0;
      while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
      const [t0, p0, l0] = keys[i], [t1, p1, l1] = keys[i + 1];
      const k = ease(clamp01((t - t0) / (t1 - t0)));
      return [new THREE.Vector3().lerpVectors(p0, p1, k), new THREE.Vector3().lerpVectors(l0, l1, k)];
    };
    if (t < 5.3) {
      // establishing shot -> over the deck hand's shoulder
      [pos, look] = seg([
        [0.0, W(16, 10, 10), W(0, 1.5, -2)],
        [2.0, W(5.5, 3.4, -0.5), W(1.4, 1.8, -6.2)],
        [5.3, W(5.2, 3.0, -2.6), W(1.6, 2.6, -7.4)],
      ]);
    } else if (!this.splashed || t < this.splashT + 0.8) {
      // follow the flight from the boat's quarter, then hold on the splash at water level
      pos = W(6.5, 1.6, -5.5);
      look = rovP.clone();
    } else {
      // underwater: circle the sinking ROV, seabed and surface in frame
      const a = 0.9 + (t - this.splashT) * 0.35;
      pos = rovP.clone().add(new THREE.Vector3(Math.cos(a) * 3.2, 0.9, Math.sin(a) * 3.2));
      look = rovP.clone().add(new THREE.Vector3(0, -0.3, 0));
      if (pos.y > -0.4) pos.y = -0.4;
    }
    // smooth hand-off between shots
    if (!this._camPos) { this._camPos = pos.clone(); this._camLook = look.clone(); }
    const s = t < 5.3 ? 1 : 0.12;
    this._camPos.lerp(pos, s); this._camLook.lerp(look, t < 5.3 ? 1 : 0.25);
    cam.position.copy(this._camPos);
    cam.lookAt(this._camLook);
  }

  dispose() {
    for (const o of [this.boat, this.tether, this.splash, this.bubbles, this.ring, this.foam]) this.scene.remove(o);
  }
}
