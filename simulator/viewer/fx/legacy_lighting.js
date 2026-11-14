// Low-quality compatibility path: retain the original depth shader and per-frame work.
import * as THREE from 'three';
const originals = new WeakMap();

export function rememberWaterMaterial(material) {
  if (!originals.has(material)) {
    originals.set(material, { compile: material.onBeforeCompile, key: material.customProgramCacheKey });
  }
}

export function restoreWaterMaterials(scene) {
  scene.traverse(function restore(object) {
    if (!object.isMesh) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      const original = originals.get(material);
      if (!original) continue;
      material.onBeforeCompile = original.compile;
      material.customProgramCacheKey = original.key;
      material.userData.waterLighting = false;
      delete material.userData.waterUniforms;
      material.needsUpdate = true;
    }
  });
}

export function applyLegacyLighting(scene) {
  scene.traverse(function installLegacy(object) {
    if (!object.isMesh) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (!material?.isMeshStandardMaterial || material.userData.waterLighting) return;
      rememberWaterMaterial(material);
      material.userData.waterLighting = true;
      const previous = material.onBeforeCompile;
      material.onBeforeCompile = function compileLegacy(shader, renderer) {
        previous.call(this, shader, renderer);
        shader.vertexShader = 'varying float vWaterDepth;\n' + shader.vertexShader;
        shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', `
          vec4 waterLocal = vec4(transformed, 1.0);
          #ifdef USE_INSTANCING
          waterLocal = instanceMatrix * waterLocal;
          #endif
          vWaterDepth = max(0.0, -(modelMatrix * waterLocal).y);
          #include <project_vertex>`);
        shader.fragmentShader = 'varying float vWaterDepth;\n' + shader.fragmentShader;
        const directional = 'getDirectionalLightInfo( directionalLight, directLight );';
        const hemisphere = 'getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal )';
        const attenuation = '(0.06 + 0.94 * exp(-vWaterDepth / 10.0))';
        const chunk = THREE.ShaderChunk.lights_fragment_begin
          .replace(directional, directional + ' directLight.color *= ' + attenuation + ';')
          .replace(hemisphere, hemisphere + ' * ' + attenuation);
        shader.fragmentShader = shader.fragmentShader.replace('#include <lights_fragment_begin>', chunk);
      };
      const oldKey = material.customProgramCacheKey.bind(material);
      material.customProgramCacheKey = function legacyProgramKey() {
        return oldKey() + '|water-depth-v1';
      };
      material.needsUpdate = true;
    }
  });
}
