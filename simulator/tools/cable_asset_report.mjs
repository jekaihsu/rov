// Reproducible runtime geometry and portable-asset budgets, including the shared seabed texture allocation.
import {register} from 'node:module';
import {execFileSync} from 'node:child_process';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const {buildStructures} = await import('../viewer/structures.js');
const world = JSON.parse(execFileSync('python', ['-c',
  'import json; from qysim.engine import Simulator; from qysim.server import _json_default; ' +
  'print(json.dumps(Simulator("cable_survey",51).world_description(),default=_json_default))'],
{cwd: new URL('..', import.meta.url), encoding: 'utf8', maxBuffer: 16000000}));
const report = {tiers: {}, files: {}, seed: 51};
for (const detail of ['low', 'medium', 'high']) {
  const materials = new Map();
  const set = buildStructures(world, {detail, makeMaterial: (kind) => {
    if (!materials.has(kind)) materials.set(kind, new THREE.MeshStandardMaterial());
    materials.get(kind).userData.structureKind = kind;
    return materials.get(kind);
  }});
  let triangles = 0;
  let calls = 0;
  set.group.traverse((mesh) => {
    if (!mesh.isMesh) return;
    calls++;
    triangles += (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3;
  });
  const [north, east] = world.terrain.size.map((n) => n - 1);
  const seabedTriangles = north * east * 2 + 4 * (north + east);
  report.tiers[detail] = {structureTriangles: triangles, structureDrawCalls: calls,
    seabedTriangles, totalSiteTriangles: triangles + seabedTriangles};
  if (triangles + seabedTriangles > 200000) throw Error('Triangle budget exceeded');
  set.dispose();
}
// Conservative reserve: nine cable materials, four seabed maps, five shared structure maps.
// Includes unused maps and the untextured sign; map and bump share one texture.
report.textureMiBWithMips = (9 + 4 + 5) * 256 * 256 * 4 * 4 / 3 / 1024 ** 2;
for (const name of ['route.glb', 'weathering.webp', 'mission.json']) {
  report.files[name] = statSync(new URL(`../viewer/models/cable_route/${name}`, import.meta.url)).size;
}
const glb = readFileSync(new URL('../viewer/models/cable_route/route.glb', import.meta.url));
const doc = JSON.parse(glb.subarray(20, 20 + glb.readUInt32LE(12)).toString());
report.glbRequiredExtensions = doc.extensionsRequired;
report.glbTriangles = doc.meshes.reduce((n, mesh) => n + mesh.primitives.reduce(
  (n, primitive) => n + doc.accessors[primitive.indices].count / 3, 0), 0);
writeFileSync(new URL('../../docs/design/scenes/cable_route/asset-report.json', import.meta.url),
  JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
