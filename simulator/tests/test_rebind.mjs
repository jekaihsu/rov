// Saved input changes must respect context ownership and survive upgrades from the flight-only editor.
import assert from 'node:assert/strict';
import test from 'node:test';
import { editablePadBindings, keyCollisions, findCollisions } from '../viewer/input/bindings.js';

test('v2 preserves custom flight inputs and initializes menu navigation from the table', () => {
  const converted = editablePadBindings({photo: 'b18', accept: 'b99'}, 2);
  assert.equal(converted.photo, 'b18');
  assert.equal(converted.accept, 'b0');
  converted.accept = 'b19';
  converted.back = '';
  assert.deepEqual(editablePadBindings(converted, 3), converted);
});

test('dialogue and menu edits detect same-context conflicts', () => {
  assert.ok(keyCollisions('console', {dialogueSkip: ['Enter']}).length);
  assert.equal(keyCollisions('console', {dialogueSkip: ['KeyP']}).length, 0);
  const pad = editablePadBindings();
  assert.ok(findCollisions(undefined, {...pad, back: pad.accept}).some(row => row.context === 'menu'));
});

import { shapeStick } from '../viewer/input/actions.js';
import { createFidelity } from '../viewer/fidelity.js';
import '../viewer/prefs/accessibility.js';

test('stick preferences preserve the preset and shape only the selected physical pair', () => {
  const fidelity = createFidelity();
  fidelity.set('leftDeadzone', 0.4);
  fidelity.set('rightResponse', 1);
  fidelity.set('rightInvert', true);
  assert.equal(fidelity.preset, 'real');
  const left = shapeStick(0.1, 0.1, {inner: fidelity.get('leftDeadzone')});
  assert.deepEqual(left, [0, 0]);
  const right = shapeStick(0, 0.5, {inner: 0, outer: 0, expo: fidelity.get('rightResponse'), invert: true});
  assert.deepEqual(right, [0, -0.125]);
  fidelity.dispose();
});

test('a single button assigned to settings yields to dialogue and menu ownership', async () => {
  const {createResolver} = await import('../viewer/input/bindings.js');
  const sources = {...editablePadBindings(), settings: 'b0', photo: ''};
  const frame = {buttons: [1], axes: []};
  for (const context of ['dialogue', 'menu']) {
    const actions = createResolver().resolve(sources, frame, new Set(['flight', context]), 0);
    assert.equal(actions.settings, 0);
  }
  assert.equal(createResolver().resolve(sources, frame, new Set(['flight']), 0).settings, 1);
});
