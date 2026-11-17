// Cold open cutscene look (story/cold_open_presentation.js): a scoped override that never touches the fidelity
// store, and is gone the moment the player takes control.
import test from 'node:test';
import assert from 'node:assert/strict';

import { createFidelity, STORAGE_KEY } from '../viewer/fidelity.js';
import { BEAUTIFY_ID, beautifyEnabled } from '../viewer/fx/beautify.js';
import { TIMING, createColdOpenDirector } from '../viewer/story/cold_open_model.js';
import {
  CINEMATIC_LOOK_ID, cinematicLookActive, createCinematicLook, isScriptedBeat,
} from '../viewer/story/cold_open_presentation.js';

function recordingStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  const writes = [];
  return {
    writes,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem(key, value) {
      writes.push(key);
      data.set(key, String(value));
    },
    removeItem: (key) => data.delete(key),
  };
}

test('the override is the beautify item and only that', () => {
  assert.equal(CINEMATIC_LOOK_ID, BEAUTIFY_ID);
});

test('scripted beats are the ones before the player takes over', () => {
  const director = createColdOpenDirector({anode: [-6.93, -6.93], start: [-12, -9]});
  const scripted = new Map();
  for (let t = 0; t <= 16; t += 0.1) {
    const view = director.step(Math.round(t * 10) / 10, {photos: 0, snagged: false, tension: 1, pos: [-12, -9, 12]});
    scripted.set(view.beat, isScriptedBeat(view));
  }
  assert.deepEqual(Object.fromEntries(scripted), {black: true, establish: true, handover: false, approach: false});
  assert.ok(TIMING.black + TIMING.establish < 16);
  assert.equal(isScriptedBeat(director.skip(17)), false, 'the closing card after a skip is not a scripted flight');
  assert.equal(isScriptedBeat(null), false);
});

test('fidelity state after the handover equals the state before the cold open', () => {
  for (const stored of [{}, {[STORAGE_KEY]: JSON.stringify({version: 1, base: 'real', overrides: {}})},
    {[STORAGE_KEY]: JSON.stringify({version: 1, base: 'assisted', overrides: {[BEAUTIFY_ID]: false}})}]) {
    const storage = recordingStorage(stored);
    const fidelity = createFidelity({storage});
    const seen = [];
    fidelity.subscribe(function changed(snapshot, ids) {
      seen.push(ids);
    });
    const before = JSON.stringify(fidelity.snapshot());
    const raw = storage.getItem(STORAGE_KEY);
    const look = createCinematicLook();
    assert.equal(cinematicLookActive(), false);
    look.set(true);
    look.set(true);
    assert.equal(cinematicLookActive(), true);
    assert.equal(JSON.stringify(fidelity.snapshot()), before, 'the store does not move during the cutscene');
    look.set(false);
    assert.equal(cinematicLookActive(), false);
    look.release();
    assert.equal(cinematicLookActive(), false, 'releasing twice is harmless');
    assert.equal(JSON.stringify(fidelity.snapshot()), before);
    assert.equal(storage.getItem(STORAGE_KEY), raw);
    assert.deepEqual(storage.writes, [], 'nothing is written to storage');
    assert.deepEqual(seen, [], 'no subscriber hears of a change');
    fidelity.dispose();
  }
});

test('two holders: the look stays until the last one lets go', () => {
  const first = createCinematicLook();
  const second = createCinematicLook();
  first.set(true);
  second.set(true);
  first.release();
  assert.equal(cinematicLookActive(), true);
  assert.ok(second.active && !first.active);
  second.release();
  assert.equal(cinematicLookActive(), false);
});

test('the picture reads the override, the settings do not', () => {
  const before = beautifyEnabled();
  const look = createCinematicLook();
  look.set(true);
  assert.equal(beautifyEnabled(), true);
  look.release();
  assert.equal(beautifyEnabled(), before);
});
