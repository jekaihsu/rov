// Camera auto white balance (viewer/fx/white_balance.js): saturated water is not a white-point candidate, so its
// colour survives; near-neutral lamp-lit subjects are balanced; corrections stay inside the camera's range.
import assert from 'node:assert/strict';
import test from 'node:test';
import {WHITE_BALANCE, gainsFromCast, whiteBalanceGains, whitePointWeight} from '../viewer/fx/white_balance.js';

function frame(parts) {
  // parts: [[rgb, share]]; a 32 x 18 meter with uniform centre weight.
  const cells = [];
  for (const [rgb, share] of parts) {
    for (let i = 0; i < Math.round(576 * share); i++) cells.push({rgb, weight: 1});
  }
  return cells;
}

test('open water of every type keeps its colour (no candidates, no correction)', () => {
  const waters = {
    pen: [0.0008, 0.01, 0.003],          // footage: R/G 0-0.1, B/G 0.25-0.7
    harbour: [0.0045, 0.01, 0.0043],     // grey-green
    reef: [0.0004, 0.01, 0.014],         // blue-cyan
    pool: [0.0025, 0.01, 0.011],
  };
  for (const [name, rgb] of Object.entries(waters)) {
    const gains = whiteBalanceGains(frame([[rgb, 1]]));
    assert.ok(Math.abs(Math.log(gains[0])) < 0.02 && Math.abs(Math.log(gains[2])) < 0.02, `${name} ${gains}`);
  }
});

test('lamp-lit near subjects are balanced towards neutral, water around them is ignored', () => {
  const warm = [0.06, 0.05, 0.038];
  const gains = whiteBalanceGains(frame([[warm, 0.4], [[0.0008, 0.01, 0.003], 0.6]]));
  assert.ok(gains[0] < 0.97 && gains[2] > 1.03, `warm lamp-lit subject cools: ${gains}`);
  const balanced = [warm[0] * gains[0], warm[1], warm[2] * gains[2]];
  assert.ok(Math.abs(Math.log(balanced[0] / balanced[2])) < Math.abs(Math.log(warm[0] / warm[2])));
});

test('a green cast is never turned mauve: the tint correction is small', () => {
  for (const cast of [[-0.3, -0.3], [-0.8, -0.6], [-2.5, -1.2], [-3, 0]]) {
    const gains = gainsFromCast(cast[0], cast[1], 1);
    const tint = (gains[0] + gains[2]) / 2;
    assert.ok(tint <= WHITE_BALANCE.tintLimit + 1e-9, `tint ${tint}`);
    assert.ok(Math.abs(gains[0] - gains[2]) / 2 <= WHITE_BALANCE.temperatureLimit + 1e-9);
  }
  assert.ok(whitePointWeight(0, 0) > 0.99);
  assert.ok(whitePointWeight(-2.3, -1.2) < 0.01, 'green water is not a white-point candidate');
});

test('a dark frame does not drive the balance (cells count by brightness)', () => {
  const gains = whiteBalanceGains(frame([[[0.0001, 0.0001, 0.00008], 0.95], [[0.0008, 0.01, 0.003], 0.05]]));
  assert.ok(gains.every((g) => g > 0.8 && g < 1.25), `${gains}`);
});

test('bright lamp-lit subjects with a daylight cyan cast are warmed; uniform water of that hue is not', () => {
  const pool = [0.0025, 0.01, 0.011];
  const lampLit = [0.05, 0.07, 0.07];
  const lit = whiteBalanceGains(frame([[lampLit, 0.4], [pool, 0.6]]));
  assert.ok(lit[0] > 1.1 && lit[2] < lit[0], `lamp-lit reef sand is balanced warmer: ${lit}`);
  const water = whiteBalanceGains(frame([[[0.004, 0.01, 0.011], 1]]));
  const slight = Math.abs(Math.log(water[0])) < 0.1 && Math.abs(Math.log(water[2])) < 0.1;
  assert.ok(slight, `at most a slight warming: ${water}`);
});
