// Node tests for viewer/trailer/camera_path.js (Catmull-Rom + path modes).
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  catmullRom,
  evaluateCameraPath,
  interpolateScalar,
  interpolateVector,
  segmentIndex,
} from '../viewer/trailer/camera_path.js';

test('catmullRom midpoint of a straight line', () => {
  const mid = catmullRom([0], [1], [2], [3], 0.5);
  assert.ok(Math.abs(mid[0] - 1.5) < 1e-9);
});

test('catmullRom returns p1 at t=0 and p2 at t=1', () => {
  assert.deepEqual(catmullRom([0, 0], [1, 2], [3, 4], [5, 6], 0), [1, 2]);
  const end = catmullRom([0, 0], [1, 2], [3, 4], [5, 6], 1);
  assert.ok(Math.abs(end[0] - 3) < 1e-9);
  assert.ok(Math.abs(end[1] - 4) < 1e-9);
});

test('segmentIndex finds the enclosing span', () => {
  assert.equal(segmentIndex([0, 2, 5], 1), 0);
  assert.equal(segmentIndex([0, 2, 5], 4), 1);
  assert.equal(segmentIndex([0, 2, 5], 9), 1);
});

test('interpolateVector holds a single keyframe', () => {
  const frames = [{t: 0, position: [1, 2, 3]}];
  assert.deepEqual(interpolateVector(frames, 'position', 4), [1, 2, 3]);
});

test('interpolateVector returns null when the attribute is omitted', () => {
  const frames = [{t: 0, position: [1, 2, 3]}, {t: 1, position: [2, 2, 3]}];
  assert.equal(interpolateVector(frames, 'lookAt', 0.5), null);
  assert.equal(interpolateVector([{t: 0}], 'offset', 0), null);
});

test('interpolateScalar blends fov', () => {
  const frames = [{t: 0, fov: 40}, {t: 2, fov: 60}];
  assert.ok(Math.abs(interpolateScalar(frames, 'fov', 1, 50) - 50) < 1e-6);
});

test('evaluateCameraPath onboard', () => {
  const sample = evaluateCameraPath({mode: 'onboard'}, 0, {position: [0, 0, 0]});
  assert.equal(sample.mode, 'onboard');
  assert.equal(sample.position, null);
});

test('evaluateCameraPath fixed', () => {
  const path = {
    mode: 'fixed',
    keyframes: [
      {t: 0, position: [0, 1, 0], lookAt: [0, 0, 5], fov: 50},
      {t: 2, position: [4, 1, 0], lookAt: [0, 0, 5], fov: 50},
    ],
  };
  const sample = evaluateCameraPath(path, 1, {position: [0, 0, 0]});
  assert.ok(Math.abs(sample.position[0] - 2) < 1e-5);
});

test('evaluateCameraPath fixed without lookAt falls back to ROV', () => {
  const path = {mode: 'fixed', keyframes: [{t: 0, position: [1, 2, 3]}]};
  const sample = evaluateCameraPath(path, 0, {position: [9, 8, 7]});
  assert.deepEqual(sample.lookAt, [9, 8, 7]);
});

test('evaluateCameraPath follow without lookOffset uses the default', () => {
  const path = {mode: 'follow', keyframes: [{t: 0, offset: [0, 1, -2]}]};
  const sample = evaluateCameraPath(path, 0, {position: [0, 0, 0], heading: 0});
  assert.deepEqual(sample.lookAt, [0, 0.2, 1.5]);
});

test('evaluateCameraPath orbit', () => {
  const path = {
    mode: 'orbit',
    keyframes: [
      {t: 0, azimuth: 0, radius: 4, height: 1},
      {t: 1, azimuth: 0, radius: 6, height: 1},
    ],
  };
  const sample = evaluateCameraPath(path, 0.5, {position: [0, 0, 0]});
  assert.ok(Math.abs(sample.position[0] - 5) < 1e-5);
});
