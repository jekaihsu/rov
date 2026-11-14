// Pure audio mappings must remain safe for repeated snapshots and replay resets.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {motorParameters, depthCutoff, detectEvents} from '../viewer/audio/mapping.js';
test('motor output has bounded gain, increasing pitch and reverse timbre', () => {
  assert.equal(motorParameters(0).gain, 0);
  assert.ok(motorParameters(1).frequency > motorParameters(0.25).frequency);
  assert.deepEqual(motorParameters(2), motorParameters(1));
  assert.equal(motorParameters(-1).frequency, motorParameters(1).frequency);
  assert.notEqual(motorParameters(-1).type, motorParameters(1).type);
});
test('depth darkens ambience with finite bounded cutoff', () => {
  assert.equal(depthCutoff(-5), depthCutoff(0));
  assert.ok(depthCutoff(30) < depthCutoff(5));
  assert.ok(depthCutoff(1000) >= 250);
});
test('edges fire once and initial or rewound snapshots stay silent', () => {
  const a = {t: 1, locked: true, photos: 0, tether: {}, events: []};
  const b = {...a, t: 2, locked: false, photos: 1, tether: {warn: true},
    events: [{t: 2, severity: 'hard', obstacle: 'wall'}]};
  assert.deepEqual(detectEvents(null, b), []);
  assert.deepEqual(detectEvents(a, b), ['locked', 'photos', 'warn', 'hard']);
  assert.deepEqual(detectEvents(b, structuredClone(b)), []);
  assert.deepEqual(detectEvents(b, a), []);
});
test('warning, completion and control edges preserve severity without repeated beeps', () => {
  const a = {t: 3, battery: 21, score: {}, rc: {right_switch: 0}, tether: {}};
  const b = {...a, t: 4, battery: 20, score: {finished: true}, rc: {right_switch: 2},
    keep_depth: true, tether: {broken: true}};
  assert.deepEqual(detectEvents(a, b), ['keep_depth', 'light', 'broken', 'complete', 'warn']);
  assert.deepEqual(detectEvents(b, {...b, t: 5}), []);
});
