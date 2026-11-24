// Node tests for Chapter 2 beat directors (viewer/story/chapter2_model.js).
import {describe, it} from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const modelUrl = pathToFileURL(path.join(root, 'viewer/story/chapter2_model.js')).href;
const {createChapter2Director, CHAPTER2_CONTRACTS, TIMING} = await import(modelUrl);

function advanceTo(director, target, telemetry = {}) {
  let now = 0;
  let view = director.step(now, telemetry);
  for (let i = 0; i < 40 && view.beat !== target; i += 1) {
    now += 0.5;
    view = director.step(now, telemetry);
  }
  assert.equal(view.beat, target);
  return {view, now};
}

describe('chapter2_model', () => {
  it('lists the three aquaculture contracts', () => {
    assert.deepEqual([...CHAPTER2_CONTRACTS], [
      'c2_net_inspection',
      'c2_mort_recovery',
      'c2_escape_event',
    ]);
  });

  it('C2-1 opens through establish then reacts to billow', () => {
    const d = createChapter2Director('c2_net_inspection');
    const {now} = advanceTo(d, 'search');
    const view = d.step(now + 1, {billow: true, input: 0.2});
    assert.equal(view.beat, 'billow');
    assert.equal(view.outcome.billow, true);
    assert.ok(view.said.some((line) => line.id === 'c21Billow'));
  });

  it('C2-1 idle nudge and timeout advance the story', () => {
    const d = createChapter2Director('c2_net_inspection');
    const {now} = advanceTo(d, 'search');
    let view = d.step(now + TIMING.idleNudge + 1, {input: 0});
    assert.ok(view.said.some((line) => line.id === 'c21Idle'));
    view = d.step(now + TIMING.playerLimit + 1, {input: 0});
    assert.equal(view.beat, 'wrap');
  });

  it('C2-2 enters silt when visibility collapses', () => {
    const d = createChapter2Director('c2_mort_recovery');
    const {now} = advanceTo(d, 'approach');
    const view = d.step(now + 1, {visibility: 1.2, silted: true, input: 0.3});
    assert.equal(view.beat, 'silt');
    assert.equal(view.outcome.silt, true);
  });

  it('C2-3 found → watch → relief with time pressure', () => {
    const d = createChapter2Director('c2_escape_event');
    const {now} = advanceTo(d, 'search');
    let view = d.step(now + 1, {nearHole: true, input: 0.4});
    assert.equal(view.beat, 'found');
    view = d.step(now + 2, {reports: 1, input: 0.2});
    assert.equal(view.beat, 'watch');
    view = d.step(now + 30, {complete: true});
    assert.equal(view.beat, 'relief');
  });
});
