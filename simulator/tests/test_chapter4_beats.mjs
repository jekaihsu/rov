// A silent watch must reach handover, and valid shutter observations may advance a watch early.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {beatDecision} from '../viewer/story/beat_director.js';

for (const chapter of ['c4_sheets', 'c4_frame']) {
  const script = JSON.parse(await readFile(new URL(`../campaign/${chapter}.json`, import.meta.url)));
  test(chapter + ' has a bounded route to handover with no evidence', () => {
    let id = script.beats[0].id;
    const seen = new Set();
    while (id !== 'done') {
      assert.ok(!seen.has(id));
      seen.add(id);
      const beat = script.beats.find(item => item.id === id);
      assert.equal(beatDecision(beat, 0, {}), null);
      id = beatDecision(beat, beat.limit, {});
    }
    assert.equal(seen.size, script.beats.length);
    assert.ok(seen.has('receipt'));
  });
  test(chapter + ' advances the photograph beat only on its specified subject', () => {
    const beat = script.beats.find(item => item.hint === 'photo');
    const subject = beat.condition.path.split('.')[1];
    const surveyPhotos = {other: {t: 1}};
    assert.equal(beatDecision(beat, 1, {surveyPhotos}), null);
    surveyPhotos[subject] = {t: 2};
    assert.equal(beatDecision(beat, 2, {surveyPhotos}), beat.next);
  });
}
