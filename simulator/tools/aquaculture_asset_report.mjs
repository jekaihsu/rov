// Offline reproducible geometry budget; includes every drawn pen fish and the four morts.
import {register} from 'node:module';
import {execFileSync} from 'node:child_process';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const {buildStructures} = await import('../viewer/structures.js');
const {fishGeometry} = await import('../viewer/fish_life.js');
const {salmonGeometry} = await import('../viewer/pen_life.js');
const {FISH_LOD, PEN_CROWD} = await import('../viewer/fish_schools.js');
const obstacles = JSON.parse(execFileSync('python', ['-c',
  'import json; from qysim.aquaculture import layout; print(json.dumps([o.as_dict() for o in layout()[0]]))'],
{cwd: new URL('..', import.meta.url), encoding: 'utf8'}));
const triangles = (geometry) => geometry.index.count / 3;
const result = {species: 'salmon', tiers: {}, files: {}};
for (const detail of ['low', 'medium', 'high']) {
  const perFish = {full: triangles(fishGeometry('salmon', detail)), distance: triangles(fishGeometry('salmon', 'low')),
    card: triangles(fishGeometry('salmon', 'silhouette'))};
  const lod = FISH_LOD[detail];
  const drawn = Math.ceil(48 * PEN_CROWD[detail]) * 8;
  const full = Math.min(lod.full, drawn);
  const distance = Math.min(lod.distance, drawn - full);
  const morts = 4 * triangles(salmonGeometry());
  const fishTriangles = full * perFish.full + distance * perFish.distance + (drawn - full - distance) * perFish.card +
    morts;
  const perSchool = drawn / 8;
  const set = buildStructures({obstacles, seabed_depth: 25}, {detail});
  let structureTriangles = 0;
  let calls = 0;
  set.group.traverse((mesh) => {
    if (!mesh.isMesh) return;
    calls++;
    structureTriangles += (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3;
  });
  result.tiers[detail] = {structureTriangles, fishTriangles, fishDrawn: perSchool * 8,
    totalTriangles: structureTriangles + fishTriangles, structureDrawCalls: calls,
    fishDrawCalls: 8 * (detail === 'low' ? 2 : 3) + 4};
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
