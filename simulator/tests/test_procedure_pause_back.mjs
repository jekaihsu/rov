// Esc during the deck checklist must open the pause menu, not be swallowed by intro-skip.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const VIEWER = new URL('../viewer/', import.meta.url);

test('intro skip only consumes Esc while the skip prompt is visible', async () => {
  const source = await readFile(new URL('play/intro_skip.js', VIEWER), 'utf8');
  assert.match(source, /introSkippable\(\)/);
  assert.match(source, /onMenuBack/);
  // The capture listener must not fire solely because the intro is held on deck.
  assert.doesNotMatch(
    source,
    /keydown[\s\S]*if \(event\.code !== KEY \|\| !active\(\)\) return/,
  );
});

test('procedure exposes a navigable check for the pause back hook', async () => {
  const source = await readFile(new URL('procedure/index.js', VIEWER), 'utf8');
  assert.match(source, /function navigable\(/);
  assert.match(source, /canNavigate:\s*navigable/);
});
