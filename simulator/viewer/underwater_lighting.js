// Underwater light paths in every MeshStandardMaterial of the main scene.
// Optics tiers: daylight is attenuated per channel from the surface down to each surface point, lamp light
// from the lamp to the surface, and the result again from the surface to the camera, with daylight and
// lamp light scattered into that last path (fx/water_optics.js). Low quality, and automatic quality once it
// has dropped post-processing, keep the original single-coefficient depth shader at its original cost.
// Unlit helpers (markers, lines, sprites) are made exposure-neutral so camera gain does not wash them out.
import * as THREE from 'three';
import { applyLegacyLighting, rememberWaterMaterial, restoreWaterMaterials } from './fx/legacy_lighting.js';
import { WATER_COMMON, shareWaterUniforms, releaseLamps } from './fx/water_optics.js';
import { neutraliseExposure, restoreExposureNeutral } from './fx/exposure.js';
import { renderQualityState } from './render_quality.js';

const modes = new WeakMap();
const PROGRAM_KEY = '|water-optics-v3|';

const directional = 'getDirectionalLightInfo( directionalLight, directLight );';
const hemisphere = 'getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal )';
const ambient = 'getAmbientLightIrradiance( ambientLightColor )';
const spotlight = 'getSpotLightInfo( spotLight, geometryPosition, directLight );';

// True when the frame uses the legacy look: low quality, or automatic quality after its first fallback step.
export function legacyWaterLook(renderer) {
  const quality = renderQualityState(renderer);
  return ['performance', 'low'].includes(quality?.mode) || !!quality?.effectsSuppressed;
}

function lightLoop() {
  return THREE.ShaderChunk.lights_fragment_begin
    .replace(directional, `${directional} directLight.color *= waterDaylight(vWaterWorld);`)
    .replace(hemisphere, `${hemisphere} * waterDaylight(vWaterWorld)`)
    .replace(ambient, `${ambient} * waterDaylight(vWaterWorld)`)
    .replace(spotlight, `${spotlight}
      directLight.color *= uLampScale * exp(-uWaterC * length(spotLight.position - geometryPosition));`);
}

const DETAIL_NORMAL = `
  #include <normal_fragment_maps>
  float detailHeight = sin(vWaterWorld.x * 45.0) * sin(vWaterWorld.z * 37.0) * 0.0015;
  vec3 q0 = dFdx(-vViewPosition);
  vec3 q1 = dFdy(-vViewPosition);
  vec3 r1 = cross(q1, normal);
  vec3 r2 = cross(normal, q0);
  float determinant = dot(q0, r1);
  vec3 gradient = sign(determinant) * (dFdx(detailHeight) * r1 + dFdy(detailHeight) * r2);
  normal = normalize(max(abs(determinant), 0.000001) * normal - gradient);
`;

// Beautify only: moving caustic bands on upward-facing surfaces, fading with daylight.
const CAUSTICS = `
  #include <color_fragment>
  if (uWaterBeauty > 0.5) {
    vec2 p = vWaterWorld.xz;
    float a = sin(p.x * 3.2 + sin(p.y * 2.7 + uWaterTime * 0.5));
    float b = sin(p.y * 3.7 - sin(p.x * 2.2 - uWaterTime * 0.4));
    float caustic = pow(max(0.0, 1.0 - abs(a + b)), 8.0);
    float up = clamp(dot(normalize(cross(dFdx(vWaterWorld), dFdy(vWaterWorld))), vec3(0.0, 1.0, 0.0)), 0.0, 1.0);
    diffuseColor.rgb *= 1.0 + caustic * 0.35 * up * waterDaylight(vWaterWorld).g;
  }
`;

const IBL_DEPTH = `
  #include <lights_fragment_maps>
  #if defined( RE_IndirectDiffuse )
    iblIrradiance *= waterDaylight(vWaterWorld);
  #endif
  #if defined( RE_IndirectSpecular )
    radiance *= waterDaylight(vWaterWorld);
    clearcoatRadiance *= waterDaylight(vWaterWorld);
  #endif
`;

function compileWater(shader, renderer, previous) {
  previous.call(this, shader, renderer);
  shareWaterUniforms(shader.uniforms);
  shader.vertexShader = 'varying vec3 vWaterWorld;\n' + shader.vertexShader.replace('#include <project_vertex>', `
    vec4 waterLocal = vec4(transformed, 1.0);
    #ifdef USE_INSTANCING
    waterLocal = instanceMatrix * waterLocal;
    #endif
    vWaterWorld = (modelMatrix * waterLocal).xyz;
    #include <project_vertex>`);
  let fragment = 'varying vec3 vWaterWorld;\n' + WATER_COMMON + shader.fragmentShader;
  fragment = fragment.replace('#include <lights_fragment_begin>', lightLoop());
  fragment = fragment.replace('#include <lights_fragment_maps>', IBL_DEPTH);
  fragment = fragment.replace('#include <color_fragment>', CAUSTICS);
  if (this.userData.waterDetail) fragment = fragment.replace('#include <normal_fragment_maps>', DETAIL_NORMAL);
  // The water path replaces three's fog; it runs before tone mapping and the output transfer.
  fragment = fragment.replace('#include <fog_fragment>', '');
  fragment = fragment.replace('#include <tonemapping_fragment>', `
    gl_FragColor.rgb = waterApply(gl_FragColor.rgb, vWaterWorld);
    #include <tonemapping_fragment>`);
  shader.fragmentShader = fragment;
}

function installMaterial(material, detail) {
  if (material.userData.waterDetail !== detail) {
    material.userData.waterDetail = detail;
    material.needsUpdate = true;
  }
  if (material.userData.waterLighting) return;
  rememberWaterMaterial(material);
  material.userData.waterLighting = true;
  const previous = material.onBeforeCompile;
  material.onBeforeCompile = function compile(shader, activeRenderer) {
    compileWater.call(this, shader, activeRenderer, previous);
  };
  const oldKey = material.customProgramCacheKey.bind(material);
  material.customProgramCacheKey = function waterProgramKey() {
    return oldKey() + PROGRAM_KEY + material.userData.waterDetail;
  };
  material.needsUpdate = true;
}

export function applyUnderwaterLighting(scene, state, renderer) {
  const low = legacyWaterLook(renderer);
  scene.userData.waterCurrent = state?.current_here;
  scene.userData.waterState = state;
  if (modes.get(scene) !== low) {
    restoreWaterMaterials(scene);
    restoreExposureNeutral();
    if (low) releaseLamps(scene);
    modes.set(scene, low);
  }
  if (low) return applyLegacyLighting(scene);
  const detail = ['high', 'ultra'].includes(renderQualityState(renderer)?.mode);
  scene.traverse(function installObject(object) {
    if (!object.material) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (material?.isMeshStandardMaterial && object.isMesh) installMaterial(material, detail);
      else if (material && !material.isShaderMaterial && !material.isMeshStandardMaterial) neutraliseExposure(material);
    }
  });
}
