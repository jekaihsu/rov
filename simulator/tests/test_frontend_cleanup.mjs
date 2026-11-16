// Small ownership rules from the integration audit: touch sticks, tether updates, favicon, showcase links.
import test from "node:test";
import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { installTouchSticks } from "../viewer/input/touch_sticks.js";
import { createRenderState } from "../viewer/state_buffer.js";

const VIEWER = new URL("../viewer/", import.meta.url);
async function source(path) {
  return readFile(new URL(path, VIEWER), "utf8");
}

function sticks(coarse) {
  const element = { hidden: true };
  const preference = new EventTarget();
  preference.checked = true;
  const events = new EventTarget();
  installTouchSticks({ element, preference, events, coarse });
  function emit(type, fields) {
    events.dispatchEvent(Object.assign(new Event(type), fields));
  }
  return { element, preference, emit };
}

test("on-screen sticks follow the device in use and the pilot's preference", () => {
  const desktop = sticks(false);
  assert.equal(desktop.element.hidden, true);
  desktop.emit("pointerdown", { pointerType: "mouse" });
  assert.equal(desktop.element.hidden, true);
  desktop.emit("pointerdown", { pointerType: "touch" });
  assert.equal(desktop.element.hidden, false);
  desktop.emit("rov-input-device", { detail: "" });
  assert.equal(desktop.element.hidden, true, "keyboard input hides them");
  desktop.emit("rov-input-device", { detail: "touch" });
  assert.equal(desktop.element.hidden, false);
  desktop.emit("rov-input-device", { detail: "Some gamepad" });
  assert.equal(desktop.element.hidden, true, "gamepad input hides them");
  const phone = sticks(true);
  assert.equal(phone.element.hidden, false);
  phone.preference.checked = false;
  phone.preference.dispatchEvent(new Event("change"));
  assert.equal(phone.element.hidden, true, "the checkbox can switch them off");
  phone.emit("pointerdown", { pointerType: "touch" });
  assert.equal(phone.element.hidden, true);
});

test("only input/touch_sticks.js decides whether the sticks are shown", async () => {
  const hud = await source("hud/hud.css");
  assert.equal(/\.sticks[^{]*\{[^}]*!important/.test(hud), false);
  assert.equal(hud.includes("hud-touch"), false);
  assert.equal((await source("hud/flight_hud.js")).includes("hud-touch"), false);
  assert.equal(/optSticks'\)\.onchange/.test(await source("app.js")), false);
  const input = await source("input/index.js");
  assert.match(input, /installTouchSticks\(/);
  assert.equal(input.includes("#sticks{visibility"), false);
  assert.match(await source("index.html"), /<div class="sticks" id="sticks" hidden>/);
});

test("the tether is updated once per rendered frame, from the render state only", async () => {
  const app = await source("app.js");
  const calls = app.match(/updateTether\(/g) || [];
  assert.equal(calls.length, 1, "app.js defines updateTether and must not call it per network state");
  let updates = 0;
  const rig = createRenderState({
    rovG: { position: {}, quaternion: {} },
    P() {},
    Q() {},
    fleet: { ingest() {} },
    updateTether() {
      updates += 1;
    },
    fidelity: { get: () => 150 },
  });
  for (let i = 0; i < 4; i++) rig.ingest({ t: i * 0.05, pos: [0, 0, 0], q: [1, 0, 0, 0] }, false, 10 + i * 0.05);
  rig.update(null, false, 10.2);
  assert.equal(updates, 1);
});

test("pages declare a favicon that exists", async () => {
  await access(new URL("favicon.svg", VIEWER));
  assert.match(await source("index.html"), /<link rel="icon" type="image\/svg\+xml" href="favicon\.svg">/);
  assert.match(await source("instructor/instructor.html"), /href="\.\.\/favicon\.svg"/);
});

test("links to pages the showcase build skips are hidden in replay", async () => {
  const build = await readFile(new URL("../tools/build_showcase.py", import.meta.url), "utf8");
  const skipped = /SKIP_FILES = \{([^}]*)\}/.exec(build)[1].match(/[\w-]+\.html/g);
  const html = await source("index.html");
  const hud = await source("hud/hud.css");
  for (const page of skipped.filter((name) => name !== "index.html")) {
    for (const link of html.matchAll(new RegExp(`<a [^>]*href="${page}"[^>]*>`, "g"))) {
      const id = /id="(\w+)"/.exec(link[0])?.[1];
      assert.ok(id, `${page} link needs an id`);
      assert.match(hud, new RegExp(`body\\.replaying #${id} \\{ display: none; \\}`));
    }
  }
  assert.match(html, /href="controller-check\.html"/);
});

test("showcase ships korean_castle quality LODs used by scene_models", async () => {
  const build = await readFile(new URL("../tools/build_showcase.py", import.meta.url), "utf8");
  assert.match(build, /korean_castle_lod1\.glb/);
  assert.match(build, /korean_castle_lod2\.glb/);
});
