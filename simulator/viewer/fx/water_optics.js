// Shared underwater optics state for every shader in the main scene: per-channel water coefficients, the
// in-scattered water colour "at infinity", the vehicle lamps and the GLSL that applies them along each
// light path (daylight: surface -> object -> camera; lamp: lamp -> object -> camera). One set of uniform
// objects is shared by all materials, so a frame update costs a handful of uniform writes.
import * as THREE from 'three';
import { waterCoefficients, waterRadianceAtInfinity, combineMedium } from './water_model.js';

// Vehicle lamps, in the same relative units as the scene's daylight (hemisphere 1.5 + directional 1.6 at the
// surface, three's physical light units: an irradiance of 1 is "1 lux" of this scale). The lamp is a vehicle
// parameter and every number below is provisional (docs/reference/x1-measurement-checklist.md has no lamp item
// measured yet): research gives "several thousand lumens, 120-160 degree beams" for observation-class lamps
// (1,500-3,000 lm per lamp; the vendor claims 2 x 6,000 lm, 120 degrees for X1, unverified). The surface
// daylight the rig stands for is an assumption too (overcast, the low end of 10,000-100,000 lux).
export const LAMP_ASSUMED = Object.freeze({
  lumens: 4000,          // effective flux of one lamp at full power, in water
  beamHalfAngleDeg: 60,  // 120 degree flood; intensity falls smoothly from the axis to the edge (penumbra 1)
  appCandela: 260,       // what app.js sets on each SpotLight at full power
  surfaceLux: 10000      // what the daylight rig at the surface stands for
});
// Daylight rig at the surface, hemisphere + directional (fx/daylight.js UNDERWATER_DAYLIGHT).
const DAYLIGHT_RIG = 3.1;
// Solid angle of the smooth cone: smoothstep from the edge to the axis averages one half over the cone.
const LAMP_SOLID_ANGLE = Math.PI * (1 - Math.cos(LAMP_ASSUMED.beamHalfAngleDeg * Math.PI / 180));
// App candela -> scene units: on-axis intensity (lm / sr) over the app's value, times scene units per lux. About
// 0.003: each lamp is about 2,500 cd on its axis, so two at full power give about 5,000 lux at 1 m before water,
// half of overcast surface daylight.
// The first optics calibration (0.03) made the lamps ten times brighter than this relative to daylight: lamp-lit
// subjects outshone daylight 7-150 times at 1 m and up to 18 times at 2 m and clipped, while footage shows colour
// coming back only within about 1 m (research_notes/洋流與波浪對ROV作業/real_dive_footage.md §2.4);
// docs/design/lamp-exposure/.
export const LAMP_SCALE = LAMP_ASSUMED.lumens / LAMP_SOLID_ANGLE / LAMP_ASSUMED.appCandela *
  DAYLIGHT_RIG / LAMP_ASSUMED.surfaceLux;
// Fraction of scattered light that returns towards the camera, for daylight and for the lamps. The lamp value sets
// the veil relative to the lamp-lit subjects (both scale with lamp power), which was tuned on the review shots and is
// kept: with a phase of 0.0025 (Petzold-type particles near 180 degrees, about 0.002-0.005 per steradian) the
// single-scatter integral here, with the lamps at the lens and the near-lamp 1/d^2 limited at 0.5 m, buries a hull at
// 1 m in 4 m water (docs/design/lamp-exposure/README.md).
export const DAYLIGHT_PHASE = 0.015;
const LAMP_PHASE = 0.00025;
// Daylight reaching the surface, as the radiance factor used by the in-scatter integral.
const SURFACE_DAYLIGHT = new THREE.Color(0.93, 1.0, 1.0).multiplyScalar(3.1);
// Generic soft LED flood: a wide beam without a hard spot edge (research: 120-160 degree beams).
const LAMP_HALF_ANGLE = LAMP_ASSUMED.beamHalfAngleDeg * Math.PI / 180;
// Full penumbra: intensity falls smoothly from the beam axis to the 60 degree edge, so the near-field pool
// has a readable hot centre instead of a flat disc.
const LAMP_PENUMBRA = 1.0;
const MAX_LAMPS = 2;
// Multiple scattering: in dense water (a silt-out) the lamp light diffuses into a glowing cloud around the
// vehicle that single scattering misses, since extinction then kills the single-scatter path within
// centimetres. Empirical: lamp power x single-scatter albedo b/c x (1 - exp(-0.3 c))^3, so it is negligible in
// ordinary water (c below about 1/m) and saturates in a silt-out. Calibrated against main's silt look
// (docs/design/silt/after_onboard_lamps_full.jpg: grey-brown near white-out with the lamps full). Like the veil it
// scales with lamp power, so its ratio to the lamp-lit subjects is kept when the lamp scale changes (keeping its
// absolute level instead fogged a hull at 1 m in 4 m water, docs/design/lamp-exposure/README.md).
const LAMP_GLOW = 0.007;
const LAMP_REFRESH_FRAMES = 30;

export const waterUniforms = {
  uWaterC: { value: new THREE.Vector3(0.6, 0.33, 0.3) },
  uWaterKd: { value: new THREE.Vector3(0.4, 0.15, 0.13) },
  uWaterB: { value: new THREE.Vector3(0.25, 0.25, 0.25) },
  uWaterSun: { value: new THREE.Vector3() },
  uWaterTime: { value: 0 },
  uWaterBeauty: { value: 0 },
  uLampScale: { value: LAMP_SCALE },
  uLampCount: { value: 0 },
  uLampPos: { value: [new THREE.Vector3(), new THREE.Vector3()] },
  uLampDir: { value: [new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 0, -1)] },
  uLampColor: { value: [new THREE.Vector3(), new THREE.Vector3()] },
  uLampCone: { value: new THREE.Vector2(0.5, 0.9) },
  uLampGlow: { value: new THREE.Vector3() },
  // Aerial haze for paths entirely above water (rgb horizon radiance, w = 1 / haze distance); set from
  // fx/daylight.js only while the camera is above water, zero otherwise.
  uAirHaze: { value: new THREE.Vector4() }
};

// Uniform declarations and the light-path functions. World space throughout; `cameraPosition` is three's.
export const WATER_COMMON = /* glsl */ `
  uniform vec3 uWaterC;
  uniform vec3 uWaterKd;
  uniform vec3 uWaterB;
  uniform vec3 uWaterSun;
  uniform float uWaterTime;
  uniform float uWaterBeauty;
  uniform float uLampScale;
  uniform float uLampCount;
  uniform vec3 uLampPos[${MAX_LAMPS}];
  uniform vec3 uLampDir[${MAX_LAMPS}];
  uniform vec3 uLampColor[${MAX_LAMPS}];
  uniform vec2 uLampCone;
  uniform vec3 uLampGlow;
  uniform vec4 uAirHaze;

  // Daylight left after travelling from the surface down to a world point.
  vec3 waterDaylight(vec3 world) {
    return exp(-uWaterKd * max(0.0, -world.y));
  }
  // The underwater part of the segment from the camera to a point: where it starts and how long it is.
  float waterSegment(vec3 eye, vec3 world, out vec3 origin, out vec3 dir) {
    vec3 span = world - eye;
    float total = length(span);
    dir = span / max(total, 1e-4);
    origin = eye;
    if (eye.y >= 0.0 && world.y >= 0.0) return 0.0;
    if (eye.y >= 0.0) {
      float enter = eye.y / max(eye.y - world.y, 1e-4);
      origin = eye + span * enter;
      return total * (1.0 - enter);
    }
    if (world.y >= 0.0) return total * (-eye.y) / max(world.y - eye.y, 1e-4);
    return total;
  }
  // Daylight scattered into the ray: b * E(z0) * (1 - exp(-(c - Kd u) L)) / (c - Kd u), per channel.
  // An infinite ray gives the water colour seen in that direction, so distant objects end in exactly it.
  vec3 waterInscatter(vec3 origin, vec3 dir, float len) {
    vec3 k = max(uWaterC - uWaterKd * dir.y, vec3(0.02));
    return uWaterSun * uWaterB * waterDaylight(origin) * (1.0 - exp(-k * len)) / k;
  }
  // Lamp light scattered back into the camera (backscatter): quadratic sample spacing puts most samples
  // in the first metres where the lamp is bright. Inverse-square, beam cone and extinction both ways.
  vec3 lampInscatter(vec3 origin, vec3 dir, float len) {
    if (uLampCount < 0.5) return vec3(0.0);
    float range = min(len, 14.0);
    vec3 sum = vec3(0.0);
    for (int i = 0; i < 8; i++) {
      float t0 = float(i) / 8.0;
      float t1 = float(i + 1) / 8.0;
      float s0 = range * t0 * t0;
      float s1 = range * t1 * t1;
      float s = 0.5 * (s0 + s1);
      vec3 p = origin + dir * s;
      for (int j = 0; j < ${MAX_LAMPS}; j++) {
        if (float(j) >= uLampCount) break;
        vec3 ray = p - uLampPos[j];
        float d2 = max(dot(ray, ray), 0.25);
        float d = sqrt(d2);
        float spot = smoothstep(uLampCone.x, uLampCone.y, dot(ray / d, uLampDir[j]));
        sum += uLampColor[j] * (spot * (s1 - s0) / d2) * exp(-uWaterC * (d + s));
      }
    }
    // Plus the multiply scattered glow of the lamps in dense water (see lampGlow()), along the same path.
    return sum * uWaterB * ${LAMP_PHASE.toFixed(4)} + uLampGlow * (1.0 - exp(-uWaterC * len));
  }
  // Direct signal attenuation from a surface to the camera plus everything scattered into that path.
  vec3 waterApply(vec3 color, vec3 world) {
    vec3 origin;
    vec3 dir;
    float len = waterSegment(cameraPosition, world, origin, dir);
    if (len <= 0.0) {
      if (uAirHaze.w <= 0.0) return color;
      return mix(color, uAirHaze.rgb, 1.0 - exp(-length(world - cameraPosition) * uAirHaze.w));
    }
    return color * exp(-uWaterC * len) + waterInscatter(origin, dir, len) + lampInscatter(origin, dir, len);
  }
`;

// Adds the shared uniforms to a compiled shader (onBeforeCompile) or a ShaderMaterial uniforms object.
export function shareWaterUniforms(uniforms) {
  return Object.assign(uniforms, waterUniforms);
}

const lampCache = new WeakMap();
const lampDefaults = new WeakMap();
const scratch = new THREE.Vector3();
const target = new THREE.Vector3();

function findLamps(scene) {
  let cache = lampCache.get(scene);
  if (cache && cache.age++ < LAMP_REFRESH_FRAMES) return cache.lights;
  const lights = [];
  const beams = [];
  scene.traverse(function collect(object) {
    if (object.isSpotLight) lights.push(object);
    if (object.userData.legacyBeam) beams.push(object);
  });
  cache = { lights, beams, age: 0 };
  lampCache.set(scene, cache);
  return lights;
}

// Physical falloff for every vehicle lamp while optics are active; the legacy look keeps its own values.
function configureLamp(light, physical) {
  if (!lampDefaults.has(light)) {
    lampDefaults.set(light, { decay: light.decay, distance: light.distance, angle: light.angle,
      penumbra: light.penumbra });
  }
  const values = physical
    ? { decay: 2, distance: 0, angle: LAMP_HALF_ANGLE, penumbra: LAMP_PENUMBRA }
    : lampDefaults.get(light);
  light.decay = values.decay;
  light.distance = values.distance;
  light.angle = values.angle;
  light.penumbra = values.penumbra;
}

// The app's additive beam cones stand in for scattering in the legacy look; with optics the lamp
// backscatter integral already shows the beam (third-person views), so the cones are hidden for the render.
// Returns a function that restores their visibility.
export function hideLegacyBeams(scene) {
  const hidden = (lampCache.get(scene)?.beams || []).filter(function shown(beam) {
    return beam.visible;
  });
  for (const beam of hidden) beam.visible = false;
  return function restoreBeams() {
    for (const beam of hidden) beam.visible = true;
  };
}

// Restores the lamps' legacy falloff (low quality or automatic fallback).
export function releaseLamps(scene) {
  for (const light of lampCache.get(scene)?.lights || []) {
    if (lampDefaults.has(light)) configureLamp(light, false);
  }
}

function updateLamps(scene) {
  const lamps = findLamps(scene)
    .filter(function lit(light) {
      return light.visible && light.intensity > 0;
    })
    .sort(function brighter(a, b) {
      return b.intensity - a.intensity;
    });
  for (const light of findLamps(scene)) configureLamp(light, true);
  const count = Math.min(MAX_LAMPS, lamps.length);
  for (let i = 0; i < count; i++) {
    const light = lamps[i];
    light.getWorldPosition(waterUniforms.uLampPos.value[i]);
    light.target.getWorldPosition(target);
    waterUniforms.uLampDir.value[i].copy(target).sub(waterUniforms.uLampPos.value[i]).normalize();
    scratch.set(light.color.r, light.color.g, light.color.b).multiplyScalar(light.intensity * LAMP_SCALE);
    waterUniforms.uLampColor.value[i].copy(scratch);
  }
  waterUniforms.uLampCount.value = count;
  waterUniforms.uLampCone.value.set(Math.cos(LAMP_HALF_ANGLE), Math.cos(LAMP_HALF_ANGLE * (1 - LAMP_PENUMBRA)));
  return lamps;
}

const contributors = new Set();

// Clean-water visibility for the frame. The silt module publishes it (scene.userData.waterVisibility) together
// with its sediment as a medium contributor; without it, fall back to the scene fog (linear fog: far / 1.35,
// exponential fog with near = -c: 4.8 / c).
function baseVisibility(scene) {
  const published = scene.userData.waterVisibility;
  if (Number.isFinite(published) && published > 0) return published;
  const fog = scene.fog;
  if (!fog?.isFog) return 12;
  if (fog.near < 0) return 4.8 / -fog.near;
  return fog.far / 1.35;
}

// Registers an extra participating medium (e.g. the silt module's suspended sediment at the camera).
// `contributor({scene, camera, water})` is called once per optics frame and returns null or
// {extinction, scattering, local}: 1/m, a number or [r, g, b]. Extinction adds to the beam attenuation c of
// every light path, scattering adds to the backscatter/in-scatter coefficient b (per channel = coloured
// backscatter); the absorbed remainder also dims daylight on its way down unless `local` is set (a cloud
// around the camera rather than a property of the whole water column). Returns a remover.
export function addMediumContributor(contributor) {
  contributors.add(contributor);
  return function removeMediumContributor() {
    contributors.delete(contributor);
  };
}

function mediumContributions(scene, camera, water) {
  const list = [];
  for (const contributor of contributors) {
    try {
      list.push(contributor({ scene, camera, water }));
    } catch (error) {
      console.warn('Medium contributor failed', error);
    }
  }
  return list;
}

// Visibility comes from the scene fog the app already derives from the scenario and silt, so the existing
// "real visibility" training toggle keeps working; registered medium contributors add on top.
export function updateWaterOptics(scene, { beauty = false, camera = null } = {}) {
  const visibility = baseVisibility(scene);
  const silt = scene.userData.waterSiltTint ?? scene.userData.waterState?.silt ?? 0;
  const base = waterCoefficients(visibility, silt, scene.userData.waterType);
  const water = combineMedium(base, mediumContributions(scene, camera, base));
  waterUniforms.uWaterC.value.fromArray(water.c);
  waterUniforms.uWaterKd.value.fromArray(water.kd);
  waterUniforms.uWaterB.value.fromArray(water.b);
  waterUniforms.uWaterSun.value.set(SURFACE_DAYLIGHT.r, SURFACE_DAYLIGHT.g, SURFACE_DAYLIGHT.b)
    .multiplyScalar(DAYLIGHT_PHASE);
  waterUniforms.uWaterTime.value = performance.now() / 1000;
  waterUniforms.uWaterBeauty.value = beauty ? 1 : 0;
  const haze = camera && camera.position.y > 0 ? scene.userData.daylightHaze : null;
  if (haze) waterUniforms.uAirHaze.value.set(haze.colour.x, haze.colour.y, haze.colour.z, haze.rate);
  else waterUniforms.uAirHaze.value.set(0, 0, 0, 0);
  const lamps = updateLamps(scene);
  updateLampGlow(water);
  return { water, lamps };
}

function updateLampGlow(water) {
  const power = new THREE.Vector3();
  for (let i = 0; i < waterUniforms.uLampCount.value; i++) power.add(waterUniforms.uLampColor.value[i]);
  const channel = [power.x, power.y, power.z].map(function glow(lamp, i) {
    const c = water.c[i];
    const dense = (1 - Math.exp(-0.3 * c)) ** 3;
    return lamp * (water.b[i] / c) * dense * LAMP_GLOW;
  });
  waterUniforms.uLampGlow.value.fromArray(channel);
}

// Horizontal water colour at a depth (linear), for three's own fog on materials outside the optics shaders
// (lines, unlit helpers), so they fade into the same colour as the background.
export function horizontalWaterColour(depth, water, out = new THREE.Color()) {
  const radiance = waterRadianceAtInfinity(depth, 0, water);
  const r = radiance[0] * SURFACE_DAYLIGHT.r * DAYLIGHT_PHASE;
  const g = radiance[1] * SURFACE_DAYLIGHT.g * DAYLIGHT_PHASE;
  const b = radiance[2] * SURFACE_DAYLIGHT.b * DAYLIGHT_PHASE;
  return out.setRGB(r, g, b, THREE.LinearSRGBColorSpace);
}

// Full-screen water colour behind everything: the in-scatter integral for an infinite ray in each pixel's
// direction. It replaces the flat clear colour, so there is no horizon edge and no black band.
export function createWaterBackground() {
  const material = new THREE.ShaderMaterial({
    uniforms: shareWaterUniforms({ uInverseViewProjection: { value: new THREE.Matrix4() } }),
    depthTest: false,
    depthWrite: false,
    fog: false,
    vertexShader: /* glsl */ `
      uniform mat4 uInverseViewProjection;
      varying vec3 vFar;
      void main() {
        vec4 far = uInverseViewProjection * vec4(position.xy, 1.0, 1.0);
        vFar = far.xyz / far.w;
        gl_Position = vec4(position.xy, 1.0, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      ${WATER_COMMON}
      varying vec3 vFar;
      void main() {
        vec3 dir = normalize(vFar - cameraPosition);
        float len = 1e4;
        if (dir.y > 0.0) len = min(len, -cameraPosition.y / dir.y);
        vec3 water = waterInscatter(cameraPosition, dir, len) + lampInscatter(cameraPosition, dir, len);
        gl_FragColor = vec4(water, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
  mesh.name = 'water-background';
  mesh.frustumCulled = false;
  mesh.renderOrder = -1e9;
  mesh.userData.observationIgnore = true;
  mesh.onBeforeRender = function aimBackground(renderer, scene, camera) {
    material.uniforms.uInverseViewProjection.value
      .multiplyMatrices(camera.matrixWorld, camera.projectionMatrixInverse);
  };
  return mesh;
}
