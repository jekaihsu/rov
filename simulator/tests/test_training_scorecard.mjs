// Score calculation and CSV / HTML export formats for the internal training mode.
import assert from 'node:assert/strict';
import test from 'node:test';
import {createSessionMetrics, observeState, recordFidelityChange, photoQualitySummary}
  from '../viewer/training/metrics.js';
import {
  buildScorecard,
  evaluatePass,
  recordsToCsv,
  CSV_COLUMNS,
} from '../viewer/training/scorecard.js';
import {buildScorecardHtml} from '../viewer/training/export.js';
import {lessonsByGroup, findLesson} from '../viewer/training/catalogue.js';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';

const root = dirname(fileURLToPath(import.meta.url));
const catalogue = JSON.parse(readFileSync(join(root, '../viewer/training/courses.json'), 'utf8'));

test('course map groups match S6 levels', () => {
  const groups = lessonsByGroup(catalogue);
  assert.deepEqual(groups.map((g) => g.id), ['intro', 'operator', 'advanced', 'incident']);
  assert.equal(groups[0].lessons.length, 4);
  assert.equal(groups[1].lessons.length, 4);
  assert.equal(groups[2].lessons.length, 4);
  assert.equal(groups[3].lessons.length, 5);
  assert.ok(groups.every((group) => group.lessons.every((lesson) => lesson.goal && lesson.criteria)));
});

test('metrics track tether contacts, tension, collisions and photo standoff', () => {
  const metrics = createSessionMetrics({lessonId: 'course_b01'});
  observeState(metrics, {
    score: {elapsed: 12, objectives: [{done: true, point: [0, 0, 5]}, {done: false, point: [2, 0, 5]}], current_index: 1},
    tether: {contact_nodes: 2, tension_max: 180, snagged_on: []},
    events: [{severity: 'touch'}, {severity: 'hard'}],
    photos: 0,
    pos: [0, 0, 5],
  });
  observeState(metrics, {
    score: {elapsed: 18, objectives: [{done: true, point: [0, 0, 5]}, {done: false, point: [2, 0, 5]}], current_index: 1},
    tether: {contact_nodes: 2, tension_max: 180, snagged_on: []},
    events: [{severity: 'touch'}, {severity: 'hard'}],
    photos: 1,
    pos: [2.2, 0.1, 5.1],
  });
  observeState(metrics, {
    score: {elapsed: 20, objectives: [{done: true, point: [0, 0, 5]}, {done: true, point: [2, 0, 5]}], current_index: 2, finished: true, score: 90},
    tether: {contact_nodes: 0, tension_max: 40, snagged_on: []},
    events: [{severity: 'touch'}, {severity: 'hard'}],
    photos: 1,
    pos: [2.2, 0.1, 5.1],
  });
  assert.equal(metrics.tetherContactEpisodes, 1);
  assert.equal(metrics.maxTensionN, 180);
  assert.equal(metrics.collisions, 2);
  assert.equal(metrics.photos, 1);
  assert.equal(metrics.procedureInOrder, true);
  const photo = photoQualitySummary(metrics);
  assert.equal(photo.photos, 1);
  assert.ok(photo.meanStandoffM != null);
});

test('leaving real fidelity blocks provisional pass and is recorded', () => {
  const metrics = createSessionMetrics({lessonId: 'course_b02'});
  observeState(metrics, {
    score: {elapsed: 30, finished: true, score: 80, objectives: []},
    tether: {contact_nodes: 0, tension_max: 10, snagged_on: []},
    events: [],
    photos: 0,
  });
  recordFidelityChange(metrics, {preset: 'assisted', assisted: true});
  const lesson = findLesson(catalogue, 'course_b02');
  const verdict = evaluatePass(metrics, lesson);
  assert.equal(verdict.passProvisional, false);
  assert.ok(verdict.reasons.includes('fidelity_not_real'));
  const card = buildScorecard({metrics, lesson, student: '學員甲'});
  assert.equal(card.fidelityLeftReal, true);
  assert.equal(card.assistedUsed, true);
  assert.match(card.passStatus, /暫定/);
});

test('CSV export keeps a stable header and one row per record', () => {
  const metrics = createSessionMetrics({lessonId: 'course_b01'});
  observeState(metrics, {
    score: {elapsed: 5, finished: true, score: 100, objectives: []},
    tether: {contact_nodes: 0, tension_max: 0, snagged_on: []},
    events: [],
    photos: 0,
  });
  const card = buildScorecard({metrics, lesson: findLesson(catalogue, 'course_b01')});
  const csv = recordsToCsv([card]);
  const lines = csv.trim().split('\n');
  assert.equal(lines[0], CSV_COLUMNS.join(','));
  assert.equal(lines.length, 2);
  assert.ok(lines[1].includes('course_b01'));
});

test('scorecard HTML is a single printable page with required fields', () => {
  const metrics = createSessionMetrics({lessonId: 'course_i01'});
  observeState(metrics, {
    score: {elapsed: 40, finished: true, score: 70, objectives: []},
    tether: {contact_nodes: 1, tension_max: 220, snagged_on: ['pile']},
    events: [{severity: 'touch'}],
    photos: 2,
  });
  const card = buildScorecard({metrics, lesson: findLesson(catalogue, 'course_i01'), student: 'JK'});
  const html = buildScorecardHtml(card);
  assert.match(html, /學員成績單/);
  assert.match(html, /@page\{size:A4/);
  assert.match(html, /纜線接觸/);
  assert.match(html, /最大張力/);
  assert.match(html, /碰撞/);
  assert.match(html, /照片/);
  assert.match(html, /程序照順序/);
  assert.match(html, /擬真設定/);
  assert.ok(!html.includes('<script'));
});
