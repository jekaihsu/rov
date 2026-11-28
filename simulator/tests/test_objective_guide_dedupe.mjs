// First-dive checklist must appear once: onboarding owns it; the objective card never hosts it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { objectiveCardSections } from '../viewer/play/objective_card.js';

test('objective card sections never include a first-dive guide', () => {
  assert.deepEqual(objectiveCardSections({}), []);
  assert.deepEqual(objectiveCardSections({ hasBoard: true }), ['contracts']);
  assert.deepEqual(objectiveCardSections({ careerWork: true }), ['career']);
  assert.deepEqual(objectiveCardSections({ inChapter: true, hasBoard: true }), []);
  assert.deepEqual(objectiveCardSections({ careerWork: true, hasBoard: true }), ['career']);
  for (const sections of [
    objectiveCardSections({}),
    objectiveCardSections({ hasBoard: true }),
    objectiveCardSections({ careerWork: true }),
    objectiveCardSections({ inChapter: true }),
  ]) {
    assert.equal(sections.includes('guide'), false);
  }
});
