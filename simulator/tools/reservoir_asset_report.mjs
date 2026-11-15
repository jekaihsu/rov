// Reproducible runtime scene budgets including instance multiplicity and portable asset compression.
import {register} from 'node:module';
import {execFileSync} from 'node:child_process';
import {readFileSync, writeFileSync} from 'node:fs';
register('./three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const {buildStructures} = await import('../viewer/structures.js');
const {buildReservoirSurface} = await import('../viewer/reservoir.js');
const raw = execFileSync('python', ['-c', `
import sys,json
sys.path.insert(0,'simulator')
from qysim.reservoir import scenario
sc=scenario()
print(json.dumps(dict(scenario=sc.summary(),obstacles=[o.as_dict() for o in sc.obstacles])))
`], {encoding: 'utf8'});
const world = JSON.parse(raw);
const report = {seed: 71, textureRGBAWithMipsMiB: 5 * 256 * 256 * 4 * 4 / 3 / 1024 ** 2,
  textureScope: 'one reservoir texture + four shared seabed textures; excludes shared vehicle and render targets',
  tiers: {}, portable: {}};
for (const tier of ['low', 'medium', 'high']) {
  const set = buildStructures(world, {detail: tier});
  const horizon = new THREE.Group();
  buildReservoirSurface(horizon, tier);
  let structure = 0;
  let above = 0;
  let underwater = 0;
  let landscape = 0;
  set.group.traverse(o => {
    if (!o.isMesh) return;
    const count = (o.geometry.index?.count ?? o.geometry.attributes.position.count) / 3;
    o.geometry.computeBoundingBox();
    const bounds = o.geometry.boundingBox;
    structure += count;
    if (bounds.max.y >= 0) above += count;
    if (bounds.min.y <= 0) underwater += count;
  });
  horizon.traverse(o => {
    if (o.isMesh) landscape += (o.geometry.index?.count ?? o.geometry.attributes.position.count) / 3
      * (o.isInstancedMesh ? o.count : 1);
  });
  report.tiers[tier] = {structure, landscape, aboveConservative: above + landscape,
    underwaterConservative: underwater + landscape, underwaterStructures: underwater};
  if (above + landscape > 200000 || underwater + landscape > 150000) throw new Error(`budget exceeded: ${tier}`);
  set.dispose();
}
for (const tier of ['default', 'low']) {
  const bytes = readFileSync(`simulator/viewer/models/reservoir/${tier}.glb`);
  const json = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString());
  report.portable[tier] = {bytes: bytes.length, extensions: json.extensionsUsed};
  for (const name of ['EXT_meshopt_compression', 'EXT_texture_webp']) {
    if (!json.extensionsUsed.includes(name)) throw new Error(`missing ${name}`);
  }
}
if (report.textureRGBAWithMipsMiB > 48) throw new Error('texture budget');
writeFileSync('docs/design/scenes/reservoir/asset-report.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
