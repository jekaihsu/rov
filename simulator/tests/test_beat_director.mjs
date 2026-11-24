// Step the cold-open timing cuts and the pool watch with synthetic telemetry.
import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {beatDecision, conditionMatches, idleReminder} from '../viewer/story/beat_director.js';

const {beats} = JSON.parse(await readFile(new URL('../campaign/prologue.json', import.meta.url)));

test('campaign condition paths support arrays and missing readings', () => {
  const condition = {path: 'pos.2', op: 'gt', value: 4};
  assert.equal(conditionMatches(condition, {pos: [0, 0, 5]}), true);
  assert.equal(conditionMatches(condition, {}), false);
});

test('every idle route reaches the final card within fifteen minutes', () => {
  let id = beats[0].id;
  let elapsed = 0;
  while (id !== 'done') {
    const beat = beats.find(item => item.id === id);
    assert.equal(beatDecision(beat, beat.limit - 0.1, {}), null);
    elapsed += beat.limit;
    assert.ok(elapsed < 900);
    id = beatDecision(beat, beat.limit, {});
  }
});

test('depth loss decides the hold instruction, including right at the deadline', () => {
  const coast = beats.find(item => item.id === 'coast');
  assert.equal(beatDecision(coast, 6, {drift: 0}), null);
  assert.equal(beatDecision(coast, coast.limit, {drift: .21}), 'hold');
  assert.equal(beatDecision(coast, coast.limit, {drift: .02}), 'trim');
});

test('idle radio waits for the deadline and speaks once per beat', () => {
  assert.equal(idleReminder('again', 18, 17, false), null);
  assert.equal(idleReminder('again', 18, 18, false), 'again');
  assert.equal(idleReminder('again', 18, 40, true), null);
});
