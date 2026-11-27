// CC0 photo-scanned textures and rocks (Poly Haven, ambientCG; sources and licence proof in models/CREDITS.md),
// built into models/scan/ by tools/build_scan_materials.py. Presentation only: nothing here changes geometry the
// physics knows about.
//
// Textures are requested by name. A shared 1x1 placeholder (neutral colour, flat normal) is returned at once and
// the caller's `assign` callback receives the real texture when the WebP has loaded, so materials compile once
// and never sample an unbound texture. Clones made for a different repeat share the uploaded image.
//
//   material.map = scanTexture('coating_c', {repeat: 1 / 1.6}, (t) => { material.map = t; });
//   loadScanRocks().then((rocks) => rocks.geometry('rock_07', 1));
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

const BASE = 'models/scan/';
// Metres covered by one repeat of each texture (scan sizes from the source pages; ambientCG gives none, assumed).
export const SCAN_TILE = Object.freeze({
  sand: 2.0, shell: 3.0, gravel: 2.0, mud: 2.5, rockbed: 2.17, ripple: 12.0, macro: 47.0,
  coating: 1.6, rust: 2.2, concrete: 4.0, plate: 1.2, grating: 1.2
});
// Linear mean of every normalised colour texture (seabed sets, rock atlas, paint luminance of the coating).
export const SCAN_MEAN = 0.4;
// Habitat rocks by server variant (boulder_01 is the least round scan; it is used for rock armour only).
export const HABITAT_ROCKS = Object.freeze(['rock_07', 'rock_09', 'stone_01']);
export const ARMOUR_ROCKS = Object.freeze({scour_rock: 'boulder_01', toe_rock: 'rock_09'});

const loaded = new Map();
const placeholders = new Map();
let rocksPromise = null;

function placeholder(kind) {
  if (placeholders.has(kind)) return placeholders.get(kind);
  // colour: mid grey at the normalised mean, alpha 0 (no rust on the coating); normal: flat, roughness 0.8 in
  // alpha; mask: opaque (gratings)
  const values = {colour: [170, 170, 170, 0], normal: [128, 128, 255, 204], mask: [170, 170, 170, 255]}[kind];
  const texture = new THREE.DataTexture(new Uint8Array(values), 1, 1, THREE.RGBAFormat);
  texture.colorSpace = kind === 'normal' ? THREE.NoColorSpace : THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  texture.userData.scanPlaceholder = true;
  placeholders.set(kind, texture);
  return texture;
}

function downscale(image, size) {
  if (!size || !globalThis.document || image.width <= size) return image;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  canvas.getContext('2d').drawImage(image, 0, 0, size, size);
  return canvas;
}

function loadBase(name, size, flipY) {
  const key = `${name}:${size || 0}:${flipY}`;
  if (!loaded.has(key)) {
    loaded.set(key, new Promise(function loadImage(resolve) {
      new THREE.ImageLoader().load(BASE + name + '.webp', function onImage(image) {
        const texture = new THREE.Texture(downscale(image, size));
        texture.colorSpace = name.endsWith('_c') ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
        texture.anisotropy = 4;
        texture.flipY = flipY;
        texture.needsUpdate = true;
        texture.userData.scanName = name;
        resolve(texture);
      }, undefined, function onError() {
        resolve(null);
      });
    }));
  }
  return loaded.get(key);
}

/**
 * Placeholder texture now; `assign(texture)` once the named WebP has loaded (not called if it fails or there is
 * no browser). Options: repeat (number or [u, v]), size (downscale, e.g. 512 on the low tier), flipY (false for
 * glTF-style UVs), mask (placeholder for colour textures whose alpha is a mask).
 */
export function scanTexture(name, options = {}, assign = null) {
  const kind = name.endsWith('_n') ? 'normal' : options.mask ? 'mask' : 'colour';
  const fallback = placeholder(kind);
  if (!globalThis.document) return fallback;
  loadBase(name, options.size, options.flipY ?? true).then(function shareTexture(base) {
    if (!base || !assign) return;
    const texture = base.clone();
    const repeat = options.repeat ?? 1;
    if (Array.isArray(repeat)) texture.repeat.set(repeat[0], repeat[1]);
    else texture.repeat.set(repeat, repeat);
    assign(texture);
  });
  return fallback;
}

/** Sets a uniform's value to the placeholder now and to the loaded texture later. */
export function scanUniform(name, options = {}) {
  const uniform = {value: null};
  uniform.value = scanTexture(name, options, function assignUniform(texture) {
    uniform.value = texture;
  });
  return uniform;
}

/**
 * Rock levels from models/scan/rocks.glb: {geometry(rock, lod), inner(rock)}. Geometries are about the rock's
 * inner centre with every vertex inside the unit sphere; inner() is the radius of the largest sphere about that
 * centre inside every level, as a share of the bounding radius. Resolves null without a browser or on error.
 */
export function loadScanRocks() {
  if (rocksPromise) return rocksPromise;
  if (!globalThis.document) return Promise.resolve(null);
  rocksPromise = new GLTFLoader().loadAsync(BASE + 'rocks.glb').then(function indexRocks(gltf) {
    const levels = new Map();
    const inner = new Map();
    gltf.scene.traverse(function collect(node) {
      if (!node.isMesh || !node.userData.rock) return;
      levels.set(`${node.userData.rock}:${node.userData.lod}`, node.geometry);
      inner.set(node.userData.rock, node.userData.inner);
    });
    return {
      geometry: (rock, lod) => levels.get(`${rock}:${lod}`) || null,
      inner: (rock) => inner.get(rock) ?? 0.5
    };
  }).catch(function noRocks() {
    return null;
  });
  return rocksPromise;
}

/** Rock level by detail tier: high 1200 triangles, medium 320, low 96. */
export function rockLod(detail) {
  return {high: 0, medium: 1, low: 2}[detail] ?? 1;
}

/** Adds the rock atlas (colour and normal, glTF UVs) to a standard material once it has loaded. */
export function applyRockAtlas(material, detail = 'medium') {
  const size = detail === 'high' ? 0 : 512;
  material.map = scanTexture('rocks_c', {flipY: false, size}, function assignMap(texture) {
    material.map = texture;
  });
  if (detail !== 'low') {
    const half = detail === 'high' ? 0 : 512;
    material.normalMap = scanTexture('rocks_n', {flipY: false, size: half}, function assignNormal(texture) {
      material.normalMap = texture;
    });
  }
  // the atlas is normalised to SCAN_MEAN, so the textured rock keeps the material colour as its mean albedo
  material.color.multiplyScalar(1 / SCAN_MEAN);
  material.needsUpdate = true;
  return material;
}

/**
 * Habitat rock (server kind 'rock', variant 0-2) as a scan: its collider is a sphere of radius 0.6 x scale
 * standing on the seabed. The scan is scaled so its inner and bounding radii straddle that sphere by equal
 * amounts (what you see stays within about 0.15-0.2 x scale of what you hit) and lifted to the sphere's centre.
 */
export function habitatRockGeometry(rocks, variant, detail) {
  const rock = HABITAT_ROCKS[variant % HABITAT_ROCKS.length];
  const source = rocks.geometry(rock, rockLod(detail));
  if (!source) return null;
  const scale = 1.2 / (1 + rocks.inner(rock));
  const geometry = source.clone();
  geometry.scale(scale, scale, scale);
  geometry.translate(0, 0.6, 0);
  geometry.computeBoundingSphere();
  return geometry;
}

/** Swaps an instanced rock mesh to a scanned rock and the rock atlas once both have loaded. */
export function upgradeRockMesh(mesh, makeGeometry, detail) {
  return loadScanRocks().then(function swapRock(rocks) {
    const geometry = rocks && makeGeometry(rocks);
    if (!geometry) return false;
    mesh.geometry = geometry;
    applyRockAtlas(mesh.material, detail);
    mesh.computeBoundingSphere();
    mesh.userData.scanRock = true;
    return true;
  });
}

/**
 * Rock armour (scour protection, quay toe): every instance is scaled to stay inside its capsule from the unit
 * sphere, so the scan (all vertices inside the unit sphere) can replace the procedural rock as is. Medium and high
 * use 96 triangles a rock (a scour apron has about a thousand); low keeps the procedural 8-face rocks.
 */
export function upgradeArmourRocks(mesh, kind, detail) {
  if (detail === 'low') return Promise.resolve(false);
  const rock = ARMOUR_ROCKS[kind] || 'boulder_01';
  return upgradeRockMesh(mesh, (rocks) => rocks.geometry(rock, 2), detail);
}
