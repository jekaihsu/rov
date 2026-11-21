// Career radio line triggers from contracts.json (viewer/career/radio.js).
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {linesFor} from '../viewer/career/radio.js';

const CAREER = new URL('../viewer/career/', import.meta.url);

async function contracts() {
  return JSON.parse(await readFile(new URL('contracts.json', CAREER), 'utf8'));
}

test('linesFor prefers radio.lines and falls back to start/done', () => {
  const radio = {
    speaker: '林岑',
    start: 'legacy start',
    done: 'legacy done',
    lines: [
      {when: 'start', speaker: '林岑', text: '向潮－指揮呼叫 R-1。'},
      {when: 'start', speaker: '周楷', text: '纜手就位。線我看著。'},
      {when: 'cp1', speaker: '周楷', text: '一號過。線還夠。'},
    ],
  };
  assert.deepEqual(linesFor(radio, 'start').map((line) => line.speaker), ['林岑', '周楷']);
  assert.equal(linesFor(radio, 'cp1')[0].text, '一號過。線還夠。');
  assert.deepEqual(linesFor({speaker: '林岑', start: 'only'}, 'start'),
    [{speaker: '林岑', text: 'only'}]);
  assert.deepEqual(linesFor({speaker: '林岑', done: 'ok'}, 'done'),
    [{speaker: '林岑', text: 'ok'}]);
  assert.deepEqual(linesFor(radio, 'missing'), []);
});

test('prologue career radios use bible crew names, not 阿禾', async () => {
  const file = await contracts();
  const prologue = file.contracts.filter((entry) => entry.chapter === 'prologue');
  assert.ok(prologue.length >= 3);
  const blob = JSON.stringify(prologue);
  assert.equal(blob.includes('阿禾'), false);
  assert.equal(blob.includes('林督導'), false);
  assert.ok(blob.includes('林岑'));
  assert.ok(blob.includes('周楷'));
  const p2 = prologue.find((entry) => entry.id === 'p2_open_water');
  assert.ok(linesFor(p2.radio, 'start').some((line) => line.text.includes('浮標')));
  assert.ok(linesFor(p2.radio, 'licence').some((line) => line.speaker === '林岑'));
});
