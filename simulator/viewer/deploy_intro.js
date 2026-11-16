// Deployment intro: a short cinematic of a realistic launch from the support work boat's stern.
//
// Sequence (docs/reference/real-rov-research.md, research_notes/臍帶纜物理與收放文獻/shipboard_handling.md):
// the vehicle sits on the aft deck on its lifting bridle; the deck hand works the A-frame from a pendant while
// the tether tender steadies the vehicle by its frame; the vehicle is hoisted clear of the bulwark, the A-frame
// luffs outboard and the vehicle is lowered on the lifting wire (never thrown, never lifted by the tether) and
// set into the water; the hook is released; tether is paid out from the winch (the drum turns) through the
// tender's hands; a short surface function check follows (lamps blink, thrusters twitch, only once the vehicle
// is in the water: thrusters are not run in air); then the vehicle descends to its start position.
// Assumptions (no public X1 launch procedure exists): A-frame launch of a ~30 kg vehicle, quick-release hook
// worked from the pendant, a two-person deck crew.
//
// Models (see models/CREDITS.md): ROV support work boat (original, cad/build_support_vessel.py), deck crew
// (Quaternius "Animated Men", CC0, dressed by cad/build_deck_crew.py). Sea, sky and sunlight come from the
// viewer's shared daylight model (fx/daylight.js), the same as every other view above the water.
//
//   const assets = await DeployIntro.loadAssets('models/');
//   const intro = new DeployIntro(scene, { spool: [n,e,d], start: [n,e,d], seabed: 30, assets });
//   intro.play(rovObject3D, camera, () => { /* hand control back */ });
//   each frame: intro.update(dt)            // returns true while playing
//   intro.skip()                            // jump to the end
// World mapping (same as the viewer): three = (-east, -down, north).
import * as THREE from 'three';
import { loadGLTF } from './glb.js';
import { Humanoid } from './humanoid.js';
import { Cable } from './cable.js';
import { LaunchRig } from './launch_rig.js';
import { IntroEffects } from './intro_effects.js';
import { assetTextureTier } from './render_quality.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);

// Timeline (seconds). Total length stays in the 8–12 s range of the previous intro.
const T = {
  grab: 0.5,            // tender's hands on the frame
  hoist0: 1.2,
  hoist1: 2.3,          // vehicle clear of the bulwark
  luff0: 2.4,
  guideEnd: 3.2,        // vehicle over the transom: tender lets go of the frame, keeps a hand on the tether
  luff1: 4.2,           // A-frame fully outboard
  wet: 6.4,             // vehicle afloat
  release: 6.9,         // hook released
  twitch0: 8.1,
  hookHome: 8.1,
  stow0: 8.3,
  twitch1: 8.7,
  dive: 8.8,
  stow1: 10.6,
  end: 11.8,
};
const THETA_IN = 0.5;           // A-frame apex inboard: hook over the vehicle's deck spot
const THETA_OUT = -0.45;        // apex about 1.3 m aft of the transom
const BRIDLE = 0.42;            // master link height above the vehicle top while lifting (m)
const LIFT_CLEAR = 0.3;         // vehicle underside above the bulwark cap while luffing (m)
const FLOAT_DRAFT = 0.55;       // fraction of the half height below the surface when afloat
const LIGHT_BLINKS = [[7.15, 7.45], [7.65, 7.95]];
const TWITCH_PULSES = [8.15, 8.35, 8.55];
const DRUM_RADIUS = 0.27;

const toThree = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);

function ease(t) {
  return t * t * (3 - 2 * t);
}

function clamp01(t) {
  return Math.max(0, Math.min(1, t));
}

function phase(t, a, b) {
  return ease(clamp01((t - a) / (b - a)));
}

function material(color, options = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.1, ...options });
}

// Support vessel GLB (cad/build_support_vessel.py): metres, stern towards -Z, waterline at y = 0. The root node's
// extras give the deck and transom heights; "TetherDrum" spins about its local X, "TetherExit" is the drum top.
function findVesselInfo(src) {
  let info = null;
  src.traverse(function visit(o) {
    if (!info && o.userData && typeof o.userData.deckY === 'number') info = o.userData;
  });
  return info;
}

/** Group the "LOD0/1/2" children into a THREE.LOD and hide the collision proxy. */
function setUpDetailLevels(model) {
  const levels = [];
  model.traverse(function collect(o) {
    if (/^LOD\d$/.test(o.name)) levels.push(o);
  });
  const proxy = model.getObjectByName('CollisionProxy') || null;
  if (proxy) proxy.visible = false;
  if (levels.length < 2) return { lod: null, proxy };
  const lod = new THREE.LOD();
  lod.name = 'VesselLOD';
  const parent = levels[0].parent;
  levels.sort(function byIndex(a, b) {
    return a.name.localeCompare(b.name);
  });
  for (const level of levels) {
    lod.addLevel(level, level.userData.lodDistance ?? 0);
  }
  parent.add(lod);
  return { lod, proxy };
}

function placeVesselModel(src) {
  const info = findVesselInfo(src);
  if (!info) return null;
  const boat = new THREE.Group();
  const model = src.clone(true);
  model.traverse(function enableShadows(o) {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
  });
  const detail = setUpDetailLevels(model);
  boat.add(model);
  boat.userData = {
    L: info.length,
    deckY: info.deckY,
    sternZ: info.sternZ,
    transomY: info.transomY,
    drum: model.getObjectByName('TetherDrum'),
    exit: model.getObjectByName('TetherExit'),
    fairlead: model.getObjectByName('TetherFairlead'),
    lod: detail.lod,
    proxy: detail.proxy,
  };
  return boat;
}

function buildFallbackBoat() {                           // used only if the model fails to load
  const boat = new THREE.Group();
  const length = 10;
  const beam = 3.6;
  const shape = new THREE.Shape();
  shape.moveTo(-beam / 2, -length / 2);
  shape.lineTo(beam / 2, -length / 2);
  shape.lineTo(beam / 2, length / 2 - 3);
  shape.quadraticCurveTo(beam / 2, length / 2 - 0.4, 0, length / 2);
  shape.quadraticCurveTo(-beam / 2, length / 2 - 0.4, -beam / 2, length / 2 - 3);
  shape.closePath();
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: 0.85, bevelEnabled: true, bevelSize: 0.08,
    bevelThickness: 0.08 });
  geometry.rotateX(Math.PI / 2);
  const hull = new THREE.Mesh(geometry, material(0xf0f0ea));
  hull.position.y = 0.4;
  boat.add(hull);
  boat.userData = { L: length, deckY: 0.4, sternZ: -length / 2, transomY: 0.75 };
  return boat;
}

/** Stand-in tether drum for the fallback boat: a yellow-wound cylinder on the deck. */
function buildFallbackDrum(boat) {
  const ud = boat.userData;
  const holder = new THREE.Group();
  holder.position.set(-0.75, ud.deckY + 0.5, ud.sternZ + 2.2);
  const drum = new THREE.Group();
  const wound = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.26, 0.66, 24), material(0xe9c534));
  wound.rotation.z = Math.PI / 2;
  drum.add(wound);
  holder.add(drum);
  boat.add(holder);
  const exit = new THREE.Object3D();
  exit.position.set(0, 0.27, 0);
  holder.add(exit);
  ud.drum = drum;
  ud.exit = exit;
}

/** Head yaw/pitch (Humanoid convention) for a figure looking at world point ``target``. */
function lookAt(person, target) {
  const local = person.root.worldToLocal(target.clone());
  local.y -= 1.6;
  const yaw = THREE.MathUtils.clamp(Math.atan2(local.x, local.z), -1.0, 1.0);
  const pitch = THREE.MathUtils.clamp(Math.atan2(-local.y, Math.hypot(local.x, local.z)), -0.5, 0.7);
  return [yaw, pitch];
}

/** Bounds of the vehicle's opaque meshes (leaves out lamp beams, glows and other effect geometry). */
function solidBounds(root) {
  const box = new THREE.Box3();
  const part = new THREE.Box3();
  root.updateMatrixWorld(true);
  root.traverse(function addMesh(o) {
    if (!o.isMesh || o.isSprite || !o.geometry) return;
    const mat = Array.isArray(o.material) ? o.material[0] : o.material;
    if (!mat || mat.transparent || mat.isShaderMaterial) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    box.union(part.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld));
  });
  return box;
}

/** Catenary-like sag between ``a`` and ``b`` (``sag`` metres at mid-span), points appended to ``out``. */
function sagLine(out, a, b, sag, count, floorY = -Infinity) {
  for (let i = 1; i <= count; i++) {
    const u = i / count;
    const p = a.clone().lerp(b, u);
    p.y -= Math.sin(Math.PI * u) * sag;
    p.y = Math.max(p.y, floorY);
    out.push(p);
  }
}

export class DeployIntro {
  static async loadAssets(base = 'models/', { tier = assetTextureTier() } = {}) {
    const boatFile = tier === 'high' ? 'workboat_high.glb' : 'workboat.glb';
    const loadBoat = function loadBoat() {
      return loadGLTF(base + boatFile).catch(function standardBoat() {
        return loadGLTF(base + 'workboat.glb');
      });
    };
    const [boat, human] = await Promise.all([
      loadBoat().then((g) => g.scene).catch(() => null),
      Humanoid.load(base + 'worker.glb').catch(() => null),
    ]);
    return { boat, human };
  }

  constructor(scene, { spool, start, seabed = 30, assets = {} }) {
    this.scene = scene;
    this.spool = toThree(spool);
    this.start = toThree(start);
    this.seabed = seabed;
    this.duration = T.end;
    this.t = 0;
    this.playing = false;
    this.objects = [];

    // boat: stern (-Z local) at the spool, bow pointing away from the dive site
    this.boat = (assets.boat && placeVesselModel(assets.boat)) || buildFallbackBoat();
    const dir = new THREE.Vector3().subVectors(this.start, this.spool);
    dir.y = 0;
    if (dir.lengthSq() < 1e-6) dir.set(0, 0, -1);
    dir.normalize();
    this.boat.rotation.y = Math.atan2(-dir.x, -dir.z);
    const ud = this.boat.userData;
    this.boat.position.copy(this.spool).addScaledVector(dir, ud.sternZ + 0.15);   // transom just inboard of the spool
    this.boat.position.y = 0;
    this._add(this.boat);
    if (!ud.drum || !ud.exit) buildFallbackDrum(this.boat);
    this.boat.updateMatrixWorld(true);

    this.rig = new LaunchRig(this.boat);
    this._add(this.rig.group);
    this.effects = new IntroEffects();
    this._add(this.effects.group);

    // deck crew: deck hand on the A-frame pendant (port side), tether tender beside the vehicle (starboard)
    this.deckhand = null;
    this.tender = null;
    if (assets.human) {
      this.deckhand = new Humanoid(assets.human, { shirt: 0x2b3f55, pants: 0x2a2f36, vest: 0xff6a13,
        helmet: 0xf4f4ef });
      this.deckhand.root.position.set(1.05, ud.deckY, ud.sternZ + 1.75);
      this.deckhand.root.rotation.y = Math.PI + 0.55;
      this.deckhand.play('Idle');
      this.boat.add(this.deckhand.root);
      this.tender = new Humanoid(assets.human, { shirt: 0x5b6770, pants: 0x30343a, vest: 0xffc21a,
        helmet: 0xf4f4ef, height: 1.7 });
      this.tender.root.position.set(-0.62, ud.deckY, ud.sternZ + 0.78);
      this.tender.root.rotation.y = Math.PI / 2;
      this.tender.play('Idle', { at: 1.3 });
      this.boat.add(this.tender.root);
      this.pendant = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.17, 0.05), material(0xe0a21a));
      this.boat.add(this.pendant);
    }

    // tether: real-thickness yellow cable, rebuilt each frame
    this.cable = new Cable(material(0xe9c534, { roughness: 0.5, metalness: 0 }),
      { radius: 0.0065, segments: 160, radial: 6 });
    this._add(this.cable.mesh);
  }

  /**
   * ``getModel`` returns the vehicle's visual model (or null while it loads). The viewer hides it in the onboard
   * camera; the intro shows it while playing and puts back the visibility it found when it ends.
   */
  showVehicle(getModel) {
    this._getModel = getModel;
  }

  _forceVehicleVisible() {
    const model = this._getModel ? this._getModel() : null;
    if (!model) return;
    if (this._shownModel !== model) {
      this._shownModel = model;
      this._shownWas = model.visible;
    }
    model.visible = true;
  }

  _restoreVehicleVisibility() {
    if (this._shownModel) this._shownModel.visible = this._shownWas;
    this._shownModel = null;
  }

  _add(object) {
    this.scene.add(object);
    this.objects.push(object);
    return object;
  }

  _boatPoint(x, y, z) {
    return this.boat.localToWorld(V(x, y, z));
  }

  play(rov, camera, onDone) {
    this.rov = rov;
    this.camera = camera;
    this.onDone = onDone;
    this.t = 0;
    this.playing = true;
    this._camPos = null;
    this._events = new Set();
    this._tetherLength = null;
    this._handPhase = 0;
    this.qStart = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, this.boat.rotation.y + Math.PI, 0));
    this._measureVehicle();
    this.rig.group.visible = true;
    this.cable.mesh.visible = true;
    this.update(0);
  }

  /**
   * Hold the opening frame (vehicle on the aft deck) while the operator works the pre-dive checklist; the
   * procedure releases it when the vehicle is lowered. While held the clock stands still and skip does nothing.
   */
  hold() {
    this.held = true;
  }

  release() {
    this.held = false;
  }

  skip() {
    if (!this.playing || this.held) return;
    this.t = this.duration;
    this.update(0);
  }

  /** Half extents of the vehicle in its own frame (lifting points, deck rest height, draft, lamp positions). */
  _measureVehicle() {
    const half = V(0.3, 0.2, 0.4);
    if (this.rov) {
      const saved = this.rov.quaternion.clone();
      const savedPos = this.rov.position.clone();
      this.rov.quaternion.identity();
      this.rov.position.set(0, 0, 0);
      this.rov.updateMatrixWorld(true);
      const box = solidBounds(this.rov);
      if (!box.isEmpty()) box.getSize(half).multiplyScalar(0.5);
      half.clamp(V(0.15, 0.1, 0.2), V(0.6, 0.4, 0.8));
      this.rov.quaternion.copy(saved);
      this.rov.position.copy(savedPos);
    }
    this.half = half;
    this.slingPoints = [
      V(half.x * 0.55, half.y, half.z * 0.5), V(-half.x * 0.55, half.y, half.z * 0.5),
      V(-half.x * 0.55, half.y, -half.z * 0.5), V(half.x * 0.55, half.y, -half.z * 0.5),
    ];
    this.lampPoints = [V(Math.min(0.12, half.x * 0.4), -0.02, half.z * 0.95),
      V(-Math.min(0.12, half.x * 0.4), -0.02, half.z * 0.95)];
    this.thrusterPoints = [V(half.x * 0.8, 0, half.z * 0.6), V(-half.x * 0.8, 0, half.z * 0.6),
      V(half.x * 0.8, 0, -half.z * 0.6), V(-half.x * 0.8, 0, -half.z * 0.6)];
    this.glandPoint = V(0, Math.min(0.06, half.y * 0.3), -half.z * 0.95);
  }

  /** A-frame angle over the sequence: inboard for the pick-up, outboard to lower, stowed after release. */
  _frameAngle(t) {
    if (t < T.luff0) return THETA_IN;
    if (t < T.stow0) return THETA_IN + (THETA_OUT - THETA_IN) * phase(t, T.luff0, T.luff1);
    return THETA_OUT * (1 - phase(t, T.stow0, T.stow1));
  }

  /** Pendulum swing of the hanging vehicle (radians about the boat's X axis) from the A-frame motion. */
  _swing(t) {
    if (t < T.luff0) return 0;
    if (t < T.luff1) return 0.09 * Math.sin(Math.PI * phase(t, T.luff0, T.luff1));
    const s = t - T.luff1;
    return -0.05 * Math.sin(s * 4.2) * Math.exp(-s * 1.4);
  }

  /** Vehicle pose for intro time ``t`` (pure function of t and the boat's current pose). */
  _vehiclePose(t) {
    const ud = this.boat.userData;
    const half = this.half;
    const restY = ud.deckY + half.y + 0.01;
    const liftY = Math.max(ud.transomY + half.y + LIFT_CLEAR, restY + 0.8);
    const floatY = -half.y * FLOAT_DRAFT;
    const swing = this._swing(t);
    const quat = this.qStart.clone();
    let pos;
    let hanging = true;
    if (t < T.luff1) {
      const sheave = this.rig.sheaveLocal(this._frameAngle(t));
      const pendulum = Math.max(0.3, sheave.y - liftY);
      const y = restY + (liftY - restY) * phase(t, T.hoist0, T.hoist1);
      pos = this._boatPoint(sheave.x, y, sheave.z + Math.sin(swing) * pendulum);
    } else {
      const outboard = this.rig.sheaveLocal(THETA_OUT);
      const lifted = this._boatPoint(outboard.x, liftY, outboard.z + Math.sin(swing) * 1.2);
      pos = lifted.clone();
      pos.y = lifted.y + (floatY - lifted.y) * phase(t, T.luff1, T.wet);
      if (t >= T.wet) {
        hanging = false;
        const s = t - T.wet;
        pos.y = floatY + Math.sin(s * 2.1) * 0.03;
        quat.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.sin(s * 1.7) * 0.03, 0,
          Math.sin(s * 2.3) * 0.04)));
      }
    }
    if (t < T.wet) quat.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(swing * 0.6,
      0.06 * Math.sin(t * 1.3), 0)));
    if (t >= T.twitch0 && t < T.twitch1) {
      const pulse = TWITCH_PULSES.reduce(function nearest(m, p) {
        return Math.max(m, Math.exp(-(((t - p) * 18) ** 2)));
      }, 0);
      quat.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0.05 * pulse, 0)));
    }
    if (t >= T.dive) {
      const s = t - T.dive;
      const k = phase(t, T.dive + 0.2, T.end - 0.2);
      const settle = pos.clone();
      settle.y -= 0.5 * (1 - Math.exp(-s * 2.0));
      pos = settle.lerp(this.start, k);
      pos.y += Math.sin(s * 3) * 0.05 * (1 - k);
      quat.slerp(this.qStart, Math.min(1, s * 0.9));
    }
    return { pos, quat, hanging, floatY };
  }

  _local(point) {
    return this.rov.localToWorld(point.clone());
  }

  update(dt) {
    if (!this.playing) {
      this.effects.update(dt);
      return false;
    }
    if (!this.held) this.t += dt;
    const t = Math.min(this.t, this.duration);
    this.boat.updateMatrixWorld(true);

    // gentle swell on the boat
    this.boat.rotation.z = Math.sin(t * 0.9) * 0.018;
    this.boat.rotation.x = Math.sin(t * 0.7 + 1) * 0.012;
    this.boat.position.y = Math.sin(t * 0.8) * 0.05;
    this.boat.updateMatrixWorld(true);
    this.rig.setAngle(this._frameAngle(t));

    const pose = this._vehiclePose(t);
    this._forceVehicleVisible();
    if (this.rov) {
      this.rov.position.copy(pose.pos);
      this.rov.quaternion.copy(pose.quat);
      this.rov.updateMatrixWorld(true);
      this._drawRigging(t, pose);
      this._phaseEvents(t, dt, pose);
      this._surfaceCheck(t, dt);
    }
    this._crew(t, dt);
    this._drawTether(t, dt);
    this.effects.update(dt);
    this._cameraPath(t);

    if (this.t >= this.duration) this._finish();
    return this.playing;
  }

  _finish() {
    this.playing = false;
    if (this.rov) this.rov.position.copy(this.start);
    if (this.rov) this.rov.quaternion.copy(this.qStart);
    this.rig.setAngle(0);
    this.rig.hideRigging();
    this._restoreVehicleVisibility();
    this.effects.clear();
    this.cable.mesh.visible = false;               // the viewer draws the live tether from here on
    if (this.onDone) this.onDone();
  }

  /** Lifting wire, hook and bridle: link above the vehicle while lifting, slack after set-down, hook home. */
  _drawRigging(t, pose) {
    const slings = this.slingPoints.map((p) => this._local(p));
    const top = this._local(V(0, this.half.y, 0));
    const up = V(0, 1, 0);
    let link;
    if (t < T.wet) {
      link = this._local(V(0, this.half.y + BRIDLE, 0));
    } else {
      const k = phase(t, T.wet, T.release);
      link = this._local(V(0, this.half.y + BRIDLE * (1 - k) + 0.04 * k, 0));
    }
    let hook = this.rig.hookForLink(link);
    if (t >= T.release) {
      const home = this.rig.sheaveWorld().addScaledVector(up, -0.32);
      hook = hook.lerp(home, phase(t, T.release, T.hookHome));
    }
    if (t >= T.dive) link = top.addScaledVector(up, 0.02);              // bridle left lying on the frame
    this.rig.draw(hook, link, slings);
    this.rig.group.visible = t < T.end;
    for (const leg of this.rig.legs) leg.visible = leg.visible && pose.pos.y > -2.5;
  }

  /** One-shot effects when a phase begins (only while playing forward, not on skip). */
  _phaseEvents(t, dt, pose) {
    if (dt <= 0) return;
    const fire = (name, at) => {
      if (t < at || this._events.has(name)) return false;
      this._events.add(name);
      return true;
    };
    if (fire('wet', T.wet - 0.05)) this.effects.setDown(pose.pos);
    if (fire('dive', T.dive + 0.1)) this.effects.ripple(pose.pos, { size: 0.5, grow: 1.0, life: 2.0 });
    if (t > T.dive && t < T.dive + 1.6 && Math.random() < 0.8) {
      this.effects.bubble(pose.pos, 2, null, 0.6);
    }
  }

  /** Surface function check: lamps blink twice, then three short thruster pulses (vehicle afloat only). */
  _surfaceCheck(t, dt) {
    const lit = LIGHT_BLINKS.some(([a, b]) => t >= a && t < b);
    const lampLevel = lit ? 1 : 0;
    this.effects.setLamps(this.lampPoints.map((p) => this._local(p)), lampLevel);
    if (dt <= 0 || t < T.twitch0 || t >= T.twitch1 || this.rov.position.y > 0) return;
    for (const pulse of TWITCH_PULSES) {
      const key = 'pulse' + pulse;
      if (t < pulse || this._events.has(key)) continue;
      this._events.add(key);
      for (const p of this.thrusterPoints) {
        const at = this._local(p);
        const push = this._local(V(p.x, 0, p.z * 3)).sub(at).setLength(0.6);
        this.effects.bubble(at, 6, push, 0.12);
        this.effects.ripple(V(at.x, 0, at.z), { size: 0.12, grow: 0.7, life: 1.0, alpha: 0.4 });
      }
    }
  }

  _crew(t, dt) {
    if (!this.tender || !this.rov) return;
    const rovPos = this.rov.position;
    // deck hand: both hands on the pendant, thumb work while the rig moves, eyes on the load
    const working = (t > T.hoist0 && t < T.wet) || (t > T.release - 0.2 && t < T.release + 0.3);
    const press = working ? 0.01 * Math.sin(t * 9) : 0;
    const handL = V(0.08, 1.1 + press, 0.3);
    const handR = V(-0.06, 1.06 - press, 0.31);
    this.deckhand.update(dt, { pelvis: [0, -0.02, 0], bend: 0.12, head: lookAt(this.deckhand, rovPos),
      handL, handR });
    const grip = this.deckhand.hand('L').lerp(this.deckhand.hand('R'), 0.5);
    this.pendant.position.copy(this.boat.worldToLocal(grip));
    this.pendant.rotation.set(-0.5, this.deckhand.root.rotation.y, 0);

    // tether tender: steadies the frame, then turns aft and feeds the tether hand over hand
    const turn = phase(t, T.guideEnd - 0.5, T.guideEnd + 0.4);
    this.tender.root.rotation.y = Math.PI / 2 + turn * (Math.PI / 2 - 0.3);
    this.tender.root.updateMatrixWorld(true);
    const guide = phase(t, 0, T.grab) * (1 - phase(t, T.guideEnd - 0.3, T.guideEnd));
    const inRov = this.rov.worldToLocal(this.tender.root.getWorldPosition(V(0, 0, 0)));
    const side = Math.sign(inRov.x) || 1;
    const frontGrip = this.tender.root.worldToLocal(this._local(V(side * (this.half.x + 0.02), 0, 0.2)));
    const backGrip = this.tender.root.worldToLocal(this._local(V(side * (this.half.x + 0.02), 0, -0.2)));
    const swing = Math.sin(this._handPhase);
    const feedL = V(0.1, 1.02 + 0.05 * swing, 0.4 + 0.07 * Math.cos(this._handPhase));
    const feedR = V(-0.12, 0.95 - 0.05 * swing, 0.55 - 0.07 * Math.cos(this._handPhase));
    const rovAboveDeck = this.boat.worldToLocal(rovPos.clone()).y - this.boat.userData.deckY;
    const crouch = guide * clamp01((0.75 - rovAboveDeck) / 0.5);
    this.tender.update(dt, {
      pelvis: [0, -0.4 * crouch, -0.1 * crouch],
      bend: 0.25 + 0.6 * crouch,
      head: lookAt(this.tender, rovPos),
      handL: feedL.lerp(frontGrip, guide),
      handR: feedR.lerp(backGrip, guide),
    });
  }

  /** Tether: drum top -> fairlead -> tender's hands -> (over the transom) -> vehicle gland. Drives the drum. */
  _drawTether(t, dt) {
    const ud = this.boat.userData;
    const pts = [];
    const exit = ud.exit.getWorldPosition(V(0, 0, 0));
    pts.push(exit);
    const hands = this.tender ? this.tender.hand('L').lerp(this.tender.hand('R'), 0.5)
      : this._boatPoint(-0.6, ud.deckY + 1.0, ud.sternZ + 0.8);
    if (ud.fairlead) {
      const fair = ud.fairlead.getWorldPosition(V(0, 0, 0));
      pts.push(fair);
      sagLine(pts, fair, hands, 0.25, 6);
    } else {
      sagLine(pts, exit, hands, 0.3, 6);
    }
    const gland = this.rov ? this._local(this.glandPoint) : this.start.clone();
    const deckY = this._boatPoint(0, ud.deckY + 0.015, 0).y;
    const glandLocal = this.boat.worldToLocal(gland.clone());
    let length = hands.distanceTo(gland);
    if (glandLocal.z > ud.sternZ + 0.05) {
      // vehicle still over the deck: a slack bight from the tender's hands, partly lying on the deck
      sagLine(pts, hands, gland, 0.35, 12, deckY);
    } else {
      const handsLocal = this.boat.worldToLocal(hands.clone());
      const capX = THREE.MathUtils.clamp(handsLocal.x, -1.2, 1.2);
      const cap = this._boatPoint(capX, ud.transomY + 0.03, ud.sternZ + 0.02);
      sagLine(pts, hands, cap, 0.05, 3);
      const wetSag = t > T.wet ? 0.4 + Math.min(1.8, (t - T.wet) * 0.5) : 0.25;
      const n = 16;
      for (let i = 1; i <= n; i++) {
        const u = i / n;
        const p = cap.clone().lerp(gland, u);
        p.y -= Math.sin(Math.PI * u) * wetSag * (p.y > 0 ? 0.5 : 1);
        pts.push(p);
      }
      length = hands.distanceTo(cap) + cap.distanceTo(gland) + wetSag;
    }
    this.cable.update(pts);
    // pay-out turns the drum and the tender's hands
    if (this._tetherLength !== null && dt > 0) {
      const paid = Math.max(0, length - this._tetherLength);
      ud.drum.rotation.x -= paid / DRUM_RADIUS;
      this._handPhase += paid * 14;
    }
    this._tetherLength = length;
  }

  _cameraPath(t) {
    const cam = this.camera;
    if (!cam) return;
    const ud = this.boat.userData;
    const sz = ud.sternZ;
    const dy = ud.deckY;
    const W = (x, y, z) => this._boatPoint(x, y, z);
    const rovP = this.rov ? this.rov.position.clone() : this.start.clone();
    const seg = (keys) => {
      let i = 0;
      while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
      const [t0, p0, l0] = keys[i];
      const [t1, p1, l1] = keys[i + 1];
      const k = phase(t, t0, t1);
      return [new THREE.Vector3().lerpVectors(p0, p1, k), new THREE.Vector3().lerpVectors(l0, l1, k)];
    };
    let pos;
    let look;
    let smooth = 1;
    if (t < T.luff1) {
      // establishing shot from off the starboard bow -> three-quarter on the crew and the A-frame from the sea
      [pos, look] = seg([
        [0.0, W(13, 5.5, 5), W(0, dy + 0.8, sz + 2.5)],
        [2.2, W(3.8, dy + 1.4, sz - 2.8), W(0, dy + 0.9, sz + 0.9)],
        [T.luff1, W(4.4, dy + 1.1, sz - 4.0), W(0, dy + 1.0, sz - 0.4)],
      ]);
      smooth = t < 2.2 ? 1 : 0.2;
    } else if (t < T.dive) {
      // low over the water, off the port quarter: set-down, release and the surface check
      const entry = this._boatPoint(0, 0, sz - 1.3);
      const k = phase(t, T.luff1, T.wet);
      pos = W(4.4 - 1.6 * k, dy + 1.1 - 0.75 * k, sz - 4.0 + 0.6 * k);
      look = rovP.clone().lerp(entry, 0.4);
      look.y = rovP.y * 0.6 + 0.15;
      smooth = 0.12;
    } else {
      // underwater: circle the descending vehicle with the hull and the cable in view
      const a = 0.9 + (t - T.dive) * 0.35;
      pos = rovP.clone().add(V(Math.cos(a) * 3.0, 0.8, Math.sin(a) * 3.0));
      look = rovP.clone().add(V(0, -0.2, 0));
      if (pos.y > -0.5) pos.y = -0.5;
      smooth = 0.12;
    }
    if (!this._camPos) {
      this._camPos = pos.clone();
      this._camLook = look.clone();
    }
    if (pos.y < 0 && this._camPos.y > 0) {        // cut under water, don't drift through the surface
      this._camPos.copy(pos);
      this._camLook.copy(look);
    }
    this._camPos.lerp(pos, smooth);
    this._camLook.lerp(look, Math.min(1, smooth * 2));
    cam.position.copy(this._camPos);
    cam.lookAt(this._camLook);
  }

  dispose() {
    this._restoreVehicleVisibility();
    for (const o of this.objects) this.scene.remove(o);
    this.cable.dispose();
    this.rig.dispose();
    this.effects.dispose();
  }
}
