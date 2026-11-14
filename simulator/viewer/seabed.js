// Seabed material per dive site: sand ripples, gravel, mud, shell debris and rock outcrops blended in world space.
// The relief is only shading (bump from the ripple field, a few centimetres): the visible floor stays where the
// physics seabed is. Textures are drawn on canvases at start-up (original procedural work). Two rotated scales of
// every texture are mixed by low-frequency noise, so no repeating tile is visible from flying height.
//
//   const material = seabedMaterial(siteProfile(world), 'medium');
import * as THREE from 'three';

const SIZE = 256;
let textures = null;

// weights: sand, gravel, mud, shell, rock outcrop; colours in linear-ish sRGB hex
const PROFILES = {
  offshore: {sand: 0xb3a57f, mud: 0x6f6650, gravel: .35, mud_w: .1, shell: .45, rock: .12, ripple: 1},
  harbour: {sand: 0x7d735c, mud: 0x4b4639, gravel: .25, mud_w: .75, shell: .55, rock: 0, ripple: .25},
  wreck: {sand: 0x8f866b, mud: 0x575142, gravel: .4, mud_w: .55, shell: .3, rock: .08, ripple: .45},
  reef: {sand: 0xd6cdb0, mud: 0x9d927a, gravel: .5, mud_w: 0, shell: .7, rock: .25, ripple: .8},
  seagrass: {sand: 0xbfb48f, mud: 0x6b6450, gravel: .1, mud_w: .45, shell: .35, rock: 0, ripple: .5},
  pool: {sand: 0xdfe8ea, mud: 0xdfe8ea, gravel: 0, mud_w: 0, shell: 0, rock: 0, ripple: 0, tiles: 1},
};

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

/** R: ripple height (asymmetric crests, wavelength 1/8 tile), G: fine grain noise, B: shell / pebble mask. */
function drawField(g, n) {
  const image = g.createImageData(n, n);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const wobble = Math.sin(x / n * Math.PI * 4) * 6 + Math.sin(x / n * Math.PI * 10 + 1) * 2;
      const phase = ((y + wobble) / n * 8) % 1;
      const crest = phase < 0.65 ? phase / 0.65 : (1 - phase) / 0.35;
      const grain = hash2(x, y);
      const pebble = hash2(Math.floor(x / 3) * 3, Math.floor(y / 3) * 3) > 0.9 ? 1 : 0;
      const i = (y * n + x) * 4;
      image.data[i] = Math.round(crest * 255);
      image.data[i + 1] = Math.round(grain * 255);
      image.data[i + 2] = pebble * 255;
      image.data[i + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
}

function drawGravel(g, n) {
  g.fillStyle = '#7d7462';
  g.fillRect(0, 0, n, n);
  for (let i = 0; i < 2200; i++) {
    const r = 1 + hash2(i, 1) * 4;
    const l = 70 + hash2(i, 2) * 120;
    const shell = hash2(i, 3) > 0.82;
    g.fillStyle = shell ? `rgb(${200 + l / 6},${190 + l / 8},${170 + l / 10})` : `rgb(${l},${l * 0.95},${l * 0.85})`;
    g.beginPath();
    g.ellipse(hash2(i, 4) * n, hash2(i, 5) * n, r, r * (0.5 + hash2(i, 6) * 0.5), hash2(i, 7) * 3, 0, Math.PI * 2);
    g.fill();
  }
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
  if (!textures) {
    textures = {field: canvas(drawField, false), gravel: canvas(drawGravel), tiles: canvas(drawTiles),
      noise: canvas(drawNoise, false)};
  }
  return textures;
}

/** Which seabed a world gets: by biome, then by what stands on it. */
export function siteProfile(world) {
  const key = world?.scenario?.key || '';
  const biome = world?.biome || world?.habitat?.biome;
  if (key === 'tutorial_pool') return 'pool';
  if (biome === 'reef' || biome === 'seagrass') return biome;
  if (biome === 'harbor') return 'harbour';
  const kinds = new Set((world?.obstacles || []).map((ob) => ob.kind));
  if (kinds.has('quay')) return 'harbour';
  if (kinds.has('wreck') || key.includes('wreck') || key === 'korean_castle') return 'wreck';
  return 'offshore';
}

function shaderPatch(profile, maps) {
  const uniforms = {
    uField: {value: maps.field},
    uGravel: {value: maps.gravel},
    uTiles: {value: maps.tiles},
    uNoise: {value: maps.noise},
    uSand: {value: new THREE.Color(profile.sand)},
    uMud: {value: new THREE.Color(profile.mud)},
    uWeights: {value: new THREE.Vector4(profile.gravel, profile.mud_w, profile.shell, profile.rock)},
    uRipple: {value: profile.ripple},
    uTileFloor: {value: profile.tiles || 0},
  };
  return function onBeforeCompile(shader) {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = 'varying vec3 vSeaPos;\n' + shader.vertexShader.replace('#include <project_vertex>',
      `vSeaPos = (modelMatrix * vec4(transformed, 1.0)).xyz;
      #include <project_vertex>`);
    shader.fragmentShader = `varying vec3 vSeaPos;
      uniform sampler2D uField;
      uniform sampler2D uGravel;
      uniform sampler2D uTiles;
      uniform sampler2D uNoise;
      uniform vec3 uSand;
      uniform vec3 uMud;
      uniform vec4 uWeights;
      uniform float uRipple;
      uniform float uTileFloor;
      // ripple field read along a 0.35 rad rotated grid (and a second 1.95 rad grid on high): no visible tiling
      const mat2 SEA_ROT_A = mat2(0.9394, -0.3429, 0.3429, 0.9394);
      const mat2 SEA_ROT_B = mat2(-0.3702, -0.9290, 0.9290, -0.3702);
      float seaRipple(vec2 p, float mixer) {
        float a = texture2D(uField, SEA_ROT_A * p * 0.16).r;
        #if SEA_QUALITY >= 2
        return mix(a, texture2D(uField, SEA_ROT_B * p * 0.083).r, mixer);
        #else
        return a;
        #endif
      }
      ` + shader.fragmentShader
      .replace('#include <map_fragment>', `#include <map_fragment>
      vec2 seaP = vSeaPos.xz;
      #if SEA_QUALITY >= 1
      vec3 seaN = texture2D(uNoise, seaP * 0.00625).rgb;   // 160 m tile of smooth noise
      float seaLow = seaN.r;
      float seaMid = seaN.g;
      float seaMix = smoothstep(0.3, 0.7, seaN.b);
      vec4 seaF = texture2D(uField, SEA_ROT_A * seaP * 0.16);
      #else
      float seaLow = 0.5;
      float seaMid = 0.5;
      float seaMix = 0.0;
      vec4 seaF = texture2D(uField, seaP * 0.16);
      #endif
      #if SEA_QUALITY >= 2
      float seaR = mix(seaF.r, texture2D(uField, SEA_ROT_B * seaP * 0.083).r, seaMix);
      #else
      float seaR = seaF.r;
      #endif
      vec3 seaCol = uSand * (0.82 + 0.3 * seaR * uRipple + 0.12 * (seaF.g - 0.5));
      float mudW = clamp(uWeights.y * (0.6 + 0.8 * (seaLow - 0.5)), 0.0, 1.0);
      seaCol = mix(seaCol, uMud * (0.9 + 0.2 * seaF.g), mudW);
      #if SEA_QUALITY >= 1
      vec3 gravel = texture2D(uGravel, seaP * 0.55).rgb;
      #else
      vec3 gravel = uMud;
      #endif
      #if SEA_QUALITY >= 2
      gravel = mix(gravel, texture2D(uGravel, SEA_ROT_A * seaP * 0.21).rgb, seaMix);
      #endif
      float gravelW = uWeights.x * smoothstep(0.55, 0.75, seaMid * 0.6 + seaLow * 0.5);
      seaCol = mix(seaCol, gravel, gravelW);
      float shellW = uWeights.z * seaF.b * smoothstep(0.35, 0.7, seaMid);
      seaCol = mix(seaCol, vec3(0.86, 0.82, 0.74), shellW * 0.8);
      #if SEA_QUALITY >= 1
      float rockW = uWeights.w * smoothstep(0.72, 0.8, seaLow * 0.7 + seaN.b * 0.4);
      seaCol = mix(seaCol, vec3(0.36, 0.35, 0.31) * (0.8 + 0.4 * seaF.g), rockW);
      #endif
      #ifdef SEA_TILES
      seaCol = texture2D(uTiles, seaP * 0.5).rgb;
      #endif
      diffuseColor.rgb *= seaCol;
      float seaBump = uRipple * (1.0 - mudW * 0.7) * (1.0 - uTileFloor);`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
      #if SEA_QUALITY >= 2
      {
        float e = 0.06;
        float hx = (seaRipple(seaP + vec2(e, 0.0), seaMix) - seaR) * 2.0;
        float hz = (seaRipple(seaP + vec2(0.0, e), seaMix) - seaR) * 2.0;
        vec3 tilt = vec3(-hx, 0.0, -hz) * 0.9 * seaBump;
        normal = normalize(normal + (viewMatrix * vec4(tilt, 0.0)).xyz);
      }
      #endif`);
  };
}

const QUALITY = {low: 0, medium: 1, high: 2};

/**
 * Seabed material for a profile name from siteProfile(). ``detail`` (low / medium / high) sets the shader cost:
 * low reads one texture (cost of the old single sand texture); medium three (a baked smooth-noise texture for
 * mud, gravel and rock patches, the ripple field, gravel); high adds a second ripple and gravel scale and ripple
 * shading of the normal (seven reads). No procedural noise is evaluated per pixel.
 */
export function seabedMaterial(name, detail = 'medium') {
  const profile = PROFILES[name] || PROFILES.offshore;
  const material = new THREE.MeshStandardMaterial({color: 0xffffff, roughness: 1, metalness: 0});
  material.onBeforeCompile = shaderPatch(profile, sharedTextures());
  material.defines = {SEA_QUALITY: QUALITY[detail] ?? 1};
  if (profile.tiles) material.defines.SEA_TILES = 1;
  material.customProgramCacheKey = () => `seabed-site-v3-${material.defines.SEA_QUALITY}-${profile.tiles ? 1 : 0}`;
  material.userData.seabedProfile = name;
  return material;
}
