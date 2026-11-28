// Story gates, cinematic handover and persistent versus session-local discoveries.
import assert from 'node:assert/strict';
import test from 'node:test';
import {diveLog, divePhase} from '../viewer/free_dive_model.js';
import {unlockedDiveSites} from '../viewer/menu/catalogue.js';

test('the Bihai exception opens after prologue, without opening later chapters', () => {
  const scenes = ['pool', 'harbor', 'reef', 'korean_castle'].map(key => ({key}));
  const chapters = [
    {id: 'prologue', scenario: 'pool'},
    {id: 'harbor', scenario: 'harbor', requires: 'prologue'},
    {id: 'reef', scenario: 'reef', requires: 'harbor'},
  ];
  assert.deepEqual(unlockedDiveSites(scenes, chapters, []), [scenes[0]]);
  assert.deepEqual(unlockedDiveSites(scenes, chapters, ['prologue']), [scenes[0], scenes[1], scenes[3]]);
});

test('the camera releases after four seconds and radio waits a minute', () => {
  assert.equal(divePhase(3999).opening, true);
  assert.deepEqual(divePhase(4000), {opening: false, progress: 1, radioDue: false});
  assert.equal(divePhase(60000).radioDue, true);
});

test('repeated sightings and old photos are excluded from the departure log', () => {
  const log = diveLog('free_dive_wreck');
  log.restore([{metadata: {scene: 'free_dive_wreck'}, observation: {category: 'chain'}}]);
  for (const subject of ['bow', 'chain', 'bow']) log.record(subject);
  assert.deepEqual([...log.fresh], ['bow']);
});
