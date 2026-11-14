// Viewer flow cues: decoding and interpolating the host's state.flow_field grid.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FlowField, decodeFlowGrid, sampleGrid} from '../viewer/flow_field.js';

function packet(seq, f) {
  const size = [3, 2, 2];
  const origin = [10, -5, 4];
  const step = [6, 6, 6];
  const cm_s = [];
  for (let i = 0; i < size[0]; i++) {
    for (let j = 0; j < size[1]; j++) {
      for (let k = 0; k < size[2]; k++) {
        const n = origin[0] + i * step[0];
        const e = origin[1] + j * step[1];
        const d = origin[2] + k * step[2];
        cm_s.push(...f(n, e, d).map((v) => Math.round(v * 100)));
      }
    }
  }
  return {seq, t: 0, origin, step, size, cm_s};
}

const linear = (n, e, d) => [0.01 * n + 0.02 * e, -0.03 * d, 0.005 * n];

test('grid nodes decode exactly and linear fields interpolate exactly', () => {
  const grid = decodeFlowGrid(packet(1, linear));
  assert.deepEqual(sampleGrid(grid, 16, 1, 10).map((v) => Math.round(v * 100)), [18, -30, 8]);
  const mid = sampleGrid(grid, 13, -2, 7);
  const expected = linear(13, -2, 7);
  for (let c = 0; c < 3; c++) assert.ok(Math.abs(mid[c] - expected[c]) < 0.006);
});

test('points outside the grid clamp to the edge', () => {
  const grid = decodeFlowGrid(packet(1, linear));
  assert.deepEqual(sampleGrid(grid, -100, -5, 4), sampleGrid(grid, 10, -5, 4));
  assert.deepEqual(sampleGrid(grid, 100, 100, 100), sampleGrid(grid, 22, 1, 10));
});

test('malformed packets are ignored and missing grids report not ready', () => {
  const field = new FlowField();
  assert.equal(field.ready, false);
  assert.equal(field.sample(0, 0, 0, 0), null);
  field.ingest({seq: 1, size: [2, 2, 2], cm_s: [1, 2, 3]}, 0);
  field.ingest(null, 0);
  assert.equal(field.ready, false);
});

test('new grids blend in over half a second and repeats are ignored', () => {
  const field = new FlowField(500);
  field.ingest(packet(1, () => [1, 0, 0]), 0);
  field.ingest(packet(2, () => [2, 0, 0]), 1000);
  const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
  near(field.sample(12, 0, 5, 1000)[0], 1);
  near(field.sample(12, 0, 5, 1250)[0], 1.5);
  near(field.sample(12, 0, 5, 1600)[0], 2);
  field.ingest(packet(2, () => [9, 0, 0]), 1700);
  near(field.sample(12, 0, 5, 1800)[0], 2);
  assert.deepEqual(field.horizontalBox(), [10, -5, 6, 6, 3, 2]);
});
