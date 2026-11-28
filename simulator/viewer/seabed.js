// Seabed material per dive site from CC0 scanned ground textures (scan_materials.js; models/CREDITS.md): a base
// sediment (sand, mud), a secondary patch material (shell hash, coral rubble, sand, mud) and on rocky sites a
// rock outcrop texture, blended in world space by a baked smooth-noise texture. The scans are normalised grey
// textures tinted with the site palette below, so each site keeps its calibrated colour under the water optics.
// The relief is only shading (normal maps and sand ripples, a few centimetres): the visible floor stays where the
// physics seabed is.
//
// No repeat is visible from 1-10 m: the base is read twice (2 m tile and a rotated 2.7 m tile) and the two are
// mixed by a 5 m noise; a 47 m scan of beach sand and the 160 m noise vary the colour on top; ripples have their
// own 12 m tile.
//
//   const material = seabedMaterial(siteProfile(world), 'medium');
import * as THREE from 'three';
import {SCAN_MEAN, SCAN_TILE, scanUniform} from './scan_materials.js';

const SIZE = 256;
let textures = null;

// sand / mud: palette colours (sRGB hex); base / second / rock: scan sets; gravel, mud_w, shell, rock: weights of
// the secondary patches, mud tint and rock outcrops; ripple: sand-ripple normal strength; tiles: pool floor.
export const PROFILES = {
  offshore: {sand: 0xb3a57f, mud: 0x6f6650, gravel: .35, mud_w: .1, shell: .45, rock: .12, ripple: 1,
    base: 'sand', second: 'shell', secondTint: 0xc9bea2},
  harbour: {sand: 0x7d735c, mud: 0x4b4639, gravel: .25, mud_w: .75, shell: .55, rock: 0, ripple: .25,
    base: 'mud', second: 'shell', secondTint: 0x8a8068},
  wreck: {sand: 0x8f866b, mud: 0x575142, gravel: .4, mud_w: .55, shell: .3, rock: .08, ripple: .45,
    base: 'mud', second: 'sand', secondTint: 0x9a9074},
  reef: {sand: 0xd6cdb0, mud: 0x9d927a, gravel: .5, mud_w: 0, shell: .7, rock: .25, ripple: 1.1,
    base: 'sand', second: 'gravel', secondTint: 0xb8ad94, rockSet: 'rockbed', rockTint: 0x6b6a5c},
  seagrass: {sand: 0xbfb48f, mud: 0x6b6450, gravel: .1, mud_w: .45, shell: .35, rock: 0, ripple: .5,
    base: 'sand', second: 'mud', secondTint: 0x7a7258},
  pool: {sand: 0xdfe8ea, mud: 0xdfe8ea, gravel: 0, mud_w: 0, shell: 0, rock: 0, ripple: 0, tiles: 1},
};

/** Hex colour for seabed rocks at a site: sand→mud blend so snag rocks match the floor. */
export function siteRockColor(world) {
  const profile = PROFILES[siteProfile(world)] || PROFILES.offshore;
  const mud = profile.mud_w || 0;
  const sand = new THREE.Color(profile.sand);
  const dirt = new THREE.Color(profile.mud);
  return sand.lerp(dirt, 0.35 + 0.45 * mud).getHex();
}

function hash2(x, y) {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

function canvas(draw, colour = true) {
  const c = document.createElement('canvas');
  c.width = SIZE;
  c.height = SIZE;
  draw(c.getContext('2d'), SIZE);
  const texture = new THREE.CanvasTexture(c);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = colour ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  return texture;
}

function drawTiles(g, n) {
  g.fillStyle = '#9fb3b7';
  g.fillRect(0, 0, n, n);
  const cell = n / 8;
  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 8; x++) {
      const l = 210 + hash2(x + 3, y) * 25;
      g.fillStyle = `rgb(${l - 12},${l},${l + 5})`;
      g.fillRect(x * cell + 1.5, y * cell + 1.5, cell - 3, cell - 3);
    }
  }
}

/** Smooth tileable value noise, one octave per channel: R 8 cells, G 32 cells, B 4 cells across the tile. */
function drawNoise(g, n) {
  const image = g.createImageData(n, n);
  const octave = (x, y, cells, seed) => {
    const fx = x / n * cells;
    const fy = y / n * cells;
    const ix = Math.floor(fx);
    const iy = Math.floor(fy);
    const u = (fx - ix) * (fx - ix) * (3 - 2 * (fx - ix));
    const v = (fy - iy) * (fy - iy) * (3 - 2 * (fy - iy));
    const h = (a, b) => hash2((a % cells) + seed, (b % cells) + seed * 3);
    const top = h(ix, iy) * (1 - u) + h(ix + 1, iy) * u;
    const bottom = h(ix, iy + 1) * (1 - u) + h(ix + 1, iy + 1) * u;
    return top * (1 - v) + bottom * v;
  };
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const i = (y * n + x) * 4;
      image.data[i] = Math.round(octave(x, y, 8, 11) * 255);
      image.data[i + 1] = Math.round(octave(x, y, 32, 23) * 255);
      image.data[i + 2] = Math.round(octave(x, y, 4, 37) * 255);
      image.data[i + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
}

function sharedTextures() {
  if (!textures) textures = {tiles: canvas(drawTiles), noise: canvas(drawNoise, false)};
  return textures;
}

/** Which seabed a world gets: by biome, then by what stands on it. */
export function siteProfile(world) {
  const key = world?.scenario?.key || '';
  const biome = world?.biome || world?.habitat?.biome;
  if (key === 'tutorial_pool') return 'pool';
  if (biome === 'reef' || biome === 'seagrass') return biome;
  // the host's seabed type (silt model and bed roughness) picks the look when the scenario names one
  const type = world?.scenario?.seabed_type;
  if (type === 'mud' || type === 'fluff') return 'harbour';
  if (type === 'silt') return 'wreck';
  if (biome === 'harbor') return 'harbour';
  const kinds = new Set((world?.obstacles || []).map((ob) => ob.kind));
  if (kinds.has('quay')) return 'harbour';
  if (kinds.has('wreck') || key.includes('wreck') || key === 'korean_castle') return 'wreck';
  return 'offshore';
}

/** Scan textures of a profile for a quality tier; low reads one downscaled colour map. */
function scanSet(profile, quality) {
  if (profile.tiles) return {};
  const low = quality === 0;
  const small = quality >= 2 ? 0 : 512;
  const set = {uBaseC: scanUniform(`${profile.base}_c`, {size: small})};
  if (low) return set;
  // Keep the colour detail on medium. The filtered relief maps modulate only the bed normal.
  const reliefSize = quality >= 2 ? 0 : 256;
  set.uSecondC = scanUniform(`${profile.second}_c`, {size: small});
  set.uBaseN = scanUniform(`${profile.base}_n`, {size: reliefSize});
  set.uRippleN = scanUniform('ripple_n', {size: reliefSize});
  if (profile.rockSet) set.uRockC = scanUniform(`${profile.rockSet}_c`, {size: small});
  if (quality >= 2) {
    set.uSecondN = scanUniform(`${profile.second}_n`);
    set.uMacro = scanUniform('macro_c');
    if (profile.rockSet) set.uRockN = scanUniform(`${profile.rockSet}_n`);
  }
  return set;
}

const VERTEX_HEAD = `varying vec3 vSeaPos;
  varying vec3 vSeaN;
  varying vec3 vSeaNormal;
  uniform sampler2D uNoise;
`;

const VERTEX_BODY = `vSeaPos = (modelMatrix * vec4(transformed, 1.0)).xyz;
  vSeaNormal = normalize(mat3(modelMatrix) * objectNormal);
  #if SEA_QUALITY == 1
  // medium: the 160 m noise is smooth enough to read per vertex
  vSeaN = texture2D(uNoise, vSeaPos.xz * 0.00625).rgb;
  #endif
  #include <project_vertex>`;

const FRAGMENT_HEAD = `varying vec3 vSeaPos;
  varying vec3 vSeaN;
  varying vec3 vSeaNormal;
  uniform sampler2D uTiles;
  uniform sampler2D uNoise;
  uniform sampler2D uBaseC;
  uniform sampler2D uBaseN;
  uniform sampler2D uSecondC;
  uniform sampler2D uSecondN;
  uniform sampler2D uRippleN;
  uniform sampler2D uRockC;
  uniform sampler2D uRockN;
  uniform sampler2D uMacro;
  uniform vec3 uSand;
  uniform vec3 uMud;
  uniform vec3 uSecondTint;
  uniform vec3 uRockTint;
  uniform vec4 uWeights;
  uniform vec4 uTiles4;     // base, second, ripple, rock tile sizes (m)
  uniform float uRipple;
  // second base read on a 0.35 rad rotated, 1.37x larger grid; mixed by noise so no tile repeats
  const mat2 SEA_ROT = mat2(0.9394, -0.3429, 0.3429, 0.9394);
  const float SEA_GAIN = ${(1 / SCAN_MEAN).toFixed(4)};
  vec3 seaTs = vec3(0.0, 0.0, 1.0);
  float seaRough = 1.0;
  vec3 seaNormalTs(vec4 texel) {
    return texel.xyz * 2.0 - 1.0;
  }
  // a normal read on the rotated grid, back in the world-aligned frame
  vec3 seaUnrotate(vec3 n) {
    return vec3(transpose(SEA_ROT) * n.xy, n.z);
  }
`;

// Colour, tangent-space normal and roughness of the floor at this pixel (diffuseColor is multiplied).
const FRAGMENT_COLOUR = `#include <map_fragment>
  vec2 seaP = vSeaPos.xz;
  vec2 seaUv = vec2(seaP.x, -seaP.y);          // tangent +u = east (+x), +v = -z: right-handed about +y
  #ifdef SEA_TILES
  vec3 seaCol = texture2D(uTiles, seaP * 0.5).rgb;
  #elif SEA_QUALITY == 0
  // low: one downscaled read and the site's sand / mud mix as a constant
  vec3 seaCol = texture2D(uBaseC, seaUv / uTiles4.x).rgb * SEA_GAIN * mix(uSand, uMud, uWeights.y * 0.6);
  #else
  #if SEA_QUALITY >= 2
  vec3 seaN = texture2D(uNoise, seaP * 0.00625).rgb;   // 160 m tile of smooth noise
  #else
  vec3 seaN = vSeaN;
  #endif
  float seaLow = seaN.r;
  float seaMid = seaN.g;
  // 5 m noise from the same texture (G channel at 32 cells / 160 m) decides which base read shows
  float seaPick = smoothstep(0.35, 0.65, texture2D(uNoise, seaP * 0.0061 + 0.31).g);
  vec2 seaUvA = seaUv / uTiles4.x;
  vec2 seaUvB = SEA_ROT * seaUv / (uTiles4.x * 1.37) + 0.37;
  vec3 seaCol = mix(texture2D(uBaseC, seaUvA).rgb, texture2D(uBaseC, seaUvB).rgb, seaPick) * SEA_GAIN;
  seaCol *= mix(uSand, uMud, clamp(uWeights.y * (0.6 + 0.8 * (seaLow - 0.5)), 0.0, 1.0) * 0.8);
  #if SEA_QUALITY >= 2
  vec3 seaMacro = texture2D(uMacro, seaUv / 47.0).rgb * SEA_GAIN;
  seaCol *= mix(vec3(1.0), seaMacro, 0.55) * (0.88 + 0.24 * seaLow);
  #else
  seaCol *= 0.88 + 0.24 * seaLow;
  #endif
  vec4 seaRip = texture2D(uRippleN, seaUv / uTiles4.z);
  vec4 seaBn = texture2D(uBaseN, seaUvA);
  vec3 seaBase = seaNormalTs(seaBn);
  seaRough = seaBn.a;
  #if SEA_QUALITY >= 2
  vec4 seaBnB = texture2D(uBaseN, seaUvB);
  seaBase = normalize(mix(seaBase, seaUnrotate(seaNormalTs(seaBnB)), seaPick));
  seaRough = mix(seaRough, seaBnB.a, seaPick);
  #endif
  vec3 seaRipple = seaNormalTs(seaRip);
  seaTs = normalize(vec3(seaBase.xy + seaRipple.xy * uRipple * 0.55, seaBase.z));
  seaCol *= 1.0 + (seaRip.a - 0.5) * 0.1 * uRipple;   // ripple troughs collect darker grains
  // secondary patches: shell hash, coral rubble, sand or mud, by the gravel / shell weights
  float seaSecondW = clamp(uWeights.x * smoothstep(0.5, 0.72, seaMid * 0.6 + seaLow * 0.5)
    + uWeights.z * 0.6 * smoothstep(0.55, 0.8, seaMid), 0.0, 1.0);
  // (reads outside branches: mipmapped lookups need uniform control flow for their derivatives)
  vec2 seaUvS = SEA_ROT * seaUv / uTiles4.y + 0.11;
  vec3 seaSecond = texture2D(uSecondC, seaUvS).rgb * SEA_GAIN * uSecondTint;
  seaCol = mix(seaCol, seaSecond, seaSecondW);
  #if SEA_QUALITY >= 2
  vec4 seaSn = texture2D(uSecondN, seaUvS);
  seaTs = normalize(mix(seaTs, seaUnrotate(seaNormalTs(seaSn)), seaSecondW));
  seaRough = mix(seaRough, seaSn.a, seaSecondW);
  #endif
  #ifdef SEA_ROCK
  float seaRockW = uWeights.w * smoothstep(0.7, 0.8, seaLow * 0.7 + seaN.b * 0.4);
  vec2 seaUvR = seaUv / uTiles4.w;
  seaCol = mix(seaCol, texture2D(uRockC, seaUvR).rgb * SEA_GAIN * uRockTint, seaRockW);
  #if SEA_QUALITY >= 2
  vec4 seaRn = texture2D(uRockN, seaUvR);
  seaTs = normalize(mix(seaTs, seaNormalTs(seaRn), seaRockW));
  seaRough = mix(seaRough, seaRn.a, seaRockW);
  #endif
  #endif
  #endif
  diffuseColor.rgb *= seaCol;`;

// The world-space floor frame (east, north on the terrain's slope) turns the tangent normal into view space.
const FRAGMENT_NORMAL = `
  #if !defined(SEA_TILES) && SEA_QUALITY > 0
  {
    vec3 seaUp = normalize(vSeaNormal);
    vec3 seaT = normalize(vec3(1.0, 0.0, 0.0) - seaUp * seaUp.x);
    vec3 seaB = cross(seaUp, seaT);
    vec3 seaWorld = normalize(seaT * seaTs.x + seaB * seaTs.y + seaUp * seaTs.z);
    normal = normalize((viewMatrix * vec4(seaWorld, 0.0)).xyz);
  }
  #endif
  #include <normal_fragment_maps>`;

const FRAGMENT_ROUGHNESS = `#include <roughnessmap_fragment>
  #if !defined(SEA_TILES) && SEA_QUALITY > 0
  roughnessFactor = clamp(0.45 + 0.55 * seaRough, 0.45, 1.0);   // wet grains keep a faint lamp sheen
  #endif`;

function shaderPatch(profile, maps, quality) {
  const uniforms = {
    uTiles: {value: maps.tiles},
    uNoise: {value: maps.noise},
    uSand: {value: new THREE.Color(profile.sand)},
    uMud: {value: new THREE.Color(profile.mud)},
    uSecondTint: {value: new THREE.Color(profile.secondTint ?? profile.sand)},
    uRockTint: {value: new THREE.Color(profile.rockTint ?? profile.mud)},
    uWeights: {value: new THREE.Vector4(profile.gravel, profile.mud_w, profile.shell, profile.rock)},
    uTiles4: {value: new THREE.Vector4(SCAN_TILE[profile.base] ?? 2, SCAN_TILE[profile.second] ?? 2,
      SCAN_TILE.ripple, SCAN_TILE[profile.rockSet] ?? 2)},
    uRipple: {value: profile.ripple},
    ...scanSet(profile, quality),
  };
  // unused samplers still need a texture bound: point them at the noise
  for (const name of ['uBaseC', 'uBaseN', 'uSecondC', 'uSecondN', 'uRippleN', 'uRockC', 'uRockN', 'uMacro']) {
    if (!uniforms[name]) uniforms[name] = {value: maps.noise};
  }
  return function onBeforeCompile(shader) {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = VERTEX_HEAD + shader.vertexShader.replace('#include <project_vertex>', VERTEX_BODY);
    shader.fragmentShader = FRAGMENT_HEAD + shader.fragmentShader
      .replace('#include <map_fragment>', FRAGMENT_COLOUR)
      .replace('#include <normal_fragment_maps>', FRAGMENT_NORMAL)
      .replace('#include <roughnessmap_fragment>', FRAGMENT_ROUGHNESS);
  };
}

const QUALITY = {low: 0, medium: 1, high: 2};

/**
 * Seabed material for a profile name from siteProfile(). ``detail`` (low / medium / high) sets the cost:
 * low reads one 512 px scan colour map with a constant sand / mud mix (the cost of the old single texture);
 * medium reads the base colour twice (no visible repeat), its normal, the ripple normal and the secondary colour
 * (plus the rock colour on reefs), with the 160 m noise per vertex; high adds the noise and the 47 m colour
 * variation per pixel, the second base normal and the secondary and rock normals.
 */
export function seabedMaterial(name, detail = 'medium') {
  const profile = PROFILES[name] || PROFILES.offshore;
  const quality = QUALITY[detail] ?? 1;
  const material = new THREE.MeshStandardMaterial({color: 0xffffff, roughness: 1, metalness: 0});
  material.onBeforeCompile = shaderPatch(profile, sharedTextures(), quality);
  material.defines = {SEA_QUALITY: quality};
  if (profile.tiles) material.defines.SEA_TILES = 1;
  if (profile.rockSet) material.defines.SEA_ROCK = 1;
  material.customProgramCacheKey = function seabedProgramKey() {
    return `seabed-scan-v1-${quality}-${profile.tiles ? 1 : 0}-${profile.rockSet ? 1 : 0}`;
  };
  material.userData.seabedProfile = name;
  return material;
}
