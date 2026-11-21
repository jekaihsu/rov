// Net material, batching and visual motion stay inside the authoritative collision envelope.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const {buildStructures} = await import('../viewer/structures.js');
const {updatePenNet} = await import('../viewer/aquaculture.js');

test('alpha net batches across panels and flow displacement is bounded', () => {
  const obstacles = [0, 1].map((i) => ({type: 'box', kind: 'pen_net', name: `net-${i}`,
    center: [24, i * 2, 8], half: [1, .025, 8], yaw_deg: 0}));
  const set = buildStructures({obstacles, seabed_depth: 25}, {detail: 'low'});
  assert.equal(set.group.children.length, 1);
  assert.equal(set.entries.size, 2);
  const mesh = set.group.children[0];
  assert.equal(mesh.material.alphaTest, .35);
  const original = mesh.geometry.attributes.position.array.slice();
  const flow = {ready: true, sample(n, e, d, t, out) { out.splice(0, 3, 20, 20, 0); }};
  updatePenNet(set, flow, 1);
  const moved = mesh.geometry.attributes.position.array;
  assert.ok(moved.some((v, i) => v !== original[i]));
  assert.ok(moved.every((v, i) => Math.abs(v - original[i]) <= .036));
  const strong = moved.reduce((peak, v, i) => Math.max(peak, Math.abs(v - original[i])), 0);
  const steady = speed => ({ready: true, sample(n, e, d, t, out) { out.splice(0, 3, speed, speed, 0); }});
  updatePenNet(set, steady(.2), 1);
  const weak = moved.reduce((peak, v, i) => Math.max(peak, Math.abs(v - original[i])), 0);
  assert.ok(weak > 0 && weak < strong);
  updatePenNet(set, steady(0), 1);
  assert.deepEqual(moved, original);
  updatePenNet(set, flow, 1);
  updatePenNet(set, null, 1);
  assert.deepEqual(moved, original);
  set.dispose();
});
