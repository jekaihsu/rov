// Deck pre-dive check helpers: current step and camera shot, prop spin while pulsed on deck (and the unchanged
// formula otherwise), which contexts may ask for a planted defect, and the radio-call event watch.
import test from "node:test";
import assert from "node:assert/strict";
import {
  DECK_SPIN, beginFields, createEventWatch, currentStation, deckShot, deckStep, nextThruster, rotorRate,
} from "../viewer/procedure/deck_flow.js";

const ORDER = ["walkaround", "power", "thrusters", "lights", "camera"];

function deck(extra = {}) {
  return { flow: "deck", phase: "checks", order: ORDER, checked: [], seen: [], tests: [], thrusters: 6, ...extra };
}

test("step and shot follow the server's progress", () => {
  assert.equal(deckStep({ phase: "checks", checked: [] }), null, "legacy flow has no deck step");
  assert.deepEqual(deckShot(deck()), { key: "overview" });
  assert.deepEqual(deckShot(deck({ seen: [0, 1] })), { key: "station", station: 1 });
  assert.equal(currentStation(deck({ seen: [0, 2, 1] })), 2);
  const pulsing = deck({ checked: ORDER.slice(0, 2), tests: [0], diagnostic: 1.2, diagnostic_index: 3 });
  assert.deepEqual(deckShot(pulsing), { key: "thruster", thruster: 3 });
  assert.deepEqual(deckShot(deck({ checked: ORDER.slice(0, 2), tests: [0, 1] })), { key: "thruster", thruster: 2 });
  assert.equal(nextThruster(deck({ tests: [0, 1, 2, 3, 4, 5] })), -1);
  assert.deepEqual(deckShot(deck({ checked: ORDER.slice(0, 4) })), { key: "onboard" });
  assert.deepEqual(deckShot(deck({ phase: "launch", checked: ORDER })), { key: "launch" });
});

test("a pulsed prop spins on deck; every other case keeps the old formula", () => {
  const memory = [];
  const flying = { thrust: [0.5, -0.2], locked: false };
  assert.equal(rotorRate(flying, 0, 0.016, memory), 20);
  assert.equal(rotorRate({ ...flying, locked: true }, 0, 0.016, memory), 0);
  const pulse = { thrust: [0.05], locked: true, procedure: { diagnostic: 1.5, diagnostic_index: 0 } };
  let rate = 0;
  for (let i = 0; i < 60; i++) rate = rotorRate(pulse, 0, 0.016, memory);
  assert.ok(rate > DECK_SPIN * 0.9, rate);
  const after = { thrust: [0], locked: true, procedure: { diagnostic: 0 } };
  const first = rotorRate(after, 0, 0.016, memory);
  assert.ok(first > 0 && first < rate, "the prop runs down, it does not stop dead");
  for (let i = 0; i < 200; i++) rate = rotorRate(after, 0, 0.016, memory);
  assert.equal(rate, 0);
});

test("defects are requested only in career, exam and campaign contexts", () => {
  const random = () => 0.25;
  assert.deepEqual(beginFields(new URLSearchParams("play=1"), random), { flow: "deck" });
  assert.deepEqual(beginFields(new URLSearchParams("scene=open_water"), random), { flow: "deck" });
  for (const query of ["contract=c1", "exam=1", "mission=campaign"]) {
    assert.deepEqual(beginFields(new URLSearchParams(query), random), { flow: "deck", defects: true, seed: 250000000 });
  }
  assert.deepEqual(beginFields(new URLSearchParams("predive_defect=oring_debris")), {
    flow: "deck", defect: "oring_debris",
  });
});

test("each crew call is announced once", () => {
  const watch = createEventWatch();
  const events = [
    { t: 1, action: "look", phase: "checks" },
    { t: 4, action: "crew", key: "trim" },
  ];
  assert.deepEqual(watch.fresh(events).map((event) => event.key), ["trim"]);
  events.push({ t: 6, action: "defect_found", defect: "line_fouled" });
  assert.deepEqual(watch.fresh(events).map((event) => event.action), ["defect_found"]);
  assert.deepEqual(watch.fresh(events), []);
  watch.clear();
  assert.equal(watch.fresh(events).length, 2);
});
