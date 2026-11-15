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
function strand(color, radius) {
  return new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 1, 10),
    new THREE.MeshStandardMaterial({ color, roughness: 0.7 }));
}
function between(mesh, a, b) {
  const delta = b.clone().sub(a);
  mesh.position.copy(a).add(b).multiplyScalar(0.5);
  mesh.scale.y = delta.length();
  mesh.quaternion.setFromUnitVectors(UP, delta.normalize());
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
    const [boat, human, normals] = await Promise.all([
      loadGLTF(base + 'small_boat.glb'),
      Humanoid.load(base + 'worker.glb').catch(() => null),
      new THREE.TextureLoader().loadAsync(base + 'waternormals.jpg').catch(() => null),
    ]);
    return { boat: boat.scene, human, normals };
  }

  constructor(scene, options) {
    super(scene, { ...options, assets: { ...options.assets, human: null } });
    this.surfacePresentation = true;
    this.arms = new THREE.Group();
    this.arms.name = 'HandLaunchArms';
    for (let i = 0; i < 2; i++) {
      this.arms.add(strand(0x344d61, 0.065), strand(0x344d61, 0.055), strand(0xe9b88c, 0.045));
    }
    this._add(this.arms);
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
    this._horizon();
    if (this.water) {
      this.water.material.uniforms.waterColor.value.set(0x003556);
      this.water.material.uniforms.sunColor.value.set(0x617c94);
      this.water.material.uniforms.distortionScale.value = 0.7;
      this.water.material.uniforms.size.value = 8.0;
      // Deep-blue open-water grade; retain the Water shader's moving normals and reflections.
      this.water.material.fragmentShader = this.water.material.fragmentShader.replace(
        'vec3 outgoingLight = albedo;', 'vec3 outgoingLight = albedo * vec3(0.035, 0.16, 0.27);');
      this.water.material.needsUpdate = true;
    }
  }

  _horizon() {
    this.horizon = new THREE.Group();
    this.horizon.name = 'WindFarmSilhouettes';
    const mat = new THREE.MeshStandardMaterial({ color: 0x667b88, roughness: 0.9 });
    for (let i = 0; i < 5; i++) {
      const tower = new THREE.Group();
      tower.position.copy(this._boatPoint(-150 + i * 70, 0, -500));
      const mast = new THREE.Mesh(new THREE.CylinderGeometry(1, 2.5, 65, 6), mat);
      mast.position.y = 32.5;
      tower.add(mast);
      for (let b = 0; b < 3; b++) {
        const blade = new THREE.Mesh(new THREE.BoxGeometry(1.8, 30, 0.5), mat);
        const a = b * Math.PI * 2 / 3 + i;
        blade.position.set(Math.sin(a) * 15, 65 + Math.cos(a) * 15, 0);
        blade.rotation.z = -a;
        tower.add(blade);
      }
      this.horizon.add(tower);
    }
    const platform = new THREE.Group();
    platform.position.copy(this._boatPoint(220, 0, -470));
    const deck = new THREE.Mesh(new THREE.BoxGeometry(48, 7, 22), mat);
    deck.position.y = 12;
    platform.add(deck);
    for (const x of [-20, 20]) {
      for (const z of [-8, 8]) {
        const leg = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 48, 5), mat);
        leg.position.set(x, 24, z);
        platform.add(leg);
      }
    }
    const bridge = new THREE.Mesh(new THREE.BoxGeometry(12, 9, 15), mat);
    bridge.position.set(15, 20, 0);
    platform.add(bridge);
    const crane = new THREE.Mesh(new THREE.BoxGeometry(2, 40, 2), mat);
    crane.position.set(-8, 33, 0);
    crane.rotation.z = -0.5;
    platform.add(crane);
    this.horizon.add(platform);
    this._add(this.horizon);
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

  _crew(t) {
    if (!this.arms || !this.rov) return;
    this.arms.visible = t >= 0.5 && t < 7.0;
    const release = phase(t, 6.4, 7.0);
    for (let i = 0; i < 2; i++) {
      const side = i === 0 ? -1 : 1;
      const hand = this._local(V(-side * this.half.x * 0.8, this.half.y * 0.7, 0));
      const shoulder = this._boatPoint(-0.78 + side * 0.28, 1.15 - 0.5 * phase(t, 4.2, 6.4),
        -1.5 - 1.05 * phase(t, 2.4, 4.2));
      hand.lerp(shoulder.clone().add(V(0, -0.25, 0)), release);
      const elbow = shoulder.clone().lerp(hand, 0.5).add(V(side * 0.1, 0.1, 0.12));
      between(this.arms.children[i * 3], shoulder, elbow);
      between(this.arms.children[i * 3 + 1], elbow, hand);
      between(this.arms.children[i * 3 + 2], hand, hand.clone().add(V(0, -0.09, 0)));
    }
  }

  _drawTether(t) {
    if (!this.marker || !this.rov) return;
    const exit = this.boat.userData.exit.getWorldPosition(V(0, 0, 0));
    const gland = this._local(this.glandPoint);
    const pts = [exit, this._boatPoint(1.2, 0.32, -2.45)];
    if (t < 4.2) {
      pts.push(this._boatPoint(0.3, 0.32, -2.6), gland);
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
    const end = this.cable.curve.getPoint(0.88);
    this.marker.update([end, this.cable.curve.getPoint(0.94), gland]);
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
    if (this.water) {
      this.water.visible = true;
      this.sky.visible = true;
    }
  }

  _finish() {
    super._finish();
    this.marker.mesh.visible = false;
    this.arms.visible = false;
  }

  dispose() {
    super.dispose();
    this.marker.dispose();
    this.marker.mesh.material.dispose();
    this.cable.mesh.material.dispose();
    const geometries = new Set();
    const materials = new Set();
    for (const group of [this.arms, this.horizon]) {
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
