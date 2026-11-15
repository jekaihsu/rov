// Measure the live collider-derived renderer separately from the Blender interchange export.
import {register} from 'node:module';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const {buildStructures} = await import('../viewer/structures.js');
const world = JSON.parse(readFileSync(new URL('../output/wind-jacket/colliders.json', import.meta.url)));
world.scenario = {key: 'jacket_inspection'};
const report = {};
function material(kind) {
  const value = new THREE.MeshStandardMaterial();
  value.userData.structureKind = kind;
  return value;
}
for (const detail of ['low', 'medium', 'high']) {
  const set = buildStructures(world, {detail, makeMaterial: material});
  let underwater = 0;
  let above = 0;
  let calls = 0;
  set.group.updateMatrixWorld(true);
  set.group.traverse(function measure(mesh) {
    if (!mesh.isMesh) return;
    calls++;
    const g = mesh.geometry;
    const p = g.attributes.position;
    const matrix = new THREE.Matrix4();
    const v = new THREE.Vector3();
    for (let instance = 0; instance < (mesh.isInstancedMesh ? mesh.count : 1); instance++) {
      matrix.identity();
      if (mesh.isInstancedMesh) mesh.getMatrixAt(instance, matrix);
      matrix.premultiply(mesh.matrixWorld);
      for (let i = 0; i < (g.index?.count ?? p.count); i += 3) {
        const heights = [];
        for (let j = 0; j < 3; j++) {
          v.fromBufferAttribute(p, g.index ? g.index.getX(i + j) : i + j).applyMatrix4(matrix);
          heights.push(v.y);
        }
        if (Math.min(...heights) < 0) underwater++;
        if (Math.max(...heights) >= 0) above++;
      }
    }
  });
  if (underwater > 250000 || above > 80000) throw new Error(`Geometry budget exceeded: ${detail}`);
  report[detail] = {underwaterTriangles: underwater, aboveWaterTriangles: above,
    drawCallsBeforeFrustumCulling: calls, proceduralTextureUpperBoundBytes: 5 * 256 * 256 * 4 * 4 / 3};
}
const directory = new URL('../../docs/design/scenes/wind-jacket/', import.meta.url);
mkdirSync(directory, {recursive: true});
writeFileSync(new URL('live-asset-report.json', directory), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
