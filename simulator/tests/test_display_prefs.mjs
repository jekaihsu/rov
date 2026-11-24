// Player display preferences: validated, persisted, presentation only; camera preferences are neutral fidelity
// items that never change the real preset.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  COMFORT_HAPTIC_SCALE,
  DISPLAY_DEFAULTS,
  createDisplayPrefs,
  createFrameGate,
  lengthIn,
  lengthUnit,
  normaliseDisplay,
} from "../viewer/prefs/display.js";
import { createFidelity, fidelityItems } from "../viewer/fidelity.js";
import { EXTERNAL_FOV_ITEM, MOTION_COMFORT_ITEM } from "../viewer/prefs/camera_items.js";
import { hapticMagnitude } from "../viewer/input/haptics.js";

function memoryStorage() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
  };
}

test("display preferences are clamped, validated and persisted", () => {
  assert.deepEqual(normaliseDisplay({ brightness: 9, uiScale: 0.1, colorBlind: "x", units: "furlongs",
    fpsCap: 45, language: "xx", hapticStrength: 4 }), {
    ...DISPLAY_DEFAULTS, brightness: 1.4, uiScale: 0.85, hapticStrength: 1,
  });
  const storage = memoryStorage();
  const prefs = createDisplayPrefs({ storage });
  const seen = [];
  prefs.subscribe((values) => seen.push(values.units));
  prefs.set("units", "imperial");
  prefs.set("fpsCap", 60);
  prefs.set("hapticStrength", 0.4);
  assert.deepEqual(seen, ["imperial", "imperial", "imperial"]);
  const again = createDisplayPrefs({ storage });
  assert.equal(again.get("units"), "imperial");
  assert.equal(again.get("fpsCap"), 60);
  assert.equal(again.get("hapticStrength"), 0.4);
});

test("the language is stored only after the player picks one", function languageStorage() {
  const storage = memoryStorage();
  const prefs = createDisplayPrefs({ storage });
  prefs.set("brightness", 1.1);
  assert.equal("language" in JSON.parse(storage.getItem("rov.display.v1")), false);
  prefs.set("language", "ja");
  prefs.set("brightness", 1.2);
  assert.equal(JSON.parse(storage.getItem("rov.display.v1")).language, "ja");
  const again = createDisplayPrefs({ storage });
  again.set("uiScale", 1.1);
  assert.equal(JSON.parse(storage.getItem("rov.display.v1")).language, "ja");
});

test("units convert lengths for display only", () => {
  assert.equal(lengthIn(10, "metric"), 10);
  assert.ok(Math.abs(lengthIn(10, "imperial") - 32.8084) < 1e-3);
  assert.equal(lengthUnit("imperial"), "ft");
  assert.equal(lengthUnit("metric"), "m");
});

test("the frame cap skips frames that come too early and never with no cap", () => {
  let cap = 30;
  const skip = createFrameGate(() => cap);
  const drawn = [];
  for (let now = 0; now <= 1000; now += 1000 / 60) if (!skip(now)) drawn.push(now);
  assert.ok(drawn.length >= 30 && drawn.length <= 32, drawn.length);
  cap = 0;
  assert.equal(skip(1001), false);
  assert.equal(skip(1002), false);
});

test("camera preferences are neutral fidelity items that do not change the real preset", () => {
  const ids = fidelityItems().map((item) => item.id);
  assert.ok(ids.includes(EXTERNAL_FOV_ITEM) && ids.includes(MOTION_COMFORT_ITEM));
  for (const item of fidelityItems().filter((entry) => [EXTERNAL_FOV_ITEM, MOTION_COMFORT_ITEM].includes(entry.id))) {
    assert.equal(item.presetNeutral, true, item.id);
    assert.equal(item.exceedsReal, false, item.id);
  }
  const fidelity = createFidelity({ storage: memoryStorage() });
  fidelity.set(EXTERNAL_FOV_ITEM, 75);
  fidelity.set(MOTION_COMFORT_ITEM, true);
  assert.equal(fidelity.preset, "real", "a preference change stays in the real preset");
});

test("the onboard camera keeps the real lens whatever the FOV preference", async () => {
  const rig = await readFile(new URL("../viewer/camera_rig.js", import.meta.url), "utf8");
  assert.match(rig, /mode === 'onboard' \? 70 : fidelity\.get\('externalFov'\)/);
  assert.match(rig, /comfort/);
});

test("motion comfort scales pad vibration without clearing the stored strength", () => {
  const storage = memoryStorage();
  const prefs = createDisplayPrefs({ storage });
  prefs.set("hapticStrength", 0.8);
  const fidelity = createFidelity({ storage: memoryStorage() });
  assert.equal(hapticMagnitude({ strength: 0.8 }, fidelity, prefs), 0.8);
  fidelity.set(MOTION_COMFORT_ITEM, true);
  assert.ok(Math.abs(hapticMagnitude({ strength: 0.8 }, fidelity, prefs) - 0.8 * COMFORT_HAPTIC_SCALE) < 1e-9);
  assert.equal(fidelity.preset, "real");
});
