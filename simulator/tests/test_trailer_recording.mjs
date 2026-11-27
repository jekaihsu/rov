// Node tests for trailer recording: setCam only when the path mode changes.
import test from 'node:test';
import assert from 'node:assert/strict';
import {installTrailerRecording} from '../viewer/trailer/recording.js';

function fakeParams(value = '1') {
  return new URLSearchParams(`trailer=${value}`);
}

function install(setCam) {
  const camera = {
    position: {set() {}},
    lookAt() {},
    fov: 55,
    updateProjectionMatrix() {},
  };
  const rovG = {
    position: {x: 0, y: 0, z: 0},
    quaternion: {x: 0, y: 0, z: 0, w: 1},
  };
  const doc = {
    body: {classList: {add() {}, remove() {}, toggle() {}}, dataset: {}},
    getElementById() { return null; },
  };
  return installTrailerRecording({
    params: fakeParams('1'),
    camera,
    rovG,
    setCam,
    getFidelity: () => ({set() {}}),
    document: doc,
  });
}

test('onboard setPath calls setCam once; later frames do not', () => {
  const calls = [];
  const trailer = install((mode) => calls.push(mode));
  trailer.setPath({mode: 'onboard'});
  assert.deepEqual(calls, ['onboard']);
  trailer.frame(1 / 60);
  trailer.frame(1 / 60);
  trailer.frame(1 / 60);
  assert.deepEqual(calls, ['onboard']);
});

test('follow path switches to chase once then leaves the rig alone', () => {
  const calls = [];
  const trailer = install((mode) => calls.push(mode));
  trailer.setPath({
    mode: 'follow',
    keyframes: [{t: 0, offset: [0, 1.2, -3.5]}],
  });
  assert.deepEqual(calls, []);
  trailer.frame(1 / 60);
  trailer.frame(1 / 60);
  trailer.frame(1 / 60);
  assert.deepEqual(calls, ['chase']);
});
