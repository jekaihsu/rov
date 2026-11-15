// YX work orders (viewer/career/contracts.json + rules.js): references resolve, the board hides chapters whose
// scene is missing, locks say why, and a contract launch carries its id (and an exam the real preset).
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {careerDataFrom} from '../viewer/career/data.js';
import {
  boardChapters, closeAbandonedDive, contractById, contractStatus, licenceProgress, recommendedContract,
} from '../viewer/career/rules.js';
import {defaultSave} from '../viewer/career/save.js';
import {cleanLaunchUrl} from '../viewer/career/boot.js';
import {launchUrl} from '../viewer/menu/preferences.js';

const CAREER = new URL('../viewer/career/', import.meta.url);

async function json(name) {
  return JSON.parse(await readFile(new URL(name, CAREER), 'utf8'));
}

async function careerData() {
  return careerDataFrom({
    contractsFile: await json('contracts.json'),
    licencesFile: await json('licences.json'),
    equipmentFile: await json('equipment.json'),
  });
}

async function sceneKeys() {
  const scenes = JSON.parse(await readFile(new URL('../viewer/scene_previews.json', import.meta.url), 'utf8'));
  return new Set(scenes.map((scene) => scene.key));
}

test('every reference in the work orders resolves', async () => {
  const data = await careerData();
  const contracts = new Set(data.contracts.map((contract) => contract.id));
  const grades = new Set(data.grades.map((grade) => grade.id));
  const endorsements = new Set(data.endorsements.map((entry) => entry.id));
  const chapters = new Set(data.chapters.map((chapter) => chapter.id));
  const items = new Set(data.items.map((item) => item.id));
  for (const contract of data.contracts) {
    assert.ok(chapters.has(contract.chapter), contract.id);
    assert.ok(data.clients[contract.client], contract.id);
    assert.ok(data.jobs[contract.job], contract.id);
    assert.ok(grades.has(contract.licence), contract.id);
    for (const id of contract.requires || []) assert.ok(contracts.has(id), `${contract.id} requires ${id}`);
    for (const id of contract.equipment || []) assert.ok(items.has(id), `${contract.id} equipment ${id}`);
    if (contract.exam?.grants) assert.ok(grades.has(contract.exam.grants), contract.id);
    if (contract.exam?.endorsement) assert.ok(endorsements.has(contract.exam.endorsement), contract.id);
    const ids = new Set(contract.deliverables.map((entry) => entry.id));
    for (const entry of contract.deliverables) {
      if (entry.after) assert.ok(ids.has(entry.after), `${contract.id}.${entry.id} after`);
      if (entry.equipment) assert.ok(items.has(entry.equipment), `${contract.id}.${entry.id} equipment`);
    }
    for (const hazard of contract.hazards || []) assert.ok(ids.has(hazard.until), `${contract.id} hazard`);
  }
  for (const grade of data.grades) {
    if (grade.exam) assert.equal(contractById(data, grade.exam)?.exam?.grants, grade.id, grade.id);
  }
});

test('a fresh career can take the first work orders and nothing needs equipment it cannot buy', async () => {
  const data = await careerData();
  const save = defaultSave();
  const keys = await sceneKeys();
  const open = boardChapters(data, save, keys).flatMap((chapter) => chapter.contracts)
    .filter((entry) => entry.status.available).map((entry) => entry.contract.id);
  assert.ok(open.includes('p1_pool_checkout'), open.join());
  assert.equal(recommendedContract(data, save, keys).id, 'p1_pool_checkout');
});

test('a chapter whose scene is missing is hidden from the board', async () => {
  const data = await careerData();
  const keys = await sceneKeys();
  keys.delete('aquaculture_pen');
  const shown = boardChapters(data, defaultSave(), keys).map((entry) => entry.chapter.id);
  assert.ok(!shown.includes('ch2'));
  keys.add('aquaculture_pen');
  const save = defaultSave();
  const withScene = boardChapters(data, save, keys).map((entry) => entry.chapter.id);
  assert.equal(withScene.includes('ch2'), data.contracts.some((contract) => contract.chapter === 'ch2'));
});

test('a locked work order lists every reason', async () => {
  const data = await careerData();
  const contract = contractById(data, 'c1_pier_level1');
  const status = contractStatus(contract, defaultSave(), data);
  assert.equal(status.status, 'locked');
  assert.ok(status.reasons.some((reason) => reason.kind === 'licence' && reason.text.includes('見習')));
  const licensed = {...defaultSave(), licence: 'trainee'};
  assert.equal(contractStatus(contract, licensed, data).status, 'open');
});

test('licence progress names the next grade and its real-hour requirement', async () => {
  const data = await careerData();
  const progress = licenceProgress({...defaultSave(), licence: 'trainee'}, data);
  assert.equal(progress.current.id, 'trainee');
  assert.equal(progress.next.id, 'grade2');
  assert.equal(progress.requiredHours, 0.5);
});

test('a dive left without a result is logged as aborted with its hours', () => {
  const save = defaultSave();
  save.activeDive = {id: 'd1', contract: 'p1_pool_checkout', real_s: 120, assisted_s: 30, duration_s: 150,
    deliverables: [], exam: false};
  const line = closeAbandonedDive(save);
  assert.equal(line.outcome, 'aborted');
  assert.equal(save.hours.real_s, 120);
  assert.equal(save.hours.assisted_s, 30);
  assert.equal(save.activeDive, null);
  assert.equal(save.contracts.p1_pool_checkout.attempts, 1);
  assert.equal(closeAbandonedDive(save), null);
});

const CHOICE = {model: 'x1', server: 'ws://127.0.0.1:8765', room: 'training', name: 'pilot', scenario: 'open_water',
  control: 'ROV_USA', pad: 'auto', sticker: 'none', quality: 'auto', mission: 'free_explore', intro: false};

test('a contract launch carries its id; an exam forces the real preset and drops per-item overrides', () => {
  const plain = launchUrl('http://h/?cam=chase&fidelity=assisted', {...CHOICE, contract: 'p1_pool_checkout'});
  assert.equal(plain.searchParams.get('contract'), 'p1_pool_checkout');
  assert.equal(plain.searchParams.get('fidelity'), 'assisted');
  assert.equal(plain.searchParams.has('exam'), false);
  const exam = launchUrl('http://h/?cam=chase&gimbal=1&fidelity=assisted', {...CHOICE, contract: 'x', exam: true});
  assert.equal(exam.searchParams.get('fidelity'), 'real');
  assert.equal(exam.searchParams.get('exam'), '1');
  assert.equal(exam.searchParams.has('cam'), false);
  assert.equal(exam.searchParams.has('gimbal'), false);
  const none = launchUrl('http://h/?contract=old&exam=1', CHOICE);
  assert.equal(none.searchParams.has('contract'), false);
  assert.equal(none.searchParams.has('exam'), false);
});

test('back in the menu the career launch parameters are removed', () => {
  const exam = cleanLaunchUrl('http://h/?contract=x&exam=1&fidelity=real&room=a');
  assert.equal(exam.search, '?room=a');
  const plain = cleanLaunchUrl('http://h/?contract=x&fidelity=assisted');
  assert.equal(plain.search, '?fidelity=assisted');
});
