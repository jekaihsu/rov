// New-player onboarding (viewer/play/onboarding_model.js): step order, completion from telemetry, first-time tips
// and the stored progress that keeps hints from repeating on later dives.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  MOVE_SECONDS,
  ONBOARDING_KEY,
  STEPS,
  createTracker,
  currentStep,
  loadProgress,
  observe,
  pendingTip,
  resetProgress,
  saveProgress,
} from "../viewer/play/onboarding_model.js";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

function state(extra = {}) {
  return { t: 0, locked: true, paused: false, keep_depth: true, photos: 0, operation_mode: "ROV_USA", rc: {},
    ...extra };
}

// Feed states every 0.1 s from t0 for `seconds`; returns the last time.
function run(progress, tracker, seconds, extra, t0 = 0, context = {}) {
  let t = t0;
  for (let i = 0; i <= Math.round(seconds / 0.1); i += 1) {
    t = t0 + i * 0.1;
    observe(progress, tracker, state({ t, ...extra }), context);
  }
  return t;
}

test("a fresh profile starts at unlocking, with the hints on", () => {
  const progress = loadProgress(memoryStorage());
  assert.equal(progress.enabled, true);
  assert.equal(currentStep(progress), "unlock");
  assert.deepEqual(STEPS.slice(0, 2), ["unlock", "move"]);
});

test("unlocking completes the first step; paused or remote-controlled states never count", () => {
  const progress = loadProgress(memoryStorage());
  const tracker = createTracker();
  observe(progress, tracker, state({ locked: false, paused: true }));
  assert.equal(progress.steps.unlock, false, "a paused simulation teaches nothing");
  observe(progress, tracker, state({ locked: false, remote_control: true }));
  assert.equal(progress.steps.unlock, false, "the SDK flying is not the pilot");
  const done = observe(progress, tracker, state({ t: 1, locked: false }));
  assert.deepEqual(done, ["unlock"]);
  assert.equal(currentStep(progress), "move");
});

test("move ticks off surge, yaw and heave after sustained stick input in the operation mode", () => {
  const progress = loadProgress(memoryStorage());
  const tracker = createTracker();
  // ROV_USA: surge is right_ud, yaw left_lr, heave left_wave (input/bindings.js OPERATION_AXES).
  let t = run(progress, tracker, MOVE_SECONDS / 2, { locked: false, rc: { right_ud: 1800 } });
  assert.equal(progress.moves.surge, false, "a short tap is not enough");
  t = run(progress, tracker, MOVE_SECONDS, { locked: false, rc: { right_ud: 1800 } }, t + 0.1);
  assert.equal(progress.moves.surge, true);
  run(progress, tracker, 1, { locked: true, rc: { left_lr: 1200 } }, t + 0.1);
  assert.equal(progress.moves.yaw, false, "a locked vehicle does not move");
  t = run(progress, tracker, 1, { locked: false, rc: { left_lr: 1200 } }, t + 1.2);
  t = run(progress, tracker, 1, { locked: false, rc: { left_wave: 1700 } }, t + 0.1);
  assert.equal(progress.steps.move, true);
  assert.equal(currentStep(progress), "depth");
});

test("only the pilot's depth-hold switch counts, not the simulator dropping the hold by itself", () => {
  const progress = loadProgress(memoryStorage());
  const tracker = createTracker();
  observe(progress, tracker, state({ t: 0, rc: { keep_depth: 0 } }));
  observe(progress, tracker, state({ t: 0.05, rc: { keep_depth: 1 } }));
  assert.equal(progress.steps.depth, false, "launch defaults while locked are not the pilot");
  observe(progress, tracker, state({ t: 0.1, locked: false, keep_depth: false, rc: { keep_depth: 1 } }));
  observe(progress, tracker, state({ t: 0.2, locked: false, keep_depth: true, rc: { keep_depth: 1 } }));
  assert.equal(progress.steps.depth, false);
  observe(progress, tracker, state({ t: 0.3, locked: false, keep_depth: false, rc: { keep_depth: 0 } }));
  observe(progress, tracker, state({ t: 0.4, locked: false, keep_depth: true, rc: { keep_depth: 1 } }));
  assert.equal(progress.steps.depth, true);
});

test("depth hold is learnt by using the switch and ends with depth hold on", () => {
  const progress = loadProgress(memoryStorage());
  const tracker = createTracker();
  observe(progress, tracker, state({ t: 0, locked: false, keep_depth: true }));
  observe(progress, tracker, state({ t: 0.1, locked: false, keep_depth: true }));
  assert.equal(progress.steps.depth, false, "already on is not a lesson");
  observe(progress, tracker, state({ t: 0.2, locked: false, keep_depth: false }));
  assert.equal(progress.steps.depth, false, "switched off is not finished");
  observe(progress, tracker, state({ t: 0.3, locked: false, keep_depth: true }));
  assert.equal(progress.steps.depth, true);
});

test("light, photo, the objectives peek and the pause menu complete their steps", () => {
  const progress = loadProgress(memoryStorage());
  const tracker = createTracker();
  observe(progress, tracker, state({ t: 0, photos: 3 }));
  assert.equal(progress.steps.photo, false, "photos from earlier dives are the baseline");
  observe(progress, tracker, state({ t: 0.1, photos: 4, rc: { right_switch: 1 } }));
  assert.equal(progress.steps.photo, true);
  assert.equal(progress.steps.light, true);
  observe(progress, tracker, state({ t: 0.2 }), { peekCard: 2 });
  assert.equal(progress.steps.objectives, false, "only the objectives card counts");
  observe(progress, tracker, state({ t: 0.3 }), { peekCard: 0 });
  assert.equal(progress.steps.objectives, true);
  observe(progress, tracker, state({ t: 0.4, paused: true }), { pauseOpen: true });
  assert.equal(progress.steps.pause, true, "the pause menu pauses a solo dive and still counts");
});

test("first-time tips fire on their event once per profile", () => {
  const storage = memoryStorage();
  const progress = loadProgress(storage);
  assert.equal(pendingTip(progress, state()), null);
  assert.equal(pendingTip(progress, state({ tether: { warn: true } })), "tether");
  assert.equal(pendingTip(progress, state({ tether: { warn: true, broken: true } })), null, "a break is not a tip");
  const lost = { sensors: { dvl: { status: "lost", reason: "too_high" } } };
  assert.equal(pendingTip(progress, state({ ...lost, rc: { assist: 0 } })), null, "manual flight needs no DVL");
  assert.equal(pendingTip(progress, state({ ...lost, rc: { assist: 2 } })), "dvl");
  assert.equal(pendingTip(progress, state({ turbidity: { visibility_m: 0.8 } })), "visibility");
  assert.equal(pendingTip(progress, state({ silt: 0.8 })), "visibility");
  progress.tips.tether = true;
  saveProgress(progress, storage);
  assert.equal(pendingTip(loadProgress(storage), state({ tether: { warn: true } })), null, "seen tips stay quiet");
});

test("progress survives a reload, and the reset starts over with the hints switched back on", () => {
  const storage = memoryStorage();
  const progress = loadProgress(storage);
  progress.steps.unlock = true;
  progress.enabled = false;
  saveProgress(progress, storage);
  const again = loadProgress(storage);
  assert.equal(again.steps.unlock, true);
  assert.equal(again.enabled, false);
  assert.ok(JSON.parse(storage.getItem(ONBOARDING_KEY)).steps.unlock);
  const fresh = resetProgress(storage);
  assert.equal(fresh.enabled, true);
  assert.equal(currentStep(loadProgress(storage)), "unlock");
});

test("broken storage starts fresh instead of failing", () => {
  const storage = memoryStorage();
  storage.setItem(ONBOARDING_KEY, "{not json");
  assert.equal(currentStep(loadProgress(storage)), "unlock");
  assert.equal(currentStep(loadProgress(null)), "unlock");
});

test("hint and skip modules draw keys from the binding table and glyphs, and read no pad directly", async () => {
  for (const name of ["onboarding.js", "intro_skip.js"]) {
    const text = await readFile(new URL(`../viewer/play/${name}`, import.meta.url), "utf8");
    assert.match(text, /from '\.\.\/input\/glyphs\.js'/, `${name} uses the glyph system`);
    assert.match(text, /from '\.\.\/input\/bindings\.js'/, `${name} reads the binding table`);
    assert.equal(text.includes("getGamepads"), false, `${name} goes through the input layer`);
  }
});
