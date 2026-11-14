// Registry of marine-life meshes used by the environment and by structure growth placement.
//
// Each kind has a procedural fallback (the shapes the viewer has always drawn) and an optional GLB under
// models/marine/. A GLB asset pack can be dropped in by listing it in MARINE_MODELS; placement code asks the
// registry for a geometry and calls upgradeMarineMesh() to swap the instanced geometry once the model loads, so
// instance matrices, observation targets and animation stay untouched. No model files are listed yet.
//
//   const geometry = marineGeometry('coral', variant);
//   upgradeMarineMesh(instancedMesh, 'coral', variant);   // no-op unless MARINE_MODELS has an entry
import * as THREE from 'three';

/** kind -> list of GLB paths by variant (relative to viewer/). Empty until the marine asset pack lands. */
export const MARINE_MODELS = {
  // fish: ['models/marine/fish_0.glb', ...], coral: [...], seastar: [...], kelp: [...], seagrass: [...]
};

function mergeGeometries(list) {
  const geos = list.map((g) => (g.index ? g.toNonIndexed() : g));
  let n = 0;
  for (const g of geos) n += g.attributes.position.count;
  const pos = new Float32Array(n * 3);
  const nrm = new Float32Array(n * 3);
  let o = 0;
  for (const g of geos) {
    g.computeVertexNormals();
    pos.set(g.attributes.position.array, o * 3);
    nrm.set(g.attributes.normal.array, o * 3);
    o += g.attributes.position.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
  for (const g of new Set([...geos, ...list])) g.dispose();
  return out;
}

/** A simple streamlined body (nose +Z) with a tail fin; ~0.3 m long. */
function fishGeometry() {
  const body = new THREE.SphereGeometry(0.06, 10, 6);
  body.scale(0.55, 0.8, 2.2);
  const tail = new THREE.ConeGeometry(0.05, 0.1, 4);
  tail.rotateX(Math.PI / 2);
  tail.scale(0.25, 1.2, 1);
  tail.translate(0, 0, -0.17);
  const fin = new THREE.ConeGeometry(.035, .085, 3);
  fin.scale(.2, 1, 1);
  fin.translate(0, .065, -.02);
  return mergeGeometries([body, tail, fin]);
}

function coralGeometry(variant) {
  if (variant === 0) {
    const g = new THREE.SphereGeometry(.56, 12, 8);
    g.scale(1, .8, 1);
    g.translate(0, .44, 0);
    return g;
  }
  const branches = [];
  const up = new THREE.Vector3(0, 1, 0);
  const stem = (a, b, radius) => {
    const direction = b.clone().sub(a);
    const g = new THREE.CylinderGeometry(radius * .65, radius, direction.length(), 5);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(up, direction.clone().normalize()));
    g.translate(...a.clone().add(b).multiplyScalar(.5).toArray());
    branches.push(g);
  };
  stem(new THREE.Vector3(), new THREE.Vector3(0, .65, 0), .12);
  for (let i = 0; i < 7; i++) {
    const a = i * 2.39996;
    const h = .35 + i * .065;
    const from = new THREE.Vector3(0, h * .6, 0);
    const to = new THREE.Vector3(Math.cos(a) * .45, h, Math.sin(a) * .45);
    stem(from, to, .06);
    stem(to, to.clone().add(new THREE.Vector3(.06 * Math.sin(a), .21, .06 * Math.cos(a))), .04);
  }
  return mergeGeometries(branches);
}

function seastarGeometry() {
  const shape = new THREE.Shape();
  for (let i = 0; i < 10; i++) {
    const a = i * Math.PI / 5;
    const r = i % 2 ? .32 : 1;
    const x = Math.cos(a) * r;
    const y = Math.sin(a) * r;
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  }
  shape.closePath();
  const g = new THREE.ExtrudeGeometry(shape, {depth: .11, bevelEnabled: true, bevelThickness: .06, bevelSize: .06,
    bevelSegments: 1, steps: 1});
  g.rotateX(-Math.PI / 2);
  g.translate(0, .03, 0);
  return g;
}

/** Blade rooted at the origin, 1 m tall along +Y (instances scale it); width for kelp or seagrass. */
function bladeGeometry(kind) {
  const g = new THREE.PlaneGeometry(kind === 'seagrass' ? .07 : .18, 1, 1, 7);
  g.translate(0, .5, 0);
  return g;
}

/** Plumose anemone placeholder: a short column with a frilled crown, 1 m tall along +Y (instances scale it). */
function anemoneGeometry() {
  const column = new THREE.CylinderGeometry(.3, .38, .7, 8, 1);
  column.translate(0, .35, 0);
  const crown = new THREE.SphereGeometry(.55, 8, 5, 0, Math.PI * 2, 0, Math.PI / 2);
  crown.scale(1, .55, 1);
  crown.translate(0, .68, 0);
  return mergeGeometries([column, crown]);
}

const FALLBACK = {
  fish: () => fishGeometry(),
  coral: (variant) => coralGeometry(variant),
  seastar: () => seastarGeometry(),
  kelp: () => bladeGeometry('kelp'),
  seagrass: () => bladeGeometry('seagrass'),
  anemone: () => anemoneGeometry(),
};

/** Geometry for a marine kind and variant: the procedural fallback (GLBs are swapped in by upgradeMarineMesh). */
export function marineGeometry(kind, variant = 0) {
  const make = FALLBACK[kind];
  if (!make) throw new Error(`unknown marine kind ${kind}`);
  return make(variant);
}

/** Path of a registered GLB for kind/variant, or null. */
export function marineModelPath(kind, variant = 0) {
  const list = MARINE_MODELS[kind];
  if (!list?.length) return null;
  return list[variant % list.length];
}

/** Replace an InstancedMesh's geometry with the registered GLB's first mesh once it loads; keeps instances. */
export async function upgradeMarineMesh(mesh, kind, variant = 0) {
  const path = marineModelPath(kind, variant);
  if (!path) return false;
  const {loadGLTF} = await import('./glb.js');
  const gltf = await loadGLTF(path);
  let source = null;
  gltf.scene.traverse((o) => {
    if (!source && o.isMesh) source = o;
  });
  if (!source || !mesh.parent) return false;
  const old = mesh.geometry;
  mesh.geometry = source.geometry.clone();
  old.dispose();
  return true;
}
