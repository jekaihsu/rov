// Node tests for viewer/trailer/recording.js (URL flag + HUD part normalization).
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  normalizeTrailerHud,
  trailerParamEnabled,
  TRAILER_HUD_PARTS,
} from '../viewer/trailer/recording.js';

test('trailerParamEnabled requires an explicit on value', () => {
  assert.equal(trailerParamEnabled(new URLSearchParams('')), false);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer=0')), false);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer=false')), false);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer=off')), false);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer=1')), true);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer=true')), true);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer=on')), true);
  assert.equal(trailerParamEnabled(new URLSearchParams('trailer')), true);
});

test('normalizeTrailerHud maps presets and part lists', () => {
  assert.deepEqual(normalizeTrailerHud(false), []);
  assert.deepEqual(normalizeTrailerHud('off'), []);
  assert.deepEqual(normalizeTrailerHud('minimal'), ['depth', 'heading']);
  assert.deepEqual(normalizeTrailerHud(['heading', 'depth', 'depth']), ['heading', 'depth']);
  assert.deepEqual(normalizeTrailerHud({depth: true, map: false, heading: 1}), ['depth', 'heading']);
  const full = normalizeTrailerHud(true);
  assert.equal(full.length, TRAILER_HUD_PARTS.length);
  for (const part of TRAILER_HUD_PARTS) assert.ok(full.includes(part));
});
