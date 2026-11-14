import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
async function moduleSource(name) {
  const source = (await readFile(new URL(`../viewer/${name}.js`, import.meta.url), 'utf8'))
    .replace("import * as THREE from 'three';", '');
  return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
}
const {StateBuffer, sampleSnapshots, slerp} = await moduleSource('state_buffer');
const {spring} = await moduleSource('camera_rig');
function state(t) {
  return {t, pos: [t, 0, 0], vel: [1, 0, 0], q: [1, 0, 0, 0],
    tether: {nodes: [[t, 0, 0], [0, 0, 0]]}, vehicles: [{id: 'p', pos: [t, 0, 0]}]};
}
test('shared time and quaternion shortest arc', () => {
  const s = sampleSnapshots([state(0), state(1)], .5);
  assert.equal(s.pos[0], .5);
  assert.equal(s.vehicles[0].pos[0], .5);
  assert.equal(s.tether.nodes[0][0], .5);
  assert.deepEqual(slerp([1, 0, 0, 0], [-1, 0, 0, 0], .5), [1, 0, 0, 0]);
  assert.ok(Math.abs(sampleSnapshots([state(0)], 1).pos[0] - .1) < 1e-9);
});
test('jitter, loss, reordering, duplicates and clock convergence', () => {
  const buffer = new StateBuffer();
  let previous = 0;
  for (let i = 0; i < 600; i++) {
    const t = i / 60;
    if (i % 3 === 0 && i % 21 !== 0) {
      buffer.push(state(t), t + 100 + (i % 4) * .002);
      if (i > 6) buffer.push(state(t - .03), t + 100);
    }
    const s = buffer.sample(t + 100);
    if (!s) continue;
    assert.ok(s.pos[0] >= previous - 1e-9);
    assert.ok(s.pos[0] - previous < .08);
    previous = s.pos[0];
  }
  assert.ok(Math.abs(buffer.offset - 100) < .02);
  buffer.push(state(0), 111);
  assert.equal(buffer.frames.length, 1);
});
test('critical spring agrees at 30, 60 and 144 fps', () => {
  const results = [30, 60, 144].map(fps => {
    let x = 0, v = 0;
    for (let i = 0; i < fps; i++) [x, v] = spring(x, v, 1, 8, 1 / fps);
    return x;
  });
  assert.ok(Math.max(...results) - Math.min(...results) < 1e-12);
});
test('long loss, resume and pause never teleport the displayed vehicle', () => {
  const buffer = new StateBuffer();
  let previous = null;
  for (let i = 0; i < 180; i++) {
    const time = i / 60;
    if (i % 3 === 0 && (i < 30 || i > 65)) buffer.push(state(time), time + 20);
    const output = buffer.sample(time + 20, true);
    if (previous) assert.ok(Math.abs(output.pos[0] - previous.pos[0]) <= 8 / 60 + 1e-9);
    previous = output;
  }
  assert.deepEqual(sampleSnapshots([{...state(0), paused: true}], 5).pos, [0, 0, 0]);
});

test('duplicate timestamp carries pause and resume rebases the clock', () => {
  const buffer = new StateBuffer();
  buffer.push(state(0), 10);
  buffer.push({...state(0), paused: true}, 11);
  assert.equal(buffer.sample(12).t, 0);
  buffer.push(state(.01), 13);
  assert.equal(buffer.frames.length, 1);
  assert.ok(Math.abs(buffer.offset - 12.99) < 1e-9);
});
