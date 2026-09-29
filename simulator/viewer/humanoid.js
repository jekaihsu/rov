// Rigged human (Quaternius "Animated Men", CC0) with a base animation clip plus procedural
// layers on top: pelvis offset, spine bend/twist, head turn and two-bone IK for arms and legs.
// Targets are given in the figure's local space in metres; the figure stands at the origin
// facing +Z. The rig's bone axes are never assumed: IK aims bones by world-space directions.
//
//   const lib = await Humanoid.load('models/worker.glb');
//   const h = new Humanoid(lib, { shirt: 0xf26b1d, helmet: 0xffffff });
//   scene.add(h.root); h.play('Idle');
//   each frame: h.update(dt, { pelvis:[0,-.3,0], bend:.6, handL:v3, handR:v3, head:[yaw,pitch] })
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

const MODEL_HEIGHT = 4.84;          // rest height of the source rig (model units)
const _v1 = new THREE.Vector3(), _v2 = new THREE.Vector3(), _v3 = new THREE.Vector3(), _v4 = new THREE.Vector3();
const _q1 = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _q3 = new THREE.Quaternion();

function worldPos(o, out = new THREE.Vector3()) { return o.getWorldPosition(out); }

function setWorldQuat(bone, qWorld) {
  bone.parent.getWorldQuaternion(_q3).invert();
  bone.quaternion.copy(_q3.multiply(qWorld));
  bone.updateMatrixWorld(true);
}

/** Rotate ``bone`` so the direction bone->child points from bone towards ``target`` (world). */
function aim(bone, child, target, weight = 1) {
  const p = worldPos(bone, _v1);
  const cur = worldPos(child, _v2).sub(p).normalize();
  const want = _v3.copy(target).sub(p).normalize();
  if (cur.lengthSq() < 1e-8 || want.lengthSq() < 1e-8) return;
  _q1.setFromUnitVectors(cur, want);
  if (weight < 1) _q1.slerp(_q2.identity(), 1 - weight);
  bone.getWorldQuaternion(_q2);
  setWorldQuat(bone, _q1.multiply(_q2));
}

/** Analytic two-bone IK: upper->lower->end reaches ``target``; the middle joint bends towards ``pole``. */
function twoBone(upper, lower, end, target, pole) {
  const S = worldPos(upper, new THREE.Vector3());
  const a = S.distanceTo(worldPos(lower, _v4));
  const b = _v4.distanceTo(worldPos(end, _v1));
  const toT = new THREE.Vector3().subVectors(target, S);
  const d = THREE.MathUtils.clamp(toT.length(), Math.abs(a - b) + 1e-3, a + b - 1e-4);
  const n = toT.normalize();
  const x = (a * a - b * b + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(a * a - x * x, 0));
  const p = new THREE.Vector3().subVectors(pole, S);
  p.addScaledVector(n, -p.dot(n));
  if (p.lengthSq() < 1e-8) p.set(0, -1, 0); else p.normalize();
  const elbow = S.clone().addScaledVector(n, x).addScaledVector(p, h);
  aim(upper, lower, elbow);
  const reach = S.clone().addScaledVector(n, d);
  aim(lower, end, reach);
}

export class Humanoid {
  static async load(url) {
    const g = await new GLTFLoader().loadAsync(url);
    return { scene: g.scene, animations: g.animations };
  }

  constructor(lib, { height = 1.75, shirt = null, pants = null, skin = null, helmet = null, vest = null } = {}) {
    this.root = new THREE.Group();
    this.model = SkeletonUtils.clone(lib.scene);
    this.model.scale.setScalar(height / MODEL_HEIGHT);
    this.root.add(this.model);
    const tint = { Shirt: shirt, Pants: pants, Skin: skin };
    this.model.traverse((o) => {
      if (!o.isMesh) return;
      o.castShadow = true; o.frustumCulled = false;
      o.material = o.material.clone();
      o.material.roughness = 0.85; o.material.metalness = 0;
      if (tint[o.material.name] != null) o.material.color.setHex(tint[o.material.name]);
    });
    const b = (this.b = {});
    this.model.traverse((o) => { if (o.isBone) b[o.name] = o; });
    this.mixer = new THREE.AnimationMixer(this.model);
    this.clips = {};
    for (const c of lib.animations) this.clips[c.name.replace(/^.*Man_/, '')] = c;
    this.action = null;
    this.rest = Object.values(b).map((o) => [o, o.position.clone(), o.quaternion.clone(), o.scale.clone()]);
    this.unit = height / MODEL_HEIGHT;          // metres per model unit

    if (helmet != null) {                       // hard hat on the head bone
      const hat = new THREE.Group();
      const shell = new THREE.Mesh(new THREE.SphereGeometry(0.135, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
        new THREE.MeshStandardMaterial({ color: helmet, roughness: 0.35 }));
      const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.012, 24),
        new THREE.MeshStandardMaterial({ color: helmet, roughness: 0.35 }));
      brim.position.set(0, 0.005, 0.03); brim.scale.set(1, 1, 1.12);
      hat.add(shell, brim);
      hat.scale.setScalar(1 / this.unit);
      hat.position.set(0, 0.16 / this.unit, -0.01 / this.unit);
      b.Head.add(hat);
      this.hat = hat;
    }
    if (vest != null) {                         // hi-vis life vest over the torso
      const m = new THREE.MeshStandardMaterial({ color: vest, roughness: 0.6 });
      const v = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.17, 0.46, 18, 1, true), m);
      m.side = THREE.DoubleSide;
      v.scale.set(1 / this.unit, 1 / this.unit, 0.75 / this.unit);
      v.position.set(0, 0.14 / this.unit, 0.01 / this.unit);
      const band = new THREE.Mesh(new THREE.CylinderGeometry(0.195, 0.195, 0.035, 18, 1, true),
        new THREE.MeshStandardMaterial({ color: 0xdfe6ea, roughness: 0.2, metalness: 0.5, side: THREE.DoubleSide }));
      band.position.y = 0.06; v.add(band);
      const band2 = band.clone(); band2.position.y = -0.1; v.add(band2);
      b.Torso.add(v);
      this.vest = v;
    }
  }

  play(name, { fade = 0.3, timeScale = 1, at = null } = {}) {
    const clip = this.clips[name];
    if (!clip) return;
    const next = this.mixer.clipAction(clip);
    if (this.action === next) return;
    next.reset(); next.timeScale = timeScale; next.play();
    if (at != null) next.time = at;
    if (this.action) this.action.crossFadeTo(next, fade, false);
    this.action = next;
  }

  /** Hold a clip at a fixed time (e.g. the seated frame of "Sitting"). */
  hold(name, t) {
    this.play(name, { fade: 0 });
    this.action.paused = true; this.action.time = t;
  }

  _local(v) { return this.root.localToWorld(_v4.set(v[0] ?? v.x, v[1] ?? v.y, v[2] ?? v.z).clone()); }

  update(dt, pose = {}) {
    const b = this.b;
    for (const [o, p, q, sc] of this.rest) { o.position.copy(p); o.quaternion.copy(q); o.scale.copy(sc); }
    this.mixer.update(dt);
    this.root.updateMatrixWorld(true);
    // feet keep their animated placement; remember them before moving the pelvis
    const footL = worldPos(b.FootL, new THREE.Vector3()), footR = worldPos(b.FootR, new THREE.Vector3());
    if (pose.feet) {                            // explicit foot targets (local)
      footL.copy(this._local(pose.feet[0])); footR.copy(this._local(pose.feet[1]));
    }
    if (pose.pelvis) {
      const o = pose.pelvis;
      b.Body.position.x += o[0] / this.unit; b.Body.position.y += o[1] / this.unit; b.Body.position.z += o[2] / this.unit;
      b.Body.updateMatrixWorld(true);
    }
    const right = _v1.set(1, 0, 0).transformDirection(this.root.matrixWorld).clone();
    const up = new THREE.Vector3(0, 1, 0).transformDirection(this.root.matrixWorld);
    if (pose.bend || pose.twist || pose.lean) {
      for (const [bone, share] of [[b.Abdomen, 0.45], [b.Torso, 0.55]]) {
        bone.getWorldQuaternion(_q2);
        _q1.setFromAxisAngle(right, (pose.bend || 0) * share);
        const qt = new THREE.Quaternion().setFromAxisAngle(up, (pose.twist || 0) * share);
        const fwd = new THREE.Vector3(0, 0, 1).transformDirection(this.root.matrixWorld);
        const ql = new THREE.Quaternion().setFromAxisAngle(fwd, (pose.lean || 0) * share);
        setWorldQuat(bone, ql.multiply(qt).multiply(_q1).multiply(_q2));
      }
    }
    // legs: ankles back onto the feet, knees forward
    for (const s of ['L', 'R']) {
      const foot = s === 'L' ? footL : footR;
      const hip = worldPos(b['UpperLeg' + s], new THREE.Vector3());
      const fwd = new THREE.Vector3(0, 0, 1).transformDirection(this.root.matrixWorld);
      const side = right.clone().multiplyScalar(s === 'L' ? 0.12 : -0.12);
      const pole = hip.clone().lerp(foot, 0.5).addScaledVector(fwd, 1.0).add(side);
      const ankle = b['LowerLeg' + s].children.find((c) => c.isBone) || b['LowerLeg' + s];
      twoBone(b['UpperLeg' + s], b['LowerLeg' + s], ankle, foot.clone().add(up.clone().multiplyScalar(0.02)), pole);
      b['Foot' + s].position.copy(b['Foot' + s].parent.worldToLocal(foot.clone()));
      b['Foot' + s].updateMatrixWorld(true);
    }
    // arms
    for (const s of ['L', 'R']) {
      const tgt = pose['hand' + s];
      if (!tgt) continue;
      const T = this._local(tgt);
      const sh = worldPos(b['UpperArm' + s], new THREE.Vector3());
      const out = right.clone().multiplyScalar(s === 'L' ? 1 : -1);
      const back = new THREE.Vector3(0, 0, -1).transformDirection(this.root.matrixWorld);
      const pole = pose['elbow' + s] ? this._local(pose['elbow' + s])
        : sh.clone().lerp(T, 0.5).addScaledVector(out, 0.35).addScaledVector(back, 0.25).addScaledVector(up, -0.35);
      twoBone(b['UpperArm' + s], b['LowerArm' + s], b['Palm' + s], T, pole);
    }
    if (pose.head) {
      const [yaw, pitch] = pose.head;
      b.Head.getWorldQuaternion(_q2);
      _q1.setFromAxisAngle(up, yaw).multiply(new THREE.Quaternion().setFromAxisAngle(right, pitch));
      setWorldQuat(b.Head, _q1.multiply(_q2));
    }
  }

  /** World position of a hand (palm bone). */
  hand(side, out = new THREE.Vector3()) { return worldPos(this.b['Palm' + side], out); }
}
