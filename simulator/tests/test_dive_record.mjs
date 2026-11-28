// Whole-dive history, telemetry-derived coaching and backward-compatible clip handling.
import assert from 'node:assert/strict';
import test from 'node:test';
import {createDiveRecord, findings} from '../viewer/debrief/dive_record.js';
import {createFlightLog} from '../viewer/play/flight_log.js';

test('isolates snag overload intervals and deduplicates discrete events', () => {
  const pile = {kind: 'pile', radius: 1, p0: [0,0,0], p1: [0,0,10]};
  const record = createDiveRecord({obstacles: [pile]});
  for (let t = 0; t <= 8; t++) {
    record.observe({t, pos: [2,0,t], vel: [0.8,0,0], photos: t < 2 ? 0 : 1, locked: t === 0,
      events: t < 3 ? [] : [{t: 3, obstacle: 'P1'}], tether: {warn: t < 7, tension_max: 50 - Math.abs(4-t)},
      tether_ops: {snag: t < 7 ? {name: 'P1', returned: t === 6} : null, result: {correct: true}}},
      [{kind: 'measure', id: 'A', done: t >= 1}]);
  }
  const {events, metrics} = record.snapshot();
  assert.deepEqual(events.filter(e => e.kind === 'peak').map(e => e.t), [4]);
  for (const kind of ['collision','snag','released','returned','measure','photo','unlock','dive']) {
    assert.equal(events.filter(e => e.kind === kind).length, 1, kind);
  }
  assert.deepEqual(metrics, {approach: 0.8, loaded: 6, recoveries: 1, collisions: 1});
  assert.deepEqual(findings(metrics).map(r => r.message), ['impact','slow','ease','recovered']);
  assert.deepEqual(findings(createDiveRecord({}).snapshot().metrics), []);
});

test('long flights retain start, end and between-frame peaks, reset starts a separate record', () => {
  const log = createFlightLog({getWorld: () => ({})});
  for (let i = 0; i <= 6500; i++) {
    log.update({t: i/10, tether: {tension_max: i === 111 ? 75 : 1}});
  }
  const clip = log.snapshot().clips[0];
  assert.equal(clip.frames[0].t, 0);
  assert.equal(clip.frames.at(-1).t, 650);
  assert.equal(clip.dive.events.find(e => e.kind === 'peak').t, 11.1);
  log.update({t: 0});
  log.update({t: 1});
  assert.equal(log.snapshot().clips[0].dive.samples.length, 2);
});
