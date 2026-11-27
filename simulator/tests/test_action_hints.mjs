// Unlock / action captions must follow the player's bindings and the pad family in use.
import test from 'node:test';
import assert from 'node:assert/strict';
import { BINDINGS, keyboardRows } from '../viewer/input/bindings.js';
import { actionControlLabels, formatActionHint } from '../viewer/input/hints.js';

test('lock hint uses the bound key and Xbox Y by default on keyboard', () => {
  const parts = actionControlLabels('lock', { family: 'keyboard', rows: BINDINGS });
  assert.equal(parts.key, 'Space');
  assert.equal(parts.pad, 'Y');
});

test('game keyboard layout remaps the lock key to T', () => {
  const rows = keyboardRows('game');
  const parts = actionControlLabels('lock', { family: 'keyboard', rows });
  assert.equal(parts.key, 'T');
  assert.equal(parts.pad, 'Y');
});

test('PlayStation family shows △ for the lock face button', () => {
  const parts = actionControlLabels('lock', { family: 'playstation', rows: BINDINGS });
  assert.equal(parts.pad, '△');
  const text = formatActionHint('按 {key} / 手把 {pad} 解鎖', parts);
  assert.equal(text, '按 Space / 手把 △ 解鎖');
});

test('Switch family uses the face letter at the same index', () => {
  const parts = actionControlLabels('lock', { family: 'switch', rows: BINDINGS });
  assert.equal(parts.pad, 'X');
});
