// Verify radio timing at the flight telemetry boundary without a clock, DOM or audio device.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {advanceReactions} from '../viewer/story/crew_reactions.js';

function tick(prev, t, state = {}, options = {}) {
  return advanceReactions(prev, {t, ...state}, {mission: 'harbor', ...options});
}
test('rising hazards, shared cooldown, same hazard cooldown and held edges', () => {
  const high = {tether: {warn: true}};
  let model = tick(null, 0);
  model = tick(model, 1, high);
  assert.equal(model.line, 'tension');
  model = tick(model, 2, {...high, battery: 20});
  assert.equal(model.line, null);
  assert.deepEqual(model.pending, ['battery']);
  model = tick(model, 9, {...high, battery: 20});
  assert.equal(model.line, 'battery');
  model = tick(model, 12, {battery: 20, tether: {warn: false}});
  assert.equal(model.signals.tension, false);
  model = tick(model, 13, {battery: 20, tether: {warn: false}});
  assert.equal(model.line, null);
  assert.equal(tick(tick(model, 31, {battery: 20}), 32, {...high, battery: 20}).line, 'tension');
});
test('target and battery thresholds; snag and collision', () => {
  const start = tick(null, 0, {battery: 21});
  assert.equal(tick(start, 1, {battery: 20}).line, 'battery');
  assert.equal(tick(start, 1, {tether: {snagged_on: ['pile']}}).line, 'snag');
  assert.equal(tick(start, 1, {events: [{t: 1, obstacle: 'Quay'}]}).line, 'impact');
  for (const distance of [1.99, 2, 2.01]) {
    const state = {pos: [0, 0, 0], mission: {targets: [{point: [0, 0, distance]}]}};
    assert.equal(tick(start, 1, state).line, distance <= 2 ? 'near' : null);
  }
});
test('45 seconds since activity, allowing dialogue and mission resets', () => {
  let model = tick(null, 10);
  assert.equal(tick(model, 54.99).line, null);
  assert.equal(tick(model, 55).line, 'idle');
  model = tick(model, 50, {photos: 1});
  assert.equal(tick(model, 94, {photos: 1}).line, null);
  assert.equal(tick(model, 95, {photos: 1}, {busy: true}).line, null);
  assert.equal(tick(model, 99, {}, {mission: 'other'}).line, null);
});
test('disabled feedback produces no call or stale backlog', () => {
  const off = {enabled: false, idle: false};
  assert.equal(tick(null, 1, {battery: 19}, off), null);
  assert.equal(tick(null, 80, {battery: 19}).line, null);
  assert.equal(tick(tick(null, 0), 60, {}, {idle: false}).line, null);
});

test('line pull prefers host warn and keeps the cold-open presentation band', () => {
  function load(model, t, force, warn = false) {
    return tick(model, t, {tether: {tension_spool: force, warn}});
  }
  let model = load(null, 0, 0);
  assert.equal(load(model, 1, 40).line, null);
  model = load(model, 2, 41);
  assert.equal(model.line, 'tension');
  assert.equal(load(model, 33, 26).signals.tension, true);
  model = load(model, 34, 25);
  assert.equal(model.signals.tension, false);
  assert.equal(load(model, 35, 10, true).line, 'tension');
});

test('pending hazards survive radio busy and the shared cooldown', () => {
  let model = tick(null, 0);
  model = tick(model, 1, {events: [{t: 1, obstacle: 'Pile'}]});
  assert.equal(model.line, 'impact');
  model = tick(model, 2, {events: [{t: 1, obstacle: 'Pile'}], tether: {warn: true}}, {busy: true});
  assert.equal(model.line, null);
  assert.deepEqual(model.pending, ['tension']);
  model = tick(model, 5, {events: [{t: 1, obstacle: 'Pile'}], tether: {warn: true}});
  assert.equal(model.line, null);
  assert.deepEqual(model.pending, ['tension']);
  model = tick(model, 9, {events: [{t: 1, obstacle: 'Pile'}], tether: {warn: true}});
  assert.equal(model.line, 'tension');
  assert.deepEqual(model.pending, []);
});

test('presentation seconds govern quiet time on a slow host', () => {
  const start = tick(null, 0, {}, {now: 20});
  assert.equal(tick(start, 10, {}, {now: 65}).line, 'idle');
});
