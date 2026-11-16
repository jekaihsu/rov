// PlayStation pads without the standard mapping, database hat/trigger decoding and family captions.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {normalize} from '../viewer/input/devices.js';
import {hatFromAxis, normalizePlayStation, sonyLayout, triggerFromAxis} from '../viewer/input/playstation.js';
import {deviceFamily, padNames} from '../viewer/input/glyphs.js';
import {createResolver, menuPadBindings, migrateBindings, padLabel} from '../viewer/input/bindings.js';

const database = JSON.parse(
  readFileSync(new URL('../viewer/input/controller-db.json', import.meta.url), 'utf8')
);
const HAT_RELEASED = 9 / 7;
// Hat axis values Chromium reports on Windows: logical 0..7 clockwise from up, scaled over 0..7 to -1..1.
const HAT = {up: -1, right: -1 + 4 / 7, down: -1 + 8 / 7, left: -1 + 12 / 7};

function fakePad({id, mapping = '', axes, buttons}) {
  return {
    id,
    index: 0,
    connected: true,
    mapping,
    axes,
    buttons: buttons.map(function asButton(value) {
      return {pressed: value > 0.5, touched: value > 0, value};
    }),
  };
}

// Windows/macOS HID order: □ ✕ ○ △ L1 R1 L2 R2 Share Options L3 R3 PS touchpad; axes LX LY RX L2 R2 RY … hat@9.
function hidPad({buttons = {}, axes = {}} = {}) {
  const raw = Array(14).fill(0);
  for (const [index, value] of Object.entries(buttons)) raw[index] = value;
  const values = [0, 0, 0, -1, -1, 0, 0, 0, 0, HAT_RELEASED];
  for (const [index, value] of Object.entries(axes)) values[index] = value;
  return fakePad({id: 'Wireless Controller (Vendor: 054c Product: 0ce6)', axes: values, buttons: raw});
}

// Linux evdev order: ✕ ○ △ □ L1 R1 L2 R2 Share Options PS L3 R3; axes LX LY L2 RX RY R2 hatX hatY.
function evdevPad({buttons = {}, axes = {}} = {}) {
  const raw = Array(13).fill(0);
  for (const [index, value] of Object.entries(buttons)) raw[index] = value;
  const values = [0, 0, -1, 0, 0, -1, 0, 0];
  for (const [index, value] of Object.entries(axes)) values[index] = value;
  return fakePad({id: '054c-05c4-Sony Computer Entertainment Wireless Controller', axes: values, buttons: raw});
}

test('the layout follows the id format, and only for the known Sony products', () => {
  assert.equal(sonyLayout('Wireless Controller (Vendor: 054c Product: 09cc)'), 'hid');
  assert.equal(sonyLayout('054c-0ce6-Sony Interactive Entertainment Wireless Controller'), 'evdev');
  assert.equal(sonyLayout('Wireless Controller (Vendor: 054c Product: 0268)'), null, 'DualShock 3 is not covered');
  assert.equal(sonyLayout('Xbox 360 Controller (Vendor: 045e Product: 028e)'), null);
  const standard = {...hidPad(), mapping: 'standard'};
  assert.equal(normalizePlayStation(standard), null, 'a standard pad is left alone');
});

test('hat axis decodes the eight Windows positions and treats released and no-data as neutral', () => {
  assert.deepEqual(hatFromAxis(HAT.up), {up: true, right: false, down: false, left: false});
  assert.deepEqual(hatFromAxis(HAT.right), {up: false, right: true, down: false, left: false});
  assert.deepEqual(hatFromAxis(HAT.down), {up: false, right: false, down: true, left: false});
  assert.deepEqual(hatFromAxis(HAT.left), {up: false, right: false, down: false, left: true});
  const upRight = hatFromAxis(-1 + 2 / 7);
  assert.ok(upRight.up && upRight.right);
  const upLeft = hatFromAxis(1);
  assert.ok(upLeft.up && upLeft.left);
  for (const neutral of [HAT_RELEASED, 0, undefined, NaN]) {
    assert.deepEqual(hatFromAxis(neutral), {up: false, right: false, down: false, left: false});
  }
});

test('full-range trigger axes scale to 0..1; the pre-report zero is released', () => {
  assert.equal(triggerFromAxis(-1), 0);
  assert.equal(triggerFromAxis(1), 1);
  assert.equal(triggerFromAxis(0.5), 0.75);
  assert.equal(triggerFromAxis(0), 0);
  assert.equal(triggerFromAxis(undefined), 0);
});

test('Windows-style raw pad maps faces, triggers, D-pad, PS and touchpad to standard indices', () => {
  const rest = normalize(hidPad(), database);
  assert.equal(rest.known, true);
  assert.equal(rest.buttons.length, 18);
  assert.ok(rest.buttons.every((value) => value === 0), 'released triggers and hat read zero');
  const cross = normalize(hidPad({buttons: {1: 1}}), database);
  assert.equal(cross.buttons[0], 1, '✕ is standard 0');
  const square = normalize(hidPad({buttons: {0: 1}}), database);
  assert.equal(square.buttons[2], 1, '□ is standard 2');
  const options = normalize(hidPad({buttons: {9: 1, 12: 1, 13: 1}}), database);
  assert.equal(options.buttons[9], 1);
  assert.equal(options.buttons[16], 1, 'PS is standard 16');
  assert.equal(options.buttons[17], 1, 'touchpad is 17, as in the standard mapping');
  const triggers = normalize(hidPad({axes: {3: 1, 4: 0.2}}), database);
  assert.equal(triggers.buttons[6], 1);
  assert.ok(Math.abs(triggers.buttons[7] - 0.6) < 1e-9);
  const sticks = normalize(hidPad({axes: {2: 0.4, 5: -0.6}}), database);
  assert.deepEqual(sticks.axes, [0, 0, 0.4, -0.6]);
  const down = normalize(hidPad({axes: {9: HAT.down}}), database);
  assert.equal(down.buttons[13], 1);
  assert.equal(down.buttons[12], 0);
});

test('Linux-style raw pad maps faces, triggers and the hat axis pair', () => {
  const rest = normalize(evdevPad(), database);
  assert.equal(rest.known, true);
  assert.ok(rest.buttons.every((value) => value === 0));
  assert.equal(normalize(evdevPad({buttons: {3: 1}}), database).buttons[2], 1, '□ (evdev 3) is standard 2');
  assert.equal(normalize(evdevPad({buttons: {2: 1}}), database).buttons[3], 1, '△ (evdev 2) is standard 3');
  assert.equal(normalize(evdevPad({buttons: {10: 1}}), database).buttons[16], 1);
  assert.equal(normalize(evdevPad({axes: {5: 1}}), database).buttons[7], 1);
  assert.deepEqual(normalize(evdevPad({axes: {3: 0.5, 4: -0.5}}), database).axes, [0, 0, 0.5, -0.5]);
  const left = normalize(evdevPad({axes: {6: -1}}), database);
  assert.equal(left.buttons[14], 1);
  const up = normalize(evdevPad({axes: {7: -1}}), database);
  assert.equal(up.buttons[12], 1);
});

test('database records decode hats and scale full-range trigger axes', () => {
  const record = {axes: ['a0', 'a1', 'a2', 'a3'],
    buttons: ['b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'a4', 'a5', 'b6', 'b7', 'b8', 'b9', 'h0.1', 'h0.4', 'h0.8', 'h0.2']};
  const db = {'1234:abcd': record};
  const linux = fakePad({id: '1234-abcd-Pad', axes: [0, 0, 0, 0, -1, 1, 1, -1], buttons: Array(10).fill(0)});
  const snapshot = normalize(linux, db);
  assert.equal(snapshot.buttons[6], 0, 'released full-range trigger');
  assert.equal(snapshot.buttons[7], 1);
  assert.equal(snapshot.buttons[12], 1, 'hat y -1 is up');
  assert.equal(snapshot.buttons[15], 1, 'hat x +1 is right');
  const windows = fakePad({id: 'Pad (Vendor: 1234 Product: abcd)', axes: [0, 0, 0, 0, -1, -1, 0, 0, 0, HAT.left],
    buttons: Array(10).fill(0)});
  assert.equal(normalize(windows, db).buttons[14], 1, 'Windows hat axis 9');
  assert.equal(normalize(windows, db).buttons[12], 0);
});

test('Logitech Dual Action is a generic pad; Sony ids are PlayStation with or without a product name', () => {
  assert.equal(deviceFamily('Logitech Logitech Dual Action (Vendor: 046d Product: c216)'), 'generic');
  assert.equal(deviceFamily('Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 09cc)'), 'playstation');
  assert.equal(deviceFamily('054c-0ce6-Sony Interactive Entertainment Wireless Controller'), 'playstation');
  assert.equal(deviceFamily('Wireless Controller'), 'playstation');
  assert.equal(deviceFamily('Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)'), 'xbox');
});

test('PlayStation captions name the shoulders and menu buttons', () => {
  const names = padNames('playstation');
  assert.equal(padLabel('b4', names), 'L1');
  assert.equal(padLabel('b9', names), 'Options');
  assert.equal(padLabel('b0', names), '×');
  assert.equal(padLabel('b4'), 'LB', 'without a family the generic captions stay');
  assert.equal(padNames('generic'), null);
});

test('flight input resolves the fixed menu rows for the deck checklist without leaking into flight', () => {
  const sources = {...menuPadBindings(), ...migrateBindings({}, 2)};
  const resolver = createResolver();
  const buttons = Array(18).fill(0);
  buttons[0] = 1;
  const values = resolver.resolve(sources, {axes: [0, 0, 0, 0], buttons}, new Set(['flight', 'menu']), 0);
  assert.equal(values.accept, 1);
  assert.equal(values.photo, 0, 'the menu owns ✕ while the checklist is open');
  const flight = createResolver().resolve(sources, {axes: [0, 0, 0, 0], buttons}, new Set(['flight']), 0);
  assert.equal(flight.photo, 1, 'with no menu action enabled ✕ is the photo button again');
  assert.equal(flight.accept, undefined);
});
