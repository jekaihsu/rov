// Silt presentation: exponential water fog sampled at the active camera, lamp backscatter in turbid water,
// and soft instanced billboards for the server's silt puffs (state.environment.silt_puffs, PROTOCOL.md §4a).
// Self-contained so an optics pipeline can call siltExtinctionAt()/siltBackscatterAt() instead of the fog.
// Without the optional server fields it reproduces the legacy fog (linear, 25 % floor from state.silt).
// In the underwater optics tiers (fx/water_optics.js) the sediment at the camera joins the water as a medium
// contributor, so there is one attenuation path and one lamp-backscatter integral; the fog settings made here
// are then only used by the legacy look. The silt puff sprites are made exposure-neutral there.
import * as THREE from 'three';
import {registerFidelityItem, getFidelity} from '../fidelity.js';
import {addMediumContributor} from './water_optics.js';
import {lampBackscatter, presentedVisibility, siltExtinction, siltOpticsAt, SILT_OPTICS} from './silt_field.js';

const SILT_CONTRAST = SILT_OPTICS.contrast;

const STRINGS = {
  siltVisibilityFloor: '揚沙能見度下限',
  siltVisibilityFloorHelp: '輔助：揚沙最濃時仍保留基本能見度的 25%。真機揚沙可完全看不見。'
};
const MAX_PUFFS = 64;
const LAMP_COLOUR = new THREE.Color(0xfff2dc);
const SILT_COLOUR = new THREE.Color('#3b3a26');
const SPRITE_DAY_COLOUR = new THREE.Color('#8c8466');
const LAMP_HALF_ANGLE_COS = Math.cos(0.5);
// Suspended sediment scatters most of what it removes and absorbs blue most (brown-green clouds), 1/m per 1/m.
const SEDIMENT_SCATTERING = Object.freeze([0.85, 0.8, 0.6]);

registerFidelityItem({
  id: 'siltVisibilityFloor', labelKey: 'siltVisibilityFloor', descriptionKey: 'siltVisibilityFloorHelp',
  type: 'toggle', defaults: {real: false, assisted: true}, exceedsReal: true
}, STRINGS);

// Exponential fog: three.js linear Fog with a negative `near` means "1 − exp(near · distance)", i.e. near = −c.
// Positive near/far keep the stock linear fog, so other code that sets them (intro, top view) is unchanged.
function installExponentialFogChunk() {
  const marker = 'fogNear < 0.0';
  if (THREE.ShaderChunk.fog_fragment.includes(marker)) return;
  THREE.ShaderChunk.fog_fragment = THREE.ShaderChunk.fog_fragment.replace(
    'float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );',
    'float fogFactor = fogNear < 0.0 ? 1.0 - exp( fogNear * vFogDepth ) : smoothstep( fogNear, fogFar, vFogDepth );');
}
installExponentialFogChunk();

// NED [n,e,d] from a three.js point (three = (−east, −down, north)).
function nedOf(vector) {
  return [vector.z, -vector.x, -vector.y];
}

function createPuffMesh() {
  const base = new THREE.PlaneGeometry(1, 1);
  const geometry = new THREE.InstancedBufferGeometry();
  geometry.index = base.index;
  geometry.setAttribute('position', base.getAttribute('position'));
  geometry.setAttribute('uv', base.getAttribute('uv'));
  const centre = new THREE.InstancedBufferAttribute(new Float32Array(MAX_PUFFS * 3), 3);
  const size = new THREE.InstancedBufferAttribute(new Float32Array(MAX_PUFFS * 2), 2);
  const colour = new THREE.InstancedBufferAttribute(new Float32Array(MAX_PUFFS * 4), 4);
  for (const attribute of [centre, size, colour]) attribute.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('aCentre', centre);
  geometry.setAttribute('aSize', size);
  geometry.setAttribute('aColour', colour);
  geometry.instanceCount = 0;
  const material = new THREE.ShaderMaterial({
    vertexShader: `attribute vec3 aCentre; attribute vec2 aSize; attribute vec4 aColour;
      varying vec2 vUv; varying vec4 vColour;
      void main() {
        vUv = uv; vColour = aColour;
        vec4 view = viewMatrix * vec4(aCentre, 1.0);
        view.xy += position.xy * aSize;
        gl_Position = projectionMatrix * view;
      }`,
    fragmentShader: `varying vec2 vUv; varying vec4 vColour;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
      float noise(vec2 p) {
        vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + 1.0), f.x), f.y);
      }
      void main() {
        vec2 q = vUv * 2.0 - 1.0;
        float r2 = dot(q, q);
        float soft = exp(-r2 * 4.5);
        float wisp = 0.75 + 0.25 * noise(vUv * 5.0 + vColour.rg * 7.0);
        gl_FragColor = vec4(vColour.rgb, vColour.a * soft * wisp);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    transparent: true, depthWrite: false
  });
  material.userData.exposureNeutral = true;
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.renderOrder = 6;
  return {mesh, centre, size, colour};
}

export class SiltRenderer {
  constructor(scene) {
    this.scene = scene;
    this.puffs = createPuffMesh();
    scene.add(this.puffs.mesh);
    this.optics = {mgL: 0, c: 0.4, visibility: 12, share: 0, veil: 0};
    this.environment = null;
    this.visibilityM = 12;
    this.seabed = 30;
    this._colour = new THREE.Color();
    this._lamp = new THREE.Vector3();
    this._lampDir = new THREE.Vector3();
    this._point = new THREE.Vector3();
    this.medium = null;
    this.removeMedium = addMediumContributor(this.mediumAtCamera.bind(this));
  }

  // Medium contributor for the optics tiers: sediment extinction at the camera on top of the clean water
  // (scene.userData.waterVisibility). The assisted visibility floor caps the total like presentedVisibility().
  mediumAtCamera({water}) {
    const medium = this.medium;
    if (!medium) return null;
    let sediment = medium.sediment;
    if (medium.floor) {
      const ceiling = SILT_CONTRAST / (0.25 * this.visibilityM);
      sediment = Math.min(sediment, Math.max(0, ceiling - water.c[1]));
    }
    if (!(sediment > 0)) return null;
    return {local: true, extinction: sediment, scattering: SEDIMENT_SCATTERING.map(function share(f) {
      return f * sediment;
    })};
  }

  // Attenuation c (1/m) at a three.js point, for an external optics pipeline.
  siltExtinctionAt(point) {
    return siltExtinction(this.environment, nedOf(point), {visibilityM: this.visibilityM, seabed: this.seabed});
  }

  // Lamp veil strength (0..1) seen from a three.js camera position.
  siltBackscatterAt(point, lampLevel) {
    const optics = siltOpticsAt(this.environment, nedOf(point), {visibilityM: this.visibilityM, seabed: this.seabed});
    return lampBackscatter(optics.mgL, lampLevel, point.distanceTo(this._lamp), optics.c);
  }

  /**
   * Per frame. `waterColour` is the depth-tinted water colour (modified in place to the fog colour).
   * `real` selects the physical exponential fog; otherwise the caller's display fog distances are used.
   */
  update({camera, state, world, waterColour, real, displayFar, lampLevel = 0, rov}) {
    const scene = this.scene;
    const environment = state?.environment;
    const modern = !!environment?.turbidity;
    this.environment = environment || null;
    this.visibilityM = world?.scenario?.visibility_m || 12;
    this.seabed = world?.seabed_depth ?? 30;
    this.waterType = world?.scenario?.water_type ?? null;
    if (rov) {
      this._lamp.set(0, 0, 0.36).applyQuaternion(rov.quaternion).add(rov.position);
      this._lampDir.set(0, 0, 1).applyQuaternion(rov.quaternion);
    }
    const cameraNed = nedOf(camera.position);
    let share;
    let visibility;
    if (modern) {
      const optics = siltOpticsAt(environment, cameraNed, {visibilityM: this.visibilityM, seabed: this.seabed});
      const veil = lampBackscatter(optics.mgL, lampLevel, camera.position.distanceTo(this._lamp), optics.c);
      this.optics = {...optics, veil};
      share = optics.share;
      const floor = getFidelity().get('siltVisibilityFloor');
      visibility = presentedVisibility(optics.visibility, this.visibilityM, floor);
    } else {
      share = Math.min(1, Math.max(0, state?.silt || 0));
      visibility = this.visibilityM * (1 - 0.75 * share);
      this.optics = {mgL: 0, c: 4.8 / visibility, visibility, share, veil: 0};
    }
    waterColour.lerp(SILT_COLOUR, Math.min(0.7, share * 0.7));
    if (this.optics.veil > 0) {
      // Footage of real silt-outs stays dark brown-green with lamps on: the veil lifts the fog only partly.
      this._colour.copy(LAMP_COLOUR).multiplyScalar(0.45);
      waterColour.lerp(this._colour, this.optics.veil * 0.35);
    }
    scene.background.copy(waterColour);
    scene.fog.color.copy(waterColour);
    this._publishMedium(real, modern, visibility, displayFar, share);
    if (real && modern) {
      scene.fog.near = -4.8 / visibility;
      scene.fog.far = 1;
    } else if (real) {
      scene.fog.near = 0.3;
      scene.fog.far = visibility * 1.35;
    } else {
      scene.fog.near = 5;
      scene.fog.far = displayFar;
    }
    this._updatePuffs(camera, environment?.silt_puffs, lampLevel, real ? 4.8 / visibility : 0, waterColour);
  }

  // What the optics tiers need: clean-water visibility and the sediment extinction at the camera.
  _publishMedium(real, modern, visibility, displayFar, share) {
    const data = this.scene.userData;
    data.waterType = this.waterType;
    if (real && modern) {
      data.waterVisibility = this.visibilityM;
      data.waterSiltTint = 0;
      const floor = getFidelity().get('siltVisibilityFloor');
      this.medium = {sediment: Math.max(0, this.optics.c - SILT_CONTRAST / this.visibilityM), floor};
    } else {
      data.waterVisibility = real ? visibility : displayFar / 1.35;
      data.waterSiltTint = real ? share : 0;
      this.medium = null;
    }
  }

  _updatePuffs(camera, puffs, lampLevel, attenuation, waterColour) {
    const mesh = this.puffs.mesh;
    const list = Array.isArray(puffs) ? puffs.slice(0, MAX_PUFFS) : [];
    mesh.visible = list.length > 0;
    if (!mesh.visible) return;
    const k = this.environment?.turbidity?.k_m2_per_g ?? 0.5;
    const centre = this.puffs.centre.array;
    const size = this.puffs.size.array;
    const colour = this.puffs.colour.array;
    const ambient = 0.1 + 0.9 * Math.exp(-Math.max(0, -camera.position.y) / 10);
    let count = 0;
    for (const [n, e, d, sigmaH, sigmaV, peak] of list) {
      const point = this._point.set(-e, -d, n);
      const distance = point.distanceTo(camera.position);
      // Inside the puff the camera fog already carries it; fade the sprite out instead of filling the screen.
      const inside = Math.min(1, Math.max(0, (distance - sigmaH) / Math.max(0.2, sigmaH)));
      const column = 1 - Math.exp(-k * peak * Math.sqrt(2 * Math.PI) * sigmaH);
      const alpha = Math.min(0.92, column) * inside;
      if (alpha < 0.01) continue;
      const lamp = this._lampLight(point, lampLevel, k * peak);
      this._colour.copy(SPRITE_DAY_COLOUR).multiplyScalar(ambient).lerp(waterColour, 0.35);
      this._colour.r += LAMP_COLOUR.r * lamp;
      this._colour.g += LAMP_COLOUR.g * lamp;
      this._colour.b += LAMP_COLOUR.b * lamp;
      // Same exponential extinction as the scene fog: far puffs fade into the water colour.
      this._colour.lerp(waterColour, 1 - Math.exp(-attenuation * distance));
      centre.set([point.x, point.y, point.z], count * 3);
      size.set([4.4 * sigmaH, 4.4 * Math.max(sigmaV, 0.6 * sigmaH)], count * 2);
      colour.set([this._colour.r, this._colour.g, this._colour.b, alpha], count * 4);
      count++;
    }
    mesh.geometry.instanceCount = count;
    this.puffs.centre.needsUpdate = true;
    this.puffs.size.needsUpdate = true;
    this.puffs.colour.needsUpdate = true;
  }

  // Lamp light scattered by a puff: inside the beam cone, falling with distance and turbidity on the way.
  _lampLight(point, lampLevel, attenuation) {
    if (!(lampLevel > 0)) return 0;
    const toPuff = point.clone().sub(this._lamp);
    const distance = Math.max(0.3, toPuff.length());
    const cone = toPuff.normalize().dot(this._lampDir);
    if (cone < LAMP_HALF_ANGLE_COS - 0.25) return 0;
    const edge = Math.min(1, (cone - (LAMP_HALF_ANGLE_COS - 0.25)) / 0.25);
    return 1.6 * lampLevel * edge * Math.exp(-attenuation * 0.5 * distance) / (1 + distance * distance * 0.25);
  }
}
