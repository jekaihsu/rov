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

test("Start shares light (tap) and the pause menu (hold); Esc opens the pause menu", () => {
  assert.equal(bindingRow("light").gesture, "tap");
  assert.equal(bindingRow("pause").gesture, "hold");
  assert.equal(bindingRow("pause").pad, bindingRow("light").pad);
  assert.equal(keyRow("Escape", new Set(["flight"])).action, "pause");
  assert.equal(keyRow("Escape", new Set(["flight", "menu"])).action, "back");
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const flight = new Set(["flight"]);
  resolver.resolve(bindings, snapshot([9]), flight, 0);
  assert.equal(resolver.resolve(bindings, snapshot([]), flight, 100).light, 1, "a short press is the light");
  resolver.resolve(bindings, snapshot([9]), flight, 1000);
  const held = resolver.resolve(bindings, snapshot([9]), flight, 1000 + HOLD_MS);
  assert.equal(held.pause, 1);
  assert.equal(resolver.resolve(bindings, snapshot([]), flight, 1010 + HOLD_MS).light, 0, "a long press is not");
});

test("the menu context navigates with pad, stick and keys and owns them over flight", () => {
  const menu = BINDINGS.filter((row) => row.context === "menu").map((row) => row.action);
  for (const action of ["menuUp", "menuDown", "menuLeft", "menuRight", "menuStick", "menuStickX", "menuRotate",
    "accept", "back", "tabPrevious", "tabNext"]) {
    assert.ok(menu.includes(action), action);
  }
  assert.equal(keyRow("ArrowUp", new Set(["flight", "menu"])).action, "menuUp");
  assert.equal(keyRow("ArrowUp", new Set(["flight"])).action, "right_ud");
  assert.equal(keyRow("KeyE", new Set(["flight", "menu"])).action, "tabNext");
  assert.equal("menuRotate" in defaultPadBindings(), false, "menu rows are not rebindable");
  const resolver = createResolver();
  const every = Object.fromEntries(BINDINGS.filter((row) => row.pad).map((row) => [row.action, row.pad]));
  const values = resolver.resolve(every, snapshot([5], [0.8, 0, -0.6, 0]), new Set(["flight", "menu"]), 0);
  assert.equal(values.menuStickX, 0.8);
  assert.equal(values.menuRotate, -0.6);
  assert.equal(values.tabNext, 1);
  assert.equal(values.left_lr, 0, "the menu owns the left stick");
  assert.equal(values.right_wave, 0, "and RB");
});

test("holding Start for the pause menu never toggles the light, even when the menu blocks the pad", () => {
  const resolver = createResolver();
  const bindings = defaultPadBindings();
  const flight = new Set(["flight"]);
  for (let now = 0; now <= HOLD_MS + 40; now += 33) {
    assert.equal(resolver.resolve(bindings, snapshot([9]), flight, now).light, 0);
  }
  resolver.block(snapshot([9]));
  for (let now = HOLD_MS + 80; now < HOLD_MS + 400; now += 33) {
    const values = resolver.resolve(bindings, snapshot(now < HOLD_MS + 200 ? [9] : []), flight, now);
    assert.equal(values.light, 0, `light toggled at ${now} ms`);
  }
});

test("the game keyboard layout drives pilot axes and stays collision free", async () => {
  const { KEYBOARD_LAYOUTS, keyboardRows, keyCollisions } = await import("../viewer/input/bindings.js");
  for (const layout of KEYBOARD_LAYOUTS) assert.deepEqual(findCollisions(keyboardRows(layout)), [], layout);
  const game = keyboardRows("game");
  const flight = new Set(["flight"]);
  assert.equal(keyRow("KeyW", flight, game).action, "surge");
  assert.equal(keyRow("KeyA", flight, game).action, "sway");
  assert.equal(keyRow("Space", flight, game).action, "heave");
  assert.equal(keyRow("KeyC", flight, game).action, "heave");
  assert.equal(keyRow("KeyQ", flight, game).action, "yaw");
  assert.equal(keyRow("KeyT", flight, game).action, "lock");
  assert.equal(keyRow("KeyW", flight).action, "left_ud", "the console layout is unchanged");
  assert.equal(keyRow("Space", flight).action, "lock");
  assert.equal(keyRow("KeyQ", new Set(["flight", "menu"]), game).action, "tabPrevious");
  assert.deepEqual(keyCollisions("game", { photo: ["KeyZ"] }), []);
  assert.deepEqual(keyCollisions("game", { photo: ["KeyW"] })[0].actions.sort(), ["photo", "surge"]);
  assert.equal(keyCollisions("console", { lock: ["Tab"] }).length, 1, "HUD keys cannot be taken");
  assert.equal(keyCollisions("game", { surge: ["KeyW", "KeyW"] }).length, 1, "one key cannot be both directions");
  assert.equal(keyRow("KeyZ", flight, keyboardRows("game", { photo: ["KeyZ"] })).action, "photo");
  assert.ok(!("surge" in defaultPadBindings()), "pilot axes are keyboard only");
});

test("help names stick channels by what they do in the operation mode", async () => {
  const { keyboardRows, pilotAxisKeys, actionKey, channelAxis } = await import("../viewer/input/bindings.js");
  const labels = Object.fromEntries(hintItems({ axes: true }).map((item) => [item.action, item.label]));
  assert.equal(labels.right_ud, "前進／後退");
  assert.equal(labels.left_ud, "低頭／抬頭");
  assert.equal(labels.left_wave, "上升／下潛");
  const drone = Object.fromEntries(hintItems({ axes: true, operationMode: "UAV_USA" }).map((i) => [i.action, i.label]));
  assert.equal(drone.left_ud, "上升／下潛");
  assert.deepEqual(pilotAxisKeys("surge"), ["↑", "↓"]);
  assert.deepEqual(pilotAxisKeys("pitch"), ["S", "W"]);
  assert.deepEqual(pilotAxisKeys("surge", keyboardRows("game")), ["W", "S"]);
  assert.deepEqual(pilotAxisKeys("heave", keyboardRows("game"), "UAV_CHN"), ["Space", "C"]);
  assert.equal(actionKey("lock"), "Space");
  assert.equal(actionKey("lock", keyboardRows("game")), "T");
  assert.deepEqual(channelAxis("left_ud", "ROV_USA"), { axis: "pitch", sign: -1 });
  const game = hintItems({ axes: true, rows: keyboardRows("game") });
  assert.ok(!game.some((item) => item.action === "left_ud" && item.keys.length), "game layout frees the stick keys");
});

test("the operation-mode axis table mirrors qysim/rc.py", async () => {
  const { OPERATION_AXES } = await import("../viewer/input/bindings.js");
  const source = await readFile(new URL("../qysim/rc.py", import.meta.url), "utf8");
  const table = /_MAP = \{([\s\S]*?)\n\}/.exec(source)[1];
  const python = {};
  for (const [, mode, body] of table.matchAll(/"(\w+)": \{([^}]*)\}/g)) {
    python[mode] = {};
    for (const [, axis, channel, sign] of body.matchAll(/"(\w+)": \("(\w+)", (-?1)\)/g)) {
      python[mode][axis] = [channel, Number(sign)];
    }
  }
  assert.deepEqual(OPERATION_AXES, python);
});

test("the keyboard layout is a preset-neutral preference: real console, assisted/standard game", async () => {
  const { createFidelity } = await import("../viewer/fidelity.js");
  await import("../viewer/input/keyboard_layout.js");
  assert.equal(createFidelity({ search: "?fidelity=real" }).get("keyboardLayout"), "console");
  assert.equal(createFidelity({ search: "?fidelity=assisted" }).get("keyboardLayout"), "game");
  assert.equal(createFidelity({ search: "?fidelity=standard" }).get("keyboardLayout"), "game");
  // L3: Steam edition defaults to real (console), not assisted.
  assert.equal(createFidelity({ edition: "steam" }).get("keyboardLayout"), "console");
  const store = createFidelity({ search: "?fidelity=real" });
  store.set("keyboardLayout", "game");
  assert.equal(store.preset, "real", "changing the keyboard layout does not leave the real preset");
});
