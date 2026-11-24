// Esc during the deck checklist must open the pause menu, not be swallowed by intro-skip.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  backKeyCodes, introSkippable, keySkipsIntro, menuBackPulse,
} from '../viewer/play/intro_skip.js';
import { checklistNavigable } from '../viewer/procedure/navigable.js';

test('intro skippable only while the skip prompt is visible', () => {
  const previous = globalThis.document;
  globalThis.document = {
    getElementById(id) {
      if (id !== 'skipIntro') return null;
      return { hidden: true };
    },
  };
  assert.equal(introSkippable(), false);
  globalThis.document = {
    getElementById(id) {
      if (id !== 'skipIntro') return null;
      return { hidden: false };
    },
  };
  assert.equal(introSkippable(), true);
  globalThis.document = previous;
});

test('bound back keys skip the intro only when the prompt is visible', () => {
  const backKeys = backKeyCodes([{ action: 'back', keys: ['Escape', 'Backspace'] }]);
  assert.deepEqual(backKeys, ['Escape', 'Backspace']);
  assert.equal(keySkipsIntro('Escape', { skippable: true, backKeys }), true);
  assert.equal(keySkipsIntro('Escape', { skippable: false, backKeys }), false);
  assert.equal(keySkipsIntro('KeyQ', { skippable: true, backKeys }), false);
});

test('checklist navigable matches the pause-back enablement rule', () => {
  assert.equal(checklistNavigable({ hidden: false, phase: 'checks', focusableCount: 2 }), true);
  assert.equal(checklistNavigable({ hidden: true, phase: 'checks', focusableCount: 2 }), false);
  assert.equal(checklistNavigable({ hidden: false, phase: 'diving', focusableCount: 2 }), false);
  assert.equal(checklistNavigable({ hidden: false, phase: 'checks', focusableCount: 0 }), false);
  assert.equal(checklistNavigable({ hidden: false, phase: null, focusableCount: 2 }), false);
});

test('menu back opens on keyboard dispatch and on the pad press edge', () => {
  // Keyboard: features.run → hold(1, 0).
  assert.deepEqual(menuBackPulse(1, 0, false), { fire: true, down: false });
  assert.deepEqual(menuBackPulse(0, 0, false), { fire: false, down: false });
  // Pad continuous sample: fire once when value crosses 0.5, not every held frame.
  assert.deepEqual(menuBackPulse(1, 0.016, false), { fire: true, down: true });
  assert.deepEqual(menuBackPulse(1, 0.016, true), { fire: false, down: true });
  assert.deepEqual(menuBackPulse(0, 0.016, true), { fire: false, down: false });
  assert.deepEqual(menuBackPulse(1, 0.016, false), { fire: true, down: true });
});
