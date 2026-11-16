// Offline reproducible geometry budget; includes all 384 high-tier instanced fish.
import {register} from 'node:module';
import {execFileSync} from 'node:child_process';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const {buildStructures} = await import('../viewer/structures.js');
const {fishGeometry} = await import('../viewer/fish_life.js');
const {salmonGeometry} = await import('../viewer/pen_life.js');
const obstacles = JSON.parse(execFileSync('python', ['-c',
  'import json; from qysim.aquaculture import layout; print(json.dumps([o.as_dict() for o in layout()[0]]))'],
{cwd: new URL('..', import.meta.url), encoding: 'utf8'}));
const result = {tiers: {}, files: {}};
for (const detail of ['low', 'medium', 'high']) {
  // Pen fish are the swimming salmon of fish_life.js: a dense band per school (fish_schools.js), the full body for
  // at most 24 near fish per school and the low body for the rest. Worst case: every near slot in use. Plus the
  // four morts (pen_life.js salmonGeometry).
  const body = fishGeometry('salmon', detail).index.count / 3;
  const farBody = fishGeometry('salmon', 'low').index.count / 3;
  const perSchool = Math.ceil(48 * {low: 0.25, medium: 2, high: 2.5}[detail]);
  const near = detail === 'low' ? perSchool * 8 : Math.min(24, perSchool) * 8;
  const fishTriangles = near * body + (perSchool * 8 - near) * farBody + 4 * salmonGeometry().index.count / 3;
  const set = buildStructures({obstacles, seabed_depth: 25}, {detail});
  let triangles = 0;
  let calls = 0;
  set.group.traverse((mesh) => {
    if (!mesh.isMesh) return;
    calls++;
    triangles += (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3;
  });
  result.tiers[detail] = {structureTriangles: triangles, fishTriangles, fishDrawn: perSchool * 8,
    totalTriangles: triangles + fishTriangles, structureDrawCalls: calls, fishDrawCalls: detail === 'low' ? 12 : 20};
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
