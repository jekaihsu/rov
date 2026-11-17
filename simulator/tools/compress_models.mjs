// Meshopt-compress viewer GLBs and build the missing distance LODs.
// Build-time only. Run through tools/compress_models.py, which installs
// @gltf-transform and meshoptimizer. The viewer already decodes meshopt
// (viewer/glb.js) and does not need a new runtime package.
//
// Quantized meshopt (falcon, BlueROV, crew LODs) changes integer component
// types. Fish and rocks stay bit-exact floats: those parsers read the
// accessor arrays themselves, so they only get the lossless encoder.
import { readdir, readFile, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from '@gltf-transform/extensions';
import { cloneDocument, meshopt, prune, simplify, textureCompress, weld } from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';
import sharp from 'sharp';
import * as THREE from '../viewer/vendor/three/build/three.module.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MODELS = process.env.Q1_MODELS || path.join(ROOT, 'viewer', 'models');
const CREW_CLIP = 'Man_Idle';
const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({
    'meshopt.encoder': MeshoptEncoder,
    'meshopt.decoder': MeshoptDecoder,
  });

function hasMeshopt(doc) {
  return doc.getRoot().listExtensionsUsed().some((ext) => ext.extensionName === 'EXT_meshopt_compression');
}

function triangles(doc) {
  let count = 0;
  for (const mesh of doc.getRoot().listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      const index = prim.getIndices();
      const position = prim.getAttribute('POSITION');
      count += index ? index.getCount() / 3 : (position ? position.getCount() / 3 : 0);
    }
  }
  return count;
}

function names(doc) {
  return new Set(doc.getRoot().listNodes().map((node) => node.getName()));
}

function requireNames(doc, required, label) {
  const have = names(doc);
  for (const name of required) {
    if (!have.has(name)) throw new Error(`${label} is missing node ${name}`);
  }
}

function rotorOrigins(doc) {
  return doc.getRoot().listNodes()
    .filter((node) => node.getExtras().role === 'rotor')
    .map((node) => ({
      index: node.getExtras().thruster_index,
      name: node.getName(),
      t: Array.from(node.getWorldTranslation()),
    }))
    .sort((a, b) => a.index - b.index);
}

function assertRotors(before, after, label) {
  if (before.length !== after.length) {
    throw new Error(`${label} rotor count ${before.length} -> ${after.length}`);
  }
  for (let i = 0; i < before.length; i++) {
    for (let k = 0; k < 3; k++) {
      const delta = Math.abs(before[i].t[k] - after[i].t[k]);
      if (delta > 1e-4) {
        throw new Error(`${label} rotor ${before[i].name} moved by ${delta} m`);
      }
    }
  }
}

async function fileSize(file) {
  return (await stat(file)).size;
}

function logSize(label, before, after, tris) {
  console.log(`${label}: ${(before / 1e6).toFixed(2)} MB -> ${(after / 1e6).toFixed(2)} MB, ${tris} tris`);
}

async function quantizeFile(file, guards) {
  const doc = await io.read(file);
  if (hasMeshopt(doc)) {
    console.log(`skip meshopt ${path.basename(file)}`);
    return;
  }
  const before = await fileSize(file);
  const origins = rotorOrigins(doc);
  requireNames(doc, guards, path.basename(file));
  await doc.transform(meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
  assertRotors(origins, rotorOrigins(doc), path.basename(file));
  requireNames(doc, guards, path.basename(file));
  await io.write(file, doc);
  logSize(path.basename(file), before, await fileSize(file), triangles(doc));
}

async function writeLod(sourceDoc, dest, ratio, error, guards) {
  if (await exists(dest) && hasMeshopt(await io.read(dest))) {
    console.log(`skip lod ${path.basename(dest)}`);
    return;
  }
  const doc = cloneDocument(sourceDoc);
  const origins = rotorOrigins(doc);
  await doc.transform(
    simplify({ simplifier: MeshoptSimplifier, ratio, error, lockBorder: false }),
    meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
  );
  assertRotors(origins, rotorOrigins(doc), path.basename(dest));
  requireNames(doc, guards, path.basename(dest));
  await io.write(dest, doc);
  logSize(path.basename(dest), 0, await fileSize(dest), triangles(doc));
}

async function exists(file) {
  try {
    await stat(file);
    return true;
  } catch {
    return false;
  }
}

async function compressVehicle(spec) {
  const file = path.join(MODELS, spec.file);
  const doc = await io.read(file);
  for (const lod of spec.lods) {
    await writeLod(doc, path.join(MODELS, lod.file), lod.ratio, lod.error, spec.guards);
  }
  await quantizeFile(file, spec.guards);
}

function sampleTrack(times, values, stride, time, interpolation) {
  if (interpolation === 'CUBICSPLINE') {
    throw new Error('CUBICSPLINE clips need an explicit sample; Man_Idle is linear');
  }
  const keys = times.length;
  let index = 0;
  while (index < keys - 1 && times[index + 1] <= time) index += 1;
  const next = Math.min(index + 1, keys - 1);
  const span = times[next] - times[index];
  const weight = interpolation === 'STEP' || span === 0 ? 0 : (time - times[index]) / span;
  const out = new Array(stride);
  for (let k = 0; k < stride; k++) {
    const a = values[index * stride + k];
    const b = values[next * stride + k];
    out[k] = a + (b - a) * weight;
  }
  if (stride === 4) {
    const length = Math.hypot(out[0], out[1], out[2], out[3]) || 1;
    for (let k = 0; k < 4; k++) out[k] /= length;
  }
  return out;
}

function applyClip(doc, clipName, time) {
  const clip = doc.getRoot().listAnimations().find((item) => item.getName() === clipName);
  if (!clip) throw new Error(`missing clip ${clipName}`);
  for (const channel of clip.listChannels()) {
    const sampler = channel.getSampler();
    const node = channel.getTargetNode();
    if (!sampler || !node) continue;
    const output = sampler.getOutput();
    const stride = output.getElementSize();
    const sample = sampleTrack(
      sampler.getInput().getArray(),
      output.getArray(),
      stride,
      time,
      sampler.getInterpolation() || 'LINEAR',
    );
    const target = channel.getTargetPath();
    if (target === 'translation') node.setTranslation(sample);
    else if (target === 'rotation') node.setRotation(sample);
    else if (target === 'scale') node.setScale(sample);
    else throw new Error(`unsupported channel path ${target}`);
  }
}

function matrixFrom(array) {
  return new THREE.Matrix4().fromArray(Array.from(array));
}

function posedPoint(joints, point) {
  const out = new THREE.Vector3();
  const scratch = new THREE.Vector3();
  for (let k = 0; k < joints.length; k++) {
    if (!joints[k].weight) continue;
    scratch.copy(point).applyMatrix4(joints[k].matrix);
    out.addScaledVector(scratch, joints[k].weight);
  }
  return out;
}

function posedNormal(joints, normal) {
  const out = new THREE.Vector3();
  const scratch = new THREE.Vector3();
  for (let k = 0; k < joints.length; k++) {
    if (!joints[k].weight) continue;
    scratch.copy(normal).applyMatrix3(joints[k].normal);
    out.addScaledVector(scratch, joints[k].weight);
  }
  if (out.lengthSq() > 0) out.normalize();
  return out;
}

function skinMatrices(skin) {
  const joints = skin.listJoints();
  const ibm = skin.getInverseBindMatrices().getArray();
  return joints.map((joint, index) => {
    const world = matrixFrom(joint.getWorldMatrix());
    const bind = matrixFrom(ibm.slice(index * 16, index * 16 + 16));
    const matrix = world.multiply(bind);
    return { matrix, normal: new THREE.Matrix3().getNormalMatrix(matrix) };
  });
}

function bakePrimitive(prim, skin) {
  const palette = skinMatrices(skin);
  const position = prim.getAttribute('POSITION');
  const normal = prim.getAttribute('NORMAL');
  const joints = prim.getAttribute('JOINTS_0');
  const weights = prim.getAttribute('WEIGHTS_0');
  if (!position || !joints || !weights) return;
  const count = position.getCount();
  const posed = new Float32Array(count * 3);
  const posedN = normal ? new Float32Array(count * 3) : null;
  const point = [0, 0, 0];
  const n = [0, 0, 0];
  const joint = [0, 0, 0, 0];
  const weight = [0, 0, 0, 0];
  for (let i = 0; i < count; i++) {
    position.getElement(i, point);
    joints.getElement(i, joint);
    weights.getElement(i, weight);
    const influences = [0, 1, 2, 3].map((k) => ({
      matrix: palette[Math.round(joint[k])]?.matrix,
      normal: palette[Math.round(joint[k])]?.normal,
      weight: weight[k],
    })).filter((item) => item.matrix && item.weight);
    const p = posedPoint(influences, new THREE.Vector3(point[0], point[1], point[2]));
    posed[i * 3] = p.x;
    posed[i * 3 + 1] = p.y;
    posed[i * 3 + 2] = p.z;
    if (normal) {
      normal.getElement(i, n);
      const nn = posedNormal(influences, new THREE.Vector3(n[0], n[1], n[2]));
      posedN[i * 3] = nn.x;
      posedN[i * 3 + 1] = nn.y;
      posedN[i * 3 + 2] = nn.z;
    }
  }
  position.setArray(posed);
  if (normal) normal.setArray(posedN);
  for (const semantic of prim.listSemantics()) {
    if (semantic.startsWith('JOINTS') || semantic.startsWith('WEIGHTS')) prim.setAttribute(semantic, null);
  }
}

function clampUvs(doc) {
  for (const mesh of doc.getRoot().listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      const uv = prim.getAttribute('TEXCOORD_0');
      if (!uv || uv.getComponentType() !== 5126) continue;
      const array = Float32Array.from(uv.getArray());
      for (let i = 0; i < array.length; i++) {
        if (array[i] < 0) array[i] = 0;
        else if (array[i] > 1) array[i] = 1;
      }
      uv.setArray(array);
    }
  }
}

function keepSceneNodes(doc, scene) {
  const keep = new Set();
  const visit = (node) => {
    keep.add(node);
    for (const child of node.listChildren()) visit(child);
  };
  for (const node of scene.listChildren()) visit(node);
  for (const node of [...doc.getRoot().listNodes()]) {
    if (!keep.has(node)) node.dispose();
  }
}

function bakeSkins(doc) {
  const done = new Set();
  for (const node of doc.getRoot().listNodes()) {
    const skin = node.getSkin();
    const mesh = node.getMesh();
    if (!skin || !mesh) continue;
    for (const prim of mesh.listPrimitives()) {
      if (done.has(prim)) continue;
      done.add(prim);
      bakePrimitive(prim, skin);
    }
    node.setSkin(null);
  }
}

function bboxHeight(doc) {
  let low = Infinity;
  let high = -Infinity;
  for (const mesh of doc.getRoot().listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      const position = prim.getAttribute('POSITION');
      if (!position) continue;
      const array = position.getArray();
      for (let i = 1; i < array.length; i += 3) {
        low = Math.min(low, array[i]);
        high = Math.max(high, array[i]);
      }
    }
  }
  return high - low;
}

async function bakeCrew(source, dest, ratio, error, textureSize) {
  if (await exists(dest) && hasMeshopt(await io.read(dest))) {
    console.log(`skip crew ${path.basename(dest)}`);
    return;
  }
  const doc = await io.read(source);
  applyClip(doc, CREW_CLIP, 0);
  bakeSkins(doc);
  const scene = doc.createScene('CrewLOD');
  for (const node of doc.getRoot().listNodes()) {
    if (!node.getMesh()) continue;
    node.setMatrix(IDENTITY);
    scene.addChild(node);
  }
  for (const old of [...doc.getRoot().listScenes()]) {
    if (old !== scene) old.dispose();
  }
  for (const skin of [...doc.getRoot().listSkins()]) skin.dispose();
  // dispose() on an animation leaves its samplers holding accessors, and prune()
  // then keeps those accessors. Drop the sampler data before the cleanup pass.
  for (const anim of [...doc.getRoot().listAnimations()]) {
    for (const sampler of anim.listSamplers()) {
      sampler.getInput()?.dispose();
      sampler.getOutput()?.dispose();
      sampler.dispose();
    }
    anim.dispose();
  }
  keepSceneNodes(doc, scene);
  clampUvs(doc);
  console.log(
    `${path.basename(dest)} baked nodes ${doc.getRoot().listNodes().length}`
    + ` anims ${doc.getRoot().listAnimations().length}`,
  );
  const height = bboxHeight(doc);
  if (height < 4 || height > 5.6) {
    throw new Error(`${path.basename(dest)} baked height ${height.toFixed(2)} is not the 4.84 model-unit rig`);
  }
  await doc.transform(
    prune(),
    weld({}),
    simplify({ simplifier: MeshoptSimplifier, ratio, error, lockBorder: false }),
    textureCompress({
      encoder: sharp,
      targetFormat: 'webp',
      resize: [textureSize, textureSize],
      quality: 82,
    }),
    meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
    prune(),
  );
  await io.write(dest, doc);
  logSize(path.basename(dest), 0, await fileSize(dest), triangles(doc));
}

function floatSnapshot(doc) {
  const rows = [];
  doc.getRoot().listMeshes().forEach((mesh, meshIndex) => {
    mesh.listPrimitives().forEach((prim, primIndex) => {
      for (const semantic of prim.listSemantics()) {
        const accessor = prim.getAttribute(semantic);
        if (!accessor || accessor.getComponentType() !== 5126) continue;
        rows.push({
          key: `${meshIndex}:${primIndex}:${semantic}`,
          array: Float32Array.from(accessor.getArray()),
        });
      }
    });
  });
  return rows;
}

function triangleKeys(indices) {
  const keys = [];
  for (let i = 0; i < indices.length; i += 3) {
    const tri = [indices[i], indices[i + 1], indices[i + 2]];
    let start = 0;
    if (tri[1] < tri[start]) start = 1;
    if (tri[2] < tri[start]) start = 2;
    keys.push(tri[start] + ',' + tri[(start + 1) % 3] + ',' + tri[(start + 2) % 3]);
  }
  keys.sort();
  return keys.join('|');
}

function sameFloats(doc, rows) {
  const again = new Map(floatSnapshot(doc).map((row) => [row.key, row.array]));
  return rows.every((row) => {
    const array = again.get(row.key);
    if (!array || array.length !== row.array.length) return false;
    for (let i = 0; i < array.length; i++) {
      if (array[i] !== row.array[i]) return false;
    }
    return true;
  });
}

async function losslessMeshopt(file) {
  const doc = await io.read(file);
  if (hasMeshopt(doc)) {
    console.log(`skip lossless ${path.relative(MODELS, file)}`);
    return;
  }
  const before = await fileSize(file);
  const original = await readFile(file);
  const snapshot = floatSnapshot(doc);
  const trianglesBefore = doc.getRoot().listMeshes().map((mesh) => mesh.listPrimitives().map((prim) => {
    const index = prim.getIndices();
    return index ? triangleKeys(index.getArray()) : '';
  }));
  doc.createExtension(EXTMeshoptCompression)
    .setRequired(true)
    .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
  await io.write(file, doc);
  const after = await io.read(file);
  const shrunk = await fileSize(file);
  const floats = sameFloats(after, snapshot);
  const trianglesAfter = after.getRoot().listMeshes().map((mesh) => mesh.listPrimitives().map((prim) => {
    const index = prim.getIndices();
    return index ? triangleKeys(index.getArray()) : '';
  }));
  const trianglesMatch = JSON.stringify(trianglesBefore) === JSON.stringify(trianglesAfter);
  if (!floats || !trianglesMatch || shrunk >= before) {
    await writeFile(file, original);
    const why = !floats ? 'float mismatch' : (!trianglesMatch ? 'triangle mismatch' : 'not smaller');
    console.log(`keep ${path.relative(MODELS, file)} (${why})`);
    return;
  }
  logSize(path.relative(MODELS, file), before, shrunk, triangles(after));
}

async function walkGlbs(dir) {
  const found = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) found.push(...await walkGlbs(full));
    else if (entry.name.endsWith('.glb')) found.push(full);
  }
  return found;
}

async function main() {
  await MeshoptEncoder.ready;
  await MeshoptDecoder.ready;
  await MeshoptSimplifier.ready;
  const only = process.argv[2] || 'all';
  if (!['all', 'vehicles', 'crew', 'lossless'].includes(only)) {
    throw new Error(`unknown step ${only}`);
  }
  if (only === 'all' || only === 'vehicles') {
  await compressVehicle({
    file: 'falcon.glb',
    guards: ['arm_yaw', 'arm_shoulder', 'arm_elbow', 'arm_wrist', 'arm_jaw_left', 'arm_jaw_right', 'arm_tip'],
    lods: [
      { file: 'falcon_lod1.glb', ratio: 0.4, error: 0.04 },
      { file: 'falcon_lod2.glb', ratio: 0.15, error: 0.12 },
    ],
  });
  await compressVehicle({
    file: 'bluerov2_heavy.glb',
    guards: [],
    lods: [
      { file: 'bluerov2_heavy_lod1.glb', ratio: 0.4, error: 0.04 },
      { file: 'bluerov2_heavy_lod2.glb', ratio: 0.15, error: 0.12 },
    ],
  });
  }
  if (only === 'all' || only === 'crew') {
    // One far level. simplify() barely reduces this baked mesh (about 12k
    // triangles stays near 10k), so a middle file would be another download
    // with almost the same geometry. The viewer only requests worker_lod2.glb.
    const crew = path.join(MODELS, 'worker.glb');
    // error 0.35 collapsed the hard-hat shell. 0.02 keeps the dome.
    // simplify still barely reduces the triangle count, so this is a
    // quantized far level, not a second middle mesh.
    await bakeCrew(crew, path.join(MODELS, 'worker_lod2.glb'), 0.5, 0.02, 256);
  }
  if (only === 'all' || only === 'lossless') {
    for (const file of await walkGlbs(path.join(MODELS, 'fish'))) {
      if (file.endsWith('.glb')) await losslessMeshopt(file);
    }
    await losslessMeshopt(path.join(MODELS, 'scan', 'rocks.glb'));
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
