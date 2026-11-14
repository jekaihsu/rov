// GPU-instanced suspended particles (marine snow) around the camera, lit like everything else: the vehicle
// lamps with inverse-square falloff, beam cone and extinction both ways, plus faint daylight. Near the
// lens they are large and soft (out of focus). Turbid water shows more of them. Thruster-stirred silt
// puffs are rendered by the separate silt module (feat/silt), not here.
// Particle size, density and drift are visualization assumptions; the research report has no numbers.
import * as THREE from 'three';
import { WATER_COMMON, shareWaterUniforms, waterUniforms } from './water_optics.js';

const systems = new WeakMap();
const MAX_PARTICLES = 4096;
// Real lit footage at night shows roughly 500-1000 point-like particles per frame, daylight without lamps
// about 50 (research_notes/洋流與波浪對ROV作業/real_dive_footage.md, target 12). A 4 m box around the camera
// keeps the visible count in that range while the lamps decide how many are bright enough to see.
const COUNTS = { medium: 1024, auto: 1024, high: 2048, ultra: 4096 };
const BOX = 4.0;

const VERTEX = /* glsl */ `
  ${WATER_COMMON}
  attribute vec3 seed;
  uniform vec3 uFlow;
  uniform float uDensity;
  uniform float uTime;
  uniform float uPixel;
  varying vec2 vDisc;
  varying vec3 vLight;
  varying float vSoft;
  void main() {
    float box = ${BOX.toFixed(1)};
    vec3 drift = uFlow * uTime + vec3(0.0, -0.01 * uTime, 0.0);
    vec3 world = cameraPosition + mod(seed * box * 7.31 + drift - cameraPosition, box) - box * 0.5;
    float present = step(seed.y, uDensity);
    vec3 light = uWaterSun * waterDaylight(world) * 0.1;
    for (int j = 0; j < ${2}; j++) {
      if (float(j) >= uLampCount) break;
      vec3 ray = world - uLampPos[j];
      float d2 = max(dot(ray, ray), 0.04);
      float d = sqrt(d2);
      float spot = smoothstep(uLampCone.x, uLampCone.y, dot(ray / d, uLampDir[j]));
      light += uLampColor[j] * spot / d2 * exp(-uWaterC * d) * 0.03;
    }
    vec3 origin;
    vec3 dir;
    float len = waterSegment(cameraPosition, world, origin, dir);
    vLight = light * exp(-uWaterC * len) * present;
    vec4 view = viewMatrix * vec4(world, 1.0);
    float distance = max(0.05, -view.z);
    // Point-like (about 0.3 % of the frame width in footage); slightly larger and softer right at the lens.
    float size = (0.0012 + seed.z * 0.0016) + 0.003 * exp(-distance * 2.0);
    vSoft = clamp(0.0025 / size, 0.3, 1.0);
    size = max(size, uPixel * distance);
    view.xy += position.xy * size;
    vDisc = position.xy;
    gl_Position = projectionMatrix * view;
    if (present < 0.5 || world.y > 0.0) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
  }`;

const FRAGMENT = /* glsl */ `
  varying vec2 vDisc;
  varying vec3 vLight;
  varying float vSoft;
  void main() {
    float r = length(vDisc);
    if (r > 1.0) discard;
    float disc = 1.0 - smoothstep(0.35, 1.0, r);
    gl_FragColor = vec4(vLight * disc * vSoft, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }`;

function seeds() {
  const values = new Float32Array(MAX_PARTICLES * 3);
  let state = 42;
  for (let i = 0; i < values.length; i++) {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    values[i] = (state >>> 0) / 4294967296;
  }
  return values;
}

function createSystem(scene) {
  const geometry = new THREE.InstancedBufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([
    -1, -1, 0, 1, -1, 0, 1, 1, 0, -1, -1, 0, 1, 1, 0, -1, 1, 0
  ], 3));
  geometry.setAttribute('seed', new THREE.InstancedBufferAttribute(seeds(), 3));
  const uniforms = shareWaterUniforms({
    uFlow: { value: new THREE.Vector3(0.05, 0, 0.02) }, uDensity: { value: 0.5 }, uTime: { value: 0 },
    uPixel: { value: 0.001 }
  });
  const material = new THREE.ShaderMaterial({
    uniforms, vertexShader: VERTEX, fragmentShader: FRAGMENT,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.name = 'water-suspension';
  mesh.userData.observationIgnore = true;
  scene.add(mesh);
  const system = { mesh, uniforms };
  systems.set(scene, system);
  return system;
}

export function hideSuspension(scene) {
  const system = systems.get(scene);
  if (system) system.mesh.visible = false;
}

export function updateSuspension(scene, camera, quality) {
  const system = systems.get(scene) || createSystem(scene);
  system.mesh.visible = camera.position.y < 0;
  if (!system.mesh.visible) return;
  system.mesh.geometry.instanceCount = COUNTS[quality?.mode] || COUNTS.medium;
  // Scattering 0.05/m (very clear) shows few particles; 0.6/m and beyond (harbour, silt) shows all.
  const turbidity = waterUniforms.uWaterB.value.y;
  system.uniforms.uDensity.value = Math.max(0.15, Math.min(1, turbidity / 0.6));
  const current = scene.userData.waterCurrent;
  if (current) system.uniforms.uFlow.value.set(-current[1], -current[2], current[0]);
  system.uniforms.uTime.value = performance.now() / 1000;
  const height = camera.isPerspectiveCamera ? 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) : 1;
  system.uniforms.uPixel.value = height / 900;
}
