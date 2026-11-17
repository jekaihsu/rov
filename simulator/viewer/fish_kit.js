// Photo-modelled fish from the CC0 Fish Kit (models/fish/, provenance in models/CREDITS.md): which species swim at
// each site, reading the kit's GLB files, and turning them into bodies for the swimming shader of fish_life.js.
//
// Every species comes at three levels of detail: the kit's full model (about 5,000 triangles), its distance model
// (about 700) and two crossed cards (16 triangles) baked from the full model by tools/build_fish_kit.py for far
// fish. All three are unit bodies with the nose on +Z, the species' typical length in metres, an `aSheen`
// attribute (1 on the scaled body, 0 on fins) and texture coordinates; fish_life.js swimMaterial() draws them
// with the travelling body wave and the water optics like any other MeshStandardMaterial. The kit's own
// motion code (three.js r187) is not used: only the wave parameters stored in each model (node extras `swim`).
//
//   const species = schoolKitSpecies(world, school.id);           // 'madai', 'aji', ...
//   const asset = await loadKitSpecies(species);                  // {full, distance, card, map, cardMap, ...}
//   mesh.material = kitMaterial(asset, 'full');                   // shared by 'full' and 'distance'
import * as THREE from 'three';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import {swimMaterial} from './fish_life.js';
import {siteProfile} from './seabed.js';

await MeshoptDecoder.ready;

const BASE = 'models/fish/';
// Typical length (m) the model is drawn at; instance scale varies it by +-15 %. Wild school fish at the size
// usually seen round coastal structures, the farmed red sea bream at market size (about 1-1.5 kg).
export const KIT_SPECIES = Object.freeze({
  aji: {length: 0.24},
  saba: {length: 0.32},
  buri: {length: 0.65},
  kurodai: {length: 0.32},
  mebaru: {length: 0.2},
  madai: {length: 0.38},
  isaki: {length: 0.3},
  isaki_young: {length: 0.15},
  shibudai: {length: 0.42},
  onagagure: {length: 0.36},
  kuchibuto: {length: 0.3},
});
// Server school k at a site swims as SITE_SPECIES[site][k % length] (docs/design/fish-kit/README.md: why).
export const SITE_SPECIES = Object.freeze({
  pen: ['madai'],
  offshore: ['saba', 'aji', 'buri', 'saba'],
  harbour: ['aji', 'kurodai', 'mebaru', 'kurodai'],
  reef: ['isaki', 'shibudai', 'onagagure', 'kuchibuto'],
  seagrass: ['isaki_young', 'kurodai', 'aji', 'isaki_young'],
  wreck: ['isaki', 'mebaru', 'isaki', 'mebaru'],
  pool: ['aji'],
});
export const FARMED_SPECIES = 'madai';
// The kit's convention: the snout is 47 % of the body length ahead of the model's centre.
const SNOUT = 0.47;
// Card atlas layout (tools/build_fish_kit.py): side view over the top rows, top view below.
const CARD_SIDE_ROWS = 80;
const CARD_TOP_ROWS = 48;
const CARD_SEGMENTS = 4;
// Kit body parts (_FIN.x): 0 body, 1 dorsal, 2 anal, 3 caudal, 4 pectoral, 5 pelvic, 6 eye, 7 gill cover,
// 8 and 9 jaw plates. Scaled skin can be silver; fins and the eye cannot.
const SKIN_PARTS = new Set([0, 7, 8, 9]);
// Diffuse albedo of the photographed texture: overall, and of grey (silver) skin. See fish_life.js PHOTO_FRAGMENT.
const PHOTO_ALBEDO = [0.35, 0.6];
const ATLAS_ROWS = 640;

let tierDetail = 'medium';
const cache = new Map();

/** Fish site of a world: pen, offshore, harbour, reef, seagrass, wreck or pool. */
export function fishSite(world) {
  if (String(world?.scenario?.key || '').startsWith('aquaculture_pen')) return 'pen';
  if ((world?.biome || world?.habitat?.biome) === 'aquaculture') return 'pen';
  return siteProfile(world);
}

/** Kit species of one server school (`school-<k>`, `pen-school-<k>`). */
export function schoolKitSpecies(world, schoolId) {
  const list = SITE_SPECIES[fishSite(world)] || SITE_SPECIES.offshore;
  const match = /(\d+)$/.exec(String(schoolId));
  const index = match ? Number(match[1]) : 0;
  return list[index % list.length];
}

/** Render tier the scene was built for; pen_life.js picks the dead fish's model with it. */
export function setKitDetail(detail) {
  tierDetail = detail;
}

export function kitDetail() {
  return tierDetail;
}

const COMPONENTS = {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4};
const ARRAYS = {5126: Float32Array, 5125: Uint32Array, 5123: Uint16Array, 5121: Uint8Array};

const decodedViews = new WeakMap();

// Lossless EXT_meshopt_compression: the accessor stays the kit's float layout.
// The bufferView's own byteOffset is the decoded logical range and can overlap
// the atlas, so the compressed bytes are the extension's range.
function decodedView(view, binary) {
  const ext = view.extensions && view.extensions.EXT_meshopt_compression;
  if (!ext) return null;
  const cached = decodedViews.get(view);
  if (cached) return cached;
  const source = new Uint8Array(binary, ext.byteOffset || 0, ext.byteLength);
  const target = new Uint8Array(ext.count * ext.byteStride);
  MeshoptDecoder.decodeGltfBuffer(target, ext.count, ext.byteStride, source, ext.mode, ext.filter || 'NONE');
  decodedViews.set(view, target);
  return target;
}

function readAccessor(document, binary, index) {
  const item = document.accessors[index];
  const view = document.bufferViews[item.bufferView];
  const Type = ARRAYS[item.componentType];
  if (!Type) throw new Error(`fish accessor component type ${item.componentType} is not a kit float/index`);
  const size = COMPONENTS[item.type];
  const decoded = decodedView(view, binary);
  const start = (decoded ? 0 : (view.byteOffset || 0)) + (item.byteOffset || 0);
  const bytes = item.count * size * Type.BYTES_PER_ELEMENT;
  const source = decoded ? decoded : new Uint8Array(binary);
  const raw = source.buffer.slice(source.byteOffset + start, source.byteOffset + start + bytes);
  return {array: new Type(raw), size};
}

/**
 * The kit's GLB as plain arrays: one primitive with POSITION, NORMAL, TEXCOORD_0 and _FIN (body part), its index,
 * the embedded atlas bytes (null in a distance model) and the `swim` extras. Only the layout the kit writes.
 */
export function parseFishGlb(buffer) {
  const view = new DataView(buffer);
  if (view.getUint32(0, true) !== 0x46546c67) throw new Error('not a GLB file');
  const jsonLength = view.getUint32(12, true);
  const document = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 20, jsonLength)));
  const binaryStart = 20 + jsonLength + 8;
  const binary = buffer.slice(binaryStart, binaryStart + view.getUint32(20 + jsonLength, true));
  const primitive = document.meshes[0].primitives[0];
  const attribute = (name) => readAccessor(document, binary, primitive.attributes[name]).array;
  const image = document.images?.[0];
  let atlas = null;
  if (image) {
    const imageView = document.bufferViews[image.bufferView];
    const start = imageView.byteOffset || 0;
    atlas = {bytes: new Uint8Array(binary.slice(start, start + imageView.byteLength)), type: image.mimeType};
  }
  const node = document.nodes.find((item) => item.extras?.swim);
  return {
    positions: attribute('POSITION'),
    normals: attribute('NORMAL'),
    uvs: attribute('TEXCOORD_0'),
    parts: attribute('_FIN'),
    indices: readAccessor(document, binary, primitive.indices).array,
    atlas,
    swim: node.extras.swim,
  };
}

function bodyParameters(swim, length) {
  return {
    body: {snout: SNOUT * length, length, wave: (Math.PI * 2) / swim.lambda},
    envelope: (swim.env || [0.02, -0.08, 0.16]).map((value) => value * swim.amp),
  };
}

// Kit model axes: x along the body with the snout at +swim.snout, y up, z to the side, length swim.length.
// Ours: nose +Z, the snout SNOUT x length ahead of the origin, at `length` metres.
function placer(swim, length) {
  const scale = length / swim.length;
  const shift = SNOUT * length - swim.snout * scale;
  return function place(x, y, z, out, offset) {
    out[offset] = -z * scale;
    out[offset + 1] = y * scale;
    out[offset + 2] = x * scale + shift;
  };
}

// The kit's fixFinEdges: fin texels start four rows below the body photo and body vertices stop one row above
// its lower edge, so no line of body colour shows along fin edges.
function fixFinEdges(uvs, parts, rows) {
  let bodyV = 0;
  for (let i = 0; i < uvs.length / 2; i++) {
    if (Math.round(parts[i * 3]) === 0) bodyV = Math.max(bodyV, uvs[i * 2 + 1]);
  }
  const minV = bodyV + 4 / rows;
  const maxV = bodyV - 1 / rows;
  for (let i = 0; i < uvs.length / 2; i++) {
    const part = Math.round(parts[i * 3]);
    if (part !== 0 && part !== 6 && part !== 7 && uvs[i * 2 + 1] < minV) uvs[i * 2 + 1] = minV;
    if (part === 0 && uvs[i * 2 + 1] > maxV) uvs[i * 2 + 1] = maxV;
  }
}

/** Body geometry (nose +Z, `length` metres) of a parsed kit model; userData carries the swim parameters. */
export function kitGeometry(parsed, length) {
  const count = parsed.positions.length / 3;
  const place = placer(parsed.swim, length);
  const positions = new Float32Array(count * 3);
  const normals = new Float32Array(count * 3);
  const sheen = new Float32Array(count);
  const uvs = Float32Array.from(parsed.uvs);
  fixFinEdges(uvs, parsed.parts, ATLAS_ROWS);
  for (let i = 0; i < count; i++) {
    const p = parsed.positions;
    const n = parsed.normals;
    place(p[i * 3], p[i * 3 + 1], p[i * 3 + 2], positions, i * 3);
    normals[i * 3] = -n[i * 3 + 2];
    normals[i * 3 + 1] = n[i * 3 + 1];
    normals[i * 3 + 2] = n[i * 3];
    sheen[i] = SKIN_PARTS.has(Math.round(parsed.parts[i * 3])) ? 1 : 0;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
  geometry.setAttribute('aSheen', new THREE.BufferAttribute(sheen, 1));
  geometry.setIndex(new THREE.BufferAttribute(parsed.indices, 1));
  geometry.userData.fishSwim = bodyParameters(parsed.swim, length);
  return geometry;
}

function bounds(positions) {
  const low = [Infinity, Infinity, Infinity];
  const high = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i += 3) {
    for (let k = 0; k < 3; k++) {
      low[k] = Math.min(low[k], positions[i + k]);
      high[k] = Math.max(high[k], positions[i + k]);
    }
  }
  return {low, high};
}

/**
 * Two crossed cards for a far fish: the side view in the mid plane and the top view in the horizontal plane, each
 * CARD_SEGMENTS quads along the body so the body wave bends them. Same frame and length as kitGeometry().
 */
export function cardGeometry(parsed, length) {
  const {low, high} = bounds(parsed.positions);
  const place = placer(parsed.swim, length);
  const rows = CARD_SIDE_ROWS + CARD_TOP_ROWS;
  const positions = [];
  const uvs = [];
  const indices = [];
  const corner = [0, 0, 0];
  function addCard(across, vOf) {
    const start = positions.length / 3;
    for (let i = 0; i <= CARD_SEGMENTS; i++) {
      const u = i / CARD_SEGMENTS;
      const x = low[0] + (high[0] - low[0]) * u;
      for (const edge of [0, 1]) {
        const point = across(x, edge);
        place(point[0], point[1], point[2], corner, 0);
        positions.push(...corner);
        uvs.push(u, vOf(edge));
      }
    }
    for (let i = 0; i < CARD_SEGMENTS; i++) {
      const a = start + i * 2;
      indices.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
    }
  }
  // Side card: image rows run from the back (high y) down to the belly.
  addCard((x, edge) => [x, edge ? low[1] : high[1], 0], (edge) => (edge ? CARD_SIDE_ROWS : 0) / rows);
  // Top card: rows run across the body from -z to +z.
  addCard((x, edge) => [x, 0, edge ? high[2] : low[2]], (edge) => (CARD_SIDE_ROWS + (edge ? CARD_TOP_ROWS : 0)) / rows);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  const count = positions.length / 3;
  geometry.setAttribute('aSheen', new THREE.Float32BufferAttribute(new Array(count).fill(1), 1));
  // 0 on the side card, 1 on the top card (fish_life.js CARD_FOLD).
  geometry.setAttribute('aCard', new THREE.Float32BufferAttribute(
    Array.from({length: count}, (_, i) => (i < count / 2 ? 0 : 1)), 1));
  geometry.setIndex(indices);
  // Normals of the winding; the double-sided material turns them towards the viewer.
  geometry.computeVertexNormals();
  geometry.userData.fishSwim = bodyParameters(parsed.swim, length);
  return geometry;
}

async function imageTexture(blob) {
  let image;
  if (typeof createImageBitmap === 'function') {
    image = await createImageBitmap(blob, {premultiplyAlpha: 'none', colorSpaceConversion: 'none'});
  } else {
    const url = URL.createObjectURL(blob);
    image = new Image();
    image.src = url;
    await image.decode();
    URL.revokeObjectURL(url);
  }
  const texture = new THREE.Texture(image);
  texture.flipY = false;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return texture;
}

async function fetchCard(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`cannot load ${url}`);
  return response.blob();
}

async function loadSpecies(id) {
  const {fetchGlb} = await import('./glb.js');
  const [fullBuffer, distanceBuffer, cardBlob] = await Promise.all([fetchGlb(`${BASE}${id}.glb`),
    fetchGlb(`${BASE}${id}_lo.glb`), fetchCard(`${BASE}${id}_card.webp`)]);
  const full = parseFishGlb(fullBuffer);
  const distance = parseFishGlb(distanceBuffer);
  const length = KIT_SPECIES[id].length;
  const [map, cardMap] = await Promise.all([imageTexture(new Blob([full.atlas.bytes], {type: full.atlas.type})),
    imageTexture(cardBlob)]);
  return {
    id,
    length,
    full: kitGeometry(full, length),
    distance: kitGeometry(distance, length),
    card: cardGeometry(full, length),
    map,
    cardMap,
  };
}

/** Load one species once (all three levels and both textures); rejects where files cannot be fetched. */
export function loadKitSpecies(id) {
  if (!KIT_SPECIES[id]) return Promise.reject(new Error(`unknown kit species ${id}`));
  if (!cache.has(id)) {
    const promise = loadSpecies(id);
    promise.catch(() => cache.delete(id));
    cache.set(id, promise);
  }
  return cache.get(id);
}

/** Swimming material for a level: 'full' and 'distance' share the model atlas, 'card' uses the card atlas. */
export function kitMaterial(asset, level, tint = 0xffffff) {
  const geometry = asset[level];
  const {body, envelope} = geometry.userData.fishSwim;
  // Texture objects per material, sharing the decoded image (three uploads one GL texture per image source), so
  // disposing one site's materials does not free another site's textures.
  const map = (level === 'card' ? asset.cardMap : asset.map).clone();
  return swimMaterial({body, envelope, map, photo: PHOTO_ALBEDO, tint, card: level === 'card'});
}
