// Input shaping and mapping regressions, independent of browser globals.
import test from "node:test";
import assert from "node:assert/strict";
import { radial, curve, bindingValue } from "../viewer/input/actions.js";
import { deviceKey, normalize } from "../viewer/input/devices.js";
test("radial deadzone preserves direction and saturates diagonally", () => {
  assert.deepEqual(radial(0.02, 0.03), [0, 0]);
  const [x, y] = radial(1, 1);
  assert.ok(Math.abs(Math.hypot(x, y) - 1) < 1e-10);
  assert.equal(x, y);
});
test("curve preserves neutral, supports inversion and bounds output", () => {
  assert.equal(curve(0), 0);
  assert.equal(curve(0.5, { expo: 1 }), 0.125);
  assert.equal(curve(1, { invert: true }), -1);
  assert.equal(curve(1, { sensitivity: 2 }), 1);
});
test("bindings handle signed axes, trigger buttons and absent HOTAS controls", () => {
  const snapshot = { axes: [0.75], buttons: [0.8, 0.2] };
  assert.equal(bindingValue("-a0", snapshot), -0.75);
  assert.ok(Math.abs(bindingValue(["b0", "b1"], snapshot) - 0.6) < 1e-10);
  assert.equal(bindingValue("b0~", snapshot), 1);
  assert.equal(bindingValue("a50", snapshot), 0);
});
test("standard, database and custom mappings use explicit paths", () => {
  const pad = { id: "Vendor: 1234 Product: abcd", axes: [0.2, 0.4], buttons: [{ value: 1 }] };
  assert.equal(deviceKey(pad.id), "1234:abcd");
  const db = { "1234:abcd": { axes: ["-a1"], buttons: ["b0"] } };
  assert.equal(normalize(pad, db).axes[0], -0.4);
  assert.equal(normalize({ ...pad, mapping: "standard" }, db).axes[0], 0.2);
  assert.equal(normalize({ ...pad, id: "unknown" }, db).known, false);
  assert.equal(normalize(pad, db, { [pad.id]: { axes: ["a0"], buttons: [] } }).axes[0], 0.2);
});
import { createDevices } from "../viewer/input/devices.js";
import { createHaptics } from "../viewer/input/haptics.js";
test("active device follows movement, explicit selection, hot unplug", () => {
  let pads = [0, 1].map((index) => ({
    index,
    id: String(index),
    connected: true,
    mapping: "standard",
    axes: [0, 0, 0, 0],
    buttons: [],
  }));
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { getGamepads: () => pads } });
  const devices = createDevices({}, {});
  assert.equal(devices.poll().pad.index, 0);
  pads[1].axes[0] = 0.7;
  assert.equal(devices.poll().pad.index, 1);
  assert.equal(devices.poll("0").pad.index, 0);
  assert.equal(devices.poll("keyboard").pad, null);
  pads = [];
  assert.equal(devices.poll().pad, null);
});
test("haptics ignores unsupported devices and respects strength", async () => {
  createHaptics(() => null, {}).pulse("photo");
  let effect;
  const settings = { strength: 0.5 };
  const fidelity = { get: () => true };
  const haptics = createHaptics(
    () => ({
      vibrationActuator: {
        playEffect: (...args) => {
          effect = args;
        },
      },
    }),
    settings,
    fidelity,
  );
  haptics.pulse("unlock");
  assert.equal(effect[1].strongMagnitude, 0.15);
  fidelity.get = () => false;
  effect = null;
  haptics.pulse("hard");
  assert.equal(effect, null);
});

import { assistFields } from "../viewer/input/actions.js";
import { readHUDButtons } from "../viewer/hud/flight_hud.js";
test("legacy RC omits auxiliary fields until an assist object is advertised", () => {
  const controls = { assist: 2, profile: "normal" };
  for (const state of [null, {}, { assist: null }, { assist: 2 }, { assist: [] }]) {
    assert.deepEqual(assistFields(state, controls), {});
  }
  assert.deepEqual(assistFields({ assist: {} }, controls), controls);
  assert.deepEqual(assistFields({ assist: { level: 1 } }, controls), controls);
});
test("HUD consumes semantic directions without polling a device", () => {
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: {
      getGamepads() {
        throw Error("HUD must not poll");
      },
    },
  });
  assert.deepEqual(readHUDButtons({ up: 1, right: 0.8 }), [true, false, true, false]);
  assert.deepEqual(readHUDButtons(), [false, false, false, false]);
});
