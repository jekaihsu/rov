// Snag items (world.type === 'snag') must draw inside or on their capsule colliders, same rule as
// tests/test_scene_consistency.py. Builds the viewer meshes in Node and checks every surface sample.
import assert from 'node:assert/strict';
import {register} from 'node:module';
import {test} from 'node:test';

register('../tools/three_resolve_hooks.mjs', import.meta.url);

const THREE = await import('three');
const {buildStructures, SCENE_TOLERANCE} = await import('../viewer/structures.js');
const {obstacleDistance} = await import('../viewer/structure_sdf.js');

function stubMaterial(kind) {
  const material = new THREE.MeshStandardMaterial();
  material.userData.structureKind = kind;
  return material;
}

/** Surface samples of a mesh in NED, about spacing metres apart. */
function sampleMesh(mesh, spacing = 0.2) {
  const out = [];
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  const p = new THREE.Vector3();
  const geometry = mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry;
  const position = geometry.attributes.position;
  mesh.updateMatrixWorld(true);
  for (let t = 0; t + 2 < position.count; t += 3) {
    a.fromBufferAttribute(position, t).applyMatrix4(mesh.matrixWorld);
    b.fromBufferAttribute(position, t + 1).applyMatrix4(mesh.matrixWorld);
    c.fromBufferAttribute(position, t + 2).applyMatrix4(mesh.matrixWorld);
    const ni = Math.max(1, Math.ceil(a.distanceTo(b) / spacing));
    const nj = Math.max(1, Math.ceil(a.distanceTo(c) / spacing));
    for (let i = 0; i <= ni; i++) {
      for (let j = 0; j <= nj && i / ni + j / nj <= 1 + 1e-9; j++) {
        p.copy(a).multiplyScalar(1 - i / ni - j / nj).addScaledVector(b, i / ni).addScaledVector(c, j / nj);
        out.push([p.z, -p.x, -p.y]);
      }
    }
  }
  return out;
}

const SNAGS = [
  {type: 'snag', name: 'Harbor rubble', point: [36, -2, 10], radius: 0.4, height: 0.5, kind: 'snag', item: 'rock'},
  {type: 'snag', name: 'Harbor rope tangle', point: [30, 4, 10], radius: 0.25, height: 0.3, kind: 'snag', item: 'rope'},
  {type: 'snag', name: 'Harbor mooring block', point: [24, -6, 10], radius: 0.5, height: 0.6, kind: 'snag', item: 'debris'},
  {type: 'snag', name: 'Wreck boulder 3', point: [12, 6.5, 30], radius: 0.45, height: 0.7, kind: 'snag', item: 'boulder'},
];

for (const detail of ['low', 'medium', 'high']) {
  test(`snag meshes sit inside their capsules (${detail})`, () => {
    const world = {
      seabed_depth: 30,
      scenario: {key: 'harbor_inspection', seabed_type: 'mud'},
      obstacles: SNAGS,
    };
    const set = buildStructures(world, {detail, makeMaterial: stubMaterial});
    const drawn = [...set.entries.keys()];
    for (const ob of SNAGS) {
      assert.ok(drawn.includes(ob.name), `${ob.name} must be drawn`);
    }
    // Low/medium merge by material: walk every solid mesh and check vertices against all snag colliders.
    let samples = 0;
    for (const mesh of set.group.children) {
      if (!mesh.isMesh || mesh.userData.role === 'above') continue;
      for (const ned of sampleMesh(mesh)) {
        const distance = Math.min(...SNAGS.map((ob) => obstacleDistance(ned, ob)));
        assert.ok(distance <= SCENE_TOLERANCE + 1e-3,
          `vertex ${ned} stands ${distance.toFixed(3)} m outside snag colliders`);
        samples += 1;
      }
    }
    assert.ok(samples > 20, 'expected surface samples from snag meshes');
    // Low tier must batch snags into few draw calls (merged by material after flush).
    if (detail === 'low') {
      assert.ok(set.group.children.filter((c) => c.isMesh).length <= 3,
        'low tier should merge snag materials into few meshes');
    }
  });
}
