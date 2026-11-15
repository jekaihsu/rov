import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';

const source = await readFile(new URL('../viewer/state_merge.js', import.meta.url), 'utf8');
const {mergeState, coalesceStates, coalesceStateText, createStateMerger, VIEWER_CAPS, STATIC_ONCE_CAP} =
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
    type: 'state', delta: true, t: 1.1, pos: [0.1, 0, 1],
    vehicles: [{vehicle_id: 'v1', id: 'v1', pos: [0.1, 0, 1]}],
  };
  const merged = mergeState(full, delta);
  assert.deepEqual(merged.vehicle, full.vehicle);
  assert.deepEqual(merged.campaign, full.campaign);
  assert.deepEqual(merged.power, full.power);
  assert.equal(merged.vehicles[0].vehicle.id, 'x1');
  assert.deepEqual(merged.vehicles[0].pos, [0.1, 0, 1]);
  assert.equal(merged.t, 1.1);
  assert.equal('delta' in merged, false);
});

test('explicit null replaces a retained value', () => {
  const previous = {type: 'state', expedition: {id: 'a'}, mission: {mode: 'free'}};
  const incoming = {type: 'state', delta: true, expedition: null, t: 2};
  assert.equal(mergeState(previous, incoming).expedition, null);
});

test('stateful merger resets and ignores non-state messages', () => {
  const merger = createStateMerger();
  const world = {type: 'world'};
  assert.equal(merger.merge(world), world);
  const first = merger.merge({type: 'state', t: 0, vehicle: {id: 'x1'}, campaign: {status: 'idle'}});
  assert.equal(first.vehicle.id, 'x1');
  const second = merger.merge({type: 'state', delta: true, t: 0.1});
  assert.equal(second.vehicle.id, 'x1');
  merger.reset();
  const third = merger.merge({type: 'state', delta: true, t: 0.2});
  assert.equal(third.vehicle, undefined);
});

test('unmarked state is complete and drops keys it no longer carries', () => {
  const previous = {type: 'state', vehicle: {id: 'x1'}, procedure: {step: 2}, remote_control: {owner: 'sdk'}};
  const merged = mergeState(previous, {type: 'state', t: 3, vehicle: {id: 'x1'}});
  assert.equal('procedure' in merged, false);
  assert.equal('remote_control' in merged, false);
});

test('delta keeps omitted allowlisted fields but not removed high-rate keys', () => {
  const previous = {
    type: 'state', vehicle: {id: 'x1'}, procedure: {step: 2},
    vehicles: [{vehicle_id: 'v1', vehicle: {id: 'x1'}, procedure: {step: 2}}],
  };
  const incoming = {type: 'state', delta: true, t: 3, vehicles: [{vehicle_id: 'v1'}]};
  const merged = mergeState(previous, incoming);
  assert.equal(merged.vehicle.id, 'x1');
  assert.equal('procedure' in merged, false);
  assert.equal(merged.vehicles[0].vehicle.id, 'x1');
  assert.equal('procedure' in merged.vehicles[0], false);
});

test('coalescing skipped deltas has the same effect as merging each one', () => {
  const full = {
    type: 'state', t: 0, locked: false, control_generation: 1, vehicle: {id: 'x1'}, procedure: {step: 1},
    vehicles: [{vehicle_id: 'v1', locked: false, vehicle: {id: 'x1'}, pos: [0, 0, 0]}],
  };
  const first = {
    type: 'state', delta: true, t: 1, locked: true, control_generation: 2,
    vehicles: [{vehicle_id: 'v1', locked: true, pos: [1, 0, 0]}],
  };
  const second = {type: 'state', delta: true, t: 2, vehicles: [{vehicle_id: 'v1', pos: [2, 0, 0]}]};
  const stepwise = mergeState(mergeState(full, first), second);
  const combined = coalesceStates(first, second);
  assert.equal(combined.delta, true);
  assert.equal(combined.control_generation, 2);
  assert.deepEqual(mergeState(full, combined), stepwise);
  assert.equal(stepwise.locked, true);
  assert.equal(stepwise.vehicles[0].locked, true);
  assert.equal('procedure' in stepwise, false);
});

test('coalescing onto a complete snapshot stays complete, and a complete successor replaces', () => {
  const full = {type: 'state', t: 0, vehicle: {id: 'x1'}, locked: false};
  const delta = {type: 'state', delta: true, t: 1, locked: true};
  const combined = coalesceStates(full, delta);
  assert.equal('delta' in combined, false);
  assert.deepEqual(combined, {type: 'state', t: 1, vehicle: {id: 'x1'}, locked: true});
  assert.equal(coalesceStates(delta, full), full);
  const text = JSON.stringify(full);
  assert.equal(coalesceStateText(JSON.stringify(delta), text), text);
  assert.equal(coalesceStateText(null, JSON.stringify(delta)), JSON.stringify(delta));
  assert.deepEqual(JSON.parse(coalesceStateText(text, JSON.stringify(delta))), combined);
});
