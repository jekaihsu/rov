// Quality mode scales authored LOD distances. auto / high / ultra stay put.
import assert from 'node:assert/strict';
import test from 'node:test';
import { lodDistanceScale, scaledLodDistance } from '../viewer/model_lod.js';

test('performance and medium pull LOD distances in', () => {
  assert.equal(lodDistanceScale('auto'), 1);
  assert.equal(lodDistanceScale('high'), 1);
  assert.equal(lodDistanceScale('ultra'), 1);
  assert.ok(lodDistanceScale('medium') < 1);
  assert.ok(lodDistanceScale('performance') < lodDistanceScale('medium'));
  assert.ok(scaledLodDistance(40, 'performance') < 40);
  assert.equal(scaledLodDistance(40, 'high'), 40);
});
