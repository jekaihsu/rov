// Menu actions must consume flight commands only for the currently selected device and active binding.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createFeatureActions} from '../viewer/input/feature_actions.js';

test('pause respects the normalized selected snapshot and the configured button', function selectedBinding() {
  const bindings = {pause: 'b5'};
  const features = createFeatureActions((name, fallback) => bindings[name] ?? fallback);
  let runs = 0;
  let observed;
  features.register({pause: {
    binding: 'b9',
    consume: ['light', 'left_ud'],
    enabled(snapshot, value) {
      observed = snapshot;
      return value > 0.5;
    },
    run() { runs += 1; },
  }});
  const selected = {axes: [0, 0, 0, 0], buttons: Array(17).fill(0)};
  selected.buttons[9] = 1;
  assert.equal(features.sample(selected, 0.033).size, 0);
  assert.equal(runs, 0);
  selected.buttons[5] = 1;
  assert.deepEqual([...features.sample(selected, 0.033)], ['light', 'left_ud']);
  assert.equal(observed, selected);
  assert.equal(runs, 1);
  features.sample(selected, 0.033);
  assert.equal(runs, 1);
  selected.buttons[5] = 0;
  assert.equal(features.sample(selected, 0.033).size, 0);
});

test('existing zero-argument action guards and blocked snapshots retain their behavior', function legacyGuard() {
  const features = createFeatureActions((name, fallback) => fallback);
  let runs = 0;
  features.register({legacy: {binding: 'b0', enabled: () => true, run() { runs += 1; }}});
  features.sample(null, 0);
  assert.equal(runs, 0);
  features.sample({axes: [], buttons: [1]}, 0.033);
  assert.equal(runs, 1);
});
