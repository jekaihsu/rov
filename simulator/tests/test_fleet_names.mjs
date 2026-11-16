// Player-facing YX fleet names (viewer/fleet_names.js) agree with the server export and never show vendor names.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {
  FLEET_IDS, STRINGS, blockFor, siteName, vehicleDetail, vehicleName, vehicleRole, vehicleTagline, vehicleTitle
} from '../viewer/fleet_names.js';

const VIEWER = new URL('../viewer/', import.meta.url);
const VENDOR = /\bX1\b|BlueROV|Falcon|Korean Castle|QYSEA|FIFISH/i;

test('internal ids map to the YX fleet names', () => {
  assert.deepEqual([...FLEET_IDS], ['x1', 'bluerov2_heavy', 'falcon']);
  assert.equal(vehicleName('x1'), 'YX Model R');
  assert.equal(vehicleName('bluerov2_heavy'), 'YX Model O');
  assert.equal(vehicleName('falcon'), 'YX Model V');
  assert.equal(vehicleRole('x1'), '入門觀測型');
  assert.equal(vehicleRole('bluerov2_heavy'), '重載觀測型');
  assert.equal(vehicleRole('falcon'), '輕作業型');
  assert.equal(vehicleName('mystery'), 'mystery');
  assert.equal(vehicleName(undefined), 'ROV');
  assert.equal(vehicleName('constructor'), 'constructor');
});

test('every model has a tagline and no player text names a vendor', () => {
  for (const id of FLEET_IDS) {
    assert.ok(vehicleTagline(id), id);
    assert.ok(vehicleDetail(id).startsWith(vehicleRole(id)), id);
    for (const text of Object.values(STRINGS.models[id])) {
      assert.doesNotMatch(text, VENDOR);
    }
  }
});

test('the Block number is 1 for now and appears in the title', () => {
  assert.equal(blockFor('x1'), 1);
  assert.equal(blockFor('falcon', {equipment: ['arm']}), 1);
  assert.equal(vehicleTitle('x1'), 'YX Model R · Block 1');
  assert.equal(vehicleTitle('bluerov2_heavy', null), 'YX Model O · Block 1');
});

test('the korean_castle site is shown as 碧海號', () => {
  assert.equal(siteName('korean_castle'), '碧海號');
  assert.equal(siteName('open_water'), null);
});

test('the exported menu catalogue uses the same names', async () => {
  const catalogue = JSON.parse(await readFile(new URL('menu_catalogue.json', VIEWER), 'utf8'));
  for (const vehicle of catalogue.vehicles) {
    assert.equal(vehicle.name, vehicleName(vehicle.id));
    assert.equal(vehicle.role, vehicleRole(vehicle.id));
  }
  const scenes = JSON.parse(await readFile(new URL('scene_previews.json', VIEWER), 'utf8'));
  for (const scene of scenes) {
    assert.doesNotMatch(`${scene.name} ${scene.brief}`, VENDOR, scene.key);
  }
});

test('a career save raises the Block number shown in the title', () => {
  const save = {vehicles: {x1: {block: 2}, falcon: {block: 3}}};
  assert.equal(blockFor('x1', save), 2);
  assert.equal(blockFor('falcon', save), 3);
  assert.equal(blockFor('bluerov2_heavy', save), 1);
  assert.equal(blockFor('constructor', save), 1);
  assert.equal(blockFor('x1', {vehicles: {x1: {block: 'bad'}}}), 1);
  assert.equal(vehicleTitle('x1', save), 'YX Model R · Block 2');
});
