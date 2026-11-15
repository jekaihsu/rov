// Offline reproducible geometry budget; includes all 384 high-tier instanced fish.
import {register} from 'node:module';
import {execFileSync} from 'node:child_process';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const {buildStructures} = await import('../viewer/structures.js');
const {marineGeometry} = await import('../viewer/marine_registry.js');
const obstacles = JSON.parse(execFileSync('python', ['-c',
  'import json; from qysim.aquaculture import layout; print(json.dumps([o.as_dict() for o in layout()[0]]))'],
{cwd: new URL('..', import.meta.url), encoding: 'utf8'}));
const result = {tiers: {}, files: {}};
const fish = marineGeometry('fish');
const fishTriangles = (fish.index?.count ?? fish.attributes.position.count) / 3;
for (const detail of ['low', 'medium', 'high']) {
  const set = buildStructures({obstacles, seabed_depth: 25}, {detail});
  let triangles = 0;
  let calls = 0;
  set.group.traverse((mesh) => {
    if (!mesh.isMesh) return;
    calls++;
    triangles += (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3;
  });
  const count = {low: 96, medium: 232, high: 384}[detail];
  result.tiers[detail] = {structureTriangles: triangles, fishTriangles: (count + 4) * fishTriangles,
    totalTriangles: triangles + (count + 4) * fishTriangles, structureDrawCalls: calls, fishDrawCalls: 12};
  if (result.tiers[detail].totalTriangles > 200000) throw new Error('Triangle budget exceeded');
  set.dispose();
}
const glb = readFileSync(new URL('../viewer/models/aquaculture/pen.glb', import.meta.url));
const document = JSON.parse(glb.subarray(20, 20 + glb.readUInt32LE(12)).toString());
result.referenceGLBTriangles = document.meshes.reduce((total, mesh) => total + mesh.primitives.reduce(
  (count, primitive) => count + document.accessors[primitive.indices].count / 3, 0), 0);
result.referenceGLBRequiredExtensions = document.extensionsRequired;
result.netTextureRGBAWithMipsMiB = 256 * 256 * 4 * 4 / 3 / 1024 ** 2;
// seabed.js allocates four shared 256-square maps, even if a tier samples fewer.
result.siteTextureWithSharedSeabedMiB = result.netTextureRGBAWithMipsMiB * 5;
for (const name of ['pen.glb', 'net.webp', 'mission.json']) {
  result.files[name] = statSync(new URL(`../viewer/models/aquaculture/${name}`, import.meta.url)).size;
}
writeFileSync(new URL('../../docs/design/scenes/aquaculture/asset-report.json', import.meta.url),
  JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
