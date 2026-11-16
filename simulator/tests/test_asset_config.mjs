// Asset set selection: the training models stay the default; ?assets=generic swaps only mapped vehicles.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
  assetSet, genericVehicle, genericVehicleUrl, applyGenericLabels, GENERIC_VEHICLES
} from '../viewer/asset_config.js';

test('training is the default asset set', () => {
  assert.equal(assetSet(), 'training');
  assert.equal(assetSet(null), 'training');
  assert.equal(assetSet('anything'), 'training');
  assert.equal(assetSet('generic'), 'generic');
  assert.equal(genericVehicleUrl('x1'), null);
});

test('generic set maps the default vehicle to clamped LOD urls', () => {
  assert.equal(genericVehicleUrl('x1', 0, 'generic'), 'models/observation_rov.glb');
  assert.equal(genericVehicleUrl('x1', 2, 'generic'), 'models/observation_rov_lod2.glb');
  assert.equal(genericVehicleUrl('x1', 9, 'generic'), 'models/observation_rov_lod2.glb');
  assert.equal(genericVehicleUrl('x1', -1, 'generic'), 'models/observation_rov.glb');
  assert.equal(genericVehicleUrl('falcon', 0, 'generic'), null);
  assert.equal(genericVehicle('bluerov2_heavy', 'generic'), null);
});

test('menu labels change only for swapped vehicles and only in the generic set', () => {
  const make = () => ({x1: {name: 'YX Model R', detail: 'a'}, falcon: {name: 'YX Model V', detail: 'b'}});
  const training = applyGenericLabels(make(), 'training');
  assert.equal(training.x1.name, 'YX Model R');
  assert.equal(training.x1.detail, 'a');
  const generic = applyGenericLabels(make(), 'generic');
  assert.equal(generic.x1.name, GENERIC_VEHICLES.x1.name);
  assert.equal(generic.x1.detail, GENERIC_VEHICLES.x1.detail);
  assert.notEqual(generic.x1.detail, 'a');
  assert.equal(generic.falcon.name, 'YX Model V');
  assert.equal(generic.falcon.detail, 'b');
});

test('the generic observation ROV is the YX Model R art variant', () => {
  assert.equal(GENERIC_VEHICLES.x1.name, 'YX Model R');
  assert.ok(GENERIC_VEHICLES.x1.detail);
});
