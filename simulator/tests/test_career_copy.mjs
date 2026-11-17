// career.copy mirrors the Traditional Chinese text of contracts.json, licences.json and equipment.json under
// stable ids (career.copy.<bucket>.<id>.<field>). localize_data.js prefers the copy over the JSON, so a copy that
// drifts from the JSON would silently show stale text even in Traditional Chinese. This test keeps them in step.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { COPY } from '../viewer/career/copy.js';

async function career(name) {
  return JSON.parse(await readFile(new URL(`../viewer/career/${name}.json`, import.meta.url), 'utf8'));
}

function same(actual, expected, path) {
  if (expected == null) return;
  assert.equal(actual, expected, `career.copy.${path} differs from the data file`);
}

test('career.copy clients, jobs and chapters match contracts.json', async () => {
  const data = await career('contracts');
  for (const [id, client] of Object.entries(data.clients)) same(COPY.clients[id]?.label, client.label, `clients.${id}`);
  for (const [id, label] of Object.entries(data.jobs)) same(COPY.jobs[id], label, `jobs.${id}`);
  for (const chapter of data.chapters) {
    same(COPY.chapters[chapter.id]?.title, chapter.title, `chapters.${chapter.id}.title`);
    same(COPY.chapters[chapter.id]?.summary, chapter.summary, `chapters.${chapter.id}.summary`);
  }
});

test('career.copy contracts match contracts.json', async () => {
  const data = await career('contracts');
  for (const contract of data.contracts) {
    const copy = COPY.contracts[contract.id];
    assert.ok(copy, `career.copy.contracts.${contract.id} is missing`);
    for (const field of ['title', 'clientName', 'summary', 'brief']) {
      same(copy[field], contract[field], `contracts.${contract.id}.${field}`);
    }
    for (const field of ['speaker', 'start', 'done', 'partial']) {
      same(copy.radio?.[field], contract.radio?.[field], `contracts.${contract.id}.radio.${field}`);
    }
    for (const entry of contract.deliverables || []) {
      same(copy.deliverables?.[entry.id], entry.label, `contracts.${contract.id}.deliverables.${entry.id}`);
    }
  }
});

test('career.copy grades, endorsements and items match licences.json and equipment.json', async () => {
  const licences = await career('licences');
  for (const grade of licences.grades) {
    for (const field of ['label', 'short', 'opens']) {
      same(COPY.grades[grade.id]?.[field], grade[field], `grades.${grade.id}.${field}`);
    }
  }
  for (const entry of licences.endorsements) {
    same(COPY.endorsements[entry.id]?.label, entry.label, `endorsements.${entry.id}.label`);
  }
  const equipment = await career('equipment');
  for (const item of equipment.items) {
    for (const field of ['label', 'use', 'unlocks']) {
      same(COPY.items[item.id]?.[field], item[field], `items.${item.id}.${field}`);
    }
  }
});
