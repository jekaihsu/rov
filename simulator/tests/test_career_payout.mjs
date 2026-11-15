// Deliverable tracking and payout of YX work orders (viewer/career/deliverables.js, scoring.js, settle.js):
// photos need the target in frame, measurements need the equipment, the score follows the checklist minus
// penalties, pay is base × quality − penalties, a partial hand-in pays a share and nothing locks progress.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {careerDataFrom} from '../viewer/career/data.js';
import {createTracker, photoCheck} from '../viewer/career/deliverables.js';
import {contractById} from '../viewer/career/rules.js';
import {defaultSave} from '../viewer/career/save.js';
import {QUALITY, REPEAT_RATE, payout, scoreDive} from '../viewer/career/scoring.js';
import {settleDive} from '../viewer/career/settle.js';

const CAREER = new URL('../viewer/career/', import.meta.url);
async function json(name) {
  return JSON.parse(await readFile(new URL(name, CAREER), 'utf8'));
}
async function careerData() {
  return careerDataFrom({contractsFile: await json('contracts.json'), licencesFile: await json('licences.json'),
    equipmentFile: await json('equipment.json')});
}

const CONTRACT = {
  id: 'test', pay: 10000, reputation: 10, client: 'harbor', partial: 0.5, title: 'test', scenario: 'harbor_inspection',
  deliverables: [
    {id: 'unlock', kind: 'state', label: 'unlock', condition: {path: 'locked', op: 'eq', value: false}},
    {id: 'pile', kind: 'photo', label: 'pile', point: [10, 0, 5], standoff: [1, 4]},
    {id: 'loto', kind: 'confirm', label: 'LOTO'},
    {id: 'prop', kind: 'photo', label: 'prop', point: [0, 10, 5], standoff: [1, 4], after: 'loto'},
    {id: 'growth', kind: 'measure', label: 'growth', point: [10, 0, 8], standoff: [0.5, 1.5], hold_s: 2,
      equipment: 'laser_scaler', reading: '5 cm', required: false},
    {id: 'home', kind: 'surface', label: 'home', point: [0, 0, 0.5], radius: 2},
  ],
  hazards: [{id: 'prop_zone', label: 'LOTO 前接近螺槳', point: [0, 10, 5], radius: 2, until: 'loto', points: 25}],
};

function state(pos, heading = 0, extra = {}) {
  return {t: 0, pos, euler: [0, 0, heading], vel: [0, 0, 0], locked: false, events: [], tether: {warn: false}, ...extra};
}

test('a photo counts only when the target is in frame, at the right distance and visible', () => {
  const item = CONTRACT.deliverables[1];
  assert.equal(photoCheck(item, state([7, 0, 5], 0)).ok, true);
  assert.equal(photoCheck(item, state([7, 0, 5], 180)).reason, 'offFrame');
  assert.equal(photoCheck(item, state([2, 0, 5], 0)).reason, 'tooFar');
  assert.equal(photoCheck(item, state([9.5, 0, 5], 0)).reason, 'tooClose');
  assert.equal(photoCheck(item, state([7, 0, 5], 0), {visibility: 1}).reason, 'murky');
  assert.equal(photoCheck(item, state([7, 0, 5], 0), {view: 'chase'}).reason, 'offboard');
});

test('the tracker follows the checklist, order, equipment and hazards', () => {
  const tracker = createTracker(CONTRACT, {owned: []});
  tracker.observe(state([0, 0, 3]), 0.1);
  assert.equal(tracker.snapshot().items.find((item) => item.id === 'unlock').done, true);
  tracker.observe(state([0, 9, 5], 90), 0.1);
  assert.equal(tracker.photo(state([0, 7, 5], 90)).accepted, null, 'prop photo waits for LOTO');
  assert.deepEqual(tracker.snapshot().penalties.map((entry) => entry.kind), ['safety']);
  assert.equal(tracker.confirm('loto'), true);
  assert.equal(tracker.photo(state([0, 7, 5], 90)).accepted, 'prop');
  assert.equal(tracker.photo(state([7, 0, 5], 0)).accepted, 'pile');
  for (let i = 0; i < 40; i++) tracker.observe(state([9, 0, 8], 0), 0.1);
  const growth = tracker.snapshot().items.find((item) => item.id === 'growth');
  assert.equal(growth.done, false, 'no laser scaler, no measurement');
  assert.match(growth.note, /laser_scaler/);
  tracker.observe(state([0, 0, 0.6]), 0.1);
  const snap = tracker.snapshot();
  assert.equal(snap.complete, true);
  assert.equal(snap.requiredDone, snap.requiredTotal);
  assert.equal(snap.done, 5);
});

test('with the equipment a measurement fills over its hold time and shows the reading', () => {
  const tracker = createTracker(CONTRACT, {owned: ['laser_scaler']});
  tracker.observe(state([9, 0, 8], 0), 0);
  for (let i = 0; i < 25; i++) tracker.observe(state([9, 0, 8], 0), 0.1);
  const growth = tracker.snapshot().items.find((item) => item.id === 'growth');
  assert.equal(growth.done, true);
  assert.equal(growth.reading, '5 cm');
});

test('contacts and tether overloads already on screen when the dive starts are not charged', () => {
  const tracker = createTracker(CONTRACT);
  const old = {t: 1, obstacle: 'pile', severity: 'hard'};
  tracker.observe(state([0, 0, 3], 0, {events: [old], tether: {warn: true}}), 0.1);
  assert.equal(tracker.snapshot().penalties.length, 0);
  const fresh = {t: 5, obstacle: 'pile', severity: 'touch'};
  tracker.observe(state([0, 0, 3], 0, {events: [old, fresh], tether: {warn: false}}), 0.1);
  tracker.observe(state([0, 0, 3], 0, {events: [old, fresh], tether: {warn: true, wraps: {Pile: 1.2}}}), 0.1);
  assert.deepEqual(tracker.snapshot().penalties.map((entry) => entry.points), [5, 10, 10]);
});

function snapshot(overrides = {}) {
  return {items: [], done: 6, total: 6, requiredDone: 5, requiredTotal: 5, complete: true, penalties: [],
    tetherBroken: false, ...overrides};
}

test('score and medal follow the delivered share minus penalty points', () => {
  assert.deepEqual(scoreDive(snapshot()), {score: 100, medal: 'gold', complete: true, points: 0});
  assert.equal(scoreDive(snapshot({done: 5})).medal, 'silver');
  const hit = scoreDive(snapshot({penalties: [{points: 15}, {points: 30}]}));
  assert.equal(hit.score, 55);
  assert.equal(hit.medal, 'bronze');
  assert.equal(scoreDive(snapshot({complete: false})).medal, 'none');
});

test('pay is base × quality minus itemised penalties, with a floor', () => {
  const gold = payout(CONTRACT, snapshot());
  assert.equal(gold.outcome, 'complete');
  assert.equal(gold.net, 10000 * QUALITY.gold);
  const dented = payout(CONTRACT, snapshot({penalties: [{label: 'hit', points: 15}]}));
  assert.equal(dented.medal, 'silver');
  assert.equal(dented.gross, 11500);
  assert.deepEqual(dented.penalties, [{label: 'hit', points: 15, amount: 1500}]);
  assert.equal(dented.net, 10000);
  const wrecked = payout(CONTRACT, snapshot({penalties: [{label: 'x', points: 95}]}));
  assert.equal(wrecked.net, Math.round(wrecked.gross * 0.25 / 10) * 10);
  assert.equal(payout(CONTRACT, snapshot(), {repeat: true}).base, 10000 * REPEAT_RATE);
});

test('handing in early pays a share when enough is delivered, otherwise nothing', () => {
  const partial = payout(CONTRACT, snapshot({complete: false, requiredDone: 3, done: 3}), {submitted: true});
  assert.equal(partial.outcome, 'partial');
  assert.equal(partial.net, 2400);
  assert.equal(partial.medal, 'none');
  const aborted = payout(CONTRACT, snapshot({complete: false, requiredDone: 1, done: 1}), {submitted: true});
  assert.equal(aborted.outcome, 'aborted');
  assert.equal(aborted.net, 0);
  const lost = payout(CONTRACT, snapshot({tetherBroken: true}), {submitted: true});
  assert.equal(lost.outcome, 'aborted');
});

test('settling a dive pays, logs hours apart, records the medal and lists newly opened work', async () => {
  const data = await careerData();
  const save = defaultSave();
  const contract = contractById(data, 'p1_pool_checkout');
  const {summary} = settleDive(save, data, contract, {snapshot: snapshot({done: 7, total: 7, requiredDone: 6,
    requiredTotal: 6}), real_s: 400, assisted_s: 200, duration_s: 600, vehicle: 'x1', block: 1});
  assert.equal(summary.pay.outcome, 'complete');
  assert.equal(save.money, summary.pay.net);
  assert.equal(save.hours.real_s, 400);
  assert.equal(save.hours.assisted_s, 200);
  assert.equal(save.contracts.p1_pool_checkout.completed, 1);
  assert.equal(save.contracts.p1_pool_checkout.medal, 'gold');
  assert.ok(summary.reputation.delta > 0);
  assert.ok(summary.unlocks.contracts.some((entry) => entry.id === 'p2_open_water'));
  assert.equal(save.logbook.at(-1).outcome, 'complete');
  const again = settleDive(save, data, contract, {snapshot: snapshot({complete: false, requiredDone: 0, done: 0}),
    submitted: true, real_s: 60, assisted_s: 0, duration_s: 60});
  assert.equal(again.summary.pay.outcome, 'aborted');
  assert.ok(again.summary.reputation.delta <= 0);
  assert.equal(save.contracts.p1_pool_checkout.attempts, 2);
  assert.equal(save.contracts.p1_pool_checkout.medal, 'gold', 'a bad run never lowers the best medal');
});
