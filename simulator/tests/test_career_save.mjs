// Career save model (viewer/career/save.js): defaults, normalisation, migration of the older records, logbook
// hours kept apart by fidelity, and export/import.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CAMPAIGN_KEY, CAREER_KEY, LEGACY_BONUS_CAP, RESULTS_KEY, assistedHours, defaultSave, exportCareer, importCareer,
  loadCareer, logDive, normalizeSave, realHours, storeCareer,
} from '../viewer/career/save.js';

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    raw: data,
  };
}

const NOW = Date.parse('2026-11-15T08:00:00Z');

test('a fresh career has no licence, no money, no debt and Block 1 everywhere', () => {
  const save = defaultSave(NOW);
  assert.equal(save.version, 1);
  assert.equal(save.money, 0);
  assert.equal(save.debt, 0);
  assert.equal(save.licence, 'none');
  assert.deepEqual(save.vehicles, {x1: {block: 1}, bluerov2_heavy: {block: 1}, falcon: {block: 1}});
  assert.deepEqual(save.hours, {real_s: 0, assisted_s: 0});
  assert.deepEqual(save.logbook, []);
});

test('loading without a save creates and stores one under a single key', () => {
  const storage = memoryStorage();
  const save = loadCareer({storage, now: NOW});
  assert.equal(save.money, 0);
  assert.ok(storage.raw.has(CAREER_KEY));
  assert.equal([...storage.raw.keys()].length, 1);
  assert.deepEqual(loadCareer({storage, now: NOW}), save);
});

test('normalisation drops bad fields and clamps numbers', () => {
  const save = normalizeSave({
    money: -50, licence: 'DROP TABLE', owned: ['laser_scaler', 'laser_scaler', 7], reputation: {harbor: 12.4, 'x y': 3},
    vehicles: {x1: {block: 0}, falcon: {block: 3}}, contracts: {c1: {completed: 2, best: 140, medal: 'platinum'}},
    logbook: [{outcome: 'won', medal: 'gold', real_s: -4, pay: 99.6}], activeDive: {nope: true},
  }, NOW);
  assert.equal(save.money, 0);
  assert.equal(save.licence, 'none');
  assert.deepEqual(save.owned, ['laser_scaler']);
  assert.deepEqual(save.reputation, {harbor: 12});
  assert.equal(save.vehicles.x1.block, 1);
  assert.equal(save.vehicles.falcon.block, 3);
  assert.deepEqual(save.contracts.c1, {completed: 2, attempts: 0, best: 100, medal: 'none'});
  assert.equal(save.logbook[0].outcome, 'aborted');
  assert.equal(save.logbook[0].real_s, 0);
  assert.equal(save.logbook[0].pay, 100);
  assert.equal(save.activeDive, null);
});

test('a new career migrates the older story progress and best scores without touching them', () => {
  const campaign = JSON.stringify({completed: ['prologue', 'harbor'], rewards: ['first_dive'],
    results: [{chapter: 'prologue', elapsed: 600, collisions: 0}, {chapter: 'harbor', elapsed: 900}]});
  const results = JSON.stringify({'chapter:prologue': {best: 95, medal: 'gold'},
    'scenario:open_water': {best: 80, medal: 'silver'}, 'scenario:x': {best: 10, medal: 'none'}});
  const storage = memoryStorage({[CAMPAIGN_KEY]: campaign, [RESULTS_KEY]: results});
  const save = loadCareer({storage, now: NOW});
  assert.equal(save.contracts.p0_induction.completed, 1);
  assert.equal(save.money, 1000);
  assert.equal(save.logbook.length, 2);
  assert.ok(save.logbook.every((entry) => entry.legacy && entry.real_s === 0));
  assert.equal(save.hours.assisted_s, 1500);
  assert.equal(save.hours.real_s, 0);
  assert.deepEqual(save.migration.chapters, ['prologue', 'harbor']);
  assert.equal(save.migration.records, 3);
  assert.equal(storage.getItem(CAMPAIGN_KEY), campaign);
  assert.equal(storage.getItem(RESULTS_KEY), results);
});

test('the migration bonus is capped', () => {
  const records = {};
  for (let i = 0; i < 40; i++) records[`scenario:${i}`] = {best: 99, medal: 'gold'};
  const storage = memoryStorage({[RESULTS_KEY]: JSON.stringify(records)});
  assert.equal(loadCareer({storage, now: NOW}).money, LEGACY_BONUS_CAP);
});

test('the logbook keeps real and assisted hours apart', () => {
  const save = defaultSave(NOW);
  logDive(save, {contract: 'p1', outcome: 'complete', real_s: 1800, assisted_s: 0, duration_s: 1800});
  logDive(save, {contract: 'p1', outcome: 'partial', real_s: 0, assisted_s: 900, duration_s: 900});
  assert.equal(realHours(save), 0.5);
  assert.equal(assistedHours(save), 0.25);
  assert.equal(save.logbook.length, 2);
});

test('export and import round-trip, and foreign files are refused', () => {
  const storage = memoryStorage();
  const save = loadCareer({storage, now: NOW});
  save.money = 4200;
  save.owned.push('laser_scaler');
  storeCareer(save, {storage, now: NOW, mirror: false});
  const back = importCareer(exportCareer(save, NOW), NOW);
  assert.equal(back.money, 4200);
  assert.deepEqual(back.owned, ['laser_scaler']);
  assert.throws(() => importCareer('not json'), /職涯存檔/);
  assert.throws(() => importCareer(JSON.stringify({format: 'other', save: {}})), /職涯存檔/);
  assert.throws(() => importCareer(JSON.stringify({format: 'rov-career', version: 99, save: {}})), /較新/);
});
