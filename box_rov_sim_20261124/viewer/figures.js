// Low-poly articulated figures for cinematics: a deck crew member / pilot and a gamepad.
// Units are metres, three.js Y-up. Every joint is a Group you can rotate.
import * as THREE from 'three';

const M = (color, opts = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0.05, ...opts });

function capsule(r, len, mat) {
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 12), mat);
  m.castShadow = true;
  return m;
}

function limb(parent, r, len, mat, name) {
  // joint at the top; the limb hangs along -Y
  const joint = new THREE.Group();
  joint.name = name;
  const mesh = capsule(r, len, mat);
  mesh.position.y = -len / 2;
  joint.add(mesh);
  parent.add(joint);
  return joint;
}

/**
 * makePerson({ suit, vest, helmet, skin }) -> { root, j } where j holds joints:
 * hips, spine, neck, head, shoulderL/R, elbowL/R, handL/R, hipL/R, kneeL/R.
 * Stands on y = 0 facing +Z.
 */
export function makePerson(opts = {}) {
  const suit = M(opts.suit ?? 0x1f2d44);
  const vest = M(opts.vest ?? 0xff6a13);
  const helmet = M(opts.helmet ?? 0xf2c230, { roughness: 0.4 });
  const skin = M(opts.skin ?? 0xd9a47e);
  const boot = M(0x1b1b1b);
  const root = new THREE.Group();
  const j = {};

  j.hips = new THREE.Group(); j.hips.position.y = 0.95; root.add(j.hips);
  const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.16, 0.2), suit); j.hips.add(pelvis);

  j.spine = new THREE.Group(); j.spine.position.y = 0.06; j.hips.add(j.spine);
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.5, 0.22), suit); torso.position.y = 0.27; j.spine.add(torso);
  const vestMesh = new THREE.Mesh(new THREE.BoxGeometry(0.41, 0.4, 0.25), vest); vestMesh.position.y = 0.3; j.spine.add(vestMesh);
  const strip = new THREE.Mesh(new THREE.BoxGeometry(0.415, 0.04, 0.255), M(0xe8f0f2, { emissive: 0x222222 }));
  strip.position.y = 0.22; j.spine.add(strip);

  j.neck = new THREE.Group(); j.neck.position.y = 0.55; j.spine.add(j.neck);
  j.head = new THREE.Group(); j.head.position.y = 0.1; j.neck.add(j.head);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), skin); head.scale.set(0.9, 1.05, 1); j.head.add(head);
  const hat = new THREE.Mesh(new THREE.SphereGeometry(0.125, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), helmet);
  hat.position.y = 0.03; j.head.add(hat);
  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.015, 20), helmet); brim.position.set(0, 0.03, 0.02); j.head.add(brim);
  const visor = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.04, 0.02), M(0x0d1520, { roughness: 0.2, metalness: 0.4 }));
  visor.position.set(0, 0.0, 0.1); j.head.add(visor);

  for (const s of [-1, 1]) {
    const side = s < 0 ? 'L' : 'R';
    const sh = new THREE.Group(); sh.position.set(0.24 * s, 0.5, 0); j.spine.add(sh); j['shoulder' + side] = sh;
    const upper = limb(sh, 0.055, 0.22, suit, 'upper' + side);
    const el = new THREE.Group(); el.position.y = -0.3; upper.add(el); j['elbow' + side] = el;
    const fore = limb(el, 0.048, 0.2, suit, 'fore' + side);
    const hand = new THREE.Group(); hand.position.y = -0.27; fore.add(hand); j['hand' + side] = hand;
    const glove = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.1, 0.05), M(0x2b2b2b)); glove.position.y = -0.04; hand.add(glove);

    const hp = new THREE.Group(); hp.position.set(0.1 * s, -0.04, 0); j.hips.add(hp); j['hip' + side] = hp;
    const thigh = limb(hp, 0.075, 0.32, suit, 'thigh' + side);
    const kn = new THREE.Group(); kn.position.y = -0.44; thigh.add(kn); j['knee' + side] = kn;
    const shin = limb(kn, 0.065, 0.32, suit, 'shin' + side);
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.08, 0.26), boot); foot.position.set(0, -0.47, 0.05); shin.add(foot);
  }
  root.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  return { root, j };
}

/** Standing / lifting / throwing poses (radians); blend with lerpPose. */
export const POSES = {
  stand: { spineX: 0, hipsY: 0.95, shLX: 0.05, shRX: 0.05, elL: -0.15, elR: -0.15, hipLX: 0, hipRX: 0, knL: 0, knR: 0, headX: 0, shLZ: 0.12, shRZ: -0.12 },
  crouch: { spineX: 0.75, hipsY: 0.62, shLX: -1.15, shRX: -1.15, elL: -0.35, elR: -0.35, hipLX: -1.2, hipRX: -1.2, knL: 1.6, knR: 1.6, headX: -0.35, shLZ: 0.05, shRZ: -0.05 },
  carry: { spineX: 0.15, hipsY: 0.93, shLX: -0.95, shRX: -0.95, elL: -1.1, elR: -1.1, hipLX: -0.1, hipRX: -0.1, knL: 0.15, knR: 0.15, headX: 0.1, shLZ: 0.1, shRZ: -0.1 },
  windup: { spineX: -0.25, hipsY: 0.9, shLX: -2.3, shRX: -2.3, elL: -0.5, elR: -0.5, hipLX: -0.35, hipRX: 0.25, knL: 0.35, knR: 0.1, headX: -0.2, shLZ: 0.15, shRZ: -0.15 },
  release: { spineX: 0.55, hipsY: 0.88, shLX: -1.1, shRX: -1.1, elL: -0.05, elR: -0.05, hipLX: -0.6, hipRX: 0.3, knL: 0.5, knR: 0.05, headX: 0.25, shLZ: 0.05, shRZ: -0.05 },
  seated: { spineX: 0.12, hipsY: 0.52, shLX: -0.55, shRX: -0.55, elL: -1.25, elR: -1.25, hipLX: -1.5, hipRX: -1.5, knL: 1.5, knR: 1.5, headX: 0.18, shLZ: 0.28, shRZ: -0.28 },
};

export function applyPose(j, p) {
  j.hips.position.y = p.hipsY;
  j.spine.rotation.x = p.spineX;
  j.head.rotation.x = p.headX;
  j.shoulderL.rotation.set(p.shLX, 0, p.shLZ); j.shoulderR.rotation.set(p.shRX, 0, p.shRZ);
  j.elbowL.rotation.x = p.elL; j.elbowR.rotation.x = p.elR;
  j.hipL.rotation.x = p.hipLX; j.hipR.rotation.x = p.hipRX;
  j.kneeL.rotation.x = p.knL; j.kneeR.rotation.x = p.knR;
}

export function lerpPose(a, b, t) {
  const k = t * t * (3 - 2 * t);
  const out = {};
  for (const key in a) out[key] = a[key] + (b[key] - a[key]) * k;
  return out;
}

/**
 * makeGamepad() -> { root, set(rc) }. Xbox-style pad ~16 cm wide, facing +Z (towards the viewer),
 * sticks/triggers/bumpers/face buttons animated from RC PWM values (1000..2000).
 */
export function makeGamepad() {
  const root = new THREE.Group();
  const body = M(0x22262b, { roughness: 0.5 });
  const shellShape = new THREE.Shape();
  shellShape.moveTo(-0.075, 0.02); shellShape.quadraticCurveTo(-0.085, 0.045, -0.055, 0.05);
  shellShape.lineTo(0.055, 0.05); shellShape.quadraticCurveTo(0.085, 0.045, 0.075, 0.02);
  shellShape.quadraticCurveTo(0.07, -0.055, 0.045, -0.06); shellShape.quadraticCurveTo(0.03, -0.02, 0, -0.018);
  shellShape.quadraticCurveTo(-0.03, -0.02, -0.045, -0.06); shellShape.quadraticCurveTo(-0.07, -0.055, -0.075, 0.02);
  const shell = new THREE.Mesh(new THREE.ExtrudeGeometry(shellShape, { depth: 0.03, bevelEnabled: true, bevelSize: 0.006, bevelThickness: 0.006, bevelSegments: 2 }), body);
  shell.position.z = -0.015; root.add(shell);

  const mkStick = (x, y) => {
    const g = new THREE.Group(); g.position.set(x, y, 0.022);
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.012, 8), M(0x111111));
    post.rotation.x = Math.PI / 2; post.position.z = 0.006; g.add(post);
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.012, 0.006, 20), M(0x3a3f45, { roughness: 0.9 }));
    cap.rotation.x = Math.PI / 2; cap.position.z = 0.014; g.add(cap);
    root.add(g);
    return g;
  };
  const stickL = mkStick(-0.038, 0.018);
  const stickR = mkStick(0.022, -0.012);

  const btn = (x, y, color) => {
    const b = new THREE.Mesh(new THREE.CylinderGeometry(0.0055, 0.0055, 0.006, 16), M(color, { emissive: color, emissiveIntensity: 0.05 }));
    b.rotation.x = Math.PI / 2; b.position.set(x, y, 0.02); root.add(b);
    return b;
  };
  const face = { Y: btn(0.045, 0.034, 0xf2c230), X: btn(0.034, 0.023, 0x2e7bf6), B: btn(0.056, 0.023, 0xe0412f), A: btn(0.045, 0.012, 0x3cc24a) };
  const dpad = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.006, 0.004), M(0x111111)); dpad.position.set(-0.022, -0.012, 0.02); root.add(dpad);
  const dpad2 = dpad.clone(); dpad2.rotation.z = Math.PI / 2; root.add(dpad2);

  const trig = (s) => {
    const g = new THREE.Group(); g.position.set(0.055 * s, 0.05, -0.008);
    const t = new THREE.Mesh(new THREE.BoxGeometry(0.026, 0.012, 0.02), M(0x33373c)); t.position.set(0, 0.006, -0.004); g.add(t);
    root.add(g); return g;
  };
  const bump = (s) => {
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.032, 0.006, 0.012), M(0x2a2e33)); b.position.set(0.05 * s, 0.052, 0.008); root.add(b); return b;
  };
  const LT = trig(-1), RT = trig(1), LB = bump(-1), RB = bump(1);
  const glow = new THREE.PointLight(0x7fd8ff, 0, 0.3); glow.position.set(0, 0.02, 0.05); root.add(glow);

  const u = (v) => Math.max(-1, Math.min(1, ((v ?? 1500) - 1500) / 500));
  const TILT = 0.45;
  function set(rc = {}) {
    // stick up = PWM > 1500 = pushed away from the thumb (tilt top edge away: rotate about X)
    stickL.rotation.set(-u(rc.left_ud) * TILT, u(rc.left_lr) * TILT, 0);
    stickR.rotation.set(-u(rc.right_ud) * TILT, u(rc.right_lr) * TILT, 0);
    const lw = u(rc.left_wave), rw = u(rc.right_wave);
    RT.rotation.x = Math.max(0, lw) * 0.5; LT.rotation.x = Math.max(0, -lw) * 0.5;
    RB.position.y = 0.052 - Math.max(0, rw) * 0.003; LB.position.y = 0.052 - Math.max(0, -rw) * 0.003;
    const press = (m, on) => { m.position.z = on ? 0.017 : 0.02; m.material.emissiveIntensity = on ? 1.4 : 0.05; };
    press(face.A, rc.photo); press(face.B, rc.record);
    press(face.Y, rc._flashY); press(face.X, rc._flashX);
    glow.intensity = (Math.abs(u(rc.left_ud)) + Math.abs(u(rc.right_ud)) + Math.abs(lw)) > 0.1 ? 0.25 : 0;
  }
  return { root, set, sticks: { L: stickL, R: stickR } };
}
