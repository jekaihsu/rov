// Chapter-1 career tooling: laser scale math, fouling rating vs truth, LOTO unlock gate, radio bus dedupe,
// same-angle photo compare, and measure setMeasureResult on the deliverable tracker.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createTracker } from '../viewer/career/deliverables.js';
import { foulingRatingDelta, foulingRatingOk } from '../viewer/career/fouling_rating.js';
import { thicknessCmFromSeparation, LASER_BASELINE_M } from '../viewer/career/laser_scaler.js';
import { createLotoGate, lotoConfirmIds } from '../viewer/career/loto_gate.js';
import { comparePose } from '../viewer/career/photo_compare.js';
import { createRadioBus } from '../viewer/career/radio_bus.js';

function state(pos, heading = 0, extra = {}) {
  return {
    t: 0,
    pos,
    euler: [0, 0, heading],
    vel: [0, 0, 0],
    locked: false,
    events: [],
    tether: { warn: false },
    ...extra,
  };
}

test('laser thickness scales feature pixels against the 0.10 m baseline', () => {
  assert.equal(LASER_BASELINE_M, 0.10);
  assert.equal(thicknessCmFromSeparation(50, 100), 5);
  assert.equal(thicknessCmFromSeparation(100, 100), 10);
  assert.equal(thicknessCmFromSeparation(25, 100, 0.2), 5);
  assert.equal(thicknessCmFromSeparation(10, 0), null);
});

test('fouling rating helpers compare pick against truth', () => {
  assert.equal(foulingRatingOk(3, 3), true);
  assert.equal(foulingRatingOk(2, 3), false);
  assert.equal(foulingRatingDelta(1, 4), 3);
  assert.equal(foulingRatingDelta('x', 2), null);
});

test('loto gate blocks unlock until unlock confirms are done', () => {
  const contract = {
    lotoBeforeUnlock: true,
    deliverables: [
      { id: 'loto', kind: 'confirm', label: 'LOTO', gate: 'unlock' },
      { id: 'prop', kind: 'photo', label: 'prop', point: [0, 0, 5], standoff: [1, 4] },
    ],
  };
  assert.deepEqual(lotoConfirmIds(contract), ['loto']);
  const gate = createLotoGate(contract);
  assert.equal(gate.confirmAllowed, true);
  assert.equal(gate.blocksUnlock({ items: [{ id: 'loto', done: false }] }), true);
  assert.equal(gate.blocksUnlock({ items: [{ id: 'loto', done: true }] }), false);
  assert.match(gate.pendingLabels({ items: [{ id: 'loto', done: false }] })[0], /LOTO/);
});

test('radio bus fires each trigger id once', () => {
  const heard = [];
  const bus = createRadioBus({
    radio: {
      triggers: [
        { id: 'near_a', when: 'near:pile', speaker: '林岑', text: '近了' },
        { id: 'done_a', when: 'done:pile', speaker: '周楷', text: '齊了' },
        { id: 'rush', when: 'rush', speaker: '葉理', text: '催' },
      ],
    },
  }, {
    say(speaker, text) {
      heard.push(`${speaker}:${text}`);
    },
  });
  const snap = {
    items: [{ id: 'pile', done: false, point: [10, 0, 5] }],
    penalties: [],
    requiredDone: 0,
    requiredTotal: 1,
    complete: false,
  };
  bus.observe(state([10.5, 0, 5]), snap, 0.1);
  bus.observe(state([10.2, 0, 5]), snap, 0.1);
  assert.deepEqual(heard, ['林岑:近了']);
  snap.items[0].done = true;
  bus.observe(state([10.2, 0, 5]), snap, 0.1);
  bus.observe(state([10.2, 0, 5]), snap, 0.1);
  assert.deepEqual(heard, ['林岑:近了', '周楷:齊了']);
  bus.observe(state([0, 0, 3], 0, { t: 500 }), snap, 0.1);
  bus.observe(state([0, 0, 3], 0, { t: 600 }), snap, 0.1);
  assert.deepEqual(heard, ['林岑:近了', '周楷:齊了', '葉理:催']);
});

test('photo compare yaw tolerance uses reference heading', () => {
  const def = {
    point: [10, 0, 5],
    standoff: [1, 3],
    compare: { yaw_tol_deg: 10, standoff_tol_m: 0.5 },
    reference: { yaw_deg: 0, standoff_m: 2 },
  };
  const ok = comparePose(def, state([8, 0, 5], 0));
  assert.equal(ok.ok, true);
  assert.ok(ok.yawErr <= 10);
  const drifted = comparePose(def, state([8, 0, 5], 40));
  assert.equal(drifted.ok, false);
  assert.ok(drifted.yawErr > 10);
});

test('measure setMeasureResult overrides canned reading; canned still works alone', () => {
  const contract = {
    id: 'm',
    deliverables: [
      {
        id: 'growth',
        kind: 'measure',
        label: 'growth',
        point: [10, 0, 8],
        standoff: [0.5, 1.5],
        hold_s: 1,
        equipment: 'laser_scaler',
        reading: '5 cm',
        truth_cm: 4.5,
        growth: 'hard',
      },
    ],
  };
  const canned = createTracker(contract, { owned: ['laser_scaler'] });
  for (let i = 0; i < 15; i += 1) canned.observe(state([9, 0, 8], 0), 0.1);
  assert.equal(canned.snapshot().items[0].done, true);
  assert.equal(canned.snapshot().items[0].reading, '5 cm');

  const live = createTracker(contract, { owned: ['laser_scaler'] });
  assert.equal(live.setMeasureResult('growth', { thickness_cm: 4.5, growth: 'soft' }), true);
  for (let i = 0; i < 15; i += 1) live.observe(state([9, 0, 8], 0), 0.1);
  const item = live.snapshot().items[0];
  assert.equal(item.done, true);
  assert.equal(item.growthPick, 'soft');
  assert.match(item.reading, /軟附著/);
  assert.match(item.reading, /4\.5/);
});

test('photo rating stays pending until rate(); compare drift adds a penalty', () => {
  const contract = {
    id: 'p',
    deliverables: [
      {
        id: 'hull',
        kind: 'photo',
        label: 'hull',
        point: [10, 0, 5],
        standoff: [1, 4],
        rating: 2,
        compare: { yaw_tol_deg: 5, standoff_tol_m: 0.2 },
        reference: { yaw_deg: 0, standoff_m: 2 },
      },
    ],
  };
  const tracker = createTracker(contract);
  const shot = tracker.photo(state([7, 0, 5], 30));
  assert.equal(shot.accepted, 'hull');
  assert.equal(shot.pendingRating, true);
  const pending = tracker.snapshot();
  assert.equal(pending.complete, false);
  assert.equal(pending.items[0].pendingRating, true);
  assert.equal(pending.items[0].compareOk, false);
  assert.equal(pending.penalties.some(function quality(entry) {
    return entry.kind === 'quality' && entry.points === 5;
  }), true);
  assert.equal(tracker.rate('hull', 2), true);
  const done = tracker.snapshot();
  assert.equal(done.complete, true);
  assert.equal(done.items[0].rating, 2);
  assert.equal(done.items[0].truthRating, 2);
  assert.match(done.items[0].reading, /FR 2/);
});
