// Fake getGamepads matrices: standard pads, database remaps, calibration, glyphs and haptics preference.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {bindingValue} from '../viewer/input/actions.js';
import {deviceKey, normalize, createDevices} from '../viewer/input/devices.js';
import {
  CALIBRATION_STEPS, captureCalibrationStep, buildCustomMapping, isNeutral
} from '../viewer/input/calibrate.js';
import {deviceFamily, faceLabels, glyph} from '../viewer/input/glyphs.js';
import {createFidelity, STORAGE_KEY} from '../viewer/fidelity.js';
import {
  PAD_HAPTICS_ID, padHapticsEnabled, migratePadHapticsFromInput
} from '../viewer/input/haptics_fidelity.js';
import {createHaptics} from '../viewer/input/haptics.js';
import {findCollisions} from '../viewer/input/bindings.js';

const database = JSON.parse(
  readFileSync(new URL('../viewer/input/controller-db.json', import.meta.url), 'utf8')
);

function fakePad({id, mapping = '', axes = [0, 0, 0, 0], buttons = [], index = 0}) {
  return {
    id,
    index,
    connected: true,
    mapping,
    axes,
    buttons: buttons.map(function asButton(value) {
      return {pressed: value > 0.5, touched: value > 0, value};
    })
  };
}

test('binding uniqueness still holds for the default table', () => {
  assert.deepEqual(findCollisions(), []);
});

test('signed and half-axis SDL forms resolve from raw snapshots', () => {
  const snapshot = {axes: [0.2, -0.5, 0, 0, 0.25, 0.9], buttons: [0, 0.8]};
  assert.equal(bindingValue('+a5', snapshot), 0.9);
  assert.equal(bindingValue('-a1', snapshot), 0.5);
  assert.equal(bindingValue('+a1', snapshot), 0, 'positive half-axis ignores the negative half');
  assert.equal(bindingValue('b1~', snapshot), 1);
});

test('standard Xbox-style pad uses positional indices without the database', () => {
  const pad = fakePad({
    id: 'Xbox 360 Controller (STANDARD GAMEPAD Vendor: 045e Product: 028e)',
    mapping: 'standard',
    axes: [0.1, -0.2, 0.3, -0.4],
    buttons: [1, 0, 0, 0, 0, 0, 0.7, 0]
  });
  const snapshot = normalize(pad, database);
  assert.equal(snapshot.known, true);
  assert.equal(snapshot.axes[0], 0.1);
  assert.equal(snapshot.buttons[0], 1);
  assert.equal(snapshot.buttons[6], 0.7);
  assert.equal(deviceFamily(pad.id), 'xbox');
  assert.deepEqual(faceLabels('xbox'), ['A', 'B', 'X', 'Y']);
});

test('PlayStation and Switch families swap face captions for the same positions', () => {
  assert.equal(deviceFamily('DualSense Wireless Controller Vendor: 054c Product: 0ce6'), 'playstation');
  assert.equal(deviceFamily('Pro Controller Vendor: 057e Product: 2009'), 'switch');
  assert.deepEqual(faceLabels('switch'), ['B', 'A', 'Y', 'X']);
  assert.match(glyph(0, 'switch'), /aria-label="B"/);
  assert.match(glyph(0, 'xbox'), /aria-label="A"/);
});

test('non-standard Logitech D-mode uses the vendor database entry', () => {
  const key = '046d:c216';
  assert.ok(database[key], 'F310 D-mode mapping must be in the compact DB');
  const pad = fakePad({
    id: 'Logitech Logitech Dual Action (Vendor: 046d Product: c216)',
    mapping: '',
    axes: [0.5, -0.25, 0.1, 0.2],
    buttons: Array(12).fill(0).map((_, i) => (i === 1 ? 1 : 0))
  });
  assert.equal(deviceKey(pad.id), key);
  const snapshot = normalize(pad, database);
  assert.equal(snapshot.known, true);
  // DB face order for this guid maps standard A from raw b1.
  assert.equal(snapshot.buttons[0], 1);
});

test('unknown HOTAS stays unknown until calibrated into custom storage', () => {
  const pad = fakePad({
    id: 'HOTAS unknown Vendor: 9999 Product: 9999',
    mapping: '',
    axes: [0, 0.1, 0, 0, 0.2, -0.3, 0.4],
    buttons: Array(20).fill(0)
  });
  assert.equal(normalize(pad, database).known, false);
  const values = [];
  for (let step = 0; step < 4; step++) {
    const axes = Array(7).fill(0);
    axes[step] = 0.9;
    values.push(captureCalibrationStep(step, axes, -1));
  }
  for (let button = 0; button < 17; button++) {
    values.push(captureCalibrationStep(4 + button, Array(7).fill(0), button));
  }
  assert.equal(values.length, CALIBRATION_STEPS.length);
  const custom = {[pad.id]: buildCustomMapping(values)};
  const snapshot = normalize(pad, database, custom);
  assert.equal(snapshot.known, true);
  assert.equal(snapshot.axes[0], 0);
});

test('calibration waits for release between steps', () => {
  assert.equal(isNeutral([0, 0, 0], -1), true);
  assert.equal(isNeutral([0.8, 0, 0], -1), false);
  assert.equal(captureCalibrationStep(0, [0.1, 0, 0], -1), null);
  assert.equal(captureCalibrationStep(0, [0.9, 0, 0], -1), 'a0');
  assert.equal(captureCalibrationStep(4, [0, 0], 3), 'b3');
});

test('device poll prefers the pad that moved and survives hot-unplug', () => {
  let pads = [
    fakePad({id: 'a', mapping: 'standard', index: 0}),
    fakePad({id: 'b', mapping: 'standard', index: 1})
  ];
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: {getGamepads: () => pads}
  });
  const devices = createDevices({}, {});
  assert.equal(devices.poll().pad.id, 'a');
  pads[1].axes[0] = 0.8;
  assert.equal(devices.poll().pad.id, 'b');
  pads = [];
  assert.equal(devices.poll().pad, null);
});

test('padHaptics fidelity is preset-neutral and gates the actuator', () => {
  const store = createFidelity({edition: null});
  assert.equal(store.get(PAD_HAPTICS_ID), true);
  assert.equal(padHapticsEnabled(store), true);
  store.set(PAD_HAPTICS_ID, false);
  assert.equal(store.preset, 'real');
  let effect = null;
  const haptics = createHaptics(
    () => ({vibrationActuator: {playEffect: (...args) => { effect = args; }}}),
    {strength: 1},
    store
  );
  haptics.pulse('hard');
  assert.equal(effect, null);
  store.set(PAD_HAPTICS_ID, true);
  haptics.pulse('tension');
  assert.equal(effect[0], 'dual-rumble');
});

test('legacy rov.input.v1 haptics mute migrates into padHaptics once', () => {
  const memory = new Map();
  const storage = {
    getItem(key) { return memory.has(key) ? memory.get(key) : null; },
    setItem(key, value) { memory.set(key, String(value)); },
    removeItem(key) { memory.delete(key); },
  };
  const store = createFidelity({storage, edition: null});
  const settings = {haptics: false, strength: 0.8};
  assert.equal(migratePadHapticsFromInput(settings, store), true);
  assert.equal(Object.prototype.hasOwnProperty.call(settings, 'haptics'), false);
  assert.equal(store.get(PAD_HAPTICS_ID), false);
  assert.equal(migratePadHapticsFromInput(settings, store), false);
  const saved = JSON.parse(storage.getItem(STORAGE_KEY));
  assert.equal(saved.overrides.padHaptics, false);
});
