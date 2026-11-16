/** Both wrecks share authored LOD URL routing; unrelated assets must remain untouched. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
const source = (await readFile(new URL('../viewer/scene_models.js', import.meta.url), 'utf8'))
  .replace(/^import .*;$/gm, '');
const {modelUrl} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('both wrecks resolve all authored LOD tiers', () => {
  for (const name of ['korean_castle', 'wreck_chenjiao']) {
    const ob = {model: `models/${name}.glb`};
    assert.equal(modelUrl(ob, 'high'), ob.model);
    assert.equal(modelUrl(ob, 'medium'), `models/${name}_lod1.glb`);
    assert.equal(modelUrl(ob, 'low'), `models/${name}_lod2.glb`);
  }
  assert.equal(modelUrl({model: 'models/other.glb'}, 'low'), 'models/other.glb');
});
