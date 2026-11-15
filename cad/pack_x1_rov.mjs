/**
 * Merge the X1 training GLB by material and emit three LODs.
 *
 * Usage (repository root):
 *   node cad/pack_x1_rov.mjs
 *
 * Preserves each role=rotor empty as an independent named spin pivot with its
 * propeller mesh attached. Static meshes are flattened and joined by material.
 * LOD0 keeps full geometry; LOD1 / LOD2 simplify toward ~80k / ~20k triangles.
 */
import { copyFileSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import {
  dedup,
  dequantize,
  join as joinMeshes,
  joinPrimitives,
  meshopt,
  prune,
  quantize,
  simplify,
  transformMesh,
  weld,
} from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';

const require = createRequire(import.meta.url);
const { mat4 } = require('gl-matrix');

const IDENTITY = mat4.create();

/**
 * X1_GEOMETRY carries a non-uniform scale. Flattening through TRS decomposition
 * drops the shear that scale×rotation creates. Bake every mesh into
 * X1_GEOMETRY's local space (or the scene, if that node is missing) using the
 * true world matrix, then reparent — keeping the calibration scale so the
 * viewer Box3 / centring matches the pre-I1 training model.
 */
function uniqueMeshForNode(node) {
  const mesh = node.getMesh();
  if (!mesh) return null;
  // Instanced thruster parts share one Mesh; clone before baking a per-node transform.
  const nodeParents = mesh.listParents().filter((parent) => parent.propertyType === 'Node');
  if (nodeParents.length > 1) {
    const clone = mesh.clone();
    node.setMesh(clone);
    return clone;
  }
  return mesh;
}

function findGeometryRoot(document) {
  return document.getRoot().listNodes().find((node) => (node.getName() || '').startsWith('X1_GEOMETRY'))
    || null;
}

function bakeMeshesToGeometry(document) {
  const scene = document.getRoot().listScenes()[0];
  const geometryRoot = findGeometryRoot(document);
  const spaceNode = geometryRoot || scene;
  const spaceWorld = geometryRoot
    ? Float32Array.from(geometryRoot.getWorldMatrix())
    : IDENTITY;
  const spaceInverse = geometryRoot ? mat4.invert(mat4.create(), spaceWorld) : IDENTITY;
  if (geometryRoot && !spaceInverse) throw new Error('singular X1_GEOMETRY matrix');

  const meshNodes = document.getRoot().listNodes().filter((node) => node.getMesh());
  for (const node of meshNodes) {
    if (node === geometryRoot) continue;
    const mesh = uniqueMeshForNode(node);
    const local = mat4.multiply(
      mat4.create(),
      spaceInverse,
      Float32Array.from(node.getWorldMatrix()),
    );
    transformMesh(mesh, local);
    node.setMatrix(IDENTITY);
    const parent = node.getParentNode();
    if (parent) parent.removeChild(node);
    for (const other of document.getRoot().listScenes()) {
      if (other.listChildren().includes(node)) other.removeChild(node);
    }
    if (geometryRoot) geometryRoot.addChild(node);
    else scene.addChild(node);
  }
}

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const MODELS = join(ROOT, 'simulator/viewer/models');
const SOURCE = join(MODELS, 'rov.glb');
const BASELINE = join(ROOT, 'simulator/output/x1-lod/baseline/rov.glb');
const REPORT = join(ROOT, 'docs/design/vehicle/x1-lod-report.json');
const DRAW_CALL_BUDGET = 40;

const LODS = [
  { file: 'rov.glb', ratio: null, error: null },
  // Targets ~80k / ~20k drawn triangles from the joined 486k LOD0 mesh.
  { file: 'rov_lod1.glb', ratio: 0.135, error: 0.04 },
  { file: 'rov_lod2.glb', ratio: 0.02, error: 0.35 },
];

await MeshoptDecoder.ready;
await MeshoptEncoder.ready;
await MeshoptSimplifier.ready;

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'meshopt.decoder': MeshoptDecoder,
  'meshopt.encoder': MeshoptEncoder,
});

function drawnTriangles(document) {
  const meshTris = new Map();
  for (const mesh of document.getRoot().listMeshes()) {
    let count = 0;
    for (const prim of mesh.listPrimitives()) {
      const indices = prim.getIndices();
      count += indices ? indices.getCount() / 3 : (prim.getAttribute('POSITION')?.getCount() || 0) / 3;
    }
    meshTris.set(mesh, count);
  }
  let drawn = 0;
  for (const node of document.getRoot().listNodes()) {
    const mesh = node.getMesh();
    if (mesh) drawn += meshTris.get(mesh) || 0;
  }
  return Math.round(drawn);
}

function rotorNodes(document) {
  return document.getRoot().listNodes().filter((node) => node.getExtras()?.role === 'rotor');
}

function collectSubtree(rootNode) {
  const out = [];
  const visit = (node) => {
    out.push(node);
    for (const child of node.listChildren()) visit(child);
  };
  visit(rootNode);
  return out;
}

function primGroupKey(prim) {
  // Group by material identity + mode + attribute set so joinPrimitives may run.
  const material = prim.getMaterial();
  const semantics = prim.listSemantics().slice().sort().join('+');
  return `${material ? material.getName() + '#' + documentId(material) : 'null'}|${prim.getMode()}|${semantics}`;
}

const _ids = new WeakMap();
let _nextId = 1;
function documentId(obj) {
  if (!_ids.has(obj)) _ids.set(obj, _nextId++);
  return _ids.get(obj);
}

function countDrawCalls(document) {
  let calls = 0;
  for (const node of document.getRoot().listNodes()) {
    const mesh = node.getMesh();
    if (mesh) calls += mesh.listPrimitives().length;
  }
  return calls;
}

function describe(document, path) {
  const root = document.getRoot();
  return {
    file: path.split('/').pop(),
    bytes: statSync(path).size,
    triangles_drawn: drawnTriangles(document),
    materials: root.listMaterials().length,
    nodes: root.listNodes().length,
    mesh_nodes: root.listNodes().filter((node) => node.getMesh()).length,
    draw_calls: countDrawCalls(document),
    rotors: rotorNodes(document).map((node) => ({
      name: node.getName(),
      extras: node.getExtras(),
      hasMesh: !!node.getMesh(),
      primitives: node.getMesh()?.listPrimitives().length || 0,
      children: node.listChildren().length,
    })),
    extensions: root.listExtensionsUsed().map((ext) => ext.extensionName),
  };
}

/** Drop UVs so same-material parts share one attribute layout and can join. */
function stripTexcoords(prim) {
  for (const semantic of prim.listSemantics()) {
    if (semantic.startsWith('TEXCOORD_') || semantic === 'TANGENT') {
      prim.setAttribute(semantic, null);
    }
  }
}

/**
 * Bake every mesh under a rotor empty onto that empty (rotor-local space), then
 * join same-material primitives so each propeller stays a few draw calls that
 * still spin with the empty.
 */
function consolidateRotors(document) {
  for (const rotor of rotorNodes(document)) {
    const rotorWorld = mat4.clone(rotor.getWorldMatrix());
    const rotorInverse = mat4.invert(mat4.create(), rotorWorld);
    if (!rotorInverse) throw new Error(`singular rotor matrix: ${rotor.getName()}`);
    const meshNodes = collectSubtree(rotor).filter((node) => node !== rotor && node.getMesh());
    if (!meshNodes.length) continue;

    const groups = new Map();
    for (const node of meshNodes) {
      // Use the true world matrix (keeps shear from X1_GEOMETRY's non-uniform scale).
      // Do not clearNodeParent/setMatrix — TRS decomposition would drop that shear.
      const mesh = uniqueMeshForNode(node);
      const relative = mat4.multiply(
        mat4.create(),
        rotorInverse,
        Float32Array.from(node.getWorldMatrix()),
      );
      transformMesh(mesh, relative);
      for (const prim of mesh.listPrimitives()) {
        stripTexcoords(prim);
        const key = primGroupKey(prim);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(prim);
      }
    }

    const mesh = document.createMesh(rotor.getName() || 'rotor');
    for (const prims of groups.values()) {
      mesh.addPrimitive(prims.length === 1 ? prims[0] : joinPrimitives(prims));
    }
    rotor.setMesh(mesh);

    for (const node of meshNodes) {
      const oldMesh = node.getMesh();
      node.setMesh(null);
      if (oldMesh && oldMesh.listParents().length <= 1) oldMesh.dispose();
      detachAndDispose(document, node);
    }
    for (const child of [...rotor.listChildren()]) {
      rotor.removeChild(child);
      detachAndDispose(document, child);
    }
  }
}

/**
 * After bakeMeshesToGeometry, join may leave a few same-material static nodes apart.
 * Force one unnamed node per material under the geometry root (or scene).
 */
function forceJoinStatic(document) {
  const geometryRoot = findGeometryRoot(document);
  const parent = geometryRoot || document.getRoot().listScenes()[0];
  const protectedNodes = new Set(rotorNodes(document));
  const staticNodes = document.getRoot().listNodes().filter(
    (node) => node.getMesh() && !protectedNodes.has(node),
  );
  if (staticNodes.length <= 1) return;

  const groups = new Map();
  for (const node of staticNodes) {
    for (const prim of [...node.getMesh().listPrimitives()]) {
      stripTexcoords(prim);
      node.getMesh().removePrimitive(prim);
      const key = primGroupKey(prim);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(prim);
    }
  }

  for (const prims of groups.values()) {
    const joined = prims.length === 1 ? prims[0] : joinPrimitives(prims);
    const mesh = document.createMesh('');
    mesh.addPrimitive(joined);
    parent.addChild(document.createNode('').setMesh(mesh));
  }

  for (const node of staticNodes) {
    node.setMesh(null);
    detachAndDispose(document, node);
  }
}

function detachAndDispose(document, node) {
  const parent = node.getParentNode();
  if (parent) parent.removeChild(node);
  for (const scene of document.getRoot().listScenes()) {
    if (scene.listChildren().includes(node)) scene.removeChild(node);
  }
  for (const child of [...node.listChildren()]) {
    node.removeChild(child);
    detachAndDispose(document, child);
  }
  node.dispose();
}

/** Strip names from static mesh nodes so join can merge them by material. */
function stripStaticNames(document) {
  const protectedNodes = new Set(rotorNodes(document));
  for (const node of document.getRoot().listNodes()) {
    if (protectedNodes.has(node) || !node.getMesh()) continue;
    node.setName('');
    node.getMesh().setName('');
  }
}

async function prepareMerged(document) {
  // meshopt stores NORMAL as normalized ints; transformMesh's normal path corrupts
  // those when writing back. Dequantize to float before any vertex bake.
  await document.transform(dequantize(), dedup());
  consolidateRotors(document);
  stripStaticNames(document);
  bakeMeshesToGeometry(document);
  await document.transform(joinMeshes({ keepNamed: true, keepMeshes: false }));
  forceJoinStatic(document);
  await document.transform(prune({ keepLeaves: true }));
}

async function writeCompressed(document, outPath, { weldFirst = true, positionBits = 14 } = {}) {
  const steps = [];
  if (weldFirst) steps.push(weld({ overwrite: true }));
  steps.push(
    quantize({ quantizePosition: positionBits, quantizeNormal: 12 }),
    meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
  );
  await document.transform(...steps);
  await io.write(outPath, document);
}

async function buildLod(sourcePath, lod) {
  const document = await io.read(sourcePath);
  await prepareMerged(document);
  if (lod.ratio != null) {
    await document.transform(
      weld({ overwrite: true, tolerance: 0.0001 }),
      simplify({ simplifier: MeshoptSimplifier, ratio: lod.ratio, error: lod.error }),
    );
    await document.transform(prune({ keepLeaves: true }));
  }
  const outPath = join(MODELS, lod.file);
  // LOD0 skips weld and keeps 16-bit positions so the joined mesh matches the bar.
  const lod0 = lod.ratio == null;
  await writeCompressed(document, outPath, {
    weldFirst: !lod0,
    positionBits: lod0 ? 16 : 14,
  });
  return describe(await io.read(outPath), outPath);
}

mkdirSync(dirname(BASELINE), { recursive: true });
try {
  statSync(BASELINE);
} catch {
  copyFileSync(SOURCE, BASELINE);
}

const baseline = describe(await io.read(BASELINE), BASELINE);
console.log('baseline', JSON.stringify({
  file: baseline.file,
  bytes: baseline.bytes,
  triangles_drawn: baseline.triangles_drawn,
  mesh_nodes: baseline.mesh_nodes,
  materials: baseline.materials,
  rotors: baseline.rotors.length,
}, null, 2));

const working = join(ROOT, 'simulator/output/x1-lod/working-source.glb');
copyFileSync(BASELINE, working);

const report = {
  source: 'simulator/output/x1-lod/baseline/rov.glb',
  baseline,
  lods: [],
  draw_call_budget: DRAW_CALL_BUDGET,
};
for (const lod of LODS) {
  const info = await buildLod(working, lod);
  report.lods.push(info);
  console.log(
    `${info.file.padEnd(16)} ${(info.bytes / 1e6).toFixed(2)} MB  ${String(info.triangles_drawn).padStart(7)} tris  ` +
      `${info.draw_calls} draws  ${info.materials} mats  rotors=${info.rotors.length}`,
  );
}

mkdirSync(dirname(REPORT), { recursive: true });
writeFileSync(REPORT, `${JSON.stringify(report, null, 2)}\n`);

const lod0 = report.lods[0];
if (lod0.draw_calls > DRAW_CALL_BUDGET) {
  console.error(`LOD0 draw calls ${lod0.draw_calls} exceed budget ${DRAW_CALL_BUDGET}`);
  process.exitCode = 1;
}
if (lod0.rotors.length !== 6 || lod0.rotors.some((rotor) => !rotor.hasMesh)) {
  console.error('expected 6 rotors with meshes', lod0.rotors);
  process.exitCode = 1;
}
