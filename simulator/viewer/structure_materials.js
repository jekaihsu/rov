// Procedural PBR-style materials for inspection structures: painted and bare steel, sacrificial anodes, concrete,
// rubber, antifouling hull paint, rust, pool tiles and rock. Every texture is drawn on a canvas at start-up
// (original procedural work, nothing downloaded). Marine growth is applied in the shader by water depth:
//   splash zone (above 0.5 m)   coating breakdown and rust streaks, no growth
//   0-8 m                       dense mussels and weed (dark blue-black / olive), heaviest cover
//   8-20 m                      barnacles, hydroids and tube worms (pale, patchy)
//   below 20 m                  sparse soft growth and anemones (light speckle on bare surface)
// Coverage per band is a material parameter (anodes stay cleaner than the legs, a recently cleaned hull is light).
// Growth is sampled tri-planar in world space at two scales, so large surfaces do not show a repeating tile.
import * as THREE from 'three';

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
const PRESETS = {
  steel: {color: 0x8a8070, roughness: .8, metalness: .25, coat: 0xc9a227, cover: [.9, .65, .4], splash: .6},
  brace: {color: 0x857b6b, roughness: .8, metalness: .25, coat: 0xc9a227, cover: [.85, .6, .35], splash: .6},
  transition: {color: 0xd2a91c, roughness: .55, metalness: .2, coat: 0xd2a91c, cover: [.7, .5, .3], splash: .25},
  anode: {color: 0xb4b4ac, roughness: .9, metalness: .1, coat: 0xb4b4ac, cover: [.2, .12, .08], splash: 0},
  concrete: {color: 0xffffff, roughness: .95, metalness: 0, coat: 0x9a968a, cover: [.75, .55, .35], splash: .1,
    map: 'concrete'},
  rubber: {color: 0xffffff, roughness: .85, metalness: 0, coat: 0x1d1e1f, cover: [.35, .25, .15], splash: 0,
    map: 'rubber'},
  hull: {color: 0x7b2f25, roughness: .7, metalness: .15, coat: 0x23272c, cover: [.45, .3, .2], splash: .15,
    map: 'plating', boot: 0x1b1c1e},
  wreck: {color: 0x5e4a36, roughness: .95, metalness: .1, coat: 0x5e4a36, cover: [.95, .85, .7], splash: 0,
    map: 'plating'},
  bronze: {color: 0xa8854a, roughness: .45, metalness: .8, coat: 0xa8854a, cover: [.15, .1, .1], splash: 0},
  steelPlate: {color: 0x6c6a64, roughness: .75, metalness: .35, coat: 0x6c6a64, cover: [.7, .5, .35], splash: .3,
    map: 'plating'},
  tiles: {color: 0xffffff, roughness: .3, metalness: 0, coat: 0xffffff, cover: [0, 0, 0], splash: 0, map: 'tiles'},
  rock: {color: 0x77736a, roughness: 1, metalness: 0, coat: 0x77736a, cover: [.6, .45, .3], splash: 0},
  ladder: {color: 0x8a8580, roughness: .6, metalness: .5, coat: 0xb8b2a6, cover: [.6, .4, .3], splash: .4},
};

function foulingShader(params, textures) {
  const uniforms = {
    uFouling: {value: textures.fouling},
    uCover: {value: new THREE.Vector3(...params.cover)},
    uSplash: {value: params.splash},
    uCoat: {value: new THREE.Color(params.coat)},
    uBoot: {value: new THREE.Color(params.boot ?? params.coat)},
    uHasBoot: {value: params.boot ? 1 : 0},
  };
  return function onBeforeCompile(shader) {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = 'varying vec3 vFoulPos;\nvarying vec3 vFoulNormal;\n' + shader.vertexShader.replace(
      '#include <project_vertex>', `vec4 foulWorld = vec4(transformed, 1.0);
      vec3 foulNormal = objectNormal;
      #ifdef USE_INSTANCING
      foulWorld = instanceMatrix * foulWorld;
      foulNormal = mat3(instanceMatrix) * foulNormal;
      #endif
      vFoulPos = (modelMatrix * foulWorld).xyz;
      vFoulNormal = normalize(mat3(modelMatrix) * foulNormal);
      #include <project_vertex>`);
    shader.fragmentShader = `varying vec3 vFoulPos;
      varying vec3 vFoulNormal;
      uniform sampler2D uFouling;
      uniform vec3 uCover;
      uniform float uSplash;
      uniform vec3 uCoat;
      uniform vec3 uBoot;
      uniform float uHasBoot;
      vec3 foulSample(float scale) {
        vec3 p = vFoulPos * scale;
        #if FOUL_QUALITY >= 2
        vec3 w = abs(vFoulNormal);
        w = pow(w, vec3(4.0));
        w /= (w.x + w.y + w.z + 1e-4);
        return texture2D(uFouling, p.zy).rgb * w.x + texture2D(uFouling, p.xz).rgb * w.y
          + texture2D(uFouling, p.xy).rgb * w.z;
        #else
        vec3 n = abs(vFoulNormal);
        vec2 uv = n.y > max(n.x, n.z) ? p.xz : (n.x > n.z ? p.zy : p.xy);
        return texture2D(uFouling, uv).rgb;
        #endif
      }
      ` + shader.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
      {
        float depth = -vFoulPos.y;
        vec3 coarse = foulSample(0.13);
        #if FOUL_QUALITY >= 2
        vec3 fine = foulSample(0.9);
        #else
        vec3 fine = coarse.gbr;
        #endif
        float clump = clamp(fine.r * 0.6 + coarse.r * 0.8, 0.0, 1.0);
        float band0 = 1.0 - smoothstep(6.0, 10.0, depth);
        float band2 = smoothstep(18.0, 22.0, depth);
        float band1 = 1.0 - band0 - band2;
        float wet = smoothstep(-0.6, 0.4, depth);
        float cover = (uCover.x * band0 + uCover.y * band1 + uCover.z * band2) * wet;
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
        float boot = uHasBoot * (1.0 - smoothstep(0.4, 0.6, depth)) * smoothstep(-1.2, -1.0, depth);
        diffuseColor.rgb = mix(diffuseColor.rgb, uBoot, boot);
        float topside = uHasBoot * (1.0 - smoothstep(-1.25, -1.15, depth));
        diffuseColor.rgb = mix(diffuseColor.rgb, uCoat, topside);
        float coatAbove = (1.0 - uHasBoot) * (1.0 - wet);
        diffuseColor.rgb = mix(diffuseColor.rgb, uCoat * (0.8 + 0.3 * coarse.r), coatAbove * (1.0 - splash * fine.b));
      }`);
  };
}

/**
 * A new material for one structure kind. Each call returns its own instance (the snag highlight changes the
 * emissive colour per obstacle); the shader program is shared through the cache key. ``detail`` sets the cost:
 * low has no fouling shader, medium reads the fouling mask once (dominant-axis projection), high blends three
 * projections at two scales.
 */
export function structureMaterial(kind, detail = 'medium') {
  const params = PRESETS[kind] || PRESETS.steel;
  const textures = structureTextures();
  const material = new THREE.MeshStandardMaterial({
    color: params.color, roughness: params.roughness, metalness: params.metalness,
    map: params.map && (detail !== 'low' || kind === 'tiles') ? textures[params.map] : null,
  });
  if (detail === 'low') {
    // low tier: no fouling shader, the base colour is pre-mixed toward the mid-depth growth tone
    material.color.lerp(new THREE.Color(0x3b3d35), params.cover[1] * 0.6);
  } else {
    material.onBeforeCompile = foulingShader(params, textures);
    material.defines = {FOUL_QUALITY: detail === 'high' ? 2 : 1};
    material.customProgramCacheKey = () => `structure-fouling-v2-${material.defines.FOUL_QUALITY}`;
  }
  material.userData.structureKind = kind;
  return material;
}
