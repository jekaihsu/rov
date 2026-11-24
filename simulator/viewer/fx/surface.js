// The sea surface seen from below in the optics tiers: Snell's window (critical angle for n = 1.333) with
// moving normals, total internal reflection of the water below outside it, and the same water path to the
// camera as every other surface, so the surface fades into the water colour without a hard horizon.
// Beautify adds faint sun shafts in shallow water. Above water, or in the legacy look, the app's material
// is restored unchanged.
import * as THREE from 'three';
import { WATER_COMMON, shareWaterUniforms, DAYLIGHT_PHASE, WATER_BACKGROUND_ORDER } from './water_optics.js';

const surfaces = new WeakMap();
const forward = new THREE.Vector3();
// cos of the critical angle: asin(1 / 1.333) = 48.6 degrees from the vertical.
const CRITICAL_COS = Math.cos(Math.asin(1 / 1.333)).toFixed(4);

function surfaceMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: shareWaterUniforms({}),
    side: THREE.DoubleSide,
    depthWrite: false,
    fog: false,
    vertexShader: /* glsl */ `
      varying vec3 vWorld;
      void main() {
        vWorld = (modelMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * viewMatrix * vec4(vWorld, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      ${WATER_COMMON}
      varying vec3 vWorld;
      void main() {
        vec3 view = normalize(vWorld - cameraPosition);
        vec3 normal = normalize(vec3(0.035 * cos(vWorld.x * 1.2 + uWaterTime),
                                     1.0,
                                     0.025 * sin(vWorld.z * 1.7 - uWaterTime * 0.7)));
        float incidence = clamp(dot(view, normal), 0.0, 1.0);
        float window = smoothstep(${CRITICAL_COS} - 0.02, ${CRITICAL_COS} + 0.02, incidence);
        float fresnel = 0.0204 + 0.9796 * pow(1.0 - incidence, 5.0);
        // Sky and sun through the window: radiance of the order of the surface irradiance over pi.
        vec3 sky = uWaterSun / ${DAYLIGHT_PHASE.toFixed(4)} * (0.18 + 0.2 * incidence);
        // Outside the window the surface mirrors the water below it.
        vec3 below = reflect(view, normal);
        vec3 mirrored = waterInscatter(vWorld - vec3(0.0, 0.01, 0.0), below, 1e4);
        vec3 color = mix(mirrored, sky * (1.0 - fresnel), window);
        gl_FragColor = vec4(waterApply(color, vWorld - vec3(0.0, 0.001, 0.0)), 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`
  });
}

// Beautify: soft vertical bands of scattered sunlight hanging below the surface, fading with depth.
function shaftMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    uniforms: shareWaterUniforms({}),
    vertexShader: /* glsl */ `
      varying vec2 vCoord;
      varying vec3 vWorld;
      void main() {
        vCoord = uv;
        vWorld = (modelMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * viewMatrix * vec4(vWorld, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      ${WATER_COMMON}
      varying vec2 vCoord;
      varying vec3 vWorld;
      void main() {
        float band = pow(max(0.0, sin(vCoord.x * 40.0 + sin(vCoord.x * 7.0 + uWaterTime * 0.15) * 2.0)), 10.0);
        band *= 0.6 + 0.4 * sin(vCoord.x * 13.0 - uWaterTime * 0.1);
        float fade = smoothstep(0.0, 0.35, vCoord.y) * (1.0 - smoothstep(0.75, 1.0, vCoord.y));
        vec3 light = uWaterSun * uWaterB * waterDaylight(vWorld) * 12.0;
        vec3 origin;
        vec3 dir;
        float len = waterSegment(cameraPosition, vWorld, origin, dir);
        gl_FragColor = vec4(light * band * fade * exp(-uWaterC * len), 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`
  });
}

function install(surface, scene) {
  const material = surfaceMaterial();
  const shafts = new THREE.Mesh(new THREE.PlaneGeometry(40, 16), shaftMaterial());
  shafts.name = 'shallow-sun-shafts';
  shafts.userData.observationIgnore = true;
  shafts.frustumCulled = false;
  scene.add(shafts);
  const data = { original: surface.material, originalIgnore: surface.userData.observationIgnore,
    originalOrder: surface.renderOrder, material, shafts };
  surfaces.set(surface, data);
  return data;
}

export function updateWaterSurface(surface, camera, scene, low, beauty = false) {
  if (!surface) return;
  let data = surfaces.get(surface);
  if (!data && low) return;
  if (!data) data = install(surface, scene);
  const below = camera.position.y < 0;
  const depth = -camera.position.y;
  // Below ~0.4 m the 800 m DoubleSide optics plane intersects the near frustum and fills the
  // onboard view with a solid water-colour triangle (open_water at 0.1 m). Skip optics there.
  const deepEnough = depth > 0.4;
  data.shafts.visible = !low && beauty && below && deepEnough && depth < 15;
  if (data.shafts.visible) {
    // Hang the bands ahead of the camera, facing it about the vertical axis only.
    camera.getWorldDirection(forward);
    forward.y = 0;
    if (forward.lengthSq() < 1e-6) forward.set(0, 0, -1);
    forward.normalize();
    data.shafts.position.copy(camera.position).addScaledVector(forward, 9);
    data.shafts.position.y = -8;
    data.shafts.rotation.set(0, Math.atan2(forward.x, forward.z), 0);
  }
  const optics = !low && below && deepEnough;
  surface.material = optics ? data.material : data.original;
  surface.userData.observationIgnore = optics ? true : data.originalIgnore;
  // The optics surface writes no depth: draw it after the depth-tested water background, not under it.
  surface.renderOrder = optics ? WATER_BACKGROUND_ORDER + 1 : data.originalOrder;
  if (below && !deepEnough) surface.visible = false;
}

export function disposeWaterSurface(surface) {
  const data = surfaces.get(surface);
  if (!data) return;
  surface.material = data.original;
  surface.userData.observationIgnore = data.originalIgnore;
  surface.renderOrder = data.originalOrder;
  data.material.dispose();
  data.shafts.removeFromParent();
  data.shafts.geometry.dispose();
  data.shafts.material.dispose();
  surfaces.delete(surface);
}
