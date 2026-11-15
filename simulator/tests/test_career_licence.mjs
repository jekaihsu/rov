// Licence progression (viewer/career/settle.js, rules.js, boot.js): an exam passes only at the real preset with a
// complete job, grants the next grade, only real-mode hours open the next exam, and the stashed fidelity settings
// come back after an exam.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {careerDataFrom} from '../viewer/career/data.js';
import {contractById, contractStatus, licenceProgress} from '../viewer/career/rules.js';
import {defaultSave} from '../viewer/career/save.js';
import {settleDive} from '../viewer/career/settle.js';
import {restoreFidelity} from '../viewer/career/boot.js';

const CAREER = new URL('../viewer/career/', import.meta.url);
async function json(name) {
  return JSON.parse(await readFile(new URL(name, CAREER), 'utf8'));
}
async function careerData() {
  return careerDataFrom({contractsFile: await json('contracts.json'), licencesFile: await json('licences.json'),
    equipmentFile: await json('equipment.json')});
}

function done(count = 8) {
  return {items: [], done: count, total: count, requiredDone: count, requiredTotal: count, complete: true,
    penalties: [], tetherBroken: false};
}

function examDive(extra = {}) {
  return {snapshot: done(), real_s: 600, assisted_s: 0, duration_s: 600, vehicle: 'x1', block: 1, examValid: true,
    ...extra};
}

test('the first exam needs the pool checkout and grants 見習駕駛員', async () => {
  const data = await careerData();
  const save = defaultSave();
  const exam = contractById(data, 'p2_open_water');
  assert.equal(contractStatus(exam, save, data).status, 'locked');
  save.contracts.p1_pool_checkout = {completed: 1, attempts: 1, best: 90, medal: 'gold'};
  assert.equal(contractStatus(exam, save, data).available, true);
  const {summary} = settleDive(save, data, exam, examDive());
  assert.equal(summary.exam.passed, true);
  assert.equal(save.licence, 'trainee');
  assert.equal(summary.licence.after, 'trainee');
  assert.ok(summary.unlocks.contracts.some((entry) => entry.id === 'c1_pier_level1'));
  assert.equal(save.logbook.at(-1).examPassed, true);
});

test('an exam flown with anything beyond the real vehicle does not count', async () => {
  const data = await careerData();
  const save = defaultSave();
  const exam = contractById(data, 'p2_open_water');
  const {summary} = settleDive(save, data, exam, examDive({examValid: false, real_s: 300, assisted_s: 300}));
  assert.equal(summary.exam.passed, false);
  assert.match(summary.exam.reason, /超出真機/);
  assert.equal(save.licence, 'none');
  assert.ok(summary.pay.net > 0, 'the job is still paid');
  assert.equal(save.hours.assisted_s, 300);
});

test('an incomplete or low-scoring exam fails and can be retaken', async () => {
  const data = await careerData();
  const save = defaultSave();
  const exam = contractById(data, 'p2_open_water');
  const partial = {...done(), complete: false, requiredDone: 5, done: 5};
  assert.equal(settleDive(save, data, exam, examDive({snapshot: partial, submitted: true})).summary.exam.passed, false);
  const sloppy = {...done(), penalties: [{label: 'x', points: 60}]};
  const result = settleDive(save, data, exam, examDive({snapshot: sloppy})).summary;
  assert.equal(result.exam.passed, false);
  assert.match(result.exam.reason, /銅牌/);
  assert.equal(save.licence, 'none');
  save.contracts.p1_pool_checkout = {completed: 1, attempts: 1, best: 90, medal: 'gold'};
  assert.equal(contractStatus(exam, save, data).available, true, 'never locked out of a retake');
});

test('only real-mode hours count toward the next licence', async () => {
  const data = await careerData();
  const save = {...defaultSave(), licence: 'trainee'};
  save.hours.assisted_s = 10 * 3600;
  let progress = licenceProgress(save, data);
  assert.equal(progress.next.id, 'grade2');
  assert.equal(progress.realHours, 0);
  assert.equal(progress.hoursFraction, 0);
  save.hours.real_s = 0.25 * 3600;
  progress = licenceProgress(save, data);
  assert.equal(progress.hoursFraction, 0.5);
  const grade2 = data.grades.find((grade) => grade.id === 'grade2');
  if (grade2.exam) {
    const exam = contractById(data, grade2.exam);
    const hours = contractStatus(exam, save, data).reasons.find((reason) => reason.kind === 'hours');
    assert.ok(hours, 'the exam waits for real hours');
    save.hours.real_s = 0.5 * 3600;
    assert.equal(contractStatus(exam, save, data).reasons.some((reason) => reason.kind === 'hours'), false);
  }
});

test('the fidelity settings an exam stashed are put back', () => {
  const values = new Map([['rov.fidelity.v1', '{"base":"real"}']]);
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const save = {...defaultSave(), fidelityStash: '{"version":1,"base":"assisted","overrides":{}}'};
  assert.equal(restoreFidelity(save, storage), true);
  assert.equal(values.get('rov.fidelity.v1'), '{"version":1,"base":"assisted","overrides":{}}');
  assert.equal(save.fidelityStash, null);
  assert.equal(restoreFidelity(save, storage), false);
  const none = {...defaultSave(), fidelityStash: ''};
  restoreFidelity(none, storage);
  assert.equal(values.has('rov.fidelity.v1'), false, 'no stored settings before the exam, none after');
});
