// Real-mode defaults that must agree across modules: the control layout and the age of onboard read-outs.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  CONTROL_LAYOUT_KEY,
  CONTROL_LAYOUTS,
  DEFAULT_CONTROL_LAYOUT,
  controlLayout,
  rememberControlLayout,
  storedControlLayout,
} from "../viewer/control_layout.js";
import { createRenderState } from "../viewer/state_buffer.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

test("menu, drawer and simulator share one default control layout", async () => {
  const engine = await readFile(new URL("../qysim/engine.py", import.meta.url), "utf8");
  assert.equal(/self\.operation_mode = "(\w+)"/.exec(engine)[1], DEFAULT_CONTROL_LAYOUT);
  const html = await readFile(new URL("../viewer/index.html", import.meta.url), "utf8");
  assert.equal(/<select id="opMode">\s*<option>(\w+)<\/option>/.exec(html)[1], DEFAULT_CONTROL_LAYOUT);
  const menu = await readFile(new URL("../viewer/menu/preferences.js", import.meta.url), "utf8");
  assert.match(menu, /control: CONTROL_LAYOUTS\.includes\(requestedControl\) \? requestedControl : controlLayout\(\),/);
  assert.match(menu, /rememberControlLayout\(choice\.control\)/);
  assert.equal(menu.includes("settings.control"), false, "the menu must not keep its own copy");
  const menuSettings = await readFile(new URL("../viewer/menu/launch_settings.js", import.meta.url), "utf8");
  assert.match(menuSettings, /for \(const value of CONTROL_LAYOUTS\) layout\.append/);
  assert.equal(CONTROL_LAYOUTS[0], DEFAULT_CONTROL_LAYOUT, "the menu lists the default first");
  const app = await readFile(new URL("../viewer/app.js", import.meta.url), "utf8");
  assert.match(app, /let launchControl=params\.get\('control'\)\|\|storedControlLayout\(\);/);
  assert.match(app, /rememberControlLayout\(\$\('opMode'\)\.value\)/);
});

test("the control layout is stored in one place and rejects unknown values", () => {
  const storage = memoryStorage();
  assert.equal(storedControlLayout(storage), null);
  assert.equal(controlLayout(storage), DEFAULT_CONTROL_LAYOUT);
  assert.equal(rememberControlLayout("UAV_CHN", storage), true);
  assert.equal(storage.getItem(CONTROL_LAYOUT_KEY), "UAV_CHN");
  assert.equal(controlLayout(storage), "UAV_CHN");
  assert.equal(rememberControlLayout("HELICOPTER", storage), false);
  assert.equal(controlLayout(storage), "UAV_CHN");
  assert.equal(controlLayout(memoryStorage({ [CONTROL_LAYOUT_KEY]: "bogus" })), DEFAULT_CONTROL_LAYOUT);
  assert.equal(controlLayout(null), DEFAULT_CONTROL_LAYOUT);
});

function renderState(delayMs) {
  const rig = createRenderState({
    rovG: { position: {}, quaternion: {} },
    P() {},
    Q() {},
    fleet: { ingest() {} },
    updateTether() {},
    fidelity: { get: () => delayMs },
  });
  for (let i = 0; i <= 10; i++) {
    const t = i * 0.05;
    const frame = { t, pos: [0, 0, t], vel: [0, 0, 1], q: [1, 0, 0, 0], speed_kn: t, battery: 100 - i, locked: i < 10 };
    rig.ingest({ ...frame, tether: { length: 10 + t } }, false, 100 + t);
  }
  return rig;
}

test("with a video delay the onboard read-outs are as old as the picture", () => {
  const rig = renderState(150);
  const latest = { t: 0.5, pos: [0, 0, 0.5], speed_kn: 0.5, battery: 90, locked: false, tether: { length: 10.5 } };
  assert.equal(rig.display(latest), latest, "nothing to delay before the first rendered frame");
  rig.update(null, false, 100.5);
  const shown = rig.display(latest);
  assert.ok(Math.abs(shown.pos[2] - 0.35) < 1e-9, `depth ${shown.pos[2]}`);
  assert.equal(shown.pos, rig.state.pos, "HUD depth and the rendered pose come from the same sample");
  assert.ok(Math.abs(shown.speed_kn - 0.3) < 1e-9, "scalar telemetry comes from the delayed packet");
  assert.equal(shown.battery, 94);
  assert.ok(Math.abs(shown.tether.length - 10.3) < 1e-9);
  assert.equal(shown.locked, false, "the pilot's own switches are not delayed");
  assert.equal(latest.pos[2], 0.5, "the live state is left untouched");
});

test("without a video delay, and in replay, the read-outs are the live state", () => {
  const assisted = renderState(0);
  const latest = { t: 0.5, pos: [0, 0, 0.5], locked: false };
  assisted.update(null, false, 100.5);
  assert.equal(assisted.display(latest), latest);
  const replay = renderState(150);
  replay.update(latest, true, 100.5);
  assert.equal(replay.display(latest), latest);
  assert.equal(replay.display(null), null);
});

test("the HUD and the audio engine are fed the display state", async () => {
  const app = await readFile(new URL("../viewer/app.js", import.meta.url), "utf8");
  assert.match(app, /updateFlightHUD\(renderState\.display\(S\), W, dt, input\.hudState\(\)\);/);
  assert.match(app, /audio\.update\(renderState\.display\(S\)\);/);
});
