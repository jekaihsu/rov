// Low-quality compatibility path: retain the original depth shader and per-frame work.
import * as THREE from 'three';
import {METERING} from './metering.js';
import {LAMP_SCALE} from './water_optics.js';

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
        const spotlight = 'getSpotLightInfo( spotLight, geometryPosition, directLight );';
        // Use the calibrated lamp/daylight ratio on the single-pass tier too. Unscaled candela
        // clips the whole footprint on concrete, hiding station marks and nearby metalwork.
        // This tier has no metering pass. Approximate dark adaptation on the lamp term only,
        // so unlit deep water stays dark. The working light still obeys its view cone and falloff.
        const deep = 'smoothstep(35.0, 100.0, -cameraPosition.y)';
        // In opaque water even mid-depth surfaces receive very little daylight. The existing
        // exponential fog still attenuates contrast on the entire return path after lighting.
        const adaptation = `
          float darkWater = ${deep};
          #if defined(USE_FOG) && !defined(FOG_EXP2)
            darkWater = max(darkWater, smoothstep(2.4, 6.0, -fogNear));
          #endif
        `;
        // The post-processed path meters linear radiance before display. A fixed working gain
        // here keeps a nearby anode readable without a metering texture or a second pass.
        const workingGain = METERING.reference * .4;
        const lampGain = `mix(${workingGain.toFixed(1)}, ${METERING.reference.toFixed(1)}, darkWater)`;
        const lamp = `${spotlight} directLight.color *= ${LAMP_SCALE.toFixed(8)} * ${lampGain};`;
        const chunk = THREE.ShaderChunk.lights_fragment_begin
          .replace(spotlight, lamp)
          .replace(directional, directional + ' directLight.color *= ' + attenuation + ';')
          .replace(hemisphere, hemisphere + ' * ' + attenuation);
        shader.fragmentShader = shader.fragmentShader.replace('#include <lights_fragment_begin>', adaptation + chunk)
          .replace('#include <tonemapping_fragment>', `
            float peak = max(gl_FragColor.r, max(gl_FragColor.g, gl_FragColor.b));
            gl_FragColor.rgb /= 1.0 + peak;
            #include <tonemapping_fragment>`);
      };
      const oldKey = material.customProgramCacheKey.bind(material);
      material.customProgramCacheKey = function legacyProgramKey() {
        return oldKey() + '|water-depth-v2';
      };
      material.needsUpdate = true;
    }
  });
}
