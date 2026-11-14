// Dialogue confirmation goes through the input layer and is consumed before the flight action on that button.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { createFeatureActions } from "../viewer/input/feature_actions.js";
import { bindingRow, createResolver, defaultPadBindings } from "../viewer/input/bindings.js";

const VIEWER = new URL("../viewer/", import.meta.url);
// The only modules allowed to poll devices: the input layer itself, the pre-game menu (it runs before the
// input layer exists) and the standalone controller diagnostic page.
const DEVICE_READERS = new Set(["input/devices.js", "main_menu.js", "controller-check.js"]);

async function sources(directory = "") {
  const found = [];
  for (const entry of await readdir(new URL(directory, VIEWER), { withFileTypes: true })) {
    const path = directory + entry.name;
    if (entry.isDirectory() && entry.name !== "vendor") found.push(...(await sources(path + "/")));
    else if (entry.name.endsWith(".js")) found.push(path);
  }
  return found;
}

function snapshot(pressed = []) {
  const buttons = Array.from({ length: 17 }, (_, index) => (pressed.includes(index) ? 1 : 0));
  return { axes: [0, 0, 0, 0], buttons };
}

// The same three steps input/index.js runs each sample: active contexts, resolve, feature actions.
function createInputLoop() {
  const bindings = defaultPadBindings();
  const resolver = createResolver();
  const features = createFeatureActions((name, fallback) => bindings[name] ?? fallback);
  const registered = new Map();
  function registerActions(definitions) {
    for (const [name, action] of Object.entries(definitions)) registered.set(name, action);
    features.register(definitions);
  }
  function sample(buttons, now) {
    const active = new Set(["flight"]);
    for (const [name, action] of registered) {
      if (action.enabled?.() !== false) active.add(bindingRow(name).context);
    }
    const values = resolver.resolve(bindings, snapshot(buttons), active, now);
    features.sample(snapshot(buttons), 0.033, values);
    return values;
  }
  return { registerActions, sample };
}

test("only the input layer, the pre-game menu and the diagnostic page poll gamepads", async () => {
  for (const path of await sources()) {
    const text = await readFile(new URL(path, VIEWER), "utf8");
    if (DEVICE_READERS.has(path)) continue;
    assert.equal(text.includes("getGamepads"), false, `${path} must use the input layer`);
  }
});

test("the campaign registers dialogue actions instead of listening for keys itself", async () => {
  const text = await readFile(new URL("story/campaign.js", VIEWER), "utf8");
  assert.match(text, /input\.registerActions\(\{\s*dialogueAccept:/);
  assert.match(text, /dialogueSkip:/);
  assert.equal(/addEventListener\('keydown'/.test(text), false);
});

test("confirming a dialogue advances once and never reaches the photo action", () => {
  const loop = createInputLoop();
  let showing = true;
  let advanced = 0;
  loop.registerActions({
    dialogueAccept: {
      enabled: () => showing,
      run() {
        advanced += 1;
        showing = false;
      },
    },
  });
  let photos = 0;
  let time = 0;
  function frame(buttons) {
    time += 33;
    const values = loop.sample(buttons, time);
    if (values.photo > 0.5) photos += 1;
  }
  frame([]);
  for (let i = 0; i < 10; i++) frame([0]);
  assert.equal(advanced, 1);
  assert.equal(photos, 0, "the held confirm button must not become a photo when the dialogue closes");
  frame([]);
  frame([0]);
  assert.equal(photos, 1, "after release the same button is the photo button again");
  assert.equal(advanced, 1);
});

test("a hidden dialogue leaves the confirm button to flight", () => {
  const loop = createInputLoop();
  let advanced = 0;
  loop.registerActions({
    dialogueAccept: {
      enabled: () => false,
      run() {
        advanced += 1;
      },
    },
  });
  assert.equal(loop.sample([0], 10).photo, 1);
  assert.equal(advanced, 0);
});
