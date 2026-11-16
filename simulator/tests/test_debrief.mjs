// Debrief event extraction, seek lead and HTML report builders.
import test from 'node:test';
import assert from 'node:assert/strict';
import {extractEventsFromFrames, eventsForRecording, seekTime} from '../viewer/debrief/events.js';
import {SEEK_LEAD_S, STRINGS} from '../viewer/debrief/strings.js';
import {buildDebriefHtml} from '../viewer/debrief/report.js';
import {sensorErrorSummary, studentDisplayTime, VIEW_GOD} from '../viewer/debrief/viewpoint.js';

test('seekTime jumps five seconds before the event', () => {
  assert.equal(seekTime(12), 7);
  assert.equal(seekTime(2), 0);
  assert.equal(SEEK_LEAD_S, 5);
});

test('extractEventsFromFrames marks inject, collision, tether, silt, dvl, comms, objective, penalty', () => {
  const frames = [
    {t: 0, events: [], tether: {warn: false, broken: false, wraps: {}}, silt: 0,
      sensors: {dvl: {status: 'locked'}}, link: {state: 'healthy'},
      score: {objectives: [{label: 'A', done: false}], penalties: []}},
    {t: 10, events: [{t: 10, obstacle: 'brace', severity: 'hard', where: 'nose'}],
      tether: {warn: true, broken: false, wraps: {}, tension_max: 180}, silt: 0.2,
      sensors: {dvl: {status: 'locked'}}, link: {state: 'healthy'},
      score: {objectives: [{label: 'A', done: false}], penalties: []}},
    {t: 16, events: [], tether: {warn: true, broken: false, wraps: {leg: 1}}, silt: 0.9,
      sensors: {dvl: {status: 'lost', reason: 'silt'}}, link: {state: 'lost', cause: 'cable'},
      score: {objectives: [{label: 'A', done: true}],
        penalties: [{t: 15, reason: '碰撞 brace', points: 5}]}},
    {t: 22, events: [], tether: {warn: true, broken: true, wraps: {leg: 1}}, silt: 0.9,
      sensors: {dvl: {status: 'lost'}}, link: {state: 'lost'},
      score: {objectives: [{label: 'A', done: true}], penalties: []}},
  ];
  const kinds = extractEventsFromFrames(frames, [{kind: 'current', start: 4}]).map((e) => e.kind);
  for (const needed of ['instructor_inject', 'collision', 'tether_warn', 'tether_snag', 'tether_break',
    'silt_whiteout', 'dvl_lost', 'comms_loss', 'objective_done', 'penalty']) {
    assert.ok(kinds.includes(needed), needed);
  }
});

test('legacy recording without sensors still yields collisions and prefers stored debrief.events', () => {
  const recording = {
    clips: [{frames: [
      {t: 0, events: [], tether: {warn: false, broken: false, wraps: {}}, silt: 0,
        score: {objectives: [], penalties: []}},
      {t: 3, events: [{t: 3, obstacle: 'rock', severity: 'touch', where: 'aft'}],
        tether: {warn: false, broken: false, wraps: {}}, silt: 0,
        score: {objectives: [], penalties: []}},
    ]}],
  };
  assert.equal(eventsForRecording(recording)[0].kind, 'collision');
  recording.debrief = {events: [{kind: 'penalty', t: 1, detail: 'manual'}]};
  assert.equal(eventsForRecording(recording)[0].kind, 'penalty');
});

test('studentDisplayTime applies base video delay plus recorded link lag', () => {
  assert.equal(studentDisplayTime(10, {link: {video_lag_s: 2}}), 8);
  assert.equal(studentDisplayTime(10, {link: {video_lag_s: 2}}, 0.15), 7.85);
  assert.equal(studentDisplayTime(10, {link: {}}, 0.15), 9.85);
  assert.equal(studentDisplayTime(1, {link: {video_lag_s: 2}}), 0);
  const summary = sensorErrorSummary({
    pos: [0, 0, 10], euler: [0, 0, 90], current_kn: 1.2,
    sensors: {depth: 10.4, heading: 95, dvl: {status: 'lost'}},
  });
  assert.ok(Math.abs(summary.depthError - 0.4) < 1e-9);
  assert.ok(Math.abs(summary.headingError - 5) < 1e-9);
  assert.equal(summary.dvl, 'lost');
  assert.equal(VIEW_GOD, 'god');
});

test('buildDebriefHtml keeps copy in STRINGS and only banners god-view exports', () => {
  const base = {
    report: {vehicle_id: 'v1', elapsed: 12, completion: {score: 70}},
    events: [{kind: 'collision', t: 8, detail: 'brace'}],
    notes: '停在碰撞前討論纜線',
  };
  const student = buildDebriefHtml(base);
  assert.match(student, new RegExp(STRINGS.title));
  assert.doesNotMatch(student, new RegExp(STRINGS.viewpointBanner));
  assert.match(student, /停在碰撞前討論纜線/);
  assert.match(student, new RegExp(STRINGS.collision));
  const god = buildDebriefHtml({...base, showViewpointBanner: true});
  assert.match(god, new RegExp(STRINGS.viewpointBanner));
});

test('public demo_recording replay skips the debrief panel', async () => {
  const {shouldInstallDebrief} = await import('../viewer/debrief/install.js');
  assert.equal(shouldInstallDebrief('demo_recording.json', {clips: []}), false);
  assert.equal(shouldInstallDebrief('viewer/demo_recording.json', {format: 'qysim-replay-2'}), false);
  assert.equal(shouldInstallDebrief('debrief/fixtures/debrief_smoke.json', {debrief: {}}), true);
  assert.equal(shouldInstallDebrief('local:abc', {debrief: {events: []}}), true);
});
