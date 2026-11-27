// The final watch must arbitrate actual break telemetry before a simultaneous release or timeout.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {beatDecision} from '../viewer/story/beat_director.js';

const path = new URL('../campaign/wind_return.json', import.meta.url);
const {beats} = JSON.parse(readFileSync(path));
const reverse = beats.find(beat => beat.id === 'reverse');

test('a held hook waits, returning with an intact line clears, staying put times out', () => {
  const held = {tether: {snags: [{held: true}], broken: false}};
  assert.equal(beatDecision(reverse, 10, held), null);
  assert.equal(beatDecision(reverse, 100, held), 'abort');
  assert.equal(beatDecision(reverse, 100, {tether: {snags: [], broken: false}}), 'clear');
});

test('parted line takes priority, even if the hook disappears at the deadline', () => {
  assert.equal(beatDecision(reverse, 100, {tether: {snags: [], broken: true}}), 'parted');
});
