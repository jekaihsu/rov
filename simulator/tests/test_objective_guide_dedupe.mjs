// First-dive checklist must appear once: onboarding owns it; the objective card no longer mirrors it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('objective card no longer renders a first-dive guide checklist', async () => {
  const source = await readFile(new URL('../viewer/play/objective_card.js', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /objective-guide|guideSteps|GUIDE_DIVES/);
  assert.match(source, /onboarding\.js/);
});
