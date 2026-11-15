import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';

const source = await readFile(new URL('../viewer/state_merge.js', import.meta.url), 'utf8');
const {mergeState, createStateMerger, VIEWER_CAPS, STATIC_ONCE_CAP} =
  await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('viewer declares static_once', () => {
  assert.deepEqual(VIEWER_CAPS, [STATIC_ONCE_CAP]);
});

test('merge restores omitted top-level and fleet fields', () => {
  const full = {
    type: 'state', t: 1, vehicle: {id: 'x1'}, campaign: {status: 'idle'},
    power: {demand_w: 10}, thermal: {motor_c: 30}, flow_field: {seq: 1},
    vehicles: [{vehicle_id: 'v1', id: 'v1', vehicle: {id: 'x1'}, power: {demand_w: 10}, pos: [0, 0, 1]}],
  };
  const delta = {
    type: 'state', t: 1.1, pos: [0.1, 0, 1],
    vehicles: [{vehicle_id: 'v1', id: 'v1', pos: [0.1, 0, 1]}],
  };
  const merged = mergeState(full, delta);
  assert.deepEqual(merged.vehicle, full.vehicle);
  assert.deepEqual(merged.campaign, full.campaign);
  assert.deepEqual(merged.power, full.power);
  assert.equal(merged.vehicles[0].vehicle.id, 'x1');
  assert.deepEqual(merged.vehicles[0].pos, [0.1, 0, 1]);
  assert.equal(merged.t, 1.1);
});

test('explicit null replaces a retained value', () => {
  const previous = {type: 'state', expedition: {id: 'a'}, mission: {mode: 'free'}};
  const incoming = {type: 'state', expedition: null, t: 2};
  assert.equal(mergeState(previous, incoming).expedition, null);
});

test('stateful merger resets and ignores non-state messages', () => {
  const merger = createStateMerger();
  const world = {type: 'world'};
  assert.equal(merger.merge(world), world);
  const first = merger.merge({type: 'state', t: 0, vehicle: {id: 'x1'}, campaign: {status: 'idle'}});
  assert.equal(first.vehicle.id, 'x1');
  const second = merger.merge({type: 'state', t: 0.1});
  assert.equal(second.vehicle.id, 'x1');
  merger.reset();
  const third = merger.merge({type: 'state', t: 0.2});
  assert.equal(third.vehicle, undefined);
});
