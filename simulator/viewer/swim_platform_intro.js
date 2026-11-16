// Optional hand launch presentation. Uses existing vehicle meshes and base intro lifecycle;
// all trajectories below are cinematic only and never change server tether/vehicle state.
import * as THREE from 'three';
import { DeployIntro } from './deploy_intro.js';
import { loadGLTF } from './glb.js';
import { Cable } from './cable.js';
import { Humanoid } from './humanoid.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const UP = V(0, 1, 0);
function phase(t, a, b) {
  const k = THREE.MathUtils.clamp((t - a) / (b - a), 0, 1);
  return k * k * (3 - 2 * k);
}
// Cable's transported frame uses the opposite winding to the cylinder normals.
// Correct it for this presentation without changing the live simulation cable renderer.
function outwardCable(material, options) {
  const cable = new Cable(material, options);
  const index = cable.geometry.index;
  for (let i = 0; i < index.count; i += 3) {
    const b = index.array[i + 1];
    index.array[i + 1] = index.array[i + 2];
    index.array[i + 2] = b;
  }
  index.needsUpdate = true;
  return cable;
}

export class SwimPlatformIntro extends DeployIntro {
  static async loadAssets(base = 'models/') {
    const [boat, human] = await Promise.all([
      loadGLTF(base + 'small_boat.glb'),
      Humanoid.load(base + 'worker.glb'),
    ]);
    return { boat: boat.scene, human };
  }

  constructor(scene, options) {
    super(scene, { ...options, assets: { ...options.assets, human: null } });
    this.launchCrew = new Humanoid(options.assets.human, {
      shirt: 0x344d61, vest: 0xffc21a, helmet: 0xf4f4ef,
    });
    this.boat.add(this.launchCrew.root);
    this.cable.dispose();
    this.cable.mesh.material.dispose();
    this.scene.remove(this.cable.mesh);
    this.cable = outwardCable(new THREE.MeshStandardMaterial({
      color: 0xc5f500, roughness: 0.48, emissive: 0x839e00, emissiveIntensity: 0.15 }),
      { radius: 0.008, segments: 160, radial: 6 });
    this._add(this.cable.mesh);
    this.marker = outwardCable(new THREE.MeshStandardMaterial({
      color: 0xd52128, roughness: 0.6 }),
      { radius: 0.014, segments: 16, radial: 6 });
    this.cable.mesh.name = 'FloatingUmbilical';
    this.marker.mesh.name = 'UmbilicalRedMarker';
    this._add(this.marker.mesh);
  }

  play(rov, camera, onDone) {
    // Duplicate only the existing model, never a substitute vehicle or a reference-photo mesh.
    if (this.parked) this.boat.remove(this.parked);
    this.parked = rov.clone(true);
    this.parked.name = 'ParkedModelR';
    this.parked.traverse(function show(o) {
      o.visible = !o.isLight && !(o.material?.transparent || o.material?.isShaderMaterial);
    });
    const slot = this.boat.getObjectByName('rov_slot_1');
    this.boat.add(this.parked);
    this.parked.position.copy(this.boat.worldToLocal(slot.getWorldPosition(V(0, 0, 0))));
    this.parked.position.y += 0.22;
    this.parked.quaternion.setFromAxisAngle(UP, Math.PI);
    super.play(rov, camera, onDone);
    this.parked.position.y = 0.3 + this.half.y;
  }

  _vehiclePose(t) {
    const slot = this.boat.getObjectByName('rov_slot_0');
    const local = this.boat.worldToLocal(slot.getWorldPosition(V(0, 0, 0)));
    local.y += this.half.y + 0.01 + 0.5 * phase(t, 1.2, 2.3);
    local.z -= 1.43 * phase(t, 2.4, 4.2);
    const pos = this.boat.localToWorld(local);
    const floatY = -this.half.y * 0.55;
    pos.y = THREE.MathUtils.lerp(pos.y, floatY, phase(t, 4.2, 6.4));
    if (t >= 6.4) pos.y += Math.sin((t - 6.4) * 2.1) * 0.025;
    if (t >= 8.8) pos.lerp(this.start, phase(t, 8.8, 11.6));
    return { pos, quat: this.qStart.clone(), hanging: false, floatY };
  }

  _phaseEvents(t, dt, pose) {
    super._phaseEvents(t, dt, pose);
    this.effects.foam.visible = false;
  }

  _drawRigging() {
    this.rig.hideRigging();
  }

  _crew(t, dt) {
    if (!this.launchCrew || !this.rov) return;
    const crew = this.launchCrew;
    crew.root.position.set(-0.78, 0.3, -1.35 - 1.45 * phase(t, 2.4, 4.2));
    crew.root.position.z -= .17 * phase(t, 1.2, 2.3) * (1 - phase(t, 2.4, 4.2));
    crew.root.rotation.y = Math.PI;
    crew.root.updateMatrixWorld(true);
    const release = phase(t, 6.4, 7);
    const handL = crew.root.worldToLocal(this._local(V(this.half.x * .8, this.half.y * .7, 0)));
    const handR = crew.root.worldToLocal(this._local(V(-this.half.x * .8, this.half.y * .7, 0)));
    handL.lerp(V(.2, .85, .3), release);
    handR.lerp(V(-.2, .85, .3), release);
    const crouch = 1 - phase(t, 1.2, 2.3) + phase(t, 3.8, 5.2);
    crew.update(dt, { pelvis: [0, -.52 * crouch, .12 * crouch], bend: .45 + .5 * crouch, handL, handR });
  }

  _drawTether(t) {
    if (!this.marker || !this.rov) return;
    const exit = this.boat.userData.exit.getWorldPosition(V(0, 0, 0));
    const gland = this._local(this.glandPoint);
    const pts = [exit, this._boatPoint(1.55, 0.34, -2.45)];
    if (t < 4.2) {
      pts.push(this._boatPoint(1.55, 0.34, -2.78),
        this._boatPoint(-0.3, 0.34, -2.78), gland.clone().add(V(0, .2, 0)), gland);
    } else {
      const edge = this._boatPoint(1.1, 0.3, -2.88);
      pts.push(edge);
      const aft = this._boatPoint(0, 0, -1).sub(this._boatPoint(0, 0, 0)).normalize();
      for (let i = 1; i < 20; i++) {
        const u = i / 20;
        const p = edge.clone().lerp(gland, u);
        p.x += Math.sin(u * Math.PI * 3 + t * 0.3) * Math.sin(u * Math.PI) * 0.3;
        p.addScaledVector(aft, Math.sin(u * Math.PI) * phase(t, 4.2, 6.4) * 1.6);
        const surface = 0.035 + Math.sin(u * 10 + t) * 0.008;
        const afloat = phase(t, 4.2, 6.4);
        const edgeBlend = Math.min(1, u / 0.15, (1 - u) / 0.1);
        p.y = THREE.MathUtils.lerp(p.y, surface, edgeBlend * afloat);
        pts.push(p);
      }
      pts.push(gland);
    }
    this.cable.update(pts);
    this.marker.update([this.cable.curve.getPoint(.55), this.cable.curve.getPoint(.59),
      this.cable.curve.getPoint(.63)]);
  }

  _cameraPath(t) {
    if (!this.camera) return;
    if (t >= 8.8) return super._cameraPath(t);
    const eye = this.boat.getObjectByName('menu_camera').getWorldPosition(V(0, 0, 0));
    const target = this.boat.getObjectByName('menu_target').getWorldPosition(V(0, 0, 0));
    const k = phase(t, 1.2, 4.2);
    eye.lerp(this._boatPoint(-3.6, 2.1, -4.9), k);
    target.lerp(this.rov.position, k);
    this.camera.position.copy(eye);
    this.camera.lookAt(target);
  }

  _finish() {
    super._finish();
    this.marker.mesh.visible = false;
    this.launchCrew.root.visible = false;
  }

  dispose() {
    super.dispose();
    this.marker.dispose();
    this.marker.mesh.material.dispose();
    this.cable.mesh.material.dispose();
    const geometries = new Set();
    const materials = new Set();
    for (const group of [this.launchCrew.root]) {
      group.traverse(function collect(o) {
        if (o.geometry) geometries.add(o.geometry);
        if (o.material) materials.add(o.material);
      });
    }
    for (const geometry of geometries) geometry.dispose();
    for (const material of materials) material.dispose();
  }
}

export function launchIntroClass(mode) {
  return mode === 'swim-platform' ? SwimPlatformIntro : DeployIntro;
}

// Opt-in deterministic inspection only; normal play never installs this hook.
export function installIntroReview(params, getIntro, getModel) {
  if (!params.has('introReview')) return;
  window.__seekIntro = function seekIntro(seconds) {
    const intro = getIntro();
    if (!intro?.playing || !getModel()) return false;
    intro.t = Math.max(0, Math.min(seconds, intro.duration - 0.01));
    intro.hold();
    intro.update(0);
    return true;
  };
}
