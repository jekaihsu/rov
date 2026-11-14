// The binding table is the only source of default keys; these checks fail when two actions share an input.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  BINDINGS,
  CONTEXTS,
  HOLD_MS,
  bindingRow,
  createResolver,
  defaultPadBindings,
  findCollisions,
  hintItems,
  hintText,
  inputIds,
  keyRow,
  migrateBindings,
} from "../viewer/input/bindings.js";

function snapshot(pressed = [], axes = [0, 0, 0, 0]) {
  const buttons = Array.from({ length: 17 }, (_, index) => (pressed.includes(index) ? 1 : 0));
  return { axes, buttons };
}

test("no two actions share a pad source or key inside one context", () => {
  assert.deepEqual(findCollisions(), []);
  assert.deepEqual(findCollisions(BINDINGS, defaultPadBindings()), []);
  for (const row of BINDINGS) assert.ok(CONTEXTS.includes(row.context), row.action);
  assert.equal(new Set(BINDINGS.map((row) => row.action)).size, BINDINGS.length);
});

test("the collision check reports the defects it exists to prevent", () => {
  const upAndProfile = [
    { action: "profile", context: "flight", pad: "b12" },
    { action: "up", context: "flight", pad: "b12" },
  ];
  assert.deepEqual(findCollisions(upAndProfile), [
    { context: "flight", input: "pad:b12", actions: ["profile", "up"] },
  ]);
  const twoPresses = [
    { action: "mode", context: "flight", pad: "b8" },
    { action: "engineering", context: "flight", pad: "b8", gesture: "hold" },
  ];
  assert.equal(findCollisions(twoPresses).length, 1);
  const sameKey = [
    { action: "assist", context: "flight", keys: ["KeyF"] },
    { action: "paintSpray", context: "flight", keys: ["KeyF"] },
  ];
  assert.equal(findCollisions(sameKey)[0].input, "key:KeyF");
  const rebound = { ...defaultPadBindings(), light: "b0" };
  assert.deepEqual(findCollisions(BINDINGS, rebound)[0].actions.sort(), ["light", "photo"]);
});

test("the audited collisions are separated by context or gesture", () => {
  const flight = BINDINGS.filter((row) => row.context === "flight");
  function users(id) {
    return flight.filter((row) => inputIds(row.pad).includes(id)).map((row) => row.action);
  }
  assert.deepEqual(users("b12"), ["up"]);
  assert.deepEqual(users("b0"), ["photo"]);
  assert.deepEqual(users("b1"), ["record"]);
  assert.deepEqual(users("b8"), ["mode", "engineering"]);
  assert.equal(bindingRow("mode").gesture, "tap");
  assert.equal(bindingRow("engineering").gesture, "hold");
  assert.equal(bindingRow("dialogueAccept").context, "dialogue");
  assert.equal(bindingRow("back").context, "menu");
  assert.equal(bindingRow("paintSpray").context, "tool");
  assert.equal(keyRow("KeyF", new Set(["flight"])).action, "assist");
  assert.equal(keyRow("KeyF", new Set(["flight", "tool"])).action, "paintSpray");
  assert.equal(keyRow("Enter", new Set(["flight"])), null);
  assert.equal(keyRow("Enter", new Set(["flight", "dialogue"])).action, "dialogueAccept");
});

test("a long press opens the drawer without changing the control mode", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const flight = new Set(["flight"]);
  let values = resolver.resolve(bindings, snapshot([8]), flight, 0);
  assert.equal(values.mode, 0);
  assert.equal(values.engineering, 0);
  values = resolver.resolve(bindings, snapshot([8]), flight, HOLD_MS + 10);
  assert.equal(values.engineering, 1);
  assert.equal(values.mode, 0);
  values = resolver.resolve(bindings, snapshot([]), flight, HOLD_MS + 20);
  assert.equal(values.mode, 0);
  assert.equal(values.engineering, 0);
});

test("a short press changes the control mode once, on release", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const flight = new Set(["flight"]);
  assert.equal(resolver.resolve(bindings, snapshot([8]), flight, 0).mode, 0);
  const released = resolver.resolve(bindings, snapshot([]), flight, 120);
  assert.equal(released.mode, 1);
  assert.equal(released.engineering, 0);
  assert.equal(resolver.resolve(bindings, snapshot([]), flight, 140).mode, 0);
});

test("the D-pad only drives peek cards and assist/profile share one stick click", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const flight = new Set(["flight"]);
  const values = resolver.resolve(bindings, snapshot([12]), flight, 0);
  assert.equal(values.up, 1);
  assert.equal(values.profile, 0);
  resolver.resolve(bindings, snapshot([11]), flight, 1000);
  const held = resolver.resolve(bindings, snapshot([11]), flight, 1000 + HOLD_MS);
  assert.equal(held.profile, 1);
  assert.equal(held.assist, 0);
  assert.equal(resolver.resolve(bindings, snapshot([]), flight, 1010 + HOLD_MS).assist, 0);
});

test("confirming dialogue never takes a photo, even when the dialogue closes first", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const talking = new Set(["flight", "dialogue"]);
  const flight = new Set(["flight"]);
  let values = resolver.resolve(bindings, snapshot([0]), talking, 0);
  assert.equal(values.dialogueAccept, 1);
  assert.equal(values.photo, 0);
  values = resolver.resolve(bindings, snapshot([0]), flight, 50);
  assert.equal(values.photo, 0, "the press stays claimed by the dialogue until release");
  resolver.resolve(bindings, snapshot([]), flight, 100);
  assert.equal(resolver.resolve(bindings, snapshot([0]), flight, 150).photo, 1);
});

test("record keeps working in flight and is claimed by the dialogue skip hold", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  assert.equal(resolver.resolve(bindings, snapshot([1]), new Set(["flight"]), 0).record, 1);
  resolver.resolve(bindings, snapshot([]), new Set(["flight"]), 10);
  const talking = new Set(["flight", "dialogue"]);
  let values = resolver.resolve(bindings, snapshot([1]), talking, 20);
  assert.equal(values.record, 0);
  assert.equal(values.dialogueSkip, 0);
  values = resolver.resolve(bindings, snapshot([1]), talking, 20 + HOLD_MS);
  assert.equal(values.dialogueSkip, 1);
  assert.equal(values.record, 0);
});

test("the orbit camera owns the right stick only while its context is active", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const stick = snapshot([], [0, 0, 0.5, 0]);
  const flight = resolver.resolve(bindings, stick, new Set(["flight"]), 0);
  assert.equal(flight.right_lr, 0.5);
  assert.equal(flight.cameraOrbitX, undefined);
  const orbit = resolver.resolve(bindings, stick, new Set(["flight", "orbit"]), 10);
  assert.equal(orbit.right_lr, 0);
  assert.equal(orbit.cameraOrbitX, 0.5);
});

test("buttons held while a panel owns the pad stay blocked until released", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const flight = new Set(["flight"]);
  resolver.block(snapshot([0, 8]));
  let values = resolver.resolve(bindings, snapshot([0, 8]), flight, 0);
  assert.equal(values.photo, 0);
  values = resolver.resolve(bindings, snapshot([]), flight, 100);
  assert.equal(values.mode, 0, "releasing a blocked button is not a tap");
  assert.equal(resolver.resolve(bindings, snapshot([0]), flight, 200).photo, 1);
});

test("stored bindings follow a moved default and keep deliberate choices", () => {
  const old = { profile: "b12", up: "b12", light: "b5", accept: "b0", back: "b1", cameraGimbal: "b4" };
  const migrated = migrateBindings(old, 1);
  assert.equal(migrated.profile, "b11");
  assert.equal(migrated.light, "b5");
  assert.equal(migrated.cameraGimbal, "b4");
  assert.equal("accept" in migrated, false);
  assert.equal("back" in migrated, false);
  assert.equal(migrateBindings({ profile: "b12" }, 2).profile, "b12");
  assert.deepEqual(migrateBindings(undefined), defaultPadBindings());
});

test("displayed hints come from the table and cover the previously undocumented keys", async () => {
  const text = hintText({ axes: true });
  const keys = hintItems({ axes: true }).flatMap((item) => item.keys);
  for (const key of ["F", "G", "B", "[", "]", "Tab", "1", "2", "3", "4", "Space", "H", "L", "V", "M", "P", "R"]) {
    assert.ok(keys.includes(key), `missing ${key}`);
  }
  assert.match(text, /長按 View 工程面板/);
  assert.match(text, /長按 R3 飛行檔位/);
  assert.match(text, /十字鍵上 任務速覽/);
  const html = await readFile(new URL("../viewer/index.html", import.meta.url), "utf8");
  assert.match(html, /<p class="hint keys" id="keyHints"><\/p>/, "index.html must not hard-code key hints");
  const guide = await readFile(new URL("../viewer/pilot_guide.js", import.meta.url), "utf8");
  assert.match(guide, /hintText\(\)/);
  const hud = await readFile(new URL("../viewer/hud/flight_hud.js", import.meta.url), "utf8");
  assert.match(hud, /hintText\(/);
});
