// Versioned save store: empty, legacy, corrupt JSON, oversized and missing fields must not throw.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CORRUPT_SUFFIX,
  createRecordStore,
  memoryStorage,
} from '../viewer/saves/store.js';
import {
  achievementsStore,
  audioStore,
  campaignStore,
  coldOpenStore,
  displayStore,
  fidelityStore,
  inputStore,
  onboardingStore,
  resultsStore,
  allSaveEntries,
} from '../viewer/saves/registry.js';

test('inventory lists every save with a version', () => {
  const entries = allSaveEntries();
  assert.ok(entries.length >= 20);
  for (const entry of entries) {
    assert.equal(typeof entry.key, 'string');
    assert.ok(Number.isFinite(entry.version) && entry.version >= 1, entry.key);
    assert.ok(entry.onCorrupt, entry.key);
  }
});

test('empty storage yields defaults without a corrupt backup', () => {
  const storage = memoryStorage();
  const loaded = campaignStore.load(storage);
  assert.equal(loaded.reason, 'empty');
  assert.equal(loaded.recovered, false);
  assert.deepEqual(loaded.value.completed, []);
  assert.equal(loaded.value.version, 1);
  assert.equal(storage.getItem(campaignStore.key + CORRUPT_SUFFIX), null);
});

test('legacy records without version migrate and persist version 1', () => {
  const storage = memoryStorage({
    [campaignStore.key]: JSON.stringify({ completed: ['prologue'], rewards: [], results: [], checkpoint: null }),
  });
  const loaded = campaignStore.load(storage);
  assert.equal(loaded.reason, 'migrated');
  assert.deepEqual(loaded.value.completed, ['prologue']);
  assert.equal(loaded.value.version, 1);
  const written = JSON.parse(storage.getItem(campaignStore.key));
  assert.equal(written.version, 1);
  assert.deepEqual(written.completed, ['prologue']);
});

test('corrupt JSON falls back to defaults and keeps a backup', () => {
  const storage = memoryStorage({ [onboardingStore.key]: '{not-json' });
  const loaded = onboardingStore.load(storage);
  assert.equal(loaded.recovered, true);
  assert.equal(loaded.reason, 'corrupt-json');
  assert.equal(loaded.value.enabled, true);
  assert.equal(storage.getItem(onboardingStore.key + CORRUPT_SUFFIX), '{not-json');
});

test('oversized payloads are rejected and backed up', () => {
  const store = createRecordStore({
    key: 'rov.test.huge',
    version: 1,
    maxBytes: 64,
    defaults: () => ({ ok: true }),
    normalize: (record) => record,
  });
  const huge = JSON.stringify({ version: 1, blob: 'x'.repeat(200) });
  const storage = memoryStorage({ [store.key]: huge });
  const loaded = store.load(storage);
  assert.equal(loaded.recovered, true);
  assert.equal(loaded.reason, 'oversized');
  assert.equal(loaded.value.ok, true);
  assert.ok(storage.getItem(store.key + CORRUPT_SUFFIX).startsWith('{'));
});

test('missing and invalid fields are normalised', () => {
  const storage = memoryStorage({
    [achievementsStore.key]: JSON.stringify({
      version: 1,
      earned: ['a', 3, 'a', 'b'],
      categories: null,
      extra: true,
    }),
  });
  const loaded = achievementsStore.load(storage);
  assert.deepEqual(loaded.value.earned, ['a', 'b']);
  assert.deepEqual(loaded.value.categories, []);
  assert.equal(loaded.value.version, 1);

  const audio = audioStore.load(memoryStorage({
    [audioStore.key]: JSON.stringify({ master: 2, mute: 'yes', vehicle: 0.2 }),
  }));
  assert.equal(audio.value.master, 1);
  assert.equal(audio.value.mute, false);
  assert.equal(audio.value.vehicle, 0.2);

  const cold = coldOpenStore.load(memoryStorage({
    [coldOpenStore.key]: JSON.stringify({ seen: 1 }),
  }));
  assert.equal(cold.value.seen, true);
  assert.equal(cold.value.enabled, true);
});

test('results flat map keeps chapter keys and ignores a bad entry', () => {
  const storage = memoryStorage({
    [resultsStore.key]: JSON.stringify({
      'chapter:prologue': { best: 90, medal: 'gold', at: 1 },
      bad: 'nope',
      version: 0,
    }),
  });
  const loaded = resultsStore.load(storage);
  assert.equal(loaded.value['chapter:prologue'].best, 90);
  assert.equal(loaded.value.bad, undefined);
  assert.equal(loaded.value.version, 1);
});

test('fidelity and display recover from non-object JSON', () => {
  const fidelity = fidelityStore.load(memoryStorage({ [fidelityStore.key]: '[]' }));
  assert.equal(fidelity.recovered, true);
  assert.equal(fidelity.value.base, 'real');

  const display = displayStore.load(memoryStorage({ [displayStore.key]: 'null' }));
  assert.equal(display.recovered, true);
  assert.equal(display.value.units, 'metric');
});

test('input store rejects a too-large write', () => {
  const storage = memoryStorage();
  const huge = { bindingsVersion: 2, bindings: {}, channels: {}, custom: { x: 'y'.repeat(300000) } };
  assert.equal(inputStore.save(huge, storage), false);
  assert.equal(storage.getItem(inputStore.key), null);
});

test('save then load round-trips a campaign checkpoint', () => {
  const storage = memoryStorage();
  const record = {
    completed: ['prologue'],
    rewards: ['sticker'],
    results: [{ chapter: 'prologue', elapsed: 12 }],
    checkpoint: { chapter: 'harbor', node: 'n1' },
  };
  assert.equal(campaignStore.save(record, storage), true);
  const loaded = campaignStore.load(storage);
  assert.equal(loaded.recovered, false);
  assert.deepEqual(loaded.value.completed, ['prologue']);
  assert.equal(loaded.value.checkpoint.chapter, 'harbor');
  assert.equal(loaded.value.version, 1);
});
