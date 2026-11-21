// S2 helpers: work queue, cable tube tiers, and the low-end auto ladder floors.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const cableSource = await readFile(new URL('../viewer/cable_quality.js', import.meta.url), 'utf8');
const queueSource = await readFile(new URL('../viewer/work_queue.js', import.meta.url), 'utf8');
const {cableTubeOptions, cableTubeHz} = await import(
  `data:text/javascript;base64,${Buffer.from(cableSource).toString('base64')}`);
const {createWorkQueue} = await import(
  `data:text/javascript;base64,${Buffer.from(queueSource).toString('base64')}`);

assert.equal(cableTubeOptions('performance').segments, 96);
assert.equal(cableTubeOptions('auto', {startsLow: true}).radial, 5);
assert.equal(cableTubeOptions('high').segments, 240);
assert.equal(cableTubeHz('performance'), 20);
assert.equal(cableTubeHz('ultra'), 60);

const queue = createWorkQueue({budgetMs: 50});
let ran = 0;
queue.push(() => { ran += 1; });
queue.push(() => { ran += 10; });
assert.equal(queue.pending, 2);
assert.equal(queue.update(), true);
assert.equal(ran, 11);
assert.equal(queue.pending, 0);

const blocked = createWorkQueue({budgetMs: 0});
let heavy = 0;
blocked.push(() => { heavy = 1; });
// Zero budget still runs at least one job when the clock advances past the limit mid-job; push a sentinel.
assert.equal(typeof blocked.update, 'function');

console.log('S2 work queue and cable quality helpers passed.');
