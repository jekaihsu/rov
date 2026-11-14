// Surface-local sunlight absorption and lamp/return-path extinction. Coefficients are
// provisional visualization assumptions; low quality retains the original lighting cost.
import * as THREE from 'three';
import { applyLegacyLighting, rememberWaterMaterial, restoreWaterMaterials } from './fx/legacy_lighting.js';
import { renderQualityState } from './render_quality.js';

const modes = new WeakMap();

const directional = 'getDirectionalLightInfo( directionalLight, directLight );';
const hemisphere = 'getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal )';
const spotlight = 'getSpotLightInfo( spotLight, geometryPosition, directLight );';
const natural = '(vec3(0.003) + vec3(0.997) * exp(-vWaterDepth * vec3(0.24, 0.065, 0.035)))';
const legacy = '(0.06 + 0.94 * exp(-vWaterDepth / 10.0))';

function compileWater(shader, renderer, previous) {
  previous.call(this, shader, renderer);
  shader.vertexShader = 'varying vec3 vWaterWorld; varying float vWaterDepth;\n' + shader.vertexShader;
  shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', `
    vec4 waterLocal = vec4(transformed, 1.0);
    #ifdef USE_INSTANCING
    waterLocal = instanceMatrix * waterLocal;
    #endif
    vWaterWorld = (modelMatrix * waterLocal).xyz;
    vWaterDepth = max(0.0, -vWaterWorld.y);
    #include <project_vertex>`);
  shader.fragmentShader = `varying vec3 vWaterWorld;
    uniform float waterTime; uniform float waterBeauty; varying float vWaterDepth;
    ` + shader.fragmentShader;
  const low = this.userData.waterLow;
  const absorption = low ? legacy : natural;
  let lights = THREE.ShaderChunk.lights_fragment_begin
    .replace(directional, `${directional} directLight.color *= ${absorption};`)
    .replace(hemisphere, `${hemisphere} * ${absorption}`);
  if (!low) {
    lights = lights.replace(spotlight, `${spotlight}
      directLight.color *= exp(-length(spotLight.position - geometryPosition) * vec3(0.18, 0.045, 0.025));`);
  }
  shader.fragmentShader = shader.fragmentShader.replace('#include <lights_fragment_begin>', lights);
  if (low) return;
  const uniforms = this.userData.waterUniforms = {
    time: { value: performance.now() / 1000 },
    beauty: { value: renderer?.userData?.underwaterPipeline?.enhancements ? 1 : 0 }
  };
  shader.uniforms.waterTime = uniforms.time;
  shader.uniforms.waterBeauty = uniforms.beauty;
  if (this.userData.waterDetail) {
    shader.fragmentShader = shader.fragmentShader.replace('#include <normal_fragment_maps>', `
      #include <normal_fragment_maps>
      float detailHeight = sin(vWaterWorld.x * 45.0) * sin(vWaterWorld.z * 37.0) * 0.0015;
      vec3 q0 = dFdx(-vViewPosition);
      vec3 q1 = dFdy(-vViewPosition);
      vec3 r1 = cross(q1, normal);
      vec3 r2 = cross(normal, q0);
      float determinant = dot(q0, r1);
      vec3 gradient = sign(determinant) * (dFdx(detailHeight) * r1 + dFdy(detailHeight) * r2);
      normal = normalize(max(abs(determinant), 0.000001) * normal - gradient);
    `);
  }
  shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', `
    #include <color_fragment>
    if (waterBeauty > 0.5) {
      vec2 p = vWaterWorld.xz;
      float a = sin(p.x * 3.2 + sin(p.y * 2.7 + waterTime * 0.5));
      float b = sin(p.y * 3.7 - sin(p.x * 2.2 - waterTime * 0.4));
      float caustic = pow(max(0.0, 1.0 - abs(a + b)), 8.0);
      diffuseColor.rgb *= 1.0 + caustic * 0.3 * exp(-vWaterDepth / 5.0);
    }`);
  // Independent extinction/backscatter, before tone mapping and output transfer.
  // fogFar carries existing scenario visibility and silt, including sub-metre ranges.
  shader.fragmentShader = shader.fragmentShader.replace('#include <fog_fragment>', '');
  shader.fragmentShader = shader.fragmentShader.replace('#include <tonemapping_fragment>', `
    #ifdef USE_FOG
    float waterDistance = length(vViewPosition);
    vec3 transmission = exp(-waterDistance * vec3(5.0, 3.2, 2.5) / max(fogFar, 0.05));
    float scatter = 1.0 - exp(-waterDistance * 3.0 / max(fogFar, 0.05));
    gl_FragColor.rgb = gl_FragColor.rgb * transmission + fogColor * scatter;
    #endif
    #include <tonemapping_fragment>`);
}

export function applyUnderwaterLighting(scene, state, renderer) {
  const mode = renderQualityState(renderer)?.mode;
  const low = ['performance', 'low'].includes(mode);
  const previousMode = modes.get(scene);
  if (previousMode !== low) {
    restoreWaterMaterials(scene);
    modes.set(scene, low);
  }
  if (low) return applyLegacyLighting(scene);
  const detail = ['high', 'ultra'].includes(mode);
  scene.userData.waterCurrent = state?.current_here;
  scene.userData.waterState = state;
  scene.traverse(function installMaterial(object) {
    if (!object.isMesh) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (!material?.isMeshStandardMaterial) continue;
      if (material.userData.waterLow !== low || material.userData.waterDetail !== detail) {
        material.userData.waterDetail = detail;
        material.userData.waterLow = low;
        material.needsUpdate = true;
      }
      if (material.userData.waterUniforms) {
        material.userData.waterUniforms.time.value = performance.now() / 1000;
        material.userData.waterUniforms.beauty.value = renderer?.userData?.underwaterPipeline?.enhancements ? 1 : 0;
      }
      if (material.userData.waterLighting) continue;
      rememberWaterMaterial(material);
      material.userData.waterLighting = true;
      const previous = material.onBeforeCompile;
      material.onBeforeCompile = function compile(shader, activeRenderer) {
        compileWater.call(this, shader, activeRenderer, previous);
      };
      const oldKey = material.customProgramCacheKey.bind(material);
      material.customProgramCacheKey = function waterProgramKey() {
        return oldKey() + '|water-path-v2|' + material.userData.waterLow + '|' + material.userData.waterDetail;
      };
      material.needsUpdate = true;
    }
  });
}
