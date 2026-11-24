// Chapter 1 beat directors (story/chapter1_model.js): opening, turns, idle nudge, settle, skip.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CHAPTER1_MISSIONS, TIMING, createChapter1Director, enrichTelemetry,
} from '../viewer/story/chapter1_model.js';

const SPOTS = {
  piles: [[0, 8], [4, 10]],
  prop: [0, -6],
  decoy: [6, 4],
  target: [-6, 4],
};

function run(director, from, to, telemetry) {
  const views = [];
  for (let t = from; t <= to + 1e-9; t += 0.1) {
    views.push(director.step(Math.round(t * 10) / 10, telemetry(t)));
  }
  return views;
}

function said(views) {
  return views.flatMap(function lines(view) {
    return view.said.map(function id(entry) {
      return entry.id;
    });
  });
}

function beats(views) {
  return [...new Set(views.map(function beat(view) {
    return view.beat;
  }))];
}

test('all four chapter-1 missions share the opening skeleton', () => {
  for (const missionId of CHAPTER1_MISSIONS) {
    const director = createChapter1Director(missionId, SPOTS);
    const opening = run(director, 0, TIMING.black + TIMING.establish + TIMING.handover + 0.5, () => ({input: 0}));
    assert.deepEqual(beats(opening), ['black', 'establish', 'handover', 'work'], missionId);
    assert.equal(opening[0].black, 1);
    assert.ok(opening[0].letterbox && opening[0].cinematic);
    assert.equal(opening.at(-1).beat, 'work');
    assert.ok(!opening.at(-1).letterbox);
  }
});

test('c1_pier_level2: near pile, measure, murky turn, then settle', () => {
  const director = createChapter1Director('c1_pier_level2', SPOTS);
  run(director, 0, 14, () => ({input: 0, pos: [20, 20]}));
  assert.equal(director.beat, 'work');
  const near = run(director, 14.1, 14.5, () => ({input: 0.4, pos: [0.2, 8.1], nearPile: true}));
  assert.ok(said(near).includes('pier_near'), said(near));
  assert.equal(near.at(-1).beat, 'turnNear');
  run(director, 14.6, 14.6 + TIMING.turnHold + 0.2, () => ({input: 0.2, pos: [0.2, 8.1], nearPile: true}));
  assert.equal(director.beat, 'work');
  const measured = director.step(20, {input: 0.2, measured: true, nearPile: true});
  assert.equal(measured.beat, 'turnMeasured');
  assert.ok(measured.said.some((entry) => entry.id === 'pier_measured'));
  run(director, 20.1, 20 + TIMING.turnHold + 0.3, () => ({input: 0.2, measured: true}));
  const murky = director.step(25, {input: 0.1, murky: true});
  assert.equal(murky.beat, 'turnMurky');
  run(director, 25.1, 25 + TIMING.turnHold + 0.3, () => ({input: 0.2}));
  const done = director.step(30, {input: 0.2, missionDone: true, complete: true});
  assert.equal(done.beat, 'report');
  assert.ok(said([done]).includes('pier_settle_gold') || said([done]).includes('pier_settle_silver'));
  assert.ok(said([done]).includes('pier_report'));
  const closing = run(director, 30.1, 30 + TIMING.report + TIMING.fade + 0.5, () => ({complete: true}));
  assert.ok(closing.at(-1).ended);
  assert.equal(closing.at(-1).beat, 'card');
});

test('idle nudge and work limit still advance the story', () => {
  const director = createChapter1Director('c1_dropped_object', SPOTS);
  run(director, 0, 14, () => ({input: 0}));
  const waiting = run(director, 14.1, 14 + TIMING.workNudge + 1, () => ({input: 0}));
  assert.ok(said(waiting).includes('drop_nudge'), said(waiting));
  const timed = run(director, 15, 15 + TIMING.workLimit + 1, () => ({input: 0}));
  assert.ok(said(timed).includes('drop_timeout'));
  assert.equal(timed.at(-1).beat, 'report');
  assert.ok(timed.at(-1).outcome.partial);
});

test('c1_hull_fouling turns: loto, prop, suction, rated', () => {
  const director = createChapter1Director('c1_hull_fouling', SPOTS);
  run(director, 0, 14, () => ({input: 0}));
  assert.equal(director.step(15, {input: 0.3, lotoDone: true}).beat, 'turnLoto');
  run(director, 15.1, 15 + TIMING.turnHold + 0.3, () => ({input: 0.3, lotoDone: true}));
  assert.equal(director.step(20, {input: 0.3, lotoDone: true, nearProp: true}).beat, 'turnProp');
  run(director, 20.1, 20 + TIMING.turnHold + 0.3, () => ({input: 0.3, lotoDone: true}));
  assert.equal(director.step(25, {input: 0.3, suction: true, flow: true}).beat, 'turnSuction');
  run(director, 25.1, 25 + TIMING.turnHold + 0.3, () => ({input: 0.3}));
  const rated = director.step(30, {input: 0.2, rated: true});
  assert.equal(rated.beat, 'turnRated');
  run(director, 30.1, 30 + TIMING.turnHold + 0.3, () => ({input: 0.2, rated: true}));
  const report = director.step(35, {missionDone: true, complete: true});
  assert.equal(report.beat, 'report');
});

test('c1_signoff_exam abort turn goes to report', () => {
  const director = createChapter1Director('c1_signoff_exam', SPOTS);
  run(director, 0, 14, () => ({input: 0.2}));
  const abort = director.step(15, {input: 0.1, aborted: true});
  assert.equal(abort.beat, 'turnAbort');
  assert.ok(abort.said.some((entry) => entry.id === 'sign_abort'));
  const after = run(director, 15.1, 15 + TIMING.turnHold + 0.4, () => ({aborted: true}));
  assert.equal(after.at(-1).beat, 'report');
  assert.ok(after.at(-1).outcome.aborted);
  assert.equal(after.at(-1).outcome.medal, 'abort');
});

test('enrichTelemetry fills near flags from spots', () => {
  const pier = enrichTelemetry('c1_pier_level2', {pos: [0.1, 8]}, SPOTS);
  assert.equal(pier.nearPile, true);
  const hull = enrichTelemetry('c1_hull_fouling', {pos: [0.2, -6.1], current: 0.5}, SPOTS);
  assert.equal(hull.nearProp, true);
  assert.equal(hull.suction, true);
  const drop = enrichTelemetry('c1_dropped_object', {pos: [-6, 4.1]}, SPOTS);
  assert.equal(drop.atTarget, true);
});

test('skip jumps to the closing card', () => {
  const director = createChapter1Director('c1_pier_level2', SPOTS);
  director.step(0, {});
  const view = director.skip(2);
  assert.equal(view.beat, 'card');
  assert.ok(view.ended && view.outcome.skipped);
});

test('unknown mission id throws', () => {
  assert.throws(() => createChapter1Director('c2_net', SPOTS));
});
