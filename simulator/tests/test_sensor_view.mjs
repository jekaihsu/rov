// HUD instrument readings: sensor estimates in the real preset, truth only behind the truthTelemetry item.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createFidelity } from '../viewer/fidelity.js';
import { pilotReadings, showsTruth, formatKnots } from '../viewer/hud/sensor_view.js';

const world = { seabed_depth: 30 };
const sensors = {
  heading: 87.5, depth: 10.04, altitude: 18.2, range: 3.1,
  dvl: { status: 'locked', reason: null, altitude: 18.3, ground_speed_kn: 0.4 }
};
const state = { pos: [1, 2, 10], euler: [0, 0, 90], speed_kn: 1.9, current_kn: 1.5, sensors };

test('truthTelemetry is registered, off in real and on in assisted', function () {
  assert.equal(createFidelity({}).get('truthTelemetry'), false);
  assert.equal(createFidelity({ search: '?fidelity=assisted' }).get('truthTelemetry'), true);
  const real = createFidelity({});
  real.set('truthTelemetry', true);
  assert.equal(real.exceeds('truthTelemetry'), true);
  assert.equal(real.preset, 'custom');
});

test('real preset shows sensor estimates and no water current', function () {
  const reading = pilotReadings(state, world, createFidelity({}));
  assert.equal(reading.truth, false);
  assert.equal(reading.heading, 87.5);
  assert.equal(reading.depth, 10.04);
  assert.equal(reading.altitude, 18.2);
  assert.equal(reading.speedKn, 0.4);
  assert.equal(reading.currentKn, null);
  assert.equal(reading.range, 3.1);
  assert.equal(formatKnots(reading.currentKn), '—');
});

test('lost bottom lock blanks ground speed and far echoes are not shown', function () {
  const lost = { ...sensors, range: 14, altitude: null, dvl: { status: 'lost', reason: 'too_high', ground_speed_kn: null } };
  const reading = pilotReadings({ ...state, sensors: lost }, world, createFidelity({}));
  assert.equal(reading.speedKn, null);
  assert.equal(reading.altitude, null);
  assert.equal(reading.range, null);
  assert.equal(reading.dvlLost, true);
  assert.equal(formatKnots(reading.speedKn), '—');
});

test('assisted preset and old servers keep the truth presentation', function () {
  const assisted = pilotReadings(state, world, createFidelity({ search: '?fidelity=assisted' }));
  assert.equal(assisted.truth, true);
  assert.equal(assisted.altitude, 20);
  assert.equal(assisted.speedKn, 1.9);
  assert.equal(assisted.currentKn, 1.5);
  assert.equal(assisted.range, undefined);
  const legacy = { ...state };
  delete legacy.sensors;
  assert.equal(showsTruth(legacy, createFidelity({})), true);
  assert.equal(pilotReadings(legacy, world, createFidelity({})).heading, 90);
});

test('attitude instruments select estimated roll and pitch and accept older frames', function () {
  const measured = { ...state, sensors: { ...sensors, roll: -1.2, pitch: 3.4 } };
  assert.deepEqual(pilotReadings(measured, world, createFidelity({})).attitude, [-1.2, 3.4, 87.5]);
  assert.deepEqual(pilotReadings(state, world, createFidelity({})).attitude, [0, 0, 87.5]);
});
