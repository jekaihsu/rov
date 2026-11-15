// Reproducible prototype geometry budget, split at waterline; excludes shared vehicle and renderer targets.
import {register} from 'node:module';
import {execFileSync} from 'node:child_process';
import {writeFileSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const {buildStructures} = await import('../viewer/structures.js');
const obstacles = JSON.parse(execFileSync('python', ['-c',
  'import json; from qysim.reservoir import layout; print(json.dumps([o.as_dict() for o in layout()]))'],
{cwd: new URL('..', import.meta.url), encoding: 'utf8'}));
const report = {status: 'collision blockout; photo-matched art pending', tiers: {}};
for (const detail of ['low', 'medium', 'high']) {
  const set = buildStructures({obstacles, seabed_depth: 24}, {detail});
  let above = 0;
  let below = 0;
  let calls = 0;
  set.group.traverse(mesh => {
    if (!mesh.isMesh) return;
    calls++;
    const geometry = mesh.geometry;
    const pos = geometry.attributes.position;
    const index = geometry.index;
    for (let i = 0; i < (index?.count ?? pos.count); i += 3) {
      const heights = [0, 1, 2].map(k => pos.getY(index ? index.getX(i+k) : i+k));
      if (Math.max(...heights) >= 0) above++;
      if (Math.min(...heights) <= 0) below++;
    }
  });
  report.tiers[detail] = {aboveWaterTriangles: above, underwaterTriangles: below, drawCalls: calls};
  if (above > 200000 || below > 150000) throw new Error('Budget exceeded');
  set.dispose();
}
report.sceneTextureMiB = 0;
report.sharedSeabedTextureMiB = 4*256*256*4*4/3/1024**2;
writeFileSync(new URL('../../docs/design/scenes/reservoir/asset-report.json', import.meta.url),
  JSON.stringify(report, null, 2)+'\n');
console.log(JSON.stringify(report));
