// Scanned surface detail for the inspected structure's own topside above the water (site_topside.js): painted
// steel with the CC0 coating scan (paint luminance, rust breaking through near the splash zone), galvanised
// gratings that let the light through (alpha-tested perforated walkway) and diamond-plate deck. Sources and
// licence proof: models/CREDITS.md. The merged primitives get metre UVs from a planar projection on each
// vertex's dominant normal axis (metreUv), so every part shows the textures at their real scale.
//
//   const g = metreUv(new THREE.BoxGeometry(2, 0.1, 3));  mesh.material = topsideMaterial('grating', 'medium');
import * as THREE from 'three';
import {SCAN_MEAN, SCAN_TILE, scanTexture} from './scan_materials.js';

/** Planar UVs in metres (world-space geometry), projected along each vertex normal's dominant axis. */
export function metreUv(geometry) {
  const position = geometry.attributes.position;
  if (!geometry.attributes.normal) geometry.computeVertexNormals();
  const normal = geometry.attributes.normal;
  const uv = new Float32Array(position.count * 2);
  for (let i = 0; i < position.count; i++) {
    const nx = Math.abs(normal.getX(i));
    const ny = Math.abs(normal.getY(i));
    const nz = Math.abs(normal.getZ(i));
    const x = position.getX(i);
    const y = position.getY(i);
    const z = position.getZ(i);
    if (ny >= nx && ny >= nz) {
      uv[i * 2] = x;
      uv[i * 2 + 1] = -z;
    } else if (nx >= nz) {
      uv[i * 2] = z;
      uv[i * 2 + 1] = y;
    } else {
      uv[i * 2] = x;
      uv[i * 2 + 1] = y;
    }
  }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return geometry;
}

// Painted steel: the vertex colour is the paint; the scan's paint luminance shades it and its rust shows where
// the rust propensity exceeds a threshold that drops towards the splash zone (more breakdown near the sea).
const PAINT_MAP = `
  vec4 topTexel = texture2D(map, vMapUv);
`;
const PAINT_COLOUR = `
  #include <color_fragment>
  {
    float rustAt = mix(0.74, 0.96, smoothstep(1.5, 7.0, vTopY));
    float rust = smoothstep(rustAt, rustAt + 0.1, topTexel.a);
    float shade = mix(topTexel.g * ${(1 / SCAN_MEAN).toFixed(4)}, 1.0, smoothstep(0.02, 0.08, topTexel.a));
    diffuseColor.rgb = mix(diffuseColor.rgb * (0.75 + 0.25 * shade), topTexel.rgb, rust);
  }
`;

function paintMaterial(detail) {
  const material = new THREE.MeshStandardMaterial({vertexColors: true, roughness: 0.6, metalness: 0.15});
  if (detail === 'low') return material;
  const repeat = 1 / SCAN_TILE.coating;
  material.map = scanTexture('coating_c', {repeat}, function assignMap(texture) {
    material.map = texture;
  });
  material.normalMap = scanTexture('coating_n', {repeat}, function assignNormal(texture) {
    material.normalMap = texture;
  });
  material.onBeforeCompile = function compileTopsidePaint(shader) {
    shader.vertexShader = 'varying float vTopY;\n' + shader.vertexShader.replace('#include <project_vertex>',
      'vTopY = (modelMatrix * vec4(transformed, 1.0)).y;\n#include <project_vertex>');
    shader.fragmentShader = 'varying float vTopY;\n' + shader.fragmentShader
      .replace('#include <map_fragment>', PAINT_MAP)
      .replace('#include <color_fragment>', PAINT_COLOUR)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, texture2D(normalMap, vNormalMapUv).a, 0.6);`);
  };
  material.customProgramCacheKey = function topsidePaintKey() {
    return 'topside-paint-v1';
  };
  return material;
}

function gratingMaterial(detail) {
  // galvanised perforated walkway; double-sided so it reads from below, light passes through the holes
  const material = new THREE.MeshStandardMaterial({color: 0xd8dadb, roughness: 0.55, metalness: 0.45,
    alphaTest: 0.5, side: THREE.DoubleSide});
  const repeat = 1 / SCAN_TILE.grating;
  material.map = scanTexture('grating_c', {repeat, mask: true}, function assignMap(texture) {
    material.map = texture;
  });
  if (detail !== 'low') {
    material.normalMap = scanTexture('grating_n', {repeat}, function assignNormal(texture) {
      material.normalMap = texture;
    });
  }
  return material;
}

function plateMaterial(detail) {
  const material = new THREE.MeshStandardMaterial({color: 0xffffff, roughness: 0.5, metalness: 0.55});
  if (detail === 'low') {
    material.color.setHex(0x8d9196);
    return material;
  }
  const repeat = 1 / SCAN_TILE.plate;
  material.map = scanTexture('plate_c', {repeat}, function assignMap(texture) {
    material.map = texture;
  });
  material.normalMap = scanTexture('plate_n', {repeat}, function assignNormal(texture) {
    material.normalMap = texture;
  });
  return material;
}

/** Material for one topside surface kind: 'paint' (vertex-coloured steel), 'grating' or 'plate'. */
export function topsideMaterial(kind, detail = 'medium') {
  if (kind === 'grating') return gratingMaterial(detail);
  if (kind === 'plate') return plateMaterial(detail);
  return paintMaterial(detail);
}
