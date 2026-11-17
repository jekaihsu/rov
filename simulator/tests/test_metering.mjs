// Camera metering target (viewer/fx/metering.js): the GPU adaptation pass runs the same rule. Pins that the
// highlight protection leaves frames without a bright area alone, gives up gain for a sizeable lamp-lit subject in a
// dark frame, and ignores a single bright cell.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {METERING, meterTarget} from '../viewer/fx/metering.js';

const WIDTH = 32;
const HEIGHT = 18;

function weight(x, y) {
  const u = (x + 0.5) / WIDTH - 0.5;
  const v = ((y + 0.5) / HEIGHT - 0.5) * 0.8;
  const r = Math.hypot(u, v) * 1.6;
  const t = Math.min(Math.max((r - 0.15) / 0.6, 0), 1);
  return 1 - 0.7 * t * t * (3 - 2 * t);
}

// A frame of luminance `background` with `bright` luminance inside the centred box covering `share` of the cells.
function frame(background, bright = background, share = 0) {
  const cells = [];
  const half = Math.sqrt(share) / 2;
  for (let y = 0; y < HEIGHT; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const inside = Math.abs((x + 0.5) / WIDTH - 0.5) < half && Math.abs((y + 0.5) / HEIGHT - 0.5) < half;
      cells.push({log: Math.log(inside ? bright : background), weight: weight(x, y)});
    }
  }
  return cells;
}

function partialTarget(average) {
  return METERING.compensation * (Math.log(METERING.key) - average) +
    (1 - METERING.compensation) * Math.log(METERING.reference);
}

test('frames without a bright area keep the partial-compensation target (lamps-off look unchanged)', function () {
  // Metered luminance of the lamps-off review shots is 0.0003-0.014 (docs/design/lamp-exposure/report-*.json).
  for (const luminance of [0.0004, 0.002, 0.007, 0.014]) {
    const result = meterTarget(frame(luminance));
    assert.ok(Math.abs(result.target - partialTarget(Math.log(luminance))) < 1e-9, `uniform ${luminance}`);
    const mottled = meterTarget(frame(luminance, luminance * 2, 0.3));
    assert.ok(Math.abs(mottled.target - partialTarget(mottled.average)) < 1e-9, `mottled ${luminance}`);
  }
});

test('a lamp-lit subject in dark water gives up gain so it lands at the highlight level', function () {
  const water = 0.002;
  const subject = water * 24;
  const plain = meterTarget(frame(water, subject, 0.15), {highlight: 0});
  const protectedTarget = meterTarget(frame(water, subject, 0.15));
  assert.ok(protectedTarget.target < plain.target - Math.log(2), 'at least one stop less gain');
  const exposedSubject = subject * Math.exp(protectedTarget.target);
  assert.ok(Math.abs(exposedSubject - METERING.highlight) / METERING.highlight < 0.15, `subject ${exposedSubject}`);
  assert.ok(subject * Math.exp(plain.target) > 1.0, 'without protection the subject would clip');
});

test('one bright cell (a specular glint) does not move the exposure', function () {
  const cells = frame(0.002);
  cells[9 * WIDTH + 16].log = Math.log(0.002 * 200);
  const result = meterTarget(cells);
  assert.ok(Math.abs(result.target - partialTarget(result.average)) < 1e-9);
});

test('the above-water override can switch the cap off and stays within the gain range', function () {
  const bright = meterTarget(frame(0.5, 5, 0.4), {compensation: 0, reference: 1, highlight: 0});
  assert.equal(bright.target, 0);
  const dark = meterTarget(frame(1e-7));
  assert.ok(Math.abs(dark.target - Math.log(METERING.maximum)) < 1e-9);
  const glare = meterTarget(frame(0.3, 300, 0.5));
  assert.ok(Math.abs(glare.target - Math.log(METERING.minimum)) < 1e-9);
});
