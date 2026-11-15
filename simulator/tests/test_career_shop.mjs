// YX equipment department (viewer/career/shop_rules.js, equipment.json): only equipment that maps to a
// deliverable or work order, licence and money gating, Block levels per vehicle, cosmetics only once owned.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {careerDataFrom} from '../viewer/career/data.js';
import {contractById, contractStatus} from '../viewer/career/rules.js';
import {defaultSave} from '../viewer/career/save.js';
import {blockLevel, itemStatus, purchase, stickerAvailable} from '../viewer/career/shop_rules.js';
import {STRINGS as FLEET, blockFor, vehicleTitle} from '../viewer/fleet_names.js';

const CAREER = new URL('../viewer/career/', import.meta.url);
async function json(name) {
  return JSON.parse(await readFile(new URL(name, CAREER), 'utf8'));
}
async function careerData() {
  return careerDataFrom({contractsFile: await json('contracts.json'), licencesFile: await json('licences.json'),
    equipmentFile: await json('equipment.json')});
}

test('buying needs the money and the licence, and is a one-off', async () => {
  const data = await careerData();
  const save = defaultSave();
  const scaler = data.items.find((item) => item.id === 'laser_scaler');
  assert.match(itemStatus(scaler, save, data).reason, /資金不足/);
  assert.equal(purchase(save, data, 'laser_scaler').ok, false);
  save.money = 20000;
  const sonar = data.items.find((item) => item.id === 'imaging_sonar');
  assert.match(itemStatus(sonar, save, data).reason, /見習/);
  const result = purchase(save, data, 'laser_scaler');
  assert.equal(result.ok, true);
  assert.equal(save.money, 20000 - scaler.price);
  assert.deepEqual(save.owned, ['laser_scaler']);
  assert.equal(purchase(save, data, 'laser_scaler').ok, false);
  assert.equal(itemStatus(scaler, save, data).owned, true);
});

test('equipment raises the Block of the vehicles it fits', async () => {
  const data = await careerData();
  const save = {...defaultSave(), money: 100000, licence: 'grade2'};
  const first = purchase(save, data, 'laser_scaler');
  assert.deepEqual(first.blocks.map((entry) => [entry.vehicle, entry.after]),
    [['x1', 2], ['bluerov2_heavy', 2], ['falcon', 2]]);
  assert.equal(blockFor('x1', save), 2);
  assert.equal(vehicleTitle('x1', save), `${FLEET.models.x1.name} · Block 2`);
  purchase(save, data, 'gripper');
  assert.equal(blockLevel(save, data, 'falcon'), 3);
  assert.equal(blockLevel(save, data, 'x1'), 2);
  const cosmetic = purchase(save, data, 'sticker_yx_logo');
  assert.deepEqual(cosmetic.blocks, [], 'cosmetics never change the Block');
});

test('a work order that needs equipment opens once it is bought', async () => {
  const data = await careerData();
  const withScaler = data.contracts.find((contract) => (contract.equipment || []).includes('laser_scaler'));
  if (!withScaler) return;
  const save = {...defaultSave(), money: 100000, licence: 'grade2'};
  for (const id of withScaler.requires || []) save.contracts[id] = {completed: 1, attempts: 1, best: 90, medal: 'gold'};
  assert.ok(contractStatus(withScaler, save, data).reasons.some((reason) => reason.kind === 'equipment'));
  purchase(save, data, 'laser_scaler');
  assert.ok(!contractStatus(contractById(data, withScaler.id), save, data).reasons.some((r) => r.kind === 'equipment'));
});

test('shop stickers show in the hangar only once owned; the free ones always', async () => {
  const data = await careerData();
  const save = {...defaultSave(), money: 5000};
  assert.equal(stickerAvailable(save, data, 'hazard'), true);
  assert.equal(stickerAvailable(save, data, 'yx_logo'), false);
  purchase(save, data, 'sticker_yx_logo');
  assert.equal(stickerAvailable(save, data, 'yx_logo'), true);
});
