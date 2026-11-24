import * as THREE from 'three';
// Attenuate sunlight/sky at each surface, not at the spectator camera. Vehicle
// spotlights are deliberately left untouched by this natural-light extinction.
export function applyUnderwaterLighting(scene){
  scene.traverse(object=>{
    if(!object.isMesh)return;
    for(const material of Array.isArray(object.material)?object.material:[object.material]){
      if(!material?.isMeshStandardMaterial||material.userData.waterLighting)return;
      material.userData.waterLighting=true;
      const previous=material.onBeforeCompile;
      material.onBeforeCompile=function(shader,renderer){
        previous.call(this,shader,renderer);
        shader.vertexShader='varying float vWaterDepth;\n'+shader.vertexShader;
        shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>',`vec4 waterLocal = vec4(transformed, 1.0);
          #ifdef USE_INSTANCING
          waterLocal = instanceMatrix * waterLocal;
          #endif
          vWaterDepth = max(0.0, -(modelMatrix * waterLocal).y);
          #include <project_vertex>`);
        shader.fragmentShader='varying float vWaterDepth;\n'+shader.fragmentShader;
        const chunk=THREE.ShaderChunk.lights_fragment_begin
          .replace('getDirectionalLightInfo( directionalLight, directLight );','getDirectionalLightInfo( directionalLight, directLight ); directLight.color *= 0.06 + 0.94 * exp(-vWaterDepth / 10.0);')
          .replace('getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal )','getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal ) * (0.06 + 0.94 * exp(-vWaterDepth / 10.0))');
        shader.fragmentShader=shader.fragmentShader.replace('#include <lights_fragment_begin>',chunk);
      };
      const oldKey=material.customProgramCacheKey.bind(material);
      material.customProgramCacheKey=()=>oldKey()+'|water-depth-v1';material.needsUpdate=true;
    }
  });
}
