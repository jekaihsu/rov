// S2 helpers: work queue, cable tube tiers, idle cover, and world-build queue wiring.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const require = createRequire(import.meta.url);
const viewer = new URL('../viewer/', import.meta.url);

const {cableTubeOptions, cableTubeHz, createCableTubeGate} = await import(
  pathToFileURL(require.resolve('../viewer/cable_quality.js')).href);
const {createWorkQueue} = await import(
  pathToFileURL(require.resolve('../viewer/work_queue.js')).href);
const {createWorldBuildQueue} = await import(
  pathToFileURL(require.resolve('../viewer/world_build_queue.js')).href);
const {isIdleCover} = await import(
  pathToFileURL(require.resolve('../viewer/idle_cover.js')).href);

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

// Zero budget: exactly one job per update so a caller can drain a frame at a time.
const blocked = createWorkQueue({budgetMs: 0});
let heavy = 0;
blocked.push(() => { heavy = 1; });
blocked.push(() => { heavy = 2; });
assert.equal(blocked.pending, 2);
assert.equal(blocked.update(), false);
assert.equal(heavy, 1);
assert.equal(blocked.pending, 1);
assert.equal(blocked.update(), true);
assert.equal(heavy, 2);
assert.equal(blocked.pending, 0);

const world = createWorldBuildQueue({budgetMs: 0});
let finished = 0;
const env = {finishHeavy() { finished += 1; }};
world.beginBuild();
world.scheduleFinishHeavy(env, () => { finished += 10; });
assert.equal(world.pending, 1);
assert.equal(world.update(), true);
assert.equal(finished, 11);
// A superseded build must not run the previous finishHeavy.
world.beginBuild();
world.scheduleFinishHeavy(env);
world.beginBuild();
assert.equal(world.pending, 0);

const cable = {
  opts: null,
  setOptions(opts) { this.opts = opts; },
};
let mode = 'performance';
const gate = createCableTubeGate({
  cable,
  getQuality: () => ({mode, hardware: {startsLow: false}}),
  detectHardware: () => ({startsLow: false}),
});
assert.equal(cable.opts.segments, 96);
assert.equal(gate.shouldRebuild(0), true);
assert.equal(gate.shouldRebuild(10), false);
assert.equal(gate.shouldRebuild(60), true);
mode = 'high';
gate.sync();
assert.equal(cable.opts.segments, 240);

assert.equal(isIdleCover({coldOpen: null}), false);
assert.equal(isIdleCover({coldOpen: {active: true}}), false);

// Keep a source-read smoke so CI still notices accidental deletes of the helper files.
for (const name of ['cable_quality.js', 'work_queue.js', 'world_build_queue.js', 'idle_cover.js']) {
  const text = await readFile(new URL(name, viewer), 'utf8');
  assert.ok(text.length > 40, name);
}

console.log('S2 work queue and cable quality helpers passed.');
