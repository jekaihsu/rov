// Training launch gate (Steam vs internal) and fidelity restore after a dive.
import assert from 'node:assert/strict';
import test from 'node:test';
import {createFidelity, STORAGE_KEY} from '../viewer/fidelity.js';
import {trainingLaunchParams} from '../viewer/training/session.js';
import {
  applyTrainingFidelityDefault,
  installTrainingFidelityGuard,
  restoreFidelitySnapshot,
} from '../viewer/training/fidelity_guard.js';

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    data,
  };
}

test('Steam edition ignores ?training=1 and course deep links', () => {
  const steam = {rovDesktop: {edition: 'steam'}};
  assert.deepEqual(
    trainingLaunchParams({search: '?training=1&trainingLesson=course_b01'}, steam),
    {enabled: false, lessonId: ''},
  );
  assert.deepEqual(
    trainingLaunchParams({search: '?mission=campaign&chapter=course_b01'}, steam),
    {enabled: false, lessonId: ''},
  );
});

test('internal edition enables training from query params', () => {
  const internal = {rovDesktop: {edition: 'training'}};
  assert.deepEqual(
    trainingLaunchParams({search: '?training=1&trainingLesson=course_b01'}, internal),
    {enabled: true, lessonId: 'course_b01'},
  );
  assert.deepEqual(
    trainingLaunchParams({search: '?mission=campaign&chapter=course_a01'}, {}),
    {enabled: true, lessonId: 'course_a01'},
  );
});

test('training fidelity override restores the trainee custom settings', () => {
  const storage = memoryStorage();
  const fidelity = createFidelity({storage, edition: 'training'});
  fidelity.setPreset('assisted');
  fidelity.set('videoDelayMs', 80);
  fidelity.set('hudDensity', 2);
  const before = fidelity.snapshot();
  assert.equal(before.preset, 'custom');
  assert.equal(fidelity.get('assistLevel'), 2);
  assert.equal(fidelity.get('hudDensity'), 2);

  const prior = applyTrainingFidelityDefault(fidelity);
  assert.equal(fidelity.preset, 'real');
  assert.equal(fidelity.get('assistLevel'), 0);
  assert.equal(fidelity.get('videoDelayMs'), 150);
  assert.equal(fidelity.get('hudDensity'), 2, 'preference items stay during the dive');

  restoreFidelitySnapshot(fidelity, prior);
  assert.equal(fidelity.preset, before.preset);
  assert.equal(fidelity.get('assistLevel'), 2);
  assert.equal(fidelity.get('videoDelayMs'), 80);
  assert.equal(fidelity.get('hudDensity'), 2);
  assert.deepEqual(JSON.parse(storage.data.get(STORAGE_KEY)).overrides.videoDelayMs, 80);
});

test('fidelity guard dispose restores prior without recording a leave', () => {
  const fidelity = createFidelity({edition: 'training'});
  fidelity.setPreset('assisted');
  fidelity.set('gimbal', true);
  const metricsRef = {current: {fidelityLeftReal: false, assistedUsed: false, fidelityPreset: 'real'}};
  const banners = [];
  globalThis.confirm = () => false;
  const guard = installTrainingFidelityGuard({
    fidelity,
    metricsRef,
    onBanner(text, left) {
      banners.push({text, left});
    },
  });
  assert.equal(fidelity.preset, 'real');
  assert.equal(fidelity.get('gimbal'), false);
  guard.dispose();
  assert.equal(fidelity.preset, 'assisted');
  assert.equal(fidelity.get('gimbal'), true);
  assert.equal(metricsRef.current.fidelityLeftReal, false);
  delete globalThis.confirm;
});
