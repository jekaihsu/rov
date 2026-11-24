// Chapter 2 deliverable kinds: net lap coverage, hole clock/depth reports, dead-fish basket deposits.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  clockBearing, clockDelta, createTracker, reportMatches,
} from '../viewer/career/deliverables.js';

test('clock bearing puts west-side holes near 6 o\'clock', () => {
  assert.ok(clockDelta(clockBearing([6.08, 1.17], [24, 0]), 6) < 0.6);
  assert.equal(clockDelta(1, 12), 1);
  assert.equal(reportMatches({clock: 6, depth: 7}, {clock: 6, depth: 7.5}, {clockTol: 1, depthTol: 2}), true);
  assert.equal(reportMatches({clock: 6, depth: 7}, {clock: 9, depth: 7}, {clockTol: 1, depthTol: 2}), false);
});

test('lap coverage fills sectors around the pen', () => {
  const contract = {
    id: 'lap',
    deliverables: [{
      id: 'ring', kind: 'lap', label: 'ring',
      center: [24, 0, 0], radius_range: [19.2, 22.5], depth_range: [4, 8], sectors: 24,
    }],
  };
  const tracker = createTracker(contract);
  for (let i = 0; i < 24; i += 1) {
    const a = (i + 0.5) * Math.PI * 2 / 24;
    tracker.observe({
      t: i, pos: [24 + 21 * Math.cos(a), 21 * Math.sin(a), 7], euler: [0, 0, 0], vel: [0, 0, 0],
      events: [], tether: {},
    }, 0.1);
  }
  const snap = tracker.snapshot();
  assert.equal(snap.complete, true);
  assert.equal(snap.items[0].done, true);
});

test('a hole report finishes only when clock and depth match truth', () => {
  const contract = {
    id: 'report',
    deliverables: [
      {id: 'photo', kind: 'photo', label: 'photo', point: [6.08, 1.17, 7], standoff: [0.8, 4]},
      {id: 'report', kind: 'report', label: 'report', after: 'photo',
        truth: {clock: 6, depth: 7}, clock_tol: 1, depth_tol: 2},
    ],
  };
  const tracker = createTracker(contract);
  const near = {
    t: 1, pos: [4, 1.17, 7], euler: [0, 0, 0], vel: [0, 0, 0], events: [], tether: {},
  };
  assert.equal(tracker.photo(near).accepted, 'photo');
  assert.equal(tracker.report('report', {clock: 9, depth: 7}).ok, false);
  assert.equal(tracker.snapshot().items.find((item) => item.id === 'report').done, false);
  assert.equal(tracker.report('report', {clock: 6, depth: 7}).ok, true);
  assert.equal(tracker.snapshot().items.find((item) => item.id === 'report').done, true);
});

test('deposit counts released dead fish inside the basket radius', () => {
  const contract = {
    id: 'basket',
    deliverables: [{
      id: 'put', kind: 'deposit', label: 'put', object_kind: 'dead_fish',
      point: [16, 0, 15.5], radius: 1.2, count: 2,
    }],
  };
  const tracker = createTracker(contract);
  tracker.observe({
    t: 1, pos: [16, 0, 14], euler: [0, 0, 0], vel: [0, 0, 0], events: [], tether: {},
    operations: {
      arm: {held: null},
      objects: [
        {id: 'mort-0', kind: 'dead_fish', pos: [16.1, 0.1, 15.5]},
        {id: 'mort-1', kind: 'dead_fish', pos: [16.2, -0.1, 15.4]},
      ],
    },
  }, 0.1);
  assert.equal(tracker.snapshot().complete, true);
});
