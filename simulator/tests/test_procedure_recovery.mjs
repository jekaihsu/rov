// Recovery during a dive: the pause-menu entry mirrors the server gate (surfaced and locked), and the surfacing
// reminder fires once per return from depth, never at the start of the dive.
import test from "node:test";
import assert from "node:assert/strict";
import { createSurfaceWatch, recoveryReadiness } from "../viewer/procedure/recovery.js";

function state(phase, depth, locked = true) {
  return { procedure: { active: true, phase }, pos: [0, 0, depth], locked };
}

test("recovery readiness follows the server gate", () => {
  assert.equal(recoveryReadiness(null), null);
  assert.equal(recoveryReadiness({ procedure: { active: false, phase: "quick" }, pos: [0, 0, 0] }), null);
  assert.equal(recoveryReadiness(state("checks", -0.5)), null, "only during the dive");
  assert.equal(recoveryReadiness(state("diving", 5)), "depth");
  assert.equal(recoveryReadiness(state("diving", 0.8, false)), "lock");
  assert.equal(recoveryReadiness(state("diving", 0.8)), "ready");
  assert.equal(recoveryReadiness(state("diving", 0.81)), "depth");
});

test("the surfacing reminder needs a real descent first", () => {
  const watch = createSurfaceWatch();
  assert.equal(watch.update(state("diving", 0.5)), null, "the dive starts at the surface: no reminder");
  assert.equal(watch.update(state("diving", 1.5)), null);
  assert.equal(watch.update(state("diving", 0.5)), null, "shallower than a dive: no reminder");
  assert.equal(watch.update(state("diving", 6)), null);
  assert.equal(watch.update(state("diving", 1)), null);
  assert.equal(watch.update(state("diving", 0.7)), "surfaced");
  assert.equal(watch.update(state("diving", 0.6)), null, "once per return");
  watch.update(state("diving", 3));
  assert.equal(watch.update(state("diving", 0.2, false)), "surfaced", "again after the next descent");
});

test("leaving the dive phase resets the reminder", () => {
  const watch = createSurfaceWatch();
  watch.update(state("diving", 4));
  assert.equal(watch.update(state("recovering", 0.5)), null);
  assert.equal(watch.update(state("diving", 0.5)), null);
});
