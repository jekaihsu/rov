// Build the viewer's structure meshes in Node and print every visual part as NED surface samples.
//
//   node tools/scene_manifest.mjs < worlds.json > manifest.json
//
// Input: {"<key>": <world message>, ...}. Output: {"tolerance": m, "spacing": m, "worlds": {"<key>": [{colliders,
// role, kind, points: [[n, e, d], ...]}, ...]}}: points sample every triangle at SPACING. Used by
// tests/test_scene_consistency.py to check the meshes against the Python collision shapes. Instanced meshes are
// expanded; points are rounded to 5 mm and de-duplicated.
import {register} from 'node:module';

register('./three_resolve_hooks.mjs', import.meta.url);

const THREE = await import('three');
const {buildStructures, SCENE_TOLERANCE} = await import('../viewer/structures.js');

function readStdin() {
  return new Promise((resolve) => {
    const chunks = [];
    process.stdin.on('data', (chunk) => chunks.push(chunk));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
  });
}

function stubMaterial(kind) {
  const material = new THREE.MeshStandardMaterial();
  material.userData.structureKind = kind;
  return material;
}

const SPACING = 0.35;   // m between surface samples on a triangle

/** Surface samples of a mesh (triangle vertices, a barycentric grid and the far edge), NED, 5 mm grid. */
function partPoints(mesh, seabed) {
  const seen = new Set();
  const out = [];
  const m = new THREE.Matrix4();
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  const p = new THREE.Vector3();
  const geometry = mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry;
  const position = geometry.attributes.position;
  const count = mesh.isInstancedMesh ? mesh.count : 1;
  mesh.updateMatrixWorld(true);
  function keep(v) {
    const ned = [Math.round(v.z * 200) / 200, Math.round(-v.x * 200) / 200, Math.round(-v.y * 200) / 200];
    const key = ned.join(',');
    if (seen.has(key)) return;
    seen.add(key);
    out.push(ned);
  }
  for (let k = 0; k < count; k++) {
    if (mesh.isInstancedMesh) mesh.getMatrixAt(k, m);
    else m.identity();
    m.premultiply(mesh.matrixWorld);
    for (let t = 0; t + 2 < position.count; t += 3) {
      a.fromBufferAttribute(position, t).applyMatrix4(m);
      b.fromBufferAttribute(position, t + 1).applyMatrix4(m);
      c.fromBufferAttribute(position, t + 2).applyMatrix4(m);
      if (Math.min(a.y, b.y, c.y) > 0 || Math.max(a.y, b.y, c.y) < -seabed) continue;   // above water / buried
      // grid along the two edges from a, each at most SPACING apart: slivers get few samples
      const ni = Math.max(1, Math.ceil(a.distanceTo(b) / SPACING));
      const nj = Math.max(1, Math.ceil(a.distanceTo(c) / SPACING));
      for (let i = 0; i <= ni; i++) {
        for (let j = 0; j <= nj && i / ni + j / nj <= 1 + 1e-9; j++) {
          p.copy(a).multiplyScalar(1 - i / ni - j / nj).addScaledVector(b, i / ni).addScaledVector(c, j / nj);
          keep(p);
        }
      }
      for (let k = 0; k <= Math.max(ni, nj); k++) {
        const t = k / Math.max(ni, nj);
        keep(p.copy(b).lerp(c, t));
      }
    }
  }
  return out;
}

function describe(mesh, seabed) {
  return {
    colliders: mesh.userData.colliders || [],
    role: mesh.userData.role || 'solid',
    kind: mesh.material.userData.structureKind || '',
    points: partPoints(mesh, seabed),
  };
}

const input = JSON.parse(await readStdin());
const result = {tolerance: SCENE_TOLERANCE, spacing: SPACING, worlds: {}};
for (const [key, world] of Object.entries(input)) {
  const set = buildStructures(world, {detail: process.env.SCENE_DETAIL || 'medium', makeMaterial: stubMaterial});
  result.worlds[key] = set.group.children.filter((o) => o.isMesh).map((o) => describe(o, world.seabed_depth));
}
process.stdout.write(JSON.stringify(result));
