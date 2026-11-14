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
  const make = () => ({x1: {name: 'X1', detail: 'a'}, falcon: {name: 'Falcon', detail: 'b'}});
  const training = applyGenericLabels(make(), 'training');
  assert.equal(training.x1.name, 'X1');
  const generic = applyGenericLabels(make(), 'generic');
  assert.equal(generic.x1.name, GENERIC_VEHICLES.x1.name);
  assert.equal(generic.falcon.name, 'Falcon');
});
