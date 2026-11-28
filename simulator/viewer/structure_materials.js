// Procedural PBR-style materials for inspection structures: painted and bare steel, sacrificial anodes, concrete,
// rubber, antifouling hull paint, rust, pool tiles and rock. Every texture is drawn on a canvas at start-up
// (original procedural work, nothing downloaded). Marine growth is applied in the shader by water depth:
//   splash zone (above 0.5 m)   coating breakdown and rust streaks, no growth
//   0-8 m                       dense mussels and weed (dark blue-black / olive), heaviest cover
//   8-20 m                      barnacles, hydroids and tube worms (pale, patchy)
//   below 20 m                  sparse soft growth and anemones (light speckle on bare surface)
// Coverage per band is a material parameter (anodes stay cleaner than the legs, a recently cleaned hull is light).
// Growth is sampled tri-planar in world space at two scales, so large surfaces do not show a repeating tile.
// On the medium and high tiers painted steel, concrete and rusty plate also carry CC0 scanned colour and normal
// maps (scan_materials.js, models/CREDITS.md) on the metre UVs of the tubes: painted steel reads a coating texture
// whose alpha is the rust propensity, so the paint breaks down to rust where the threshold (older steel, splash
// zone) lets it; the fouling bands are applied on top.
import * as THREE from 'three';
import {SCAN_MEAN, SCAN_TILE, scanTexture} from './scan_materials.js';

const TEXTURE_SIZE = 256;
let shared = null;

function hash2(x, y) {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

function canvasTexture(draw, repeat = true) {
  const canvas = document.createElement('canvas');
  canvas.width = TEXTURE_SIZE;
  canvas.height = TEXTURE_SIZE;
  draw(canvas.getContext('2d'), TEXTURE_SIZE);
  const texture = new THREE.CanvasTexture(canvas);
  if (repeat) texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

/** Fouling mask: R = mussel / weed clumps, G = barnacle and tube-worm speckle, B = rust streaks. */
function drawFouling(g, n) {
  const image = g.createImageData(n, n);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      let clump = 0;
      for (let o = 0; o < 3; o++) {
        const f = 4 << o;
        const fx = x / n * f;
        const fy = y / n * f;
        const ix = Math.floor(fx);
        const iy = Math.floor(fy);
        const u = fx - ix;
        const v = fy - iy;
        const a = hash2(ix % f, iy % f);
        const b = hash2((ix + 1) % f, iy % f);
        const c = hash2(ix % f, (iy + 1) % f);
        const d = hash2((ix + 1) % f, (iy + 1) % f);
        clump += ((a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v) / (1 << o);
      }
      const speckle = hash2(x * 1.3, y * 0.7) > 0.86 ? 1 : 0;
      const streak = Math.max(0, Math.sin(x * 0.21 + hash2(x, 3) * 2) * 0.5 + hash2(x, 7) - 0.75);
      const i = (y * n + x) * 4;
      image.data[i] = Math.min(255, Math.max(0, (clump / 1.75 - 0.25) * 2 * 255));
      image.data[i + 1] = speckle * 255;
      image.data[i + 2] = Math.min(255, streak * 600);
      image.data[i + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
}

function drawConcretePanel(g, n) {
  g.fillStyle = '#8a877d';
  g.fillRect(0, 0, n, n);
  for (let i = 0; i < 4000; i++) {
    const l = 110 + hash2(i, 1) * 50;
    g.fillStyle = `rgba(${l},${l - 3},${l - 10},0.35)`;
    g.fillRect(hash2(i, 2) * n, hash2(i, 3) * n, 2, 2);
  }
  for (let i = 0; i < 9; i++) {
    const x = hash2(i, 9) * n;
    const grad = g.createLinearGradient(x, 0, x, n);
    grad.addColorStop(0, 'rgba(70,58,40,0.35)');
    grad.addColorStop(1, 'rgba(70,58,40,0)');
    g.fillStyle = grad;
    g.fillRect(x, 0, 3 + hash2(i, 4) * 6, n * (0.3 + hash2(i, 5) * 0.6));
  }
  g.fillStyle = '#3c3a35';
  g.fillRect(0, 0, n, 3);
  g.fillRect(0, 0, 3, n);
}

function drawPlating(g, n) {
  g.fillStyle = '#ffffff';
  g.fillRect(0, 0, n, n);
  g.fillStyle = 'rgba(40,40,40,0.55)';
  g.fillRect(0, 0, n, 2);
  g.fillRect(0, 0, 2, n);
  for (let i = 0; i < 1600; i++) {
    const l = 200 + hash2(i, 5) * 55;
    g.fillStyle = `rgba(${l},${l},${l},0.4)`;
    g.fillRect(hash2(i, 6) * n, hash2(i, 7) * n, 3, 2);
  }
  g.fillStyle = 'rgba(120,120,120,0.5)';
  for (let k = 1; k < 4; k++) g.fillRect(0, k * n / 4, n, 1);
}

function drawTiles(g, n) {
  g.fillStyle = '#d9e4e6';
  g.fillRect(0, 0, n, n);
  const cell = n / 8;
  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 8; x++) {
      const l = 205 + hash2(x, y) * 30;
      g.fillStyle = `rgb(${l - 10},${l},${l + 4})`;
      g.fillRect(x * cell + 1, y * cell + 1, cell - 2, cell - 2);
    }
  }
}

function drawRubber(g, n) {
  g.fillStyle = '#1d1e1f';
  g.fillRect(0, 0, n, n);
  for (let i = 0; i < 2500; i++) {
    const l = 25 + hash2(i, 11) * 25;
    g.fillStyle = `rgb(${l},${l},${l})`;
    g.fillRect(hash2(i, 12) * n, hash2(i, 13) * n, 2, 1);
  }
}

/** Shared canvas textures; built once per page. */
export function structureTextures() {
  if (shared) return shared;
  shared = {
    fouling: canvasTexture(drawFouling),
    concrete: canvasTexture(drawConcretePanel),
    plating: canvasTexture(drawPlating),
    tiles: canvasTexture(drawTiles),
    rubber: canvasTexture(drawRubber),
  };
  shared.fouling.colorSpace = THREE.NoColorSpace;
  return shared;
}

// growth coverage per band: [0-8 m, 8-20 m, >20 m]; splash = coating breakdown above the waterline
// scan: scanned texture set (medium and high); rustAt: coating propensity above which the paint has rusted through
// (lower = older coat); repeat: texture repeats per UV unit (tubes have metre UVs, quay faces 5 x 3 m panels)
const PRESETS = {
  steel: {color: 0x8a8070, roughness: .8, metalness: .25, coat: 0xc9a227, cover: [.9, .65, .4], splash: .6,
    scan: 'coating', rustAt: .55},
  // monopile below the transition piece: dark grey epoxy coating (the yellow belongs to the transition piece)
  monopileSteel: {color: 0x6a6a64, roughness: .8, metalness: .25, coat: 0x55585a, cover: [.9, .65, .4], splash: .6,
    scan: 'coating', rustAt: .6},
  brace: {color: 0x857b6b, roughness: .8, metalness: .25, coat: 0xc9a227, cover: [.85, .6, .35], splash: .6,
    scan: 'coating', rustAt: .5},
  transition: {color: 0xd2a91c, roughness: .55, metalness: .2, coat: 0xd2a91c, cover: [.7, .5, .3], splash: .25,
    scan: 'coating', rustAt: .88},
  anode: {color: 0xb4b4ac, roughness: .9, metalness: .1, coat: 0xb4b4ac, cover: [.2, .12, .08], splash: 0},
  concrete: {color: 0xffffff, roughness: .95, metalness: 0, coat: 0x9a968a, cover: [.75, .55, .35], splash: .1,
    map: 'concrete', scan: 'concrete', scanColor: 0xf4f2ec, repeat: [5 / SCAN_TILE.concrete, 3 / SCAN_TILE.concrete]},
  // harbour piles: wet concrete on metre UVs
  pileConcrete: {color: 0x8f8b80, roughness: .9, metalness: 0, coat: 0x9a968a, cover: [.85, .6, .4], splash: .15,
    scan: 'concrete', scanColor: 0xd8d4ca},
  rubber: {color: 0xffffff, roughness: .85, metalness: 0, coat: 0x1d1e1f, cover: [.35, .25, .15], splash: 0,
    map: 'rubber'},
  hull: {color: 0x7b2f25, roughness: .7, metalness: .15, coat: 0x23272c, cover: [.45, .3, .2], splash: .15,
    map: 'plating', boot: 0x1b1c1e},
  wreck: {color: 0x5e4a36, roughness: .95, metalness: .1, coat: 0x5e4a36, cover: [.95, .85, .7], splash: 0,
    map: 'plating'},
  bronze: {color: 0xa8854a, roughness: .45, metalness: .8, coat: 0xa8854a, cover: [.15, .1, .1], splash: 0},
  steelPlate: {color: 0x6c6a64, roughness: .75, metalness: .35, coat: 0x6c6a64, cover: [.7, .5, .35], splash: .3,
    map: 'plating', scan: 'rust', scanColor: 0xe6ddd2},
  tiles: {color: 0xffffff, roughness: .3, metalness: 0, coat: 0xffffff, cover: [0, 0, 0], splash: 0, map: 'tiles'},
  rock: {color: 0x77736a, roughness: 1, metalness: 0, coat: 0x77736a, cover: [.6, .45, .3], splash: 0},
  ladder: {color: 0x8a8580, roughness: .6, metalness: .5, coat: 0xb8b2a6, cover: [.6, .4, .3], splash: .4},
  // galvanised perforated walkway above the water: alpha-tested, both sides, light passes through the holes
  grating: {color: 0xd8dadb, roughness: .55, metalness: .45, coat: 0xd8dadb, cover: [0, 0, 0], splash: .2,
    scan: 'grating', scanColor: 0xd8dadb, alphaTest: .5},
};

// Painted steel: paint (coat colour times the scanned paint luminance) or the scan's rust where the coating's rust
// propensity exceeds uRustAt; the splash zone breaks down sooner. Other scan sets are plain colour maps.
const SCAN_MAP = `
  #ifdef SCAN_COAT
  {
    vec4 coatTexel = texture2D(map, vMapUv);
    float coatBreak = uRustAt - (1.0 - vFoulBand.z) * uSplash * 0.3;
    float coatRust = smoothstep(coatBreak, coatBreak + 0.12, coatTexel.a);
    // RGB holds rust colour wherever the coat can break down (alpha > 0): paint shading only where it is paint
    float coatShade = mix(coatTexel.g * ${(1 / SCAN_MEAN).toFixed(4)}, 1.0, smoothstep(0.02, 0.08, coatTexel.a));
    vec3 coatPaint = uCoat * coatShade;
    diffuseColor.rgb = mix(coatPaint, coatTexel.rgb, coatRust);
  }
  #else
  #include <map_fragment>
  #endif`;

// Scanned roughness rides in the normal map's alpha.
const SCAN_ROUGHNESS = `#include <roughnessmap_fragment>
  #ifdef SCAN_ROUGH
  roughnessFactor = mix(roughnessFactor, texture2D(normalMap, vNormalMapUv).a, 0.7);
  #endif`;

function foulingShader(params, textures) {
  const uniforms = {
    uFouling: {value: textures.fouling},
    uCover: {value: new THREE.Vector3(...params.cover)},
    uSplash: {value: params.splash},
    uCoat: {value: new THREE.Color(params.coat)},
    uBoot: {value: new THREE.Color(params.boot ?? params.coat)},
    uHasBoot: {value: params.boot ? 1 : 0},
    uRustAt: {value: params.rustAt ?? 1},
  };
  return function onBeforeCompile(shader) {
    Object.assign(shader.uniforms, uniforms);
    // depth bands are smooth over metres: evaluated per vertex, interpolated, so the fragment stage stays cheap
    shader.vertexShader = `varying vec3 vFoulPos;
      varying vec3 vFoulNormal;
      varying vec4 vFoulBand;    // shallow, deep, wet, growth cover
      varying vec2 vFoulPaint;   // boot top, topside
      varying vec4 vFoulTint;    // medium tier: growth colour and amount, no texture read
      uniform vec3 uCover;
      uniform float uHasBoot;
      uniform vec3 uCoat;
      ` + shader.vertexShader.replace(
      '#include <project_vertex>', `vec4 foulWorld = vec4(transformed, 1.0);
      vec3 foulNormal = objectNormal;
      #ifdef USE_INSTANCING
      foulWorld = instanceMatrix * foulWorld;
      foulNormal = mat3(instanceMatrix) * foulNormal;
      #endif
      vFoulPos = (modelMatrix * foulWorld).xyz;
      vFoulNormal = normalize(mat3(modelMatrix) * foulNormal);
      {
        float depth = -vFoulPos.y;
        float band0 = 1.0 - smoothstep(6.0, 10.0, depth);
        float band2 = smoothstep(18.0, 22.0, depth);
        float wet = smoothstep(-0.6, 0.4, depth);
        float cover = (uCover.x * band0 + uCover.y * (1.0 - band0 - band2) + uCover.z * band2) * wet;
        vFoulBand = vec4(band0, band2, wet, cover);
        vFoulPaint = uHasBoot * vec2((1.0 - smoothstep(0.4, 0.6, depth)) * smoothstep(-1.2, -1.0, depth),
          1.0 - smoothstep(-1.25, -1.15, depth));
        vec3 growth = vec3(0.12, 0.13, 0.1) * band0 + vec3(0.52, 0.5, 0.44) * (1.0 - band0 - band2)
          + vec3(0.68, 0.64, 0.6) * band2;
        float above = (1.0 - uHasBoot) * (1.0 - wet);
        #ifdef SCAN_COAT
        above = 0.0;   // the scanned coating already shows the paint above the water
        #endif
        vFoulTint = vec4(mix(growth, uCoat, above), max(cover * 0.75, above));
      }
      #include <project_vertex>`);
    shader.fragmentShader = `varying vec3 vFoulPos;
      varying vec3 vFoulNormal;
      varying vec4 vFoulBand;
      varying vec2 vFoulPaint;
      varying vec4 vFoulTint;
      uniform sampler2D uFouling;
      uniform float uSplash;
      uniform vec3 uCoat;
      uniform vec3 uBoot;
      uniform float uHasBoot;
      uniform float uRustAt;
      float foulHash(float n) {
        return fract(sin(n) * 43758.5453);
      }
      float foulNoise(vec3 p) {
        vec3 i = floor(p);
        vec3 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        float n = i.x + i.y * 57.0 + i.z * 113.0;
        float x00 = mix(foulHash(n), foulHash(n + 1.0), f.x);
        float x10 = mix(foulHash(n + 57.0), foulHash(n + 58.0), f.x);
        float x01 = mix(foulHash(n + 113.0), foulHash(n + 114.0), f.x);
        float x11 = mix(foulHash(n + 170.0), foulHash(n + 171.0), f.x);
        return mix(mix(x00, x10, f.y), mix(x01, x11, f.y), f.z);
      }
      vec3 foulSample(float scale) {
        vec3 p = vFoulPos * scale;
        vec3 n = abs(vFoulNormal);
        vec2 uv = n.y > max(n.x, n.z) ? p.xz : (n.x > n.z ? p.zy : p.xy);
        return texture2D(uFouling, uv).rgb;
      }
      ` + shader.fragmentShader.replace('#include <roughnessmap_fragment>', SCAN_ROUGHNESS)
      .replace('#include <map_fragment>', `${SCAN_MAP}
      #if FOUL_QUALITY < 2
      {
        // Medium: no texture read, but a cheap two-octave value noise breaks the per-vertex tint into patches
        // and stains, so growth still reads as growth under the per-channel water light (fx/water_optics.js).
        float patches = foulNoise(vFoulPos * 0.9) * 0.65 + foulNoise(vFoulPos * 3.7) * 0.35;
        float amount = clamp(vFoulTint.a * (0.35 + 1.1 * patches), 0.0, 1.0);
        diffuseColor.rgb = mix(diffuseColor.rgb, vFoulTint.rgb, amount);
        diffuseColor.rgb *= mix(1.0, 0.7 + 0.5 * patches, vFoulBand.z);
      }
      diffuseColor.rgb = mix(diffuseColor.rgb, uBoot, vFoulPaint.x);
      diffuseColor.rgb = mix(diffuseColor.rgb, uCoat, vFoulPaint.y);
      #else
      {
        vec3 coarse = foulSample(0.13);
        vec3 fine = coarse.gbr;
        float clump = clamp(fine.r * 0.6 + coarse.r * 0.8, 0.0, 1.0);
        float band0 = vFoulBand.x;
        float band2 = vFoulBand.y;
        float band1 = 1.0 - band0 - band2;
        float wet = vFoulBand.z;
        float cover = vFoulBand.w;
        vec3 mussel = mix(vec3(0.05, 0.06, 0.07), vec3(0.2, 0.22, 0.12), coarse.g * 0.5 + fine.g * 0.3);
        vec3 barnacle = mix(vec3(0.62, 0.6, 0.54), vec3(0.42, 0.4, 0.33), fine.r);
        vec3 soft = mix(vec3(0.55, 0.5, 0.45), vec3(0.85, 0.82, 0.78), fine.g);
        vec3 growth = mussel * band0 + barnacle * band1 + soft * band2;
        float amount = smoothstep(1.0 - cover, 1.0 - cover + 0.35, clump);
        diffuseColor.rgb = mix(diffuseColor.rgb, growth, amount * 0.92);
        diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * (0.75 + 0.35 * fine.g), wet * 0.6);
        float splash = (1.0 - wet) * uSplash;
        vec3 rust = vec3(0.36, 0.19, 0.09);
        diffuseColor.rgb = mix(diffuseColor.rgb, rust, splash * clamp(fine.b * 2.0 + coarse.r * 0.5, 0.0, 1.0));
        diffuseColor.rgb = mix(diffuseColor.rgb, uBoot, vFoulPaint.x);
        diffuseColor.rgb = mix(diffuseColor.rgb, uCoat, vFoulPaint.y);
        #ifndef SCAN_COAT
        float coatAbove = (1.0 - uHasBoot) * (1.0 - wet);
        diffuseColor.rgb = mix(diffuseColor.rgb, uCoat * (0.8 + 0.3 * coarse.r), coatAbove * (1.0 - splash * fine.b));
        #endif
      }
      #endif`);
  };
}

/** Scanned colour and normal (roughness in alpha) maps; painted steel reads its colour through SCAN_COAT. */
function addScanMaps(material, params, normals = true, detail = 'medium') {
  const repeat = params.repeat ?? 1 / SCAN_TILE[params.scan];
  const size = detail === 'high' ? 0 : 512;
  const options = {repeat, size, mask: !!params.alphaTest};
  material.map = scanTexture(`${params.scan}_c`, options, function assignMap(texture) {
    material.map = texture;
  });
  material.color.setHex(params.scanColor ?? 0xffffff);   // raw scan colour, tinted
  if (!normals) return;
  material.normalMap = scanTexture(`${params.scan}_n`, {repeat, size}, function assignNormal(texture) {
    material.normalMap = texture;
  });
  material.defines.SCAN_ROUGH = 1;
  if (params.scan === 'coating') material.defines.SCAN_COAT = 1;
}

/**
 * A new material for one structure kind. Each call returns its own instance (the snag highlight changes the
 * emissive colour per obstacle); the shader program is shared through the cache key. ``detail`` sets the cost:
 * low has no fouling shader; medium tints by depth band per vertex (no texture read); high reads the fouling
 * mask once (dominant-axis projection) for clumps, streaks and splash rust, and uses the texture maps (panel
 * joints, plating seams).
 */
export function structureMaterial(kind, detail = 'medium') {
  const params = PRESETS[kind] || PRESETS.steel;
  const textures = structureTextures();
  const material = new THREE.MeshStandardMaterial({
    color: params.color, roughness: params.roughness, metalness: params.metalness,
    // canvas maps (panel joints, plating seams) only on high; pool tiles always; scan sets replace them
    map: params.map && !params.scan && (detail === 'high' || kind === 'tiles') ? textures[params.map] : null,
  });
  if (detail === 'low') {
    // low tier: no fouling shader, the base colour is pre-mixed toward the mid-depth growth tone
    material.color.lerp(new THREE.Color(0x3b3d35), params.cover[1] * 0.6);
  } else {
    material.onBeforeCompile = foulingShader(params, textures);
    material.defines = {FOUL_QUALITY: detail === 'high' ? 2 : 1};
    if (params.scan) addScanMaps(material, params, true, detail);
    material.customProgramCacheKey = function foulingProgramKey() {
      return `structure-fouling-v6-${material.defines.FOUL_QUALITY}-${params.scan ? params.scan : '-'}`;
    };
  }
  if (params.alphaTest) {
    material.alphaTest = params.alphaTest;
    material.side = THREE.DoubleSide;
    // the holes are the point of a grating: its colour and alpha map is read on every tier
    if (detail === 'low') addScanMaps(material, params, false);
  }
  material.userData.structureKind = kind;
  return material;
}
