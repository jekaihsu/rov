// Camera action ownership and the distinction between real and assisted rendering.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
const encode = source => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const actions = await readFile(new URL('../viewer/input/actions.js', import.meta.url), 'utf8');
const features = await readFile(new URL('../viewer/input/feature_actions.js', import.meta.url), 'utf8');
const featureSource = features.replace("'./actions.js'", JSON.stringify(encode(actions)));
const {createFeatureActions} = await import(encode(featureSource));
const stateSource = await readFile(new URL('../viewer/state_buffer.js', import.meta.url), 'utf8');
const {createRenderState} = await import(encode(stateSource));

test('registered camera key preserves profile G and ignores held repeats', () => {
  const registry = createFeatureActions((name, fallback) => fallback);
  let calls = 0;
  registry.register({gimbal: {keys: ['KeyB'], run() { calls++; }}});
  assert.equal(registry.key({code: 'KeyG'}), false);
  assert.equal(registry.key({code: 'KeyB'}), true);
  registry.key({code: 'KeyB', repeat: true});
  assert.equal(calls, 1);
});
test('orbit action consumes only its pad channels while active', () => {
  const registry = createFeatureActions((name, fallback) => fallback);
  let enabled = true;
  let motion = 0;
  registry.register({orbit: {binding: 'a2', continuous: true, consume: ['right_lr'],
    enabled: () => enabled, run(value, dt) { motion += value * dt; }}});
  const snapshot = {axes: [0, 0, .5, 0], buttons: []};
  assert.deepEqual([...registry.sample(snapshot, .1)], ['right_lr']);
  assert.equal(motion, .05);
  enabled = false;
  assert.deepEqual([...registry.sample(snapshot, .1)], []);
  assert.equal(motion, .05);
});
test('default real view shares a provisional 150 ms timeline; assisted view is opt in', () => {
  function sample(params) {
    const rovG = {position: {}, quaternion: {}};
    const rig = createRenderState({params, rovG, P(p, out) { out.value = p[0]; }, Q() {},
      fleet: {ingest() {}}, updateTether() {}});
    for (let i=0;i<=6;i++) {
      const t = i * .05;
      rig.ingest({t, pos: [t, 0, 0], vel: [1, 0, 0], q: [1, 0, 0, 0]}, false, 10 + t);
    }
    rig.update(null, false, 10.3);
    return rovG.position.value;
  }
  assert.ok(Math.abs(sample(new URLSearchParams()) - .15) < 1e-9);
  assert.ok(Math.abs(sample(new URLSearchParams('presentation=assisted')) - .325) < 1e-9);
});
