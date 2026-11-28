// Field journal helpers: continue assignment and the live backdrop stay on the same site.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { careerDataFrom } from '../viewer/career/data.js';
import { recommendedContract } from '../viewer/career/rules.js';
import { defaultSave } from '../viewer/career/save.js';
import { backdropChapter, backdropLocation, backdropScene } from '../viewer/menu/journal_backdrop.js';

const CAREER = new URL('../viewer/career/', import.meta.url);
const LOCATIONS = {
  tutorial_pool: '清晨 · 室內水池',
  open_water: '日間 · 港外',
  harbor_inspection: '日間 · 港口',
  aquaculture_pen: '陰天 · 養殖場外海',
  prologue: '清晨 · 室內水池',
  ch1: '日間 · 港口',
  ch2: '陰天 · 養殖場外海',
};

async function careerData() {
  const json = async (name) => JSON.parse(await readFile(new URL(name, CAREER), 'utf8'));
  return careerDataFrom({
    contractsFile: await json('contracts.json'),
    licencesFile: await json('licences.json'),
    equipmentFile: await json('equipment.json'),
  });
}

async function sceneKeys() {
  const scenes = JSON.parse(await readFile(new URL('../viewer/scene_previews.json', import.meta.url), 'utf8'));
  return new Set(scenes.map((scene) => scene.key));
}

function wrap(data, save, keys) {
  return {data, save, sceneKeys: keys};
}

test('a fresh career continues into the pool dive with a matching pool backdrop', async () => {
  const data = await careerData();
  const save = defaultSave();
  const keys = await sceneKeys();
  const ctx = wrap(data, save, keys);
  const next = recommendedContract(data, save, keys);
  assert.equal(next.id, 'p1_pool_checkout');
  assert.equal(backdropChapter(ctx, next), 'prologue');
  assert.equal(backdropScene(ctx, next), 'tutorial_pool');
  assert.match(backdropLocation(LOCATIONS, ctx, next), /水池/);
});

test('the continue site and the place line stay with the recommended work order', async () => {
  const data = await careerData();
  const save = defaultSave();
  save.contracts.p1_pool_checkout = {completed: 1, medal: 'bronze'};
  const keys = await sceneKeys();
  const ctx = wrap(data, save, keys);
  const next = recommendedContract(data, save, keys);
  assert.equal(next.id, 'p2_open_water');
  assert.equal(backdropScene(ctx, next), 'open_water');
  assert.equal(backdropChapter(ctx, next), 'prologue');
  assert.match(backdropLocation(LOCATIONS, ctx, next), /港外/);
});

test('a harbour work order frames the harbour piles', async () => {
  const data = await careerData();
  const save = defaultSave();
  const next = data.contracts.find((entry) => entry.id === 'c1_pier_level1')
    || data.contracts.find((entry) => entry.scenario === 'harbor_inspection');
  assert.ok(next, 'a harbour work order exists');
  const ctx = wrap(data, save, await sceneKeys());
  assert.equal(backdropScene(ctx, next), 'harbor_inspection');
  assert.match(backdropLocation(LOCATIONS, ctx, next), /港口/);
});
